"""Unani Clinical Assessment Domain Service:
Mizaj, Afaal, Asbab-e-Sittah, Diagnostic Conclusions, Concurrency, and Clinical Finalisation.
"""

import uuid
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3

from apps.api.core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError
from apps.api.core.audit import log_audit_event

VALID_DOMINANT_MIZAJ = {
    "DAMAWWI", "BALGHAMI", "SAFRAWI", "SAUDAWI", "MOTADIL", "NOT_ASSESSED", "UNCERTAIN", "MIXED"
}

VALID_MIZAJ_UNCERTAINTY = {
    "HIGH_CONFIDENCE", "MODERATE_CONFIDENCE", "UNCERTAIN", "PROVISIONAL", "NOT_ASSESSED"
}

VALID_SEMANTIC_STATES = {
    "OBSERVED", "NORMAL", "IMPAIRED", "UNKNOWN", "NOT_ASKED", "NOT_ASSESSED", "NOT_APPLICABLE"
}

VALID_PROVENANCES = {
    "PATIENT_REPORTED", "CLINICIAN_OBSERVED", "MEASURED", "IMPORTED", "AI_DRAFTED"
}

VALID_CERTAINTIES = {
    "DEFINITIVE", "PROVISIONAL", "DIFFERENTIAL", "UNCERTAIN"
}

