"""Usul-e-Ilaj Planner & Care Plan Domain Service:
Treatment Principles, Care Plan Lifecycle, Prompt 03 Prescription Linkage, and Follow-up Outcomes.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3

from apps.api.core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError
from apps.api.core.audit import log_audit_event

VALID_CARE_PLAN_STATUSES = {
    "DRAFT", "PROPOSED", "ACTIVE", "COMPLETED", "DISCONTINUED", "SUPERSEDED"
}

VALID_OUTCOME_STATUSES = {
    "ACHIEVED", "PARTIALLY_ACHIEVED", "NOT_ACHIEVED", "UNRESOLVED", "ADVERSE_REACTION"
}

ALLOWED_CARE_PLAN_TRANSITIONS = {
    "DRAFT": {"PROPOSED", "ACTIVE", "DISCONTINUED"},
    "PROPOSED": {"ACTIVE", "DISCONTINUED"},
    "ACTIVE": {"COMPLETED", "DISCONTINUED", "SUPERSEDED"},
    "COMPLETED": set(),
    "DISCONTINUED": set(),
    "SUPERSEDED": set()
}

class CarePlanService:
    @staticmethod
    def list_principles(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """List active Usul-e-Ilaj treatment principles (Tanqiya, Tadeel-e-Mizaj, Tahleel, Taqwiyat, etc.)."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.code, p.name_unani, p.name_english, p.name_urdu, p.status,
                   pv.id as active_version_id, pv.version_number, pv.definition,
                   pv.indications, pv.contraindications, pv.monitoring_guidance,
                   src.code as source_code, src.title as source_title
            FROM usul_e_ilaj_principles p
            LEFT JOIN usul_e_ilaj_principle_versions pv
                   ON p.id = pv.principle_id AND pv.status = 'APPROVED'
            LEFT JOIN clinical_sources src ON pv.source_id = src.id
            WHERE p.status = 'ACTIVE'
            ORDER BY p.code ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def create_care_plan_draft(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                               encounter_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new draft care plan linked to an active encounter."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        # Validate encounter
        cursor.execute("""
            SELECT e.id, e.organization_id, e.facility_id, e.patient_id, e.status, e.practitioner_id
            FROM encounters e
            WHERE e.id = ? AND e.organization_id = ?;
        """, (encounter_id, org_id))
        enc = cursor.fetchone()
        if not enc:
            raise NotFoundError(f"Encounter '{encounter_id}' not found in active organization.")
        if enc["status"] in ("COMPLETED", "CANCELLED"):
            raise ConflictError(f"Cannot create care plan for terminal encounter (status: {enc['status']}).")

        title = (payload.get("title") or "Usul-e-Ilaj Care Plan").strip()
        overall_goal = payload.get("overall_goal")
        clinical_rationale = payload.get("clinical_rationale")
        review_date = payload.get("review_date")

        plan_id = f"cpl-{uuid.uuid4().hex[:12]}"
        now_dt = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO care_plans (
                id, organization_id, facility_id, patient_id, encounter_id,
                author_id, responsible_practitioner_id, title, overall_goal,
                clinical_rationale, status, review_date, version_number,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, 1, ?, ?);
        """, (
            plan_id, org_id, enc["facility_id"], enc["patient_id"], encounter_id,
            user_ctx["user_id"], enc["practitioner_id"] or user_ctx["user_id"],
            title, overall_goal, clinical_rationale, review_date, now_dt, now_dt
        ))

        # Add initial items if provided
        items = payload.get("items", [])
        for idx, item in enumerate(items):
            item_id = f"cpi-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO care_plan_items (
                    id, care_plan_id, principle_id, principle_version_id,
                    objective, clinician_rationale, intended_intervention,
                    cautions, monitoring_plan, expected_outcome, status, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?);
            """, (
                item_id, plan_id,
                item.get("principle_id"), item.get("principle_version_id"),
                item.get("objective", "Restore temperamental equilibrium"),
                item.get("clinician_rationale"),
                item.get("intended_intervention", "Dietary and regiminal intervention"),
                item.get("cautions"),
                item.get("monitoring_plan"),
                item.get("expected_outcome"),
                idx
            ))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=enc["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_CARE_PLAN_CREATED",
            resource_type="CARE_PLAN",
            resource_id=plan_id,
            patient_id=enc["patient_id"],
            encounter_id=encounter_id,
            action_status="SUCCESS",
            description=f"Created draft care plan '{title}'."
        )

        return CarePlanService.get_care_plan_by_id(conn, user_ctx, plan_id)

    @staticmethod
    def get_care_plan_by_id(conn: sqlite3.Connection, user_ctx: Dict[str, Any], care_plan_id: str) -> Dict[str, Any]:
        """Fetch complete care plan aggregate with items, linked prescriptions, and outcomes."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT cp.id, cp.organization_id, cp.facility_id, cp.patient_id, cp.encounter_id,
                   cp.author_id, cp.responsible_practitioner_id, cp.title, cp.overall_goal,
                   cp.clinical_rationale, cp.status, cp.review_date, cp.finalised_at,
                   cp.finalised_by, cp.version_number, cp.parent_care_plan_id,
                   cp.created_at, cp.updated_at,
                   p.mrn as patient_mrn, p.display_name as patient_name,
                   u.full_name as author_name,
                   rp.full_name as practitioner_name
            FROM care_plans cp
            JOIN patients p ON cp.patient_id = p.id
            JOIN users u ON cp.author_id = u.id
            JOIN users rp ON cp.responsible_practitioner_id = rp.id
            WHERE cp.id = ? AND cp.organization_id = ?;
        """, (care_plan_id, org_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Care plan '{care_plan_id}' not found.")
        plan = dict(row)

        # Items
        cursor.execute("""
            SELECT cpi.id, cpi.principle_id, cpi.principle_version_id,
                   cpi.objective, cpi.clinician_rationale, cpi.intended_intervention,
                   cpi.cautions, cpi.monitoring_plan, cpi.expected_outcome, cpi.status, cpi.sort_order,
                   p.code as principle_code, p.name_unani as principle_name_unani, p.name_english as principle_name_en
            FROM care_plan_items cpi
            LEFT JOIN usul_e_ilaj_principles p ON cpi.principle_id = p.id
            WHERE cpi.care_plan_id = ?
            ORDER BY cpi.sort_order ASC;
        """, (care_plan_id,))
        items = [dict(it) for it in cursor.fetchall()]

        # For each item, fetch links & outcomes
        for item in items:
            cursor.execute("""
                SELECT cpl.id, cpl.link_type, cpl.prescription_id, cpl.notes, cpl.created_at,
                       pr.prescription_number, pr.status as prescription_status,
                       pr.overall_safety_state as prescription_safety_state
                FROM care_plan_links cpl
                JOIN prescriptions pr ON cpl.prescription_id = pr.id
                WHERE cpl.care_plan_item_id = ?;
            """, (item["id"],))
            item["linked_prescriptions"] = [dict(l) for l in cursor.fetchall()]

            cursor.execute("""
                SELECT cpo.id, cpo.outcome_status, cpo.observation_notes, cpo.observed_at,
                       cpo.uncertainty_notes, cpo.created_at, u.full_name as recorded_by_name
                FROM care_plan_outcomes cpo
                JOIN users u ON cpo.recorded_by = u.id
                WHERE cpo.care_plan_item_id = ?
                ORDER BY cpo.observed_at DESC;
            """, (item["id"],))
            item["outcomes"] = [dict(o) for o in cursor.fetchall()]

        plan["items"] = items
        return plan

    @staticmethod
    def update_care_plan_draft(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                               care_plan_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update draft care plan details and replace items under optimistic concurrency."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT id, status, version_number, facility_id, patient_id, encounter_id
            FROM care_plans
            WHERE id = ? AND organization_id = ?;
        """, (care_plan_id, org_id))
        current = cursor.fetchone()
        if not current:
            raise NotFoundError(f"Care plan '{care_plan_id}' not found.")
        if current["status"] not in ("DRAFT", "PROPOSED"):
            raise ConflictError(f"Cannot edit care plan with status '{current['status']}'.")

        client_ver = payload.get("version_number")
        if client_ver is not None and client_ver != current["version_number"]:
            raise ConflictError(f"Concurrency conflict: Care plan has been modified (current version {current['version_number']}, provided {client_ver}).")

        new_version = current["version_number"] + 1
        now_dt = datetime.utcnow().isoformat()

        cursor.execute("""
            UPDATE care_plans
            SET title = COALESCE(?, title),
                overall_goal = ?,
                clinical_rationale = ?,
                review_date = ?,
                version_number = ?,
                updated_at = ?
            WHERE id = ?;
        """, (
            payload.get("title"),
            payload.get("overall_goal"),
            payload.get("clinical_rationale"),
            payload.get("review_date"),
            new_version,
            now_dt,
            care_plan_id
        ))

        # Replace items if provided
        if "items" in payload:
            cursor.execute("DELETE FROM care_plan_items WHERE care_plan_id = ?;", (care_plan_id,))
            for idx, item in enumerate(payload["items"]):
                item_id = item.get("id") or f"cpi-{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO care_plan_items (
                        id, care_plan_id, principle_id, principle_version_id,
                        objective, clinician_rationale, intended_intervention,
                        cautions, monitoring_plan, expected_outcome, status, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?);
                """, (
                    item_id, care_plan_id,
                    item.get("principle_id"), item.get("principle_version_id"),
                    item.get("objective", "Principle Objective"),
                    item.get("clinician_rationale"),
                    item.get("intended_intervention", "Planned intervention"),
                    item.get("cautions"),
                    item.get("monitoring_plan"),
                    item.get("expected_outcome"),
                    idx
                ))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=current["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_CARE_PLAN_UPDATED",
            resource_type="CARE_PLAN",
            resource_id=care_plan_id,
            patient_id=current["patient_id"],
            encounter_id=current["encounter_id"],
            action_status="SUCCESS",
            description=f"Updated care plan to version {new_version}."
        )

        return CarePlanService.get_care_plan_by_id(conn, user_ctx, care_plan_id)

    @staticmethod
    def transition_care_plan(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                             care_plan_id: str, target_status: str,
                             notes: Optional[str] = None) -> Dict[str, Any]:
        """Transition care plan lifecycle state."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        if target_status not in VALID_CARE_PLAN_STATUSES:
            raise ValidationError(f"Invalid target_status '{target_status}'. Must be one of {sorted(VALID_CARE_PLAN_STATUSES)}.")

        cursor.execute("""
            SELECT id, status, facility_id, patient_id, encounter_id
            FROM care_plans
            WHERE id = ? AND organization_id = ?;
        """, (care_plan_id, org_id))
        plan = cursor.fetchone()
        if not plan:
            raise NotFoundError(f"Care plan '{care_plan_id}' not found.")

        current_status = plan["status"]
        allowed = ALLOWED_CARE_PLAN_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise ConflictError(f"Invalid transition from '{current_status}' to '{target_status}'. Allowed: {sorted(allowed) or 'None'}.")

        now_dt = datetime.utcnow().isoformat()
        if target_status in ("ACTIVE", "COMPLETED"):
            cursor.execute("""
                UPDATE care_plans
                SET status = ?, finalised_at = ?, finalised_by = ?, updated_at = ?
                WHERE id = ?;
            """, (target_status, now_dt, user_ctx["user_id"], now_dt, care_plan_id))
        else:
            cursor.execute("""
                UPDATE care_plans
                SET status = ?, updated_at = ?
                WHERE id = ?;
            """, (target_status, now_dt, care_plan_id))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=plan["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_CARE_PLAN_TRANSITIONED",
            resource_type="CARE_PLAN",
            resource_id=care_plan_id,
            patient_id=plan["patient_id"],
            encounter_id=plan["encounter_id"],
            action_status="SUCCESS",
            description=f"Transitioned care plan status from {current_status} to {target_status}."
        )

        return CarePlanService.get_care_plan_by_id(conn, user_ctx, care_plan_id)

    @staticmethod
    def link_prescription_to_item(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                  care_plan_id: str, item_id: str,
                                  prescription_id: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Link a Prompt 03 prescription draft or signed order to a care plan item.
        Verifies tenant and patient boundaries. Never auto-signs or bypasses prescription validation.
        """
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        # Validate care plan
        cursor.execute("SELECT id, patient_id, facility_id, encounter_id FROM care_plans WHERE id = ? AND organization_id = ?;", (care_plan_id, org_id))
        cp = cursor.fetchone()
        if not cp:
            raise NotFoundError(f"Care plan '{care_plan_id}' not found.")

        # Validate item
        cursor.execute("SELECT id FROM care_plan_items WHERE id = ? AND care_plan_id = ?;", (item_id, care_plan_id))
        if not cursor.fetchone():
            raise NotFoundError(f"Care plan item '{item_id}' not found in care plan '{care_plan_id}'.")

        # Validate prescription
        cursor.execute("SELECT id, patient_id, status FROM prescriptions WHERE id = ? AND organization_id = ?;", (prescription_id, org_id))
        rx = cursor.fetchone()
        if not rx:
            raise NotFoundError(f"Prescription '{prescription_id}' not found in active organization.")
        if rx["patient_id"] != cp["patient_id"]:
            raise ConflictError("Cannot link prescription belonging to a different patient to this care plan.")

        link_type = "PRESCRIPTION_SIGNED" if rx["status"] == "SIGNED" else "PRESCRIPTION_DRAFT"
        link_id = f"cpl-{uuid.uuid4().hex[:12]}"
        now_dt = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO care_plan_links (id, care_plan_id, care_plan_item_id, link_type, prescription_id, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (link_id, care_plan_id, item_id, link_type, prescription_id, notes, now_dt))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=cp["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_CARE_PLAN_PRESCRIPTION_LINKED",
            resource_type="CARE_PLAN",
            resource_id=care_plan_id,
            patient_id=cp["patient_id"],
            encounter_id=cp["encounter_id"],
            action_status="SUCCESS",
            description=f"Linked prescription '{prescription_id}' ({link_type}) to care plan item '{item_id}'."
        )

        return {"link_id": link_id, "care_plan_id": care_plan_id, "prescription_id": prescription_id, "link_type": link_type}

    @staticmethod
    def record_item_outcome(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                            care_plan_id: str, item_id: str,
                            payload: Dict[str, Any]) -> Dict[str, Any]:
        """Record follow-up outcome observation against a care plan item."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("SELECT id, patient_id, facility_id, encounter_id FROM care_plans WHERE id = ? AND organization_id = ?;", (care_plan_id, org_id))
        cp = cursor.fetchone()
        if not cp:
            raise NotFoundError(f"Care plan '{care_plan_id}' not found.")

        cursor.execute("SELECT id FROM care_plan_items WHERE id = ? AND care_plan_id = ?;", (item_id, care_plan_id))
        if not cursor.fetchone():
            raise NotFoundError(f"Care plan item '{item_id}' not found in care plan '{care_plan_id}'.")

        outcome_status = payload.get("outcome_status")
        if outcome_status not in VALID_OUTCOME_STATUSES:
            raise ValidationError(f"Invalid outcome_status '{outcome_status}'. Must be one of {sorted(VALID_OUTCOME_STATUSES)}.")

        observation_notes = (payload.get("observation_notes") or "").strip()
        if not observation_notes:
            raise ValidationError("Observation notes are mandatory for recording follow-up care outcomes.")

        outcome_id = f"cpo-{uuid.uuid4().hex[:12]}"
        now_dt = datetime.utcnow().isoformat()
        observed_at = payload.get("observed_at") or now_dt

        cursor.execute("""
            INSERT INTO care_plan_outcomes (
                id, care_plan_item_id, outcome_status, observation_notes,
                observed_at, recorded_by, uncertainty_notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            outcome_id, item_id, outcome_status, observation_notes,
            observed_at, user_ctx["user_id"], payload.get("uncertainty_notes"), now_dt
        ))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=cp["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_CARE_PLAN_OUTCOME_RECORDED",
            resource_type="CARE_PLAN",
            resource_id=care_plan_id,
            patient_id=cp["patient_id"],
            encounter_id=cp["encounter_id"],
            action_status="SUCCESS",
            description=f"Recorded outcome '{outcome_status}' for item '{item_id}'."
        )

        return {"id": outcome_id, "item_id": item_id, "outcome_status": outcome_status}

    @staticmethod
    def list_care_plans_for_patient(conn: sqlite3.Connection, user_ctx: Dict[str, Any], patient_id: str) -> List[Dict[str, Any]]:
        """List chronological care plans for patient."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT cp.id, cp.encounter_id, cp.title, cp.status, cp.overall_goal,
                   cp.review_date, cp.finalised_at, cp.version_number, cp.created_at,
                   u.full_name as author_name,
                   rp.full_name as practitioner_name
            FROM care_plans cp
            JOIN users u ON cp.author_id = u.id
            JOIN users rp ON cp.responsible_practitioner_id = rp.id
            WHERE cp.patient_id = ? AND cp.organization_id = ?
            ORDER BY cp.created_at DESC;
        """, (patient_id, org_id))
        return [dict(r) for r in cursor.fetchall()]
