"""Organ-Axis Mapping Domain Service:
Contextual Functional Associations, Honest Evidence Levels, and Clinician Governance.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3

from apps.api.core.errors import NotFoundError, ValidationError, ForbiddenError
from apps.api.core.audit import log_audit_event

VALID_RELATIONSHIPS = {
    "ASSOCIATED_WITH", "TRADITIONALLY_RELATED_TO", "MAY_PROMPT_REVIEW_OF", "NOT_EQUIVALENT_TO"
}

VALID_EVIDENCE_LEVELS = {
    "REVIEWED", "UNREVIEWED", "HISTORICAL_BENCHMARK"
}

VALID_MAPPING_STATUSES = {
    "DRAFT", "UNDER_REVIEW", "APPROVED", "REJECTED", "RETIRED"
}

class OrganAxisService:
    @staticmethod
    def list_concepts(conn: sqlite3.Connection, status: str = "ACTIVE") -> List[Dict[str, Any]]:
        """List master Organ-Axis concepts (Meda, Kabid, Qalb, Dimagh, etc.)."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, canonical_name, unani_name, anatomical_correlate, status
            FROM organ_axis_concepts
            WHERE status = ?
            ORDER BY canonical_name ASC;
        """, (status,))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_mappings(conn: sqlite3.Connection,
                     concept_code: Optional[str] = None,
                     status: str = "APPROVED") -> List[Dict[str, Any]]:
        """Query contextual Organ-Axis mappings. Only APPROVED mappings returned by default."""
        cursor = conn.cursor()
        query = """
            SELECT m.id, m.relationship_type, m.plain_explanation, m.clinical_utility_notes,
                   m.evidence_level, m.status, m.source_locator, m.reviewed_at,
                   sc.code as source_code, sc.canonical_name as source_name, sc.unani_name as source_unani,
                   tc.code as target_code, tc.canonical_name as target_name, tc.unani_name as target_unani,
                   src.title as source_title, src.code as source_bib_code, src.author_authority as source_author
            FROM organ_axis_mappings m
            JOIN organ_axis_concepts sc ON m.source_concept_id = sc.id
            JOIN organ_axis_concepts tc ON m.target_concept_id = tc.id
            LEFT JOIN clinical_sources src ON m.source_id = src.id
            WHERE m.status = ?
        """
        params = [status]

        if concept_code:
            query += " AND (sc.code = ? OR tc.code = ?)"
            params.extend([concept_code.upper(), concept_code.upper()])

        query += " ORDER BY m.evidence_level DESC, sc.canonical_name ASC;"
        cursor.execute(query, tuple(params))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_mapping_by_id(conn: sqlite3.Connection, mapping_id: str) -> Dict[str, Any]:
        """Fetch mapping details by ID."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.source_concept_id, m.target_concept_id, m.relationship_type,
                   m.plain_explanation, m.clinical_utility_notes, m.evidence_level,
                   m.status, m.source_locator, m.reviewed_at, m.created_at,
                   sc.code as source_code, sc.canonical_name as source_name, sc.unani_name as source_unani,
                   tc.code as target_code, tc.canonical_name as target_name, tc.unani_name as target_unani,
                   src.title as source_title, src.code as source_bib_code, src.author_authority as source_author,
                   u.full_name as reviewer_name
            FROM organ_axis_mappings m
            JOIN organ_axis_concepts sc ON m.source_concept_id = sc.id
            JOIN organ_axis_concepts tc ON m.target_concept_id = tc.id
            LEFT JOIN clinical_sources src ON m.source_id = src.id
            LEFT JOIN users u ON m.reviewed_by = u.id
            WHERE m.id = ?;
        """, (mapping_id,))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Organ-Axis mapping '{mapping_id}' not found.")
        return dict(row)

    @staticmethod
    def record_mapping_acknowledgement(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                       assessment_id: str, mapping_id: str,
                                       notes: Optional[str] = None) -> Dict[str, Any]:
        """Record clinician acknowledgement and notes regarding an Organ-Axis mapping in an encounter."""
        cursor = conn.cursor()
        # Verify assessment
        cursor.execute("SELECT id, facility_id, patient_id, encounter_id FROM unani_assessments WHERE id = ?;", (assessment_id,))
        assess = cursor.fetchone()
        if not assess:
            raise NotFoundError(f"Unani assessment '{assessment_id}' not found.")

        # Verify mapping
        cursor.execute("SELECT id FROM organ_axis_mappings WHERE id = ?;", (mapping_id,))
        if not cursor.fetchone():
            raise NotFoundError(f"Organ-Axis mapping '{mapping_id}' not found.")

        rec_id = f"oar-{uuid.uuid4().hex[:12]}"
        now_dt = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO assessment_mapping_results (id, assessment_id, mapping_id, clinician_acknowledged, clinician_notes, created_at)
            VALUES (?, ?, ?, 1, ?, ?);
        """, (rec_id, assessment_id, mapping_id, notes, now_dt))

        log_audit_event(
            conn=conn,
            organization_id=user_ctx["organization_id"],
            facility_id=assess["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="ORGAN_AXIS_MAPPING_ACKNOWLEDGED",
            resource_type="ORGAN_AXIS_MAPPING",
            resource_id=mapping_id,
            patient_id=assess["patient_id"],
            encounter_id=assess["encounter_id"],
            action_status="SUCCESS",
            description=f"Clinician acknowledged Organ-Axis mapping '{mapping_id}' with note."
        )

        return {"id": rec_id, "assessment_id": assessment_id, "mapping_id": mapping_id, "acknowledged": True}
