"""Encounter Domain Service: Lifecycle, Transitions, and Longitudinal Patient Timeline."""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import sqlite3
from apps.api.core.errors import NotFoundError, ConflictError, ValidationError, ForbiddenError
from apps.api.core.audit import log_audit_event
from apps.api.domains.patients import PatientService

# Allowed lifecycle state transitions
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "DRAFT": ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS": ["COMPLETED", "CANCELLED"],
    "COMPLETED": [], # Terminal state
    "CANCELLED": []  # Terminal state
}

class EncounterService:
    @staticmethod
    def create_encounter(conn: sqlite3.Connection, organization_id: str, facility_id: str,
                         patient_id: str, practitioner_id: Optional[str] = None,
                         encounter_type: str = "OPD_VISIT", reason_for_visit: Optional[str] = None,
                         actor_id: str = None, request_id: Optional[str] = None,
                         client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Create a new encounter in DRAFT state with automated facility token allocation."""
        # Verify patient exists in tenant
        PatientService.get_patient_by_id(conn, organization_id, patient_id)

        # Verify facility belongs to tenant
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM facilities WHERE id = ? AND organization_id = ?;", (facility_id, organization_id))
        if not cursor.fetchone():
            raise NotFoundError(f"Facility '{facility_id}' not found in organization.", request_id=request_id)

        valid_types = ["OPD_VISIT", "FOLLOW_UP", "TELECONSULT", "EMERGENCY"]
        if encounter_type not in valid_types:
            raise ValidationError(f"Invalid encounter type. Must be one of: {', '.join(valid_types)}", request_id=request_id)

        # Assign next daily token for facility
        cursor.execute("""
            SELECT COALESCE(MAX(token_number), 0) + 1 as next_token
            FROM encounters
            WHERE facility_id = ? AND date(created_at) = date('now');
        """, (facility_id,))
        token_number = cursor.fetchone()["next_token"]

        encounter_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO encounters (
                id, organization_id, facility_id, patient_id, practitioner_id, token_number,
                encounter_type, status, reason_for_visit, version, started_at, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, 1, CURRENT_TIMESTAMP, ?);
        """, (
            encounter_id, organization_id, facility_id, patient_id, practitioner_id,
            token_number, encounter_type, reason_for_visit, actor_id
        ))

        log_audit_event(
            conn=conn,
            action_type="ENCOUNTER_CREATED",
            target_entity_type="ENCOUNTER",
            target_entity_id=encounter_id,
            organization_id=organization_id,
            facility_id=facility_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"patient_id": patient_id, "token_number": token_number, "encounter_type": encounter_type}
        )

        return EncounterService.get_encounter_by_id(conn, organization_id, encounter_id)

    @staticmethod
    def get_encounter_by_id(conn: sqlite3.Connection, organization_id: str, encounter_id: str) -> Dict[str, Any]:
        """Fetch encounter record with patient and practitioner details."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.id, e.organization_id, e.facility_id, e.patient_id, e.practitioner_id,
                   e.token_number, e.encounter_type, e.status, e.reason_for_visit, e.cancellation_reason,
                   e.version, e.started_at, e.ended_at, e.created_by, e.created_at, e.updated_at,
                   p.mrn as patient_mrn, p.display_name as patient_name, p.sex as patient_sex,
                   p.date_of_birth as patient_dob,
                   f.name as facility_name,
                   u.full_name as practitioner_name
            FROM encounters e
            JOIN patients p ON e.patient_id = p.id
            JOIN facilities f ON e.facility_id = f.id
            LEFT JOIN users u ON e.practitioner_id = u.id
            WHERE e.id = ? AND e.organization_id = ?;
        """, (encounter_id, organization_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Encounter '{encounter_id}' not found.")
        return dict(row)

    @staticmethod
    def update_draft_encounter(conn: sqlite3.Connection, organization_id: str, encounter_id: str,
                               data: Dict[str, Any], current_version: int, actor_id: str,
                               request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Update draft/in-progress encounter details with concurrency protection."""
        encounter = EncounterService.get_encounter_by_id(conn, organization_id, encounter_id)

        if encounter["status"] not in ["DRAFT", "IN_PROGRESS"]:
            raise ConflictError(f"Cannot edit encounter in '{encounter['status']}' state.", request_id=request_id)

        if encounter["version"] != current_version:
            raise ConflictError(
                "Encounter was updated by another user. Please reload and review.",
                details={"server_version": encounter["version"], "submitted_version": current_version},
                request_id=request_id
            )

        reason = data.get("reason_for_visit") or data.get("chief_complaint") or encounter["reason_for_visit"]
        practitioner_id = data.get("practitioner_id", encounter["practitioner_id"])
        new_version = encounter["version"] + 1

        conn.execute("""
            UPDATE encounters
            SET reason_for_visit = ?, practitioner_id = ?, version = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?;
        """, (reason, practitioner_id, new_version, encounter_id, organization_id))

        log_audit_event(
            conn=conn,
            action_type="ENCOUNTER_DRAFT_UPDATED",
            target_entity_type="ENCOUNTER",
            target_entity_id=encounter_id,
            organization_id=organization_id,
            facility_id=encounter["facility_id"],
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"version": new_version}
        )

        return EncounterService.get_encounter_by_id(conn, organization_id, encounter_id)

    @staticmethod
    def transition_status(conn: sqlite3.Connection, organization_id: str, encounter_id: str,
                          new_status: str, cancellation_reason: Optional[str] = None,
                          current_version: Optional[int] = None, actor_id: str = None,
                          request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Transition encounter lifecycle state with strict validation and audit.
        Prevents illegal state transitions (e.g. COMPLETED -> DRAFT).
        """
        encounter = EncounterService.get_encounter_by_id(conn, organization_id, encounter_id)
        current_status = encounter["status"]

        if current_version is not None and encounter["version"] != current_version:
            raise ConflictError(
                "Encounter version conflict. Another user updated this record.",
                details={"server_version": encounter["version"], "submitted_version": current_version},
                request_id=request_id
            )

        allowed_next = ALLOWED_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_next:
            raise ValidationError(
                f"Invalid lifecycle transition from '{current_status}' to '{new_status}'. Allowed transitions: {', '.join(allowed_next) or 'None'}.",
                details={"current_status": current_status, "attempted_status": new_status},
                request_id=request_id
            )

        if new_status == "CANCELLED" and not (cancellation_reason and cancellation_reason.strip()):
            raise ValidationError("A cancellation reason is required when cancelling an encounter.", request_id=request_id)

        new_version = encounter["version"] + 1
        ended_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if new_status in ["COMPLETED", "CANCELLED"] else None

        conn.execute("""
            UPDATE encounters
            SET status = ?, cancellation_reason = COALESCE(?, cancellation_reason),
                ended_at = COALESCE(?, ended_at), version = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?;
        """, (new_status, cancellation_reason, ended_at, new_version, encounter_id, organization_id))

        log_audit_event(
            conn=conn,
            action_type="ENCOUNTER_STATUS_TRANSITIONED",
            target_entity_type="ENCOUNTER",
            target_entity_id=encounter_id,
            organization_id=organization_id,
            facility_id=encounter["facility_id"],
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={
                "from_status": current_status,
                "to_status": new_status,
                "cancellation_reason": cancellation_reason,
                "version": new_version
            }
        )

        return EncounterService.get_encounter_by_id(conn, organization_id, encounter_id)

    @staticmethod
    def get_patient_timeline(conn: sqlite3.Connection, organization_id: str, patient_id: str,
                             user_ctx: Dict[str, Any], limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """
        Aggregate longitudinal timeline combining clinical encounters, consents, and administrative events.
        Filtered by role access to protect clinical narrative from unprivileged roles.
        """
        PatientService.get_patient_by_id(conn, organization_id, patient_id)
        cursor = conn.cursor()
        timeline_items: List[Dict[str, Any]] = []

        is_practitioner_or_admin = any(r in user_ctx.get("roles", []) for r in ["PRACTITIONER", "ORG_ADMIN", "CLINIC_ADMIN"])

        # 1. Fetch Encounters
        cursor.execute("""
            SELECT e.id, e.token_number, e.encounter_type, e.status, e.reason_for_visit,
                   e.cancellation_reason, e.started_at, e.ended_at, e.created_at,
                   f.name as facility_name, u.full_name as practitioner_name
            FROM encounters e
            JOIN facilities f ON e.facility_id = f.id
            LEFT JOIN users u ON e.practitioner_id = u.id
            WHERE e.patient_id = ? AND e.organization_id = ?
            ORDER BY e.created_at DESC;
        """, (patient_id, organization_id))
        for r in cursor.fetchall():
            item = {
                "event_id": f"enc-{r['id']}",
                "event_type": "CLINICAL_ENCOUNTER",
                "category": "CLINICAL",
                "timestamp": r["created_at"],
                "status": r["status"],
                "title": f"Encounter #{r['token_number']} ({r['encounter_type'].replace('_', ' ')})",
                "facility_name": r["facility_name"],
                "actor_name": r["practitioner_name"] or "Assigned Team",
                "details": {
                    "encounter_id": r["id"],
                    "status": r["status"],
                    "token_number": r["token_number"]
                }
            }
            # Only disclose reason_for_visit and cancellation reason to practitioners/admins
            if is_practitioner_or_admin:
                item["details"]["reason_for_visit"] = r["reason_for_visit"]
                item["details"]["cancellation_reason"] = r["cancellation_reason"]

            timeline_items.append(item)

        # 2. Fetch Consents
        cursor.execute("""
            SELECT c.id, c.purpose, c.status, c.source_method, c.recorded_at, c.withdrawn_at,
                   u.full_name as recorder_name
            FROM patient_consents c
            LEFT JOIN users u ON c.recorded_by = u.id
            WHERE c.patient_id = ? AND c.organization_id = ?
            ORDER BY c.recorded_at DESC;
        """, (patient_id, organization_id))
        for r in cursor.fetchall():
            timeline_items.append({
                "event_id": f"cns-{r['id']}",
                "event_type": "CONSENT_RECORDED",
                "category": "ADMINISTRATIVE",
                "timestamp": r["recorded_at"],
                "status": r["status"],
                "title": f"Consent {r['status']}: {r['purpose'].replace('_', ' ')}",
                "facility_name": "Matab Front Desk",
                "actor_name": r["recorder_name"] or "Staff",
                "details": {
                    "consent_id": r["id"],
                    "purpose": r["purpose"],
                    "status": r["status"],
                    "source_method": r["source_method"]
                }
            })

        # Sort combined timeline descending by timestamp
        timeline_items.sort(key=lambda x: x["timestamp"], reverse=True)
        total = len(timeline_items)
        paged_items = timeline_items[offset:offset + limit]

        return paged_items, total