class UnaniAssessmentService:
    @staticmethod
    def list_templates(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """List active Unani assessment templates."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.id, t.code, t.name, t.purpose, t.language, t.status,
                   tv.id as active_version_id, tv.version_number, tv.status as version_status
            FROM unani_assessment_templates t
            LEFT JOIN unani_assessment_template_versions tv 
                   ON t.id = tv.template_id AND tv.status = 'APPROVED'
            WHERE t.status = 'ACTIVE'
            ORDER BY t.created_at ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_template_version_definition(conn: sqlite3.Connection, template_version_id: str) -> Dict[str, Any]:
        """Fetch complete template structure including domains and allowed taxonomy options."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tv.id, tv.template_id, tv.version_number, tv.definition_json,
                   tv.validation_metadata, tv.status, tv.effective_date,
                   t.code as template_code, t.name as template_name
            FROM unani_assessment_template_versions tv
            JOIN unani_assessment_templates t ON tv.template_id = t.id
            WHERE tv.id = ?;
        """, (template_version_id,))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Template version '{template_version_id}' not found.")
        tmpl = dict(row)

        # Fetch domains
        cursor.execute("""
            SELECT id, domain_key, label, description, sort_order, is_mandatory
            FROM unani_assessment_domains
            WHERE template_version_id = ?
            ORDER BY sort_order ASC;
        """, (template_version_id,))
        domains = [dict(d) for d in cursor.fetchall()]

        for d in domains:
            cursor.execute("""
                SELECT id, option_key, label, description, sort_order
                FROM unani_assessment_options
                WHERE domain_id = ?
                ORDER BY sort_order ASC;
            """, (d["id"],))
            d["options"] = [dict(o) for o in cursor.fetchall()]

        tmpl["domains"] = domains
        return tmpl

    @staticmethod
    def create_assessment_draft(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                encounter_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new draft Unani assessment linked to an active encounter."""
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
            raise ConflictError(f"Cannot create assessment for terminal encounter (status: {enc['status']}).")

        # Resolve template version
        template_version_id = payload.get("template_version_id")
        if not template_version_id:
            cursor.execute("""
                SELECT tv.id FROM unani_assessment_template_versions tv
                JOIN unani_assessment_templates t ON tv.template_id = t.id
                WHERE t.code = 'TMPL-UNANI-CORE' AND tv.status = 'APPROVED'
                ORDER BY tv.version_number DESC LIMIT 1;
            """)
            tv_row = cursor.fetchone()
            if not tv_row:
                raise NotFoundError("No approved default Unani assessment template version found.")
            template_version_id = tv_row["id"]
        else:
            cursor.execute("SELECT id, status FROM unani_assessment_template_versions WHERE id = ?;", (template_version_id,))
            tv_check = cursor.fetchone()
            if not tv_check:
                raise NotFoundError(f"Template version '{template_version_id}' not found.")
            if tv_check["status"] not in ("APPROVED", "UNDER_REVIEW"):
                raise ConflictError(f"Cannot use template version with status '{tv_check['status']}'.")

        assessment_id = f"uas-{uuid.uuid4().hex[:12]}"
        now_dt = datetime.utcnow()
        today_date = now_dt.strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO unani_assessments (
                id, organization_id, facility_id, patient_id, encounter_id,
                template_version_id, author_id, status, assessment_date,
                dominant_mizaj, secondary_mizaj, mizaj_rationale, mizaj_uncertainty,
                clinical_reasoning, alternative_considerations, unresolved_questions,
                version_number, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, 'NOT_ASSESSED', NULL, NULL, 'NOT_ASSESSED', NULL, NULL, NULL, 1, ?, ?);
        """, (
            assessment_id, org_id, enc["facility_id"], enc["patient_id"], encounter_id,
            template_version_id, user_ctx["user_id"], today_date,
            now_dt.isoformat(), now_dt.isoformat()
        ))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=enc["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_UNANI_ASSESSMENT_DRAFT_CREATED",
            resource_type="UNANI_ASSESSMENT",
            resource_id=assessment_id,
            patient_id=enc["patient_id"],
            encounter_id=encounter_id,
            action_status="SUCCESS",
            description=f"Created draft Unani assessment for encounter '{encounter_id}'."
        )

        return UnaniAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)

    @staticmethod
    def get_assessment_by_id(conn: sqlite3.Connection, user_ctx: Dict[str, Any], assessment_id: str) -> Dict[str, Any]:
        """Fetch complete assessment aggregate with responses, conclusions, and amendments."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT ua.id, ua.organization_id, ua.facility_id, ua.patient_id, ua.encounter_id,
                   ua.template_version_id, ua.author_id, ua.status, ua.assessment_date,
                   ua.dominant_mizaj, ua.secondary_mizaj, ua.mizaj_rationale, ua.mizaj_uncertainty,
                   ua.clinical_reasoning, ua.alternative_considerations, ua.unresolved_questions,
                   ua.version_number, ua.parent_assessment_id, ua.signed_at, ua.signed_by,
                   ua.signature_hash, ua.signed_snapshot, ua.created_at, ua.updated_at,
                   p.mrn as patient_mrn, p.display_name as patient_name, p.date_of_birth as patient_dob,
                   p.sex as patient_sex,
                   u.full_name as author_name,
                   t.code as template_code, t.name as template_name, tv.version_number as template_version_number
            FROM unani_assessments ua
            JOIN patients p ON ua.patient_id = p.id
            JOIN users u ON ua.author_id = u.id
            JOIN unani_assessment_template_versions tv ON ua.template_version_id = tv.id
            JOIN unani_assessment_templates t ON tv.template_id = t.id
            WHERE ua.id = ? AND ua.organization_id = ?;
        """, (assessment_id, org_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Unani assessment '{assessment_id}' not found.")
        res = dict(row)

        # Responses
        cursor.execute("""
            SELECT id, domain_key, field_key, field_label, field_value,
                   data_type, unit, semantic_state, provenance, observed_at,
                   recorded_at, notes
            FROM unani_assessment_responses
            WHERE assessment_id = ?
            ORDER BY recorded_at ASC;
        """, (assessment_id,))
        res["responses"] = [dict(r) for r in cursor.fetchall()]

        # Conclusions
        cursor.execute("""
            SELECT id, conclusion_type, code, title, description, evidence_notes, certainty, sort_order
            FROM unani_assessment_conclusions
            WHERE assessment_id = ?
            ORDER BY sort_order ASC;
        """, (assessment_id,))
        res["conclusions"] = [dict(c) for c in cursor.fetchall()]

        # Amendments
        cursor.execute("""
            SELECT am.id, am.amended_assessment_id, am.reason, am.created_at, u.full_name as author_name
            FROM unani_assessment_amendments am
            JOIN users u ON am.author_id = u.id
            WHERE am.assessment_id = ? OR am.amended_assessment_id = ?
            ORDER BY am.created_at ASC;
        """, (assessment_id, assessment_id))
        res["amendments"] = [dict(a) for a in cursor.fetchall()]

        return res

    @staticmethod
    def update_assessment_draft(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                assessment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update draft assessment fields, responses, and conclusions under optimistic concurrency."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT id, status, version_number, facility_id, patient_id, encounter_id
            FROM unani_assessments
            WHERE id = ? AND organization_id = ?;
        """, (assessment_id, org_id))
        current = cursor.fetchone()
        if not current:
            raise NotFoundError(f"Unani assessment '{assessment_id}' not found.")
        if current["status"] != "DRAFT":
            raise ConflictError(f"Cannot edit assessment with status '{current['status']}'. Only DRAFT can be modified.")

        # Optimistic Concurrency check
        client_version = payload.get("version_number")
        if client_version is not None and client_version != current["version_number"]:
            raise ConflictError(
                f"Concurrency conflict: Assessment has been modified (current version {current['version_number']}, provided {client_version})."
            )

        # Validate Mizaj inputs if provided
        dominant_mizaj = payload.get("dominant_mizaj", "NOT_ASSESSED")
        if dominant_mizaj not in VALID_DOMINANT_MIZAJ:
            raise ValidationError(f"Invalid dominant_mizaj '{dominant_mizaj}'. Must be one of {sorted(VALID_DOMINANT_MIZAJ)}.")

        mizaj_uncertainty = payload.get("mizaj_uncertainty", "NOT_ASSESSED")
        if mizaj_uncertainty not in VALID_MIZAJ_UNCERTAINTY:
            raise ValidationError(f"Invalid mizaj_uncertainty '{mizaj_uncertainty}'. Must be one of {sorted(VALID_MIZAJ_UNCERTAINTY)}.")

        new_version = current["version_number"] + 1
        now_dt = datetime.utcnow().isoformat()

        cursor.execute("""
            UPDATE unani_assessments
            SET dominant_mizaj = ?,
                secondary_mizaj = ?,
                mizaj_rationale = ?,
                mizaj_uncertainty = ?,
                clinical_reasoning = ?,
                alternative_considerations = ?,
                unresolved_questions = ?,
                version_number = ?,
                updated_at = ?
            WHERE id = ?;
        """, (
            dominant_mizaj,
            payload.get("secondary_mizaj"),
            payload.get("mizaj_rationale"),
            mizaj_uncertainty,
            payload.get("clinical_reasoning"),
            payload.get("alternative_considerations"),
            payload.get("unresolved_questions"),
            new_version,
            now_dt,
            assessment_id
        ))

        # Replace responses if provided
        if "responses" in payload:
            cursor.execute("DELETE FROM unani_assessment_responses WHERE assessment_id = ?;", (assessment_id,))
            for resp in payload["responses"]:
                semantic_state = resp.get("semantic_state", "OBSERVED")
                if semantic_state not in VALID_SEMANTIC_STATES:
                    raise ValidationError(f"Invalid semantic_state '{semantic_state}'.")

                provenance = resp.get("provenance", "CLINICIAN_OBSERVED")
                if provenance not in VALID_PROVENANCES:
                    raise ValidationError(f"Invalid provenance '{provenance}'.")

                r_id = f"uar-{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO unani_assessment_responses (
                        id, assessment_id, domain_key, field_key, field_label,
                        field_value, data_type, unit, semantic_state, provenance,
                        observed_at, recorded_at, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    r_id, assessment_id,
                    resp.get("domain_key", "GENERAL"),
                    resp.get("field_key", "unknown_field"),
                    resp.get("field_label", "Field"),
                    str(resp.get("field_value", "")) if resp.get("field_value") is not None else None,
                    resp.get("data_type", "TEXT"),
                    resp.get("unit"),
                    semantic_state,
                    provenance,
                    resp.get("observed_at"),
                    now_dt,
                    resp.get("notes")
                ))

        # Replace conclusions if provided
        if "conclusions" in payload:
            cursor.execute("DELETE FROM unani_assessment_conclusions WHERE assessment_id = ?;", (assessment_id,))
            for idx, conc in enumerate(payload["conclusions"]):
                certainty = conc.get("certainty", "PROVISIONAL")
                if certainty not in VALID_CERTAINTIES:
                    raise ValidationError(f"Invalid conclusion certainty '{certainty}'.")

                c_id = f"uac-{uuid.uuid4().hex[:12]}"
                cursor.execute("""
                    INSERT INTO unani_assessment_conclusions (
                        id, assessment_id, conclusion_type, code, title,
                        description, evidence_notes, certainty, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    c_id, assessment_id,
                    conc.get("conclusion_type", "MIZAJ"),
                    conc.get("code"),
                    conc.get("title", "Clinical Finding"),
                    conc.get("description"),
                    conc.get("evidence_notes"),
                    certainty,
                    idx
                ))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=current["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_UNANI_ASSESSMENT_DRAFT_UPDATED",
            resource_type="UNANI_ASSESSMENT",
            resource_id=assessment_id,
            patient_id=current["patient_id"],
            encounter_id=current["encounter_id"],
            action_status="SUCCESS",
            description=f"Updated Unani assessment draft to version {new_version}."
        )

        return UnaniAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)

    @staticmethod
    def finalise_assessment(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                            assessment_id: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """Clinician explicit finalisation with cryptographic snapshot hashing and immutability lock."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        # Permission check
        roles = user_ctx.get("roles", [])
        if "PRACTITIONER" not in roles and "ORG_ADMIN" not in roles and "CLINIC_ADMIN" not in roles:
            raise ForbiddenError("Only licensed practitioners or administrators may finalise clinical assessments.")

        cursor.execute("""
            SELECT id, status, version_number, facility_id, patient_id, encounter_id, dominant_mizaj, mizaj_uncertainty
            FROM unani_assessments
            WHERE id = ? AND organization_id = ?;
        """, (assessment_id, org_id))
        assess = cursor.fetchone()
        if not assess:
            raise NotFoundError(f"Unani assessment '{assessment_id}' not found.")
        if assess["status"] != "DRAFT":
            raise ConflictError(f"Cannot finalise assessment with status '{assess['status']}'. Already finalised or superseded.")

        # Require meaningful clinical determination
        if assess["dominant_mizaj"] == "NOT_ASSESSED" and (not payload or not payload.get("force_incomplete_signoff")):
            raise ValidationError("Cannot finalise assessment with dominant_mizaj='NOT_ASSESSED'. Select a valid Mizaj determination or specify force_incomplete_signoff with rationale.")

        now_dt = datetime.utcnow().isoformat()
        current_data = UnaniAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)
        snapshot_str = json.dumps(current_data, sort_keys=True, default=str)
        snapshot_hash = hashlib.sha256(snapshot_str.encode("utf-8")).hexdigest()

        cursor.execute("""
            UPDATE unani_assessments
            SET status = 'FINALISED',
                signed_at = ?,
                signed_by = ?,
                signature_hash = ?,
                signed_snapshot = ?,
                updated_at = ?
            WHERE id = ?;
        """, (now_dt, user_ctx["user_id"], snapshot_hash, snapshot_str, now_dt, assessment_id))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=assess["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=roles[0] if roles else "PRACTITIONER",
            event_type="CLINICAL_UNANI_ASSESSMENT_FINALISED",
            resource_type="UNANI_ASSESSMENT",
            resource_id=assessment_id,
            patient_id=assess["patient_id"],
            encounter_id=assess["encounter_id"],
            action_status="SUCCESS",
            description=f"Clinician finalised Unani assessment with fingerprint {snapshot_hash[:16]}..."
        )

        return UnaniAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)

    @staticmethod
    def amend_assessment(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                         assessment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Formally amend a finalised assessment. Marks parent SUPERSEDED and creates a new linked draft version."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        reason = (payload.get("reason") or "").strip()
        if not reason:
            raise ValidationError("An explicit clinical amendment reason is mandatory to amend a finalised assessment.")

        parent = UnaniAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)
        if parent["status"] != "FINALISED":
            raise ConflictError(f"Only FINALISED assessments can be amended. Current status is '{parent['status']}'.")

        now_dt = datetime.utcnow().isoformat()
        new_assessment_id = f"uas-{uuid.uuid4().hex[:12]}"
        new_version = parent["version_number"] + 1

        # Mark parent superseded
        cursor.execute("""
            UPDATE unani_assessments
            SET status = 'SUPERSEDED', updated_at = ?
            WHERE id = ?;
        """, (now_dt, assessment_id))

        # Insert new draft version
        cursor.execute("""
            INSERT INTO unani_assessments (
                id, organization_id, facility_id, patient_id, encounter_id,
                template_version_id, author_id, status, assessment_date,
                dominant_mizaj, secondary_mizaj, mizaj_rationale, mizaj_uncertainty,
                clinical_reasoning, alternative_considerations, unresolved_questions,
                version_number, parent_assessment_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            new_assessment_id, org_id, parent["facility_id"], parent["patient_id"], parent["encounter_id"],
            parent["template_version_id"], user_ctx["user_id"], parent["assessment_date"],
            parent["dominant_mizaj"], parent["secondary_mizaj"], parent["mizaj_rationale"],
            parent["mizaj_uncertainty"], parent["clinical_reasoning"], parent["alternative_considerations"],
            parent["unresolved_questions"], new_version, assessment_id, now_dt, now_dt
        ))

        # Copy existing responses to new draft
        for r in parent.get("responses", []):
            r_id = f"uar-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO unani_assessment_responses (
                    id, assessment_id, domain_key, field_key, field_label,
                    field_value, data_type, unit, semantic_state, provenance,
                    observed_at, recorded_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                r_id, new_assessment_id, r["domain_key"], r["field_key"], r["field_label"],
                r["field_value"], r["data_type"], r.get("unit"), r["semantic_state"], r["provenance"],
                r.get("observed_at"), now_dt, r.get("notes")
            ))

        # Copy conclusions
        for c in parent.get("conclusions", []):
            c_id = f"uac-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO unani_assessment_conclusions (
                    id, assessment_id, conclusion_type, code, title,
                    description, evidence_notes, certainty, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                c_id, new_assessment_id, c["conclusion_type"], c.get("code"), c["title"],
                c.get("description"), c.get("evidence_notes"), c["certainty"], c["sort_order"]
            ))

        # Record amendment record
        amend_id = f"amd-{uuid.uuid4().hex[:12]}"
        cursor.execute("""
            INSERT INTO unani_assessment_amendments (id, assessment_id, amended_assessment_id, reason, author_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (amend_id, new_assessment_id, assessment_id, reason, user_ctx["user_id"], now_dt))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=parent["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_UNANI_ASSESSMENT_AMENDED",
            resource_type="UNANI_ASSESSMENT",
            resource_id=new_assessment_id,
            patient_id=parent["patient_id"],
            encounter_id=parent["encounter_id"],
            action_status="SUCCESS",
            description=f"Amended assessment '{assessment_id}' -> created version {new_version}. Reason: {reason}"
        )

        return UnaniAssessmentService.get_assessment_by_id(conn, user_ctx, new_assessment_id)

    @staticmethod
    def list_assessments_for_patient(conn: sqlite3.Connection, user_ctx: Dict[str, Any], patient_id: str) -> List[Dict[str, Any]]:
        """List chronological assessment history for patient across all encounters."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT ua.id, ua.encounter_id, ua.status, ua.assessment_date,
                   ua.dominant_mizaj, ua.secondary_mizaj, ua.mizaj_uncertainty,
                   ua.version_number, ua.signed_at, ua.created_at,
                   u.full_name as author_name,
                   t.name as template_name
            FROM unani_assessments ua
            JOIN users u ON ua.author_id = u.id
            JOIN unani_assessment_template_versions tv ON ua.template_version_id = tv.id
            JOIN unani_assessment_templates t ON tv.template_id = t.id
            WHERE ua.patient_id = ? AND ua.organization_id = ?
            ORDER BY ua.created_at DESC;
        """, (patient_id, org_id))
        return [dict(r) for r in cursor.fetchall()]
