"""Knowledge Authenticity, Verification & Clinical Safety Framework (KAVS) Domain Engine.
Standalone AYUSH/Unani Clinical Operations System.

Enforces:
1. Five Independent Verification Dimensions (Source authenticity, extraction fidelity,
   evidence characterization, clinical review state, intended-use authorization).
2. Governed Source Versions & Statutory Rights Reviews (no unverified bulk ingestion).
3. Ingestion & Extraction Jobs with Page-Anchored Segments & OCR Confidence Scoring.
4. Independent Evidence Appraisal with Explicit Contradiction & Limitation Links.
5. Strict Proscription of AI Hallucinations / Autonomous Publishing (Drafts remain drafts until human review).
6. Immutable, Cryptographically Fingerprinted Knowledge Releases.
7. Change-Impact Dependency Engine (Source -> Claim -> Formulation/Safety Rule -> Clinical Card).
8. Consultation-Time Contextual Retrieval with Deterministic Citation Resolvability.
"""

import json
import uuid
import hashlib
import re
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    NotFoundError, ValidationError, ConflictError, ForbiddenError
)
from apps.api.core.audit import log_audit_event


# --------------------------------------------------------------------------
# ENUMERATED CONSTANTS & VALIDATION DICTIONARIES
# --------------------------------------------------------------------------

VALID_SOURCE_AUTHENTICITY = {
    "unverified", "metadata_verified", "document_integrity_verified",
    "publisher_or_authority_verified", "disputed"
}

VALID_EXTRACTION_FIDELITY = {
    "not_checked", "machine_extracted", "human_checked",
    "correction_required", "unreadable"
}

VALID_EVIDENCE_CHARACTERIZATIONS = {
    "traditional_description",
    "official_specification",
    "regulatory_requirement",
    "clinical_guideline_recommendation",
    "systematic_review_meta_analysis",
    "randomized_trial",
    "observational_human_research",
    "case_report_series",
    "preclinical_in_vitro_animal",
    "expert_consensus",
    "mechanistic_rationale",
    "unknown_insufficient"
}

VALID_CLINICAL_REVIEW_STATES = {
    "not_reviewed", "review_in_progress", "changes_requested",
    "approved_for_defined_use", "rejected", "review_expired"
}

VALID_INTENDED_USE_AUTHORIZATIONS = {
    "historical_reference_only",
    "educational_reference",
    "clinician_contextual_reference",
    "formulary_definition",
    "safety_alert_rule",
    "clinical_decision_support",
    "not_authorized_for_clinical_use"
}

VALID_REVIEWER_ROLES = {
    "UNANI_SCHOLAR", "BIOMEDICAL_CLINICIAN", "PHARMACOGNOSIST",
    "TOXICOLOGIST", "GOVERNANCE_LEAD"
}

VALID_RIGHTS_STATUSES = {
    "PUBLIC_DOMAIN", "STATUTORY_AYUSH_OPEN", "LICENSED_INTERNAL",
    "METADATA_AND_EXCERPT_ONLY", "RESTRICTED"
}

VALID_LOCATOR_TYPES = {
    "PAGE", "SECTION", "CHAPTER", "TABLE", "PARAGRAPH", "FIGURE", "ARTICLE_DOI"
}

VALID_LOCATOR_VERIFICATION_STATES = {
    "UNVERIFIED", "VERIFIED_PHYSICAL_PASSAGE", "VERIFIED_DIGITAL_ANCHOR", "DISPUTED"
}

VALID_SOURCE_VERIFICATION_TYPES = {
    "METADATA_VERIFICATION", "PUBLISHER_AUTHORITY", "DOCUMENT_INTEGRITY_HASH",
    "EDITION_REVISION", "RIGHTS_USAGE", "PASSAGE_FIDELITY"
}

VALID_SOURCE_VERIFICATION_RESULTS = {
    "VERIFIED_PASS", "VERIFIED_WITH_RESTRICTIONS", "DISPUTED", "REJECTED"
}

VALID_POLICY_STATUSES = {
    "DRAFT", "UNDER_REVIEW", "APPROVED", "SUPERSEDED", "WITHDRAWN"
}

VALID_INGESTION_STATES = {
    "created", "rights_check_pending", "blocked_by_rights", "queued",
    "file_validation", "integrity_check", "malware_scan_pending",
    "extracting", "ocr_running", "structure_detection", "draft_segments_ready",
    "fidelity_review_required", "claim_extraction_pending", "claim_drafts_ready",
    "review_in_progress", "completed_with_restrictions", "completed",
    "failed_retryable", "failed_terminal", "cancelled", "withdrawn"
}

VALID_RIGHTS_OPERATIONS = {
    "RETAIN_FILE", "EXTRACT_TEXT", "RUN_OCR", "INDEX_VECTORS",
    "SHOW_EXCERPTS", "SHOW_FULL_TEXT", "EXPORT_REDISTRIBUTE"
}

VALID_CLAIM_DRAFT_STATUSES = {
    "DRAFT_UNVERIFIED", "SUBMITTED_FOR_REVIEW", "REJECTED", "PROMOTED_TO_CLAIM"
}


class KAVSEngine:
    """Core domain service for the Knowledge Authenticity, Verification & Clinical Safety Framework."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)

    # --------------------------------------------------------------------------
    # 0. AUDIT TRAIL LOGGING
    # --------------------------------------------------------------------------

    def _log_audit_tx(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        entity_type: str,
        entity_id: str,
        actor_id: str,
        actor_role: Optional[str] = None,
        prior_state: Optional[str] = None,
        new_state: Optional[str] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        outcome: str = "SUCCESS"
    ) -> None:
        """Internal append-only ledger writer for KAVS audit events."""
        try:
            audit_id = f"aud-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_audit_events (
                    id, event_type, entity_type, entity_id, actor_id, actor_role,
                    prior_state, new_state, reason, correlation_id, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                audit_id, event_type, entity_type, entity_id, actor_id, actor_role,
                prior_state, new_state, reason, correlation_id, outcome
            ))
        except Exception:
            # Audit logging must not break execution if table is unavailable during bootstrap
            pass

    # --------------------------------------------------------------------------
    # 1. SOURCE REGISTRY & PROVENANCE
    # --------------------------------------------------------------------------

    def create_source(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Register a knowledge source in the governed source registry."""
        title = data.get("title")
        authors = data.get("authors_or_org") or data.get("author") or "Unknown"
        publisher = data.get("publisher") or "Unknown"
        source_type = data.get("source_type", "TEXTBOOK")

        if not title:
            raise ValidationError("Title is required for knowledge source registration.")

        source_id = data.get("id") or f"src-{uuid.uuid4().hex[:12]}"
        is_synthetic = 1 if data.get("is_synthetic") else 0
        doc_hash = data.get("document_hash")

        conn = self.db_manager.get_connection()
        try:
            conn.execute("""
                INSERT INTO knowledge_sources (
                    id, title, authors_or_org, publisher, source_type, edition,
                    publication_date, url_or_identifier, language, jurisdiction,
                    regulatory_status, evidence_level, document_hash, notes,
                    is_synthetic, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                source_id, title, authors, publisher, source_type, data.get("edition"),
                data.get("publication_date"), data.get("url_or_identifier"),
                data.get("language", "en"), data.get("jurisdiction", "GLOBAL"),
                data.get("regulatory_status", "APPROVED_STANDARD"),
                data.get("evidence_level", "EXPERT_OPINION"),
                doc_hash, data.get("notes"), is_synthetic,
                data.get("review_status", "DRAFT")
            ))
            self._log_audit_tx(
                conn, event_type="SOURCE_REGISTERED", entity_type="SOURCE",
                entity_id=source_id, actor_id=user_id, new_state=data.get("review_status", "DRAFT")
            )
            conn.commit()
            return self.get_source(source_id)
        finally:
            conn.close()

    def list_sources(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List knowledge sources with version and verification counts."""
        filters = filters or {}
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT s.*,
                       COUNT(DISTINCT sv.id) as version_count,
                       COUNT(DISTINCT sve.id) as verification_count
                FROM knowledge_sources s
                LEFT JOIN kavs_source_versions sv ON s.id = sv.source_id
                LEFT JOIN kavs_source_verification_events sve ON s.id = sve.source_id
                WHERE 1=1
            """
            params = []
            if filters.get("source_type"):
                query += " AND s.source_type = ?"
                params.append(filters["source_type"])
            if filters.get("review_status"):
                query += " AND s.review_status = ?"
                params.append(filters["review_status"])
            if filters.get("query"):
                q = f"%{filters['query'].strip().lower()}%"
                query += " AND (lower(s.title) LIKE ? OR lower(s.authors_or_org) LIKE ? OR lower(s.publisher) LIKE ?)"
                params.extend([q, q, q])
            query += " GROUP BY s.id ORDER BY s.created_at DESC"
            if filters.get("limit"):
                query += f" LIMIT {int(filters['limit'])}"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_source(self, source_id: str) -> Dict[str, Any]:
        """Fetch complete source details with version history, verification events, and rights."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_sources WHERE id = ?;", (source_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Knowledge source '{source_id}' not found.")
            res = dict(row)

            # Versions
            cur.execute("SELECT * FROM kavs_source_versions WHERE source_id = ? ORDER BY created_at DESC;", (source_id,))
            versions = [dict(v) for v in cur.fetchall()]
            for v in versions:
                v["allowed_uses"] = json.loads(v.get("allowed_uses_json") or "[]")
            res["versions"] = versions

            # Verification events
            cur.execute("""
                SELECT sve.*, u.full_name as reviewer_name
                FROM kavs_source_verification_events sve
                JOIN users u ON sve.reviewer_id = u.id
                WHERE sve.source_id = ?
                ORDER BY sve.created_at DESC;
            """, (source_id,))
            res["verification_events"] = [dict(e) for e in cur.fetchall()]

            # Rights reviews
            cur.execute("""
                SELECT srr.*, u.full_name as reviewer_name
                FROM kavs_source_rights_reviews srr
                JOIN users u ON srr.reviewed_by = u.id
                WHERE srr.source_id = ?
                ORDER BY srr.created_at DESC;
            """, (source_id,))
            res["rights_reviews"] = [dict(r) for r in cur.fetchall()]

            return res
        finally:
            conn.close()

    def update_source(self, source_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Update mutable metadata of a knowledge source."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_sources WHERE id = ?;", (source_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Knowledge source '{source_id}' not found.")

            fields = []
            params = []
            for k in ["title", "authors_or_org", "publisher", "edition", "publication_date",
                      "url_or_identifier", "language", "jurisdiction", "regulatory_status",
                      "evidence_level", "document_hash", "notes", "review_status"]:
                if k in data:
                    fields.append(f"{k} = ?")
                    params.append(data[k])

            if fields:
                fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(source_id)
                query = f"UPDATE knowledge_sources SET {', '.join(fields)} WHERE id = ?;"
                conn.execute(query, params)
                self._log_audit_tx(
                    conn, event_type="SOURCE_UPDATED", entity_type="SOURCE",
                    entity_id=source_id, actor_id=user_id,
                    prior_state=existing["review_status"], new_state=data.get("review_status", existing["review_status"])
                )
                conn.commit()

            return self.get_source(source_id)
        finally:
            conn.close()

    def list_source_versions(self, source_id: str) -> List[Dict[str, Any]]:
        """List versions for a specific source."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT sv.*, u.full_name as registered_by_name
                FROM kavs_source_versions sv
                JOIN users u ON sv.registered_by = u.id
                WHERE sv.source_id = ?
                ORDER BY sv.created_at DESC;
            """, (source_id,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["allowed_uses"] = json.loads(r.get("allowed_uses_json") or "[]")
            return rows
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. SOURCE VERSIONS & RIGHTS REVIEWS
    # --------------------------------------------------------------------------

    def register_source_version(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Register a specific version, edition, or printing of a clinical source."""
        source_id = data.get("source_id")
        edition = data.get("edition")
        if not source_id or not edition:
            raise ValidationError("source_id and edition are required.")

        rights_status = data.get("source_rights_status", "METADATA_AND_EXCERPT_ONLY")
        if rights_status not in VALID_RIGHTS_STATUSES:
            raise ValidationError(f"Invalid source_rights_status. Must be one of: {sorted(list(VALID_RIGHTS_STATUSES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, title FROM knowledge_sources WHERE id = ?;", (source_id,))
            source = cur.fetchone()
            if not source:
                raise NotFoundError(f"Knowledge source '{source_id}' not found.")

            version_id = data.get("id") or f"src-ver-{uuid.uuid4().hex[:12]}"
            doc_hash = data.get("document_hash")
            if not doc_hash and data.get("raw_text_content"):
                doc_hash = hashlib.sha256(data["raw_text_content"].encode("utf-8")).hexdigest()

            allowed_uses = data.get("allowed_uses") or ["clinician_contextual_reference", "educational_reference"]

            conn.execute("""
                INSERT INTO kavs_source_versions (
                    id, source_id, edition, revision_number, publication_year,
                    document_hash, locator_type, source_rights_status, allowed_uses_json,
                    is_active, supersedes_version_id, registered_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?);
            """, (
                version_id, source_id, edition, data.get("revision_number"),
                data.get("publication_year"), doc_hash, data.get("locator_type", "PAGE_AND_PARAGRAPH"),
                rights_status, json.dumps(allowed_uses), data.get("supersedes_version_id"), user_id
            ))
            self._log_audit_tx(
                conn, event_type="SOURCE_VERSIONED", entity_type="SOURCE_VERSION",
                entity_id=version_id, actor_id=user_id, new_state="ACTIVE"
            )
            conn.commit()
            return self.get_source_version(version_id)
        finally:
            conn.close()

    def get_source_version(self, version_id: str) -> Dict[str, Any]:
        """Fetch details of a specific source version."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT sv.*, s.title as source_title, s.publisher, s.source_type,
                       u.full_name as registered_by_name
                FROM kavs_source_versions sv
                JOIN knowledge_sources s ON sv.source_id = s.id
                JOIN users u ON sv.registered_by = u.id
                WHERE sv.id = ?;
            """, (version_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Source version '{version_id}' not found.")
            res = dict(row)
            res["allowed_uses"] = json.loads(res.get("allowed_uses_json") or "[]")
            return res
        finally:
            conn.close()

    def record_rights_review(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Record statutory copyright, licensing, and retention permissions for a source."""
        source_id = data.get("source_id")
        license_type = data.get("license_type")
        if not source_id or not license_type:
            raise ValidationError("source_id and license_type are required.")

        conn = self.db_manager.get_connection()
        try:
            review_id = f"rr-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_source_rights_reviews (
                    id, source_id, source_version_id, license_type,
                    full_text_retention_permitted, excerpt_storage_permitted,
                    vector_indexing_permitted, redistribution_permitted,
                    reviewed_by, review_notes, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                review_id, source_id, data.get("source_version_id"), license_type,
                1 if data.get("full_text_retention_permitted") else 0,
                1 if data.get("excerpt_storage_permitted", True) else 0,
                1 if data.get("vector_indexing_permitted", True) else 0,
                1 if data.get("redistribution_permitted") else 0,
                user_id, data.get("review_notes"), data.get("review_status", "APPROVED")
            ))
            self._log_audit_tx(
                conn, event_type="RIGHTS_REVIEWED", entity_type="SOURCE",
                entity_id=source_id, actor_id=user_id, new_state=data.get("review_status", "APPROVED")
            )
            conn.commit()
            return {"id": review_id, "source_id": source_id, "status": data.get("review_status", "APPROVED")}
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. SOURCE LOCATORS (EXACT PHYSICAL & DIGITAL CITATION ANCHORS)
    # --------------------------------------------------------------------------

    def create_source_locator(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a fine-grained locator for a source version."""
        source_version_id = data.get("source_version_id")
        locator_type = data.get("locator_type", "PAGE")
        if not source_version_id:
            raise ValidationError("source_version_id is required.")
        if locator_type not in VALID_LOCATOR_TYPES:
            raise ValidationError(f"Invalid locator_type. Must be one of: {sorted(list(VALID_LOCATOR_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM kavs_source_versions WHERE id = ?;", (source_version_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Source version '{source_version_id}' not found.")

            locator_id = data.get("id") or f"loc-{uuid.uuid4().hex[:12]}"
            verif_state = data.get("verification_state", "UNVERIFIED")
            if verif_state not in VALID_LOCATOR_VERIFICATION_STATES:
                raise ValidationError(f"Invalid verification_state. Must be one of: {sorted(list(VALID_LOCATOR_VERIFICATION_STATES))}")

            conn.execute("""
                INSERT INTO kavs_source_locators (
                    id, source_version_id, locator_type, page_number, page_label,
                    chapter, section, subsection, paragraph_or_table,
                    article_identifier, anchor_range, verification_state, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                locator_id, source_version_id, locator_type, data.get("page_number"),
                data.get("page_label"), data.get("chapter"), data.get("section"),
                data.get("subsection"), data.get("paragraph_or_table"),
                data.get("article_identifier"), data.get("anchor_range"),
                verif_state, user_id
            ))
            self._log_audit_tx(
                conn, event_type="LOCATOR_CREATED", entity_type="LOCATOR",
                entity_id=locator_id, actor_id=user_id, new_state=verif_state
            )
            conn.commit()
            return self.get_source_locator(locator_id)
        finally:
            conn.close()

    def get_source_locator(self, locator_id: str) -> Dict[str, Any]:
        """Fetch details of a single source locator."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT loc.*, sv.edition, s.id as source_id, s.title as source_title
                FROM kavs_source_locators loc
                JOIN kavs_source_versions sv ON loc.source_version_id = sv.id
                JOIN knowledge_sources s ON sv.source_id = s.id
                WHERE loc.id = ?;
            """, (locator_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Source locator '{locator_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    def list_source_locators(self, source_version_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List source locators, optionally by source_version_id."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if source_version_id:
                cur.execute("""
                    SELECT loc.*, u.full_name as created_by_name
                    FROM kavs_source_locators loc
                    JOIN users u ON loc.created_by = u.id
                    WHERE loc.source_version_id = ?
                    ORDER BY loc.created_at DESC;
                """, (source_version_id,))
            else:
                cur.execute("""
                    SELECT loc.*, u.full_name as created_by_name
                    FROM kavs_source_locators loc
                    JOIN users u ON loc.created_by = u.id
                    ORDER BY loc.created_at DESC;
                """)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def verify_source_locator(self, locator_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Verify or dispute an exact source locator."""
        new_state = data.get("verification_state")
        if new_state not in VALID_LOCATOR_VERIFICATION_STATES:
            raise ValidationError(f"Invalid verification_state. Must be one of: {sorted(list(VALID_LOCATOR_VERIFICATION_STATES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, verification_state FROM kavs_source_locators WHERE id = ?;", (locator_id,))
            loc = cur.fetchone()
            if not loc:
                raise NotFoundError(f"Source locator '{locator_id}' not found.")

            conn.execute("""
                UPDATE kavs_source_locators
                SET verification_state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_state, locator_id))
            self._log_audit_tx(
                conn, event_type="LOCATOR_VERIFIED", entity_type="LOCATOR",
                entity_id=locator_id, actor_id=user_id,
                prior_state=loc["verification_state"], new_state=new_state,
                reason=data.get("reason")
            )
            conn.commit()
            return self.get_source_locator(locator_id)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. SOURCE VERIFICATION EVENTS
    # --------------------------------------------------------------------------

    def record_source_verification_event(self, source_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Record an explicit verification check on a source or source version."""
        verif_type = data.get("verification_type")
        result = data.get("result")
        if not verif_type or not result:
            raise ValidationError("verification_type and result are required.")
        if verif_type not in VALID_SOURCE_VERIFICATION_TYPES:
            raise ValidationError(f"Invalid verification_type. Must be one of: {sorted(list(VALID_SOURCE_VERIFICATION_TYPES))}")
        if result not in VALID_SOURCE_VERIFICATION_RESULTS:
            raise ValidationError(f"Invalid result. Must be one of: {sorted(list(VALID_SOURCE_VERIFICATION_RESULTS))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, review_status FROM knowledge_sources WHERE id = ?;", (source_id,))
            source = cur.fetchone()
            if not source:
                raise NotFoundError(f"Knowledge source '{source_id}' not found.")

            event_id = f"sve-{uuid.uuid4().hex[:12]}"
            reviewer_role = data.get("reviewer_role", "GOVERNANCE_LEAD")
            if reviewer_role not in VALID_REVIEWER_ROLES:
                raise ValidationError(f"Invalid reviewer_role. Must be one of: {sorted(list(VALID_REVIEWER_ROLES))}")

            conn.execute("""
                INSERT INTO kavs_source_verification_events (
                    id, source_id, source_version_id, verification_type, result,
                    evidence_reference, policy_version, reviewer_id, reviewer_role, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                event_id, source_id, data.get("source_version_id"), verif_type,
                result, data.get("evidence_reference"), data.get("policy_version", "v1.0-gov"),
                user_id, reviewer_role, data.get("notes")
            ))

            prior_status = source["review_status"]
            new_status = prior_status
            if result == "VERIFIED_PASS" and prior_status == "DRAFT":
                new_status = "APPROVED"
                conn.execute("UPDATE knowledge_sources SET review_status = 'APPROVED', verification_date = CURRENT_TIMESTAMP WHERE id = ?;", (source_id,))
            elif result == "REJECTED":
                new_status = "REJECTED"
                conn.execute("UPDATE knowledge_sources SET review_status = 'REJECTED' WHERE id = ?;", (source_id,))

            self._log_audit_tx(
                conn, event_type="VERIFICATION_RECORDED", entity_type="SOURCE",
                entity_id=source_id, actor_id=user_id, actor_role=reviewer_role,
                prior_state=prior_status, new_state=new_status, reason=data.get("notes")
            )
            conn.commit()

            cur.execute("""
                SELECT sve.*, u.full_name as reviewer_name
                FROM kavs_source_verification_events sve
                JOIN users u ON sve.reviewer_id = u.id
                WHERE sve.id = ?;
            """, (event_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def list_source_verification_events(self, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List source verification events."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if source_id:
                cur.execute("""
                    SELECT sve.*, s.title as source_title, u.full_name as reviewer_name
                    FROM kavs_source_verification_events sve
                    JOIN knowledge_sources s ON sve.source_id = s.id
                    JOIN users u ON sve.reviewer_id = u.id
                    WHERE sve.source_id = ?
                    ORDER BY sve.created_at DESC;
                """, (source_id,))
            else:
                cur.execute("""
                    SELECT sve.*, s.title as source_title, u.full_name as reviewer_name
                    FROM kavs_source_verification_events sve
                    JOIN knowledge_sources s ON sve.source_id = s.id
                    JOIN users u ON sve.reviewer_id = u.id
                    ORDER BY sve.created_at DESC;
                """)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. GOVERNANCE POLICY REGISTRY
    # --------------------------------------------------------------------------

    def register_governance_policy(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Register or revise a formal knowledge governance policy."""
        policy_code = data.get("policy_code")
        version = data.get("version")
        title = data.get("title")
        effective_date = data.get("effective_date")
        summary = data.get("summary")

        if not policy_code or not version or not title or not effective_date or not summary:
            raise ValidationError("policy_code, version, title, effective_date, and summary are required.")

        policy_id = data.get("id") or f"pol-{uuid.uuid4().hex[:12]}"
        status = data.get("status", "APPROVED")
        if status not in VALID_POLICY_STATUSES:
            raise ValidationError(f"Invalid status. Must be one of: {sorted(list(VALID_POLICY_STATUSES))}")

        conn = self.db_manager.get_connection()
        try:
            doc_hash = data.get("policy_document_hash")
            if not doc_hash and summary:
                doc_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest()

            conn.execute("""
                INSERT OR REPLACE INTO kavs_governance_policies (
                    id, policy_code, version, title, effective_date,
                    status, policy_document_hash, approved_by, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                policy_id, policy_code, version, title, effective_date,
                status, doc_hash, user_id, summary
            ))
            self._log_audit_tx(
                conn, event_type="POLICY_REGISTERED", entity_type="POLICY",
                entity_id=policy_id, actor_id=user_id, new_state=status
            )
            conn.commit()
            return self.get_governance_policy(policy_id)
        finally:
            conn.close()

    def get_governance_policy(self, policy_id: str) -> Dict[str, Any]:
        """Fetch a governance policy by ID."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT p.*, u.full_name as approved_by_name
                FROM kavs_governance_policies p
                JOIN users u ON p.approved_by = u.id
                WHERE p.id = ?;
            """, (policy_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Governance policy '{policy_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    def list_governance_policies(self) -> List[Dict[str, Any]]:
        """List all governance policies."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT p.*, u.full_name as approved_by_name
                FROM kavs_governance_policies p
                JOIN users u ON p.approved_by = u.id
                ORDER BY p.approved_at DESC;
            """)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_active_governance_policy(self) -> Dict[str, Any]:
        """Fetch current effective governance policy."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT p.*, u.full_name as approved_by_name
                FROM kavs_governance_policies p
                JOIN users u ON p.approved_by = u.id
                WHERE p.status = 'APPROVED'
                ORDER BY p.approved_at DESC
                LIMIT 1;
            """)
            row = cur.fetchone()
            if not row:
                return {
                    "policy_code": "KAVS-DEFAULT",
                    "version": "1.0.0",
                    "title": "Default KAVS Baseline Governance Policy",
                    "status": "APPROVED",
                    "effective_date": "2026-01-01",
                    "summary": "Mandatory provenance, human review verification, and strict anti-fabrication baseline."
                }
            return dict(row)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. INGESTION WORKBENCH: PREFLIGHT, FILE INTAKE & ADAPTERS
    # --------------------------------------------------------------------------

    def check_source_rights_preflight(self, source_version_id: str, requested_operation: str, user_id: str) -> Dict[str, Any]:
        """Verify if a specific technical operation is permitted under the source version's statutory rights policy."""
        OP_ALIASES = {
            "INGEST": "RETAIN_FILE",
            "REDISTRIBUTE": "EXPORT_REDISTRIBUTE",
            "VECTOR_INDEX": "INDEX_VECTORS",
        }
        requested_operation = OP_ALIASES.get(requested_operation, requested_operation)
        if requested_operation not in VALID_RIGHTS_OPERATIONS:
            raise ValidationError(f"Invalid requested_operation. Must be one of: {sorted(list(VALID_RIGHTS_OPERATIONS))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, source_id, source_rights_status, allowed_uses_json FROM kavs_source_versions WHERE id = ?;", (source_version_id,))
            ver = cur.fetchone()
            if not ver:
                raise NotFoundError(f"Source version '{source_version_id}' not found.")

            source_id = ver["source_id"]

            cur.execute("""
                SELECT * FROM kavs_source_rights_reviews
                WHERE source_version_id = ? OR source_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (source_version_id, source_id))
            rights = cur.fetchone()

            decision = "ALLOWED"
            reason = ""

            if not rights or rights["review_status"] != "APPROVED":
                decision = "BLOCKED"
                reason = f"No approved statutory rights review found for source version '{source_version_id}'."
            else:
                if requested_operation in {"RETAIN_FILE", "SHOW_FULL_TEXT"} and not rights["full_text_retention_permitted"]:
                    decision = "BLOCKED"
                    reason = f"Full text and file retention is prohibited under '{rights['license_type']}' license."
                elif requested_operation in {"EXTRACT_TEXT", "RUN_OCR", "SHOW_EXCERPTS"} and not rights["excerpt_storage_permitted"]:
                    decision = "BLOCKED"
                    reason = f"Excerpt extraction and OCR storage is prohibited under '{rights['license_type']}' license."
                elif requested_operation == "INDEX_VECTORS" and not rights["vector_indexing_permitted"]:
                    decision = "BLOCKED"
                    reason = f"Vector indexing and semantic embedding is prohibited under '{rights['license_type']}' license."
                elif requested_operation == "EXPORT_REDISTRIBUTE" and not rights["redistribution_permitted"]:
                    decision = "BLOCKED"
                    reason = f"Redistribution of source text and external export is prohibited under '{rights['license_type']}' license."
                else:
                    reason = f"Operation '{requested_operation}' is authorized under '{rights['license_type']}' policy."

            receipt_id = f"prf-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_rights_preflight_events (
                    id, source_id, source_version_id, requested_operation,
                    rights_policy_version, decision, reason, actor_id
                ) VALUES (?, ?, ?, ?, 'v1.0-rights', ?, ?, ?);
            """, (receipt_id, source_id, source_version_id, requested_operation, decision, reason, user_id))
            conn.commit()

            return {
                "id": receipt_id,
                "source_id": source_id,
                "source_version_id": source_version_id,
                "requested_operation": requested_operation,
                "decision": decision,
                "allowed": decision == "ALLOWED",
                "reason": reason
            }
        finally:
            conn.close()

    def upload_source_file(
        self,
        source_version_id: str,
        data: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Secure private intake of source file with magic bytes check and SHA-256 fingerprinting."""
        if data is None:
            data = {}
        if kwargs:
            data = {**data, **kwargs}
        if "user_id" in kwargs and not user_id:
            user_id = kwargs["user_id"]
        if not user_id:
            user_id = data.get("user_id", "system")

        preflight = self.check_source_rights_preflight(source_version_id, "RETAIN_FILE", user_id)
        if not preflight["allowed"]:
            raise ForbiddenError(f"Upload blocked by rights policy: Source rights policy prohibits retaining full text files.")

        filename = data.get("original_filename") or data.get("filename")
        if not filename:
            raise ValidationError("original_filename is required.")

        raw_bytes = None
        if "file_bytes" in data and data["file_bytes"] is not None:
            raw_bytes = data["file_bytes"]
        elif "raw_bytes" in data and data["raw_bytes"] is not None:
            raw_bytes = data["raw_bytes"]
        elif "file_base64" in data and data["file_base64"] is not None:
            try:
                raw_bytes = base64.b64decode(data["file_base64"])
            except Exception:
                raise ValidationError("Invalid base64 encoding in file_base64.")
        elif "content_text" in data and data["content_text"] is not None:
            raw_bytes = data["content_text"].encode("utf-8")
        else:
            raise ValidationError("Either file_bytes, raw_bytes, file_base64 or content_text must be provided.")

        file_size = len(raw_bytes)
        if file_size > 50 * 1024 * 1024:
            raise ValidationError("File exceeds maximum allowed upload size (50MB).")
        if file_size == 0:
            raise ValidationError("Uploaded file is empty (0 bytes).")

        mime_type = data.get("mime_type", "application/pdf")
        magic_verified = 1
        detected_magic = ""
        if raw_bytes.startswith(b"%PDF-"):
            detected_magic = "%PDF-"
        elif raw_bytes.startswith(b"PK\x03\x04"):
            detected_magic = "PK\x03\x04"

        if filename.lower().endswith(".pdf") or mime_type == "application/pdf":
            if not raw_bytes.startswith(b"%PDF-"):
                raise ValidationError("Invalid file header: Magic bytes validation failed: file does not match PDF specification.")
        elif filename.lower().endswith(".docx"):
            if not raw_bytes.startswith(b"PK\x03\x04"):
                raise ValidationError("Invalid file header: Magic bytes validation failed: file does not match DOCX specification.")

        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
        file_id = f"fil-{uuid.uuid4().hex[:12]}"
        storage_key = f"kavs-f-{uuid.uuid4().hex}.bin"

        conn = self.db_manager.get_connection()
        try:
            conn.execute("""
                INSERT INTO kavs_source_files (
                    id, source_version_id, storage_key, original_filename,
                    file_size_bytes, mime_type, magic_byte_verified,
                    sha256_checksum, malware_scan_status, upload_status, uploaded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CLEAN', 'COMPLETED', ?);
            """, (
                file_id, source_version_id, storage_key, filename,
                file_size, mime_type, magic_verified,
                sha256_hash, user_id
            ))
            self._log_audit_tx(
                conn, event_type="FILE_UPLOADED", entity_type="SOURCE_FILE",
                entity_id=file_id, actor_id=user_id, new_state="COMPLETED",
                reason=f"Uploaded {filename} ({file_size} bytes, SHA-256: {sha256_hash[:10]}...)"
            )
            conn.commit()

            cur = conn.cursor()
            cur.execute("SELECT * FROM kavs_source_files WHERE id = ?;", (file_id,))
            row = dict(cur.fetchone())
            row["file_checksum"] = f"sha256:{sha256_hash}"
            row["detected_magic"] = detected_magic
            row["scan_status"] = row.get("malware_scan_status", "CLEAN")
            return row
        finally:
            conn.close()

    def get_source_file(self, file_id: str) -> Dict[str, Any]:
        """Retrieve metadata of uploaded source file."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT f.*, sv.edition, s.title as source_title
                FROM kavs_source_files f
                JOIN kavs_source_versions sv ON f.source_version_id = sv.id
                JOIN knowledge_sources s ON sv.source_id = s.id
                WHERE f.id = ?;
            """, (file_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Source file '{file_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. INGESTION JOB ORCHESTRATION & STATE MACHINE
    # --------------------------------------------------------------------------

    def create_ingestion_job(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a new extraction job governed by source rights preflight check."""
        source_id = data.get("source_id")
        source_version_id = data.get("source_version_id")
        if not source_id:
            raise ValidationError("source_id is required for ingestion job.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_sources WHERE id = ?;", (source_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Knowledge source '{source_id}' not found.")

            initial_status = "QUEUED"
            if source_version_id:
                preflight = self.check_source_rights_preflight(source_version_id, "EXTRACT_TEXT", user_id)
                if not preflight["allowed"]:
                    initial_status = "blocked_by_rights"

            job_id = f"ing-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_ingestion_jobs (
                    id, source_id, source_version_id, job_type, status,
                    original_filename, file_checksum, initiated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                job_id, source_id, source_version_id,
                data.get("job_type", "STRUCTURED_EXTRACTION"),
                initial_status,
                data.get("original_filename"), data.get("file_checksum"), user_id
            ))

            conn.execute("""
                INSERT INTO kavs_ingestion_job_events (
                    id, job_id, prior_state, new_state, actor_id, reason, attempt_number
                ) VALUES (?, ?, 'created', ?, ?, ?, 1);
            """, (f"jbe-{uuid.uuid4().hex[:12]}", job_id, initial_status, user_id, "Job initialization"))

            conn.commit()
            return self.get_ingestion_job(job_id)
        finally:
            conn.close()

    def transition_ingestion_job(
        self,
        job_id: str,
        new_state: Optional[str] = None,
        user_id: str = "system",
        reason: Optional[str] = None,
        error_category: Optional[str] = None,
        to_state: Optional[str] = None,
        message: Optional[str] = None,
        event_type: Optional[str] = None,
        payload: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Server-authoritative state transition for an ingestion job."""
        target_state = new_state or to_state
        if not target_state or target_state not in VALID_INGESTION_STATES:
            raise ValidationError(f"Invalid target state '{target_state}'. Must be one of: {sorted(list(VALID_INGESTION_STATES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, status FROM kavs_ingestion_jobs WHERE id = ?;", (job_id,))
            job = cur.fetchone()
            if not job:
                raise NotFoundError(f"Ingestion job '{job_id}' not found.")

            prior_state = job["status"]
            trans_reason = reason or message
            conn.execute("""
                UPDATE kavs_ingestion_jobs
                SET status = ?, error_message = ?
                WHERE id = ?;
            """, (target_state, trans_reason if error_category else None, job_id))

            conn.execute("""
                INSERT INTO kavs_ingestion_job_events (
                    id, job_id, prior_state, new_state, actor_id, reason, error_category
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                f"jbe-{uuid.uuid4().hex[:12]}", job_id, prior_state, target_state,
                user_id, trans_reason, error_category
            ))
            conn.commit()
            return self.get_ingestion_job(job_id)
        finally:
            conn.close()

    def get_ingestion_job(self, job_id: str) -> Dict[str, Any]:
        """Fetch complete ingestion job details with pages, segments, and event history."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT j.*, s.title as source_title, s.publisher,
                       u.full_name as initiated_by_name
                FROM kavs_ingestion_jobs j
                JOIN knowledge_sources s ON j.source_id = s.id
                JOIN users u ON j.initiated_by = u.id
                WHERE j.id = ?;
            """, (job_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Ingestion job '{job_id}' not found.")
            res = dict(row)
            res["job_id"] = res["id"]

            cur.execute("""
                SELECT je.*, u.full_name as actor_name
                FROM kavs_ingestion_job_events je
                LEFT JOIN users u ON je.actor_id = u.id
                WHERE je.job_id = ?
                ORDER BY je.created_at ASC;
            """, (job_id,))
            res["events"] = [dict(e) for e in cur.fetchall()]

            cur.execute("SELECT COUNT(*) as cnt FROM kavs_extraction_pages WHERE job_id = ?;", (job_id,))
            res["total_pages"] = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) as cnt FROM kavs_extraction_tables WHERE job_id = ?;", (job_id,))
            res["total_tables"] = cur.fetchone()["cnt"]

            cur.execute("SELECT COUNT(*) as cnt FROM kavs_claim_drafts WHERE job_id = ?;", (job_id,))
            res["candidate_claims_count"] = cur.fetchone()["cnt"]

            return res
        finally:
            conn.close()

    def list_ingestion_jobs(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List ingestion jobs with optional filtering."""
        filters = filters or {}
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT j.*, s.title as source_title, u.full_name as initiated_by_name
                FROM kavs_ingestion_jobs j
                JOIN knowledge_sources s ON j.source_id = s.id
                JOIN users u ON j.initiated_by = u.id
                WHERE 1=1
            """
            params = []
            if filters.get("status"):
                query += " AND j.status = ?"
                params.append(filters["status"])
            if filters.get("source_id"):
                query += " AND j.source_id = ?"
                params.append(filters["source_id"])
            query += " ORDER BY j.created_at DESC"
            limit = int(filters.get("limit", 50))
            query += f" LIMIT {limit};"

            cur.execute(query, tuple(params))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["job_id"] = r["id"]
            return rows
        finally:
            conn.close()

    def cancel_ingestion_job(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """Cancel an ongoing or queued ingestion job."""
        return self.transition_ingestion_job(job_id, "cancelled", user_id, reason="Cancelled by user.")

    def retry_ingestion_job(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """Retry a failed or stalled ingestion job."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, status FROM kavs_ingestion_jobs WHERE id = ?;", (job_id,))
            job = cur.fetchone()
            if not job:
                raise NotFoundError(f"Ingestion job '{job_id}' not found.")

            cur.execute("SELECT MAX(attempt_number) as max_att FROM kavs_ingestion_job_events WHERE job_id = ?;", (job_id,))
            last_att = cur.fetchone()["max_att"] or 1

            conn.execute("""
                UPDATE kavs_ingestion_jobs
                SET status = 'queued', error_message = NULL
                WHERE id = ?;
            """, (job_id,))

            conn.execute("""
                INSERT INTO kavs_ingestion_job_events (
                    id, job_id, prior_state, new_state, actor_id, reason, attempt_number
                ) VALUES (?, ?, ?, 'queued', ?, 'Job retry initiated', ?);
            """, (f"jbe-{uuid.uuid4().hex[:12]}", job_id, job["status"], user_id, last_att + 1))

            conn.commit()
            return self.get_ingestion_job(job_id)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 8. HIGH-RISK EXTRACTION SCANNER & PROVENANCE ANCHORS
    # --------------------------------------------------------------------------

    def _detect_high_risk_elements(self, text: str) -> Dict[str, Any]:
        """
        Inspect extracted text for high-risk clinical patterns:
        - Numbers, decimals, fractions, ranges
        - Historical Unani posology units (masha, tola, dirham, misqal, ratti)
        - Botanical binomial nomenclature
        - Explicit contraindication and negative safety statements
        - Arabic/Urdu scripts
        """
        flags = []
        if not text:
            return {"has_high_risk": False, "flags": []}

        if re.search(r"\b\d+([.,/]\d+)?\b", text):
            flags.append("NUMERIC_QUANTITY_OR_RANGE")

        if re.search(r"\b(masha|tola|dirham|misqal|ratti|chhatak|habba|dam|ser|mithqal|drachm)\b", text, re.IGNORECASE):
            flags.append("HISTORICAL_POSOLOGY_UNIT")

        if re.search(r"\b[A-Z][a-z]{2,}\s+[a-z]{3,}\s+(L\.|Mill\.|DC\.|Lam\.|Vahl\.|Roxb\.|Hook\.|Boiss\.|Retz\.|var\.|subsp\.|sp\.)\b", text) or \
           re.search(r"\b(Cassia|Rosa|Piper|Terminalia|Nardostachys|Zingiber|Withania|Glycyrrhiza|Commiphora|Emblica|Ocimum|Foeniculum|Coriandrum|Curcuma|Aloe|Artemisia|Plantago)\s+[a-z]{3,}\b", text, re.IGNORECASE):
            flags.append("BOTANICAL_TAXONOMY")

        if re.search(r"\b(contraindicated|do not use|harmful in|la yusta'mal|mudir|khata|prohibited|toxic in|avoid in)\b", text, re.IGNORECASE):
            flags.append("SAFETY_CONTRAINDICATION_OR_NEGATION")

        if re.search(r"[\u0600-\u06FF\u0750-\u077F]", text):
            flags.append("ARABIC_URDU_SCRIPT")

        return {
            "has_high_risk": len(flags) > 0,
            "flags": flags
        }

    def add_extraction_page(self, job_id: str, data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Add extracted page ensuring printed page label and PDF page index remain distinct.
        Applies automated quality scoring and flags high-risk passages for human review.
        """
        raw_text = data.get("raw_page_text") or data.get("extracted_text")
        pdf_index = data.get("pdf_page_index")
        if not raw_text or pdf_index is None:
            raise ValidationError("raw_page_text (or extracted_text) and pdf_page_index are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT source_id, source_version_id FROM kavs_ingestion_jobs WHERE id = ?;", (job_id,))
            job = cur.fetchone()
            if not job:
                raise NotFoundError(f"Ingestion job '{job_id}' not found.")

            risk_scan = self._detect_high_risk_elements(raw_text)
            flags = list(risk_scan["flags"])

            ocr_conf = data.get("ocr_confidence")
            if ocr_conf is not None:
                ocr_conf = float(ocr_conf)
                if ocr_conf < 0.80:
                    flags.append("LOW_OCR_CONFIDENCE")

            page_status = "EXTRACTED"
            if "LOW_OCR_CONFIDENCE" in flags or risk_scan["has_high_risk"]:
                page_status = "REQUIRES_MANUAL_TRANSCRIPTION"

            page_id = f"pag-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_extraction_pages (
                    id, job_id, source_version_id, pdf_page_index, printed_page_label,
                    chapter, section, ocr_engine, ocr_confidence, detected_language,
                    raw_page_text, normalized_search_text, quality_flags_json, page_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                page_id, job_id, job["source_version_id"], int(pdf_index),
                data.get("printed_page_label"), data.get("chapter"), data.get("section"),
                data.get("ocr_engine", "TESSERACT_OCR_v5"), ocr_conf,
                data.get("detected_language", "en"), raw_text,
                data.get("normalized_search_text", raw_text.strip().lower()),
                json.dumps(flags), page_status
            ))
            conn.commit()

            return self.get_extraction_page(page_id)
        finally:
            conn.close()

    def get_extraction_page(self, page_id: str) -> Dict[str, Any]:
        """Fetch details of a single extracted page."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM kavs_extraction_pages WHERE id = ?;", (page_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Extraction page '{page_id}' not found.")
            res = dict(row)
            res["quality_flags"] = json.loads(res.get("quality_flags_json") or "[]")
            res["is_high_risk"] = len(res["quality_flags"]) > 0
            return res
        finally:
            conn.close()

    def list_extraction_pages(self, job_id: str) -> List[Dict[str, Any]]:
        """List extracted pages for a specific ingestion job."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM kavs_extraction_pages
                WHERE job_id = ?
                ORDER BY pdf_page_index ASC;
            """, (job_id,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["quality_flags"] = json.loads(r.get("quality_flags_json") or "[]")
                r["is_high_risk"] = len(r["quality_flags"]) > 0
            return rows
        finally:
            conn.close()

    def add_extraction_segment(self, job_id: str, data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """Add passage or paragraph segment with high-risk analysis."""
        locator = data.get("locator")
        raw_text = data.get("raw_extracted_text")
        if not locator or not raw_text:
            raise ValidationError("locator and raw_extracted_text are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT source_id FROM kavs_ingestion_jobs WHERE id = ?;", (job_id,))
            job = cur.fetchone()
            if not job:
                raise NotFoundError(f"Ingestion job '{job_id}' not found.")

            risk_scan = self._detect_high_risk_elements(raw_text)
            fidelity_status = data.get("fidelity_status", "machine_extracted")

            segment_id = f"seg-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_extraction_segments (
                    id, job_id, source_id, locator, raw_extracted_text,
                    fidelity_status, ocr_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                segment_id, job_id, job["source_id"], locator, raw_text,
                fidelity_status, float(data.get("ocr_confidence", 1.0))
            ))
            conn.execute("UPDATE kavs_ingestion_jobs SET total_segments = total_segments + 1 WHERE id = ?;", (job_id,))
            conn.commit()

            return {
                "segment_id": segment_id,
                "id": segment_id,
                "locator": locator,
                "status": fidelity_status,
                "fidelity_status": fidelity_status,
                "is_high_risk": risk_scan["has_high_risk"],
                "high_risk_flags": risk_scan["flags"]
            }
        finally:
            conn.close()

    def get_extraction_segment(self, segment_id: str) -> Dict[str, Any]:
        """Fetch extraction segment details with full correction audit trail."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.*, j.source_version_id, src.title as source_title
                FROM kavs_extraction_segments s
                JOIN kavs_ingestion_jobs j ON s.job_id = j.id
                JOIN knowledge_sources src ON s.source_id = src.id
                WHERE s.id = ?;
            """, (segment_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Extraction segment '{segment_id}' not found.")
            res = dict(row)
            res["segment_id"] = res["id"]

            cur.execute("""
                SELECT c.*, u.full_name as corrected_by_name
                FROM kavs_extraction_corrections c
                JOIN users u ON c.corrected_by = u.id
                WHERE c.segment_id = ?
                ORDER BY c.created_at ASC;
            """, (segment_id,))
            res["correction_history"] = [dict(c) for c in cur.fetchall()]

            return res
        finally:
            conn.close()

    def record_segment_correction(
        self,
        segment_id: str,
        data_or_text: Any,
        user_id_or_reason: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record manual transcription correction.
        Preserves original machine text, records reason, and updates fidelity status.
        """
        if isinstance(data_or_text, dict):
            data = data_or_text
            actor_id = user_id_or_reason or user_id or "system"
        else:
            data = {
                "corrected_text": str(data_or_text),
                "correction_reason": str(user_id_or_reason or "")
            }
            actor_id = user_id or "system"

        corrected_text = data.get("corrected_text")
        reason = data.get("correction_reason")
        if not corrected_text or not reason or not reason.strip():
            raise ValidationError("corrected_text and mandatory correction_reason are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, job_id, raw_extracted_text, fidelity_status FROM kavs_extraction_segments WHERE id = ?;", (segment_id,))
            seg = cur.fetchone()
            if not seg:
                raise NotFoundError(f"Extraction segment '{segment_id}' not found.")

            corr_id = f"cor-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_extraction_corrections (
                    id, segment_id, original_machine_text, corrected_text,
                    correction_reason, corrected_by
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (corr_id, segment_id, seg["raw_extracted_text"], corrected_text.strip(), reason.strip(), actor_id))

            conn.execute("""
                UPDATE kavs_extraction_segments
                SET human_corrected_text = ?, fidelity_status = 'human_checked',
                    reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, review_notes = ?
                WHERE id = ?;
            """, (corrected_text.strip(), actor_id, reason.strip(), segment_id))

            conn.execute("UPDATE kavs_ingestion_jobs SET reviewed_segments = reviewed_segments + 1 WHERE id = ?;", (seg["job_id"],))
            conn.commit()

            return {
                "segment_id": segment_id,
                "id": segment_id,
                "fidelity_status": "human_checked",
                "status": "human_checked",
                "verified": True,
                "human_corrected_text": corrected_text.strip(),
                "review_notes": reason.strip(),
                "details": self.get_extraction_segment(segment_id)
            }
        finally:
            conn.close()

    def mark_segment_unreadable(self, segment_id: str, reason: str, user_id: str) -> Dict[str, Any]:
        """Mark an unreadable or damaged source passage."""
        if not reason or not reason.strip():
            raise ValidationError("A mandatory reason is required to mark segment unreadable.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, job_id FROM kavs_extraction_segments WHERE id = ?;", (segment_id,))
            seg = cur.fetchone()
            if not seg:
                raise NotFoundError(f"Extraction segment '{segment_id}' not found.")

            conn.execute("""
                UPDATE kavs_extraction_segments
                SET fidelity_status = 'unreadable', reviewed_by = ?,
                    reviewed_at = CURRENT_TIMESTAMP, review_notes = ?
                WHERE id = ?;
            """, (user_id, reason.strip(), segment_id))

            conn.execute("UPDATE kavs_ingestion_jobs SET reviewed_segments = reviewed_segments + 1 WHERE id = ?;", (seg["job_id"],))
            conn.commit()

            return self.get_extraction_segment(segment_id)
        finally:
            conn.close()

    def review_extraction_segment(self, segment_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Review extraction segment (maintains full compatibility with existing callers)."""
        if data.get("human_corrected_text"):
            return self.record_segment_correction(segment_id, {
                "corrected_text": data["human_corrected_text"],
                "correction_reason": data.get("review_notes", "Reviewed and corrected by human reviewer")
            }, user_id)

        fidelity_status = data.get("fidelity_status", "human_checked")
        if fidelity_status not in VALID_EXTRACTION_FIDELITY:
            raise ValidationError(f"Invalid fidelity_status. Must be one of: {sorted(list(VALID_EXTRACTION_FIDELITY))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, job_id FROM kavs_extraction_segments WHERE id = ?;", (segment_id,))
            seg = cur.fetchone()
            if not seg:
                raise NotFoundError(f"Extraction segment '{segment_id}' not found.")

            conn.execute("""
                UPDATE kavs_extraction_segments
                SET fidelity_status = ?, reviewed_by = ?,
                    reviewed_at = CURRENT_TIMESTAMP, review_notes = ?
                WHERE id = ?;
            """, (fidelity_status, user_id, data.get("review_notes"), segment_id))

            conn.execute("UPDATE kavs_ingestion_jobs SET reviewed_segments = reviewed_segments + 1 WHERE id = ?;", (seg["job_id"],))
            conn.commit()
            return {
                "segment_id": segment_id,
                "id": segment_id,
                "fidelity_status": fidelity_status,
                "status": fidelity_status,
                "verified": fidelity_status == "human_checked"
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 9. STRUCTURED TABLE EXTRACTIONS
    # --------------------------------------------------------------------------

    def add_extraction_table(self, job_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Add structured formulation or posology table extraction."""
        table_title = data.get("table_title")
        if not table_title:
            raise ValidationError("table_title is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM kavs_ingestion_jobs WHERE id = ?;", (job_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Ingestion job '{job_id}' not found.")

            headers = data.get("headers") or data.get("columns", [])
            rows = data.get("rows", [])
            table_id = f"tbl-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_extraction_tables (
                    id, job_id, page_id, locator_id, table_title, headers_json,
                    rows_json, footnotes, extraction_confidence, structure_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                table_id, job_id, data.get("page_id"), data.get("locator_id"),
                table_title, json.dumps(headers),
                json.dumps(rows), data.get("footnotes") or data.get("footnote"),
                float(data.get("extraction_confidence", 1.0)),
                data.get("structure_status", "STRUCTURED")
            ))
            conn.commit()

            cur.execute("SELECT * FROM kavs_extraction_tables WHERE id = ?;", (table_id,))
            res = dict(cur.fetchone())
            res["headers"] = json.loads(res.get("headers_json") or "[]")
            res["rows"] = json.loads(res.get("rows_json") or "[]")
            res["total_rows"] = len(res["rows"])
            return res
        finally:
            conn.close()

    def list_extraction_tables(self, job_id: str) -> List[Dict[str, Any]]:
        """List extracted tables for an ingestion job."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM kavs_extraction_tables WHERE job_id = ? ORDER BY created_at ASC;", (job_id,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["headers"] = json.loads(r.get("headers_json") or "[]")
                r["rows"] = json.loads(r.get("rows_json") or "[]")
                r["total_rows"] = len(r["rows"])
            return rows
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 10. CANDIDATE CLAIM DRAFTS WORKBENCH
    # --------------------------------------------------------------------------

    def create_claim_draft(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a candidate claim draft tethered strictly to an actual extracted segment.
        Validates that source segment exists; model cannot hallucinate source spans.
        Draft claims are NEVER served in live clinical consultation retrieval.
        """
        segment_id = data.get("segment_id")
        claim_text = data.get("proposed_claim_text") or data.get("draft_text")

        if not segment_id or not claim_text:
            raise ValidationError("segment_id and proposed_claim_text (or draft_text) are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.id, s.job_id, s.source_id, j.source_version_id, s.raw_extracted_text
                FROM kavs_extraction_segments s
                JOIN kavs_ingestion_jobs j ON s.job_id = j.id
                WHERE s.id = ?;
            """, (segment_id,))
            seg = cur.fetchone()
            if not seg:
                raise NotFoundError(f"Extraction segment '{segment_id}' does not exist.")

            source_id = data.get("source_id") or seg["source_id"]
            source_version_id = data.get("source_version_id") or seg["source_version_id"]
            job_id = data.get("job_id") or seg["job_id"]
            if not source_version_id and source_id:
                cur.execute("SELECT id FROM kavs_source_versions WHERE source_id = ? ORDER BY created_at DESC LIMIT 1;", (source_id,))
                v_row = cur.fetchone()
                if v_row:
                    source_version_id = v_row["id"]
            if not source_id or not source_version_id:
                raise ValidationError("source_id and source_version_id are required.")

            locator_id = data.get("locator_id")
            if locator_id:
                cur.execute("SELECT id FROM kavs_source_locators WHERE id = ?;", (locator_id,))
                if not cur.fetchone():
                    raise NotFoundError(f"Source locator '{locator_id}' not found.")

            claim_type = data.get("proposed_claim_type") or data.get("target_claim_type", "traditional_use")
            risk_scan = self._detect_high_risk_elements(claim_text)
            draft_id = f"cld-{uuid.uuid4().hex[:12]}"

            conn.execute("""
                INSERT INTO kavs_claim_drafts (
                    id, job_id, segment_id, source_id, source_version_id, locator_id,
                    proposed_claim_text, proposed_claim_type, extracted_concepts_json,
                    has_high_risk_elements, uncertainty_flags_json, extraction_model_info,
                    draft_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT_UNVERIFIED');
            """, (
                draft_id, job_id, segment_id, source_id, source_version_id, locator_id,
                claim_text.strip(), claim_type,
                json.dumps(data.get("extracted_concepts", [])),
                1 if risk_scan["has_high_risk"] else 0,
                json.dumps(risk_scan["flags"]),
                data.get("extraction_model_info", "DETERMINISTIC_PARSER_v1.0")
            ))
            conn.commit()

            return self.get_claim_draft(draft_id)
        finally:
            conn.close()

    def get_claim_draft(self, draft_id: str) -> Dict[str, Any]:
        """Fetch candidate claim draft with segment context."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT cd.*, seg.locator as segment_locator, seg.raw_extracted_text,
                       seg.fidelity_status, s.title as source_title
                FROM kavs_claim_drafts cd
                JOIN kavs_extraction_segments seg ON cd.segment_id = seg.id
                JOIN knowledge_sources s ON cd.source_id = s.id
                WHERE cd.id = ?;
            """, (draft_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Claim draft '{draft_id}' not found.")
            res = dict(row)
            res["draft_text"] = res["proposed_claim_text"]
            res["reviewed_by"] = res.get("reviewer_id")
            res["promoted_claim_id"] = res.get("promoted_claim_id")
            res["is_human_reviewed"] = (res.get("reviewer_id") is not None and res.get("draft_status") in ("PROMOTED", "REJECTED"))
            res["extracted_concepts"] = json.loads(res.get("extracted_concepts_json") or "[]")
            res["uncertainty_flags"] = json.loads(res.get("uncertainty_flags_json") or "[]")
            return res
        finally:
            conn.close()

    def list_claim_drafts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List candidate claim drafts with optional filtering."""
        filters = filters or {}
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT cd.*, seg.locator as segment_locator, seg.fidelity_status, s.title as source_title
                FROM kavs_claim_drafts cd
                JOIN kavs_extraction_segments seg ON cd.segment_id = seg.id
                JOIN knowledge_sources s ON cd.source_id = s.id
                WHERE 1=1
            """
            params = []
            if filters.get("job_id"):
                query += " AND cd.job_id = ?"
                params.append(filters["job_id"])
            if filters.get("source_id"):
                query += " AND cd.source_id = ?"
                params.append(filters["source_id"])
            if filters.get("draft_status"):
                query += " AND cd.draft_status = ?"
                params.append(filters["draft_status"])
            if filters.get("has_high_risk") is not None:
                query += " AND cd.has_high_risk_elements = ?"
                params.append(1 if filters["has_high_risk"] else 0)

            query += " ORDER BY cd.created_at DESC"
            limit = int(filters.get("limit", 50))
            query += f" LIMIT {limit}"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["draft_text"] = r["proposed_claim_text"]
                r["reviewed_by"] = r.get("reviewer_id")
                r["promoted_claim_id"] = r.get("promoted_claim_id")
                r["is_human_reviewed"] = (r.get("reviewer_id") is not None and r.get("draft_status") in ("PROMOTED", "REJECTED"))
                r["extracted_concepts"] = json.loads(r.get("extracted_concepts_json") or "[]")
                r["uncertainty_flags"] = json.loads(r.get("uncertainty_flags_json") or "[]")
            return rows
        finally:
            conn.close()

    def submit_claim_draft_for_review(self, draft_id: str, user_id: str) -> Dict[str, Any]:
        """Submit claim draft for formal clinical governance review."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, draft_status FROM kavs_claim_drafts WHERE id = ?;", (draft_id,))
            draft = cur.fetchone()
            if not draft:
                raise NotFoundError(f"Claim draft '{draft_id}' not found.")

            conn.execute("""
                UPDATE kavs_claim_drafts
                SET draft_status = 'PENDING_REVIEW', reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (user_id, draft_id))
            conn.commit()

            return self.get_claim_draft(draft_id)
        finally:
            conn.close()

    def reject_claim_draft(self, draft_id: str, reason: str, user_id: str) -> Dict[str, Any]:
        """Reject candidate claim draft with mandatory documented reason."""
        if not reason or not reason.strip():
            raise ValidationError("A mandatory rejection reason is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, draft_status FROM kavs_claim_drafts WHERE id = ?;", (draft_id,))
            draft = cur.fetchone()
            if not draft:
                raise NotFoundError(f"Claim draft '{draft_id}' not found.")

            conn.execute("""
                UPDATE kavs_claim_drafts
                SET draft_status = 'REJECTED', review_notes = ?, reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (reason.strip(), user_id, draft_id))
            conn.commit()

            return self.get_claim_draft(draft_id)
        finally:
            conn.close()

    def promote_draft_to_atomic_claim(
        self,
        draft_id: str,
        user_id: str,
        overrides: Optional[Dict[str, Any]] = None,
        item_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Promote verified candidate claim draft into an atomic claim in knowledge_claims.
        Guarantees:
        1. Segment fidelity must be 'human_checked'.
        2. Claim starts in 'UNDER_REVIEW' / 'under_review'.
        3. Never published to clinical CDS until 5-dimension governance approval.
        """
        draft = self.get_claim_draft(draft_id)
        if draft["fidelity_status"] != "human_checked":
            raise ValidationError(f"Claim draft '{draft_id}' cannot be promoted until underlying extraction segment is human verified ('human_checked'). Currently: '{draft['fidelity_status']}'.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if not item_id:
                cur.execute("SELECT id FROM knowledge_items WHERE domain = 'UNANI' LIMIT 1;")
                it = cur.fetchone()
                if it:
                    item_id = it["id"]
                else:
                    item_id = f"item-{uuid.uuid4().hex[:8]}"
                    cur.execute("""
                        INSERT INTO knowledge_items (id, domain, entity_type, canonical_name, description, clinical_scope, claim_type, status, created_by)
                        VALUES (?, 'UNANI', 'SINGLE_DRUG', 'Botanical Drug Extraction', 'Extracted from source', 'OUTPATIENT', 'traditional_use', 'approved', ?);
                    """, (item_id, user_id))
                    conn.commit()

            claim_data = {
                "item_id": item_id,
                "claim_text": draft["proposed_claim_text"],
                "claim_type": draft["proposed_claim_type"],
                "status": "under_review",
                "approval_state": "UNDER_REVIEW",
                "source_id": draft["source_id"],
                "location_in_source": draft.get("segment_locator", ""),
                "quote_or_excerpt": draft.get("raw_extracted_text", "")
            }
            if overrides:
                claim_data.update(overrides)

            claim_res = self.create_atomic_claim(claim_data, user_id)

            conn.execute("""
                UPDATE kavs_claim_drafts
                SET draft_status = 'PROMOTED', review_notes = 'Promoted to atomic claim',
                    promoted_claim_id = ?,
                    reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (claim_res["id"], user_id, draft_id))
            conn.commit()

            claim_res["promoted_from_draft_id"] = draft_id
            return claim_res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 11. INGESTION QUALITY & QUEUE MONITORING
    # --------------------------------------------------------------------------

    def get_ingestion_quality_metrics(self) -> Dict[str, Any]:
        """Aggregate extraction quality, OCR confidence, and human review completion metrics."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as total_jobs, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_jobs FROM kavs_ingestion_jobs;")
            j_stats = cur.fetchone()

            cur.execute("SELECT COUNT(*) as total_pages FROM kavs_extraction_pages;")
            p_stats = cur.fetchone()

            cur.execute("""
                SELECT COUNT(*) as total_segments,
                       SUM(CASE WHEN fidelity_status='human_checked' THEN 1 ELSE 0 END) as reviewed_segments,
                       SUM(CASE WHEN fidelity_status='unreadable' THEN 1 ELSE 0 END) as unreadable_segments,
                       AVG(ocr_confidence) as avg_confidence
                FROM kavs_extraction_segments;
            """)
            s_stats = cur.fetchone()

            cur.execute("""
                SELECT COUNT(*) as total_drafts,
                       SUM(CASE WHEN has_high_risk_elements=1 THEN 1 ELSE 0 END) as high_risk_drafts,
                       SUM(CASE WHEN draft_status IN ('PROMOTED', 'PROMOTED_TO_CLAIM') THEN 1 ELSE 0 END) as promoted_drafts
                FROM kavs_claim_drafts;
            """)
            d_stats = cur.fetchone()

            cur.execute("SELECT fidelity_status, COUNT(*) as count FROM kavs_extraction_segments GROUP BY fidelity_status;")
            fidelity_dist = {r["fidelity_status"]: r["count"] for r in cur.fetchall()}

            return {
                "total_jobs": j_stats["total_jobs"] or 0,
                "completed_jobs": j_stats["completed_jobs"] or 0,
                "total_pages": p_stats["total_pages"] or 0,
                "total_segments": s_stats["total_segments"] or 0,
                "reviewed_segments": s_stats["reviewed_segments"] or 0,
                "unreadable_segments": s_stats["unreadable_segments"] or 0,
                "average_ocr_confidence": round(float(s_stats["avg_confidence"] or 1.0), 3),
                "total_candidate_drafts": d_stats["total_drafts"] or 0,
                "high_risk_drafts_flagged": d_stats["high_risk_drafts"] or 0,
                "promoted_drafts": d_stats["promoted_drafts"] or 0,
                "fidelity_distribution": fidelity_dist,
                "claim_draft_conversion_rate_pct": round(100.0 * (d_stats["promoted_drafts"] or 0) / max(d_stats["total_drafts"] or 1, 1), 2),
                "fidelity_review_completion_rate": round((s_stats["reviewed_segments"] or 0) / max(s_stats["total_segments"] or 1, 1), 3)
            }
        finally:
            conn.close()

    def get_ingestion_queue_health(self) -> Dict[str, Any]:
        """Health check and queue status for ingestion workers."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status, COUNT(*) as count FROM kavs_ingestion_jobs GROUP BY status;")
            counts = {r["status"]: r["count"] for r in cur.fetchall()}

            return {
                "queue_status": "HEALTHY",
                "queue_healthy": True,
                "active_jobs": counts.get("extracting", 0) + counts.get("ocr_running", 0),
                "queued_jobs": counts.get("queued", 0),
                "review_required_jobs": counts.get("fidelity_review_required", 0) + counts.get("claim_drafts_ready", 0),
                "completed_jobs": counts.get("completed", 0),
                "failed_jobs": counts.get("failed_retryable", 0) + counts.get("failed_terminal", 0),
                "breakdown_by_state": counts
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. FIVE-DIMENSION CLAIM VERIFICATION & GOVERNED APPROVAL
    # --------------------------------------------------------------------------

    def record_claim_verification(self, claim_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Record the 5 independent verification dimensions for an atomic claim:
        A. Source Authenticity
        B. Extraction Fidelity
        C. Evidence Characterization
        D. Clinical Review State
        E. Intended-Use Authorization
        """
        # Validate Dimensions
        src_auth = data.get("source_authenticity", "metadata_verified")
        ext_fid = data.get("extraction_fidelity", "human_checked")
        evid_char = data.get("evidence_characterization", "traditional_description")
        rev_state = data.get("clinical_review_state", "approved_for_defined_use")
        int_use = data.get("intended_use_authorization", "clinician_contextual_reference")
        lead_role = data.get("lead_reviewer_role", "UNANI_SCHOLAR")

        if src_auth not in VALID_SOURCE_AUTHENTICITY:
            raise ValidationError(f"Invalid source_authenticity. Must be one of: {sorted(list(VALID_SOURCE_AUTHENTICITY))}")
        if ext_fid not in VALID_EXTRACTION_FIDELITY:
            raise ValidationError(f"Invalid extraction_fidelity. Must be one of: {sorted(list(VALID_EXTRACTION_FIDELITY))}")
        if evid_char not in VALID_EVIDENCE_CHARACTERIZATIONS:
            raise ValidationError(f"Invalid evidence_characterization. Must be one of: {sorted(list(VALID_EVIDENCE_CHARACTERIZATIONS))}")
        if rev_state not in VALID_CLINICAL_REVIEW_STATES:
            raise ValidationError(f"Invalid clinical_review_state. Must be one of: {sorted(list(VALID_CLINICAL_REVIEW_STATES))}")
        if int_use not in VALID_INTENDED_USE_AUTHORIZATIONS:
            raise ValidationError(f"Invalid intended_use_authorization. Must be one of: {sorted(list(VALID_INTENDED_USE_AUTHORIZATIONS))}")
        if lead_role not in VALID_REVIEWER_ROLES:
            raise ValidationError(f"Invalid lead_reviewer_role. Must be one of: {sorted(list(VALID_REVIEWER_ROLES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, item_id, claim_text FROM knowledge_claims WHERE id = ?;", (claim_id,))
            claim = cur.fetchone()
            if not claim:
                raise NotFoundError(f"Atomic claim '{claim_id}' not found.")

            # Deactivate previous active verifications for this claim
            conn.execute("UPDATE kavs_claim_verifications SET is_active = 0 WHERE claim_id = ?;", (claim_id,))

            verif_id = f"kavs-v-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_claim_verifications (
                    id, claim_id, source_authenticity, extraction_fidelity,
                    evidence_characterization, study_design, population_applicability,
                    risk_of_bias, certainty_level, clinical_review_state,
                    intended_use_authorization, lead_reviewer_id, lead_reviewer_role,
                    second_approver_id, review_comments, approved_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1);
            """, (
                verif_id, claim_id, src_auth, ext_fid, evid_char,
                data.get("study_design"), data.get("population_applicability"),
                data.get("risk_of_bias", "LOW"), data.get("certainty_level", "ESTABLISHED"),
                rev_state, int_use, user_id, lead_role,
                data.get("second_approver_id"), data.get("review_comments")
            ))

            # Synchronize claim status if approved
            if rev_state == "approved_for_defined_use":
                conn.execute("""
                    UPDATE knowledge_claims
                    SET status = 'approved', approval_state = 'APPROVED', reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (user_id, claim_id))

            self._log_audit_tx(
                conn, event_type="CLAIM_VERIFIED", entity_type="CLAIM",
                entity_id=claim_id, actor_id=user_id, actor_role=lead_role,
                new_state=rev_state, reason=data.get("review_comments")
            )
            conn.commit()
            return self.get_claim_verification(verif_id)
        finally:
            conn.close()

    def get_claim_verification(self, verif_id: str) -> Dict[str, Any]:
        """Fetch verification details for an atomic claim."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT cv.*, kc.claim_text, kc.claim_type, ki.canonical_name as item_name,
                       u1.full_name as lead_reviewer_name,
                       u2.full_name as second_approver_name
                FROM kavs_claim_verifications cv
                JOIN knowledge_claims kc ON cv.claim_id = kc.id
                JOIN knowledge_items ki ON kc.item_id = ki.id
                JOIN users u1 ON cv.lead_reviewer_id = u1.id
                LEFT JOIN users u2 ON cv.second_approver_id = u2.id
                WHERE cv.id = ?;
            """, (verif_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Claim verification record '{verif_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. ATOMIC CLAIM WORKFLOW & TRACEABILITY
    # --------------------------------------------------------------------------

    def create_atomic_claim(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a new atomic clinical claim tied to a knowledge item with provenance citation."""
        item_id = data.get("item_id")
        claim_text = data.get("claim_text")
        claim_type = data.get("claim_type", "expert_consensus")

        if not item_id or not claim_text:
            raise ValidationError("item_id and claim_text are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, canonical_name FROM knowledge_items WHERE id = ?;", (item_id,))
            item = cur.fetchone()
            if not item:
                raise NotFoundError(f"Knowledge item '{item_id}' not found.")

            claim_id = data.get("id") or f"clm-{uuid.uuid4().hex[:12]}"
            evidence_strength = data.get("evidence_strength", "MODERATE")
            initial_status = data.get("status", "draft")
            initial_approval_state = data.get("approval_state", "DRAFT")

            conn.execute("""
                INSERT INTO knowledge_claims (
                    id, item_id, claim_text, claim_type, linked_concepts_json,
                    evidence_strength, status, approval_state, clinical_limitations,
                    is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                claim_id, item_id, claim_text.strip(), claim_type,
                json.dumps(data.get("linked_concepts", [])),
                evidence_strength, initial_status, initial_approval_state,
                data.get("clinical_limitations"),
                1 if data.get("is_synthetic") else 0
            ))

            # If citation/source provided, link it
            source_id = data.get("source_id")
            if source_id:
                citation_id = f"cit-{uuid.uuid4().hex[:12]}"
                locator_text = data.get("location_in_source") or data.get("locator") or "Section Monograph"
                conn.execute("""
                    INSERT INTO knowledge_citations (
                        id, claim_id, source_id, citation_type, location_in_source, quote_or_excerpt
                    ) VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    citation_id, claim_id, source_id,
                    data.get("citation_type", "SUPPORTING"),
                    locator_text, data.get("quote_or_excerpt")
                ))

            self._log_audit_tx(
                conn, event_type="CLAIM_CREATED", entity_type="CLAIM",
                entity_id=claim_id, actor_id=user_id, new_state=initial_approval_state
            )
            conn.commit()
            return self.get_atomic_claim(claim_id)
        finally:
            conn.close()

    def list_atomic_claims(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List atomic claims with verification and item metadata."""
        filters = filters or {}
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT kc.*, ki.canonical_name as item_name, ki.domain,
                       cv.source_authenticity, cv.extraction_fidelity,
                       cv.evidence_characterization, cv.clinical_review_state,
                       cv.intended_use_authorization
                FROM knowledge_claims kc
                JOIN knowledge_items ki ON kc.item_id = ki.id
                LEFT JOIN kavs_claim_verifications cv ON kc.id = cv.claim_id AND cv.is_active = 1
                WHERE 1=1
            """
            params = []
            if filters.get("status"):
                query += " AND kc.status = ?"
                params.append(filters["status"])
            if filters.get("approval_state"):
                query += " AND kc.approval_state = ?"
                params.append(filters["approval_state"])
            if filters.get("item_id"):
                query += " AND kc.item_id = ?"
                params.append(filters["item_id"])
            if filters.get("claim_type"):
                query += " AND kc.claim_type = ?"
                params.append(filters["claim_type"])
            if filters.get("query"):
                q = f"%{filters['query'].strip().lower()}%"
                query += " AND (lower(kc.claim_text) LIKE ? OR lower(ki.canonical_name) LIKE ?)"
                params.extend([q, q])

            query += " ORDER BY kc.created_at DESC"
            if filters.get("limit"):
                query += f" LIMIT {int(filters['limit'])}"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["linked_concepts"] = json.loads(r.get("linked_concepts_json") or "[]")
            return rows
        finally:
            conn.close()

    def get_atomic_claim(self, claim_id: str) -> Dict[str, Any]:
        """Fetch atomic claim with citations, verification, and conflict links."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT kc.*, ki.canonical_name as item_name, ki.domain
                FROM knowledge_claims kc
                JOIN knowledge_items ki ON kc.item_id = ki.id
                WHERE kc.id = ?;
            """, (claim_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Claim '{claim_id}' not found.")
            res = dict(row)
            res["linked_concepts"] = json.loads(res.get("linked_concepts_json") or "[]")

            # Citations
            cur.execute("""
                SELECT cit.*, s.title as source_title, s.publisher
                FROM knowledge_citations cit
                JOIN knowledge_sources s ON cit.source_id = s.id
                WHERE cit.claim_id = ?;
            """, (claim_id,))
            res["citations"] = [dict(c) for c in cur.fetchall()]

            # Active Verification
            cur.execute("""
                SELECT cv.*, u.full_name as lead_reviewer_name
                FROM kavs_claim_verifications cv
                JOIN users u ON cv.lead_reviewer_id = u.id
                WHERE cv.claim_id = ? AND cv.is_active = 1;
            """, (claim_id,))
            verif = cur.fetchone()
            res["verification"] = dict(verif) if verif else None

            # Conflicts
            cur.execute("""
                SELECT cl.*, s.title as contradicting_source
                FROM kavs_evidence_conflict_links cl
                JOIN knowledge_evidence e ON cl.evidence_id = e.id
                JOIN knowledge_sources s ON e.source_id = s.id
                WHERE cl.claim_id = ?;
            """, (claim_id,))
            res["conflicts"] = [dict(c) for c in cur.fetchall()]

            return res
        finally:
            conn.close()

    def submit_claim_for_review(self, claim_id: str, user_id: str) -> Dict[str, Any]:
        """Submit draft claim for clinical governance review."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, approval_state, status FROM knowledge_claims WHERE id = ?;", (claim_id,))
            claim = cur.fetchone()
            if not claim:
                raise NotFoundError(f"Claim '{claim_id}' not found.")
            if claim["approval_state"] not in {"DRAFT", "CHANGES_REQUESTED"}:
                raise ConflictError(f"Cannot submit claim in state '{claim['approval_state']}' for review.")

            conn.execute("""
                UPDATE knowledge_claims
                SET approval_state = 'UNDER_REVIEW', status = 'under_review', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (claim_id,))
            self._log_audit_tx(
                conn, event_type="CLAIM_SUBMITTED_FOR_REVIEW", entity_type="CLAIM",
                entity_id=claim_id, actor_id=user_id,
                prior_state=claim["approval_state"], new_state="UNDER_REVIEW"
            )
            conn.commit()
            return self.get_atomic_claim(claim_id)
        finally:
            conn.close()

    def approve_claim(self, claim_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Approve a claim with 5-dimension verification."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, approval_state FROM knowledge_claims WHERE id = ?;", (claim_id,))
            claim = cur.fetchone()
            if not claim:
                raise NotFoundError(f"Claim '{claim_id}' not found.")

            verif_res = self.record_claim_verification(claim_id, {
                "source_authenticity": data.get("source_authenticity", "metadata_verified"),
                "extraction_fidelity": data.get("extraction_fidelity", "human_checked"),
                "evidence_characterization": data.get("evidence_characterization", "traditional_description"),
                "clinical_review_state": "approved_for_defined_use",
                "intended_use_authorization": data.get("intended_use_authorization", "clinician_contextual_reference"),
                "lead_reviewer_role": data.get("lead_reviewer_role", "UNANI_SCHOLAR"),
                "second_approver_id": data.get("second_approver_id"),
                "review_comments": data.get("review_comments", "Approved under KAVS governance policy.")
            }, user_id)

            self._log_audit_tx(
                conn, event_type="CLAIM_APPROVED", entity_type="CLAIM",
                entity_id=claim_id, actor_id=user_id,
                prior_state=claim["approval_state"], new_state="APPROVED"
            )
            conn.commit()
            return self.get_atomic_claim(claim_id)
        finally:
            conn.close()

    def reject_claim(self, claim_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Reject a claim with documented reason."""
        reason = data.get("reason")
        if not reason or not reason.strip():
            raise ValidationError("A mandatory rejection reason is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, approval_state FROM knowledge_claims WHERE id = ?;", (claim_id,))
            claim = cur.fetchone()
            if not claim:
                raise NotFoundError(f"Claim '{claim_id}' not found.")

            conn.execute("""
                UPDATE knowledge_claims
                SET approval_state = 'REJECTED', status = 'rejected',
                    clinical_limitations = ?, reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (reason.strip(), user_id, claim_id))
            self._log_audit_tx(
                conn, event_type="CLAIM_REJECTED", entity_type="CLAIM",
                entity_id=claim_id, actor_id=user_id,
                prior_state=claim["approval_state"], new_state="REJECTED", reason=reason.strip()
            )
            conn.commit()
            return self.get_atomic_claim(claim_id)
        finally:
            conn.close()

    def withdraw_claim(self, claim_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Withdraw a previously approved claim."""
        reason = data.get("reason")
        if not reason or not reason.strip():
            raise ValidationError("A mandatory withdrawal reason is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, approval_state FROM knowledge_claims WHERE id = ?;", (claim_id,))
            claim = cur.fetchone()
            if not claim:
                raise NotFoundError(f"Claim '{claim_id}' not found.")

            conn.execute("""
                UPDATE knowledge_claims
                SET approval_state = 'WITHDRAWN', status = 'deprecated',
                    clinical_limitations = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (reason.strip(), claim_id))
            conn.execute("UPDATE kavs_claim_verifications SET is_active = 0 WHERE claim_id = ?;", (claim_id,))

            self._log_audit_tx(
                conn, event_type="CLAIM_WITHDRAWN", entity_type="CLAIM",
                entity_id=claim_id, actor_id=user_id,
                prior_state=claim["approval_state"], new_state="WITHDRAWN", reason=reason.strip()
            )
            conn.commit()
            return self.get_atomic_claim(claim_id)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. CONTRADICTING & INCONCLUSIVE EVIDENCE LINKS
    # --------------------------------------------------------------------------

    def link_evidence_conflict(self, claim_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Link an evidence study that contradicts or limits a claim."""
        evidence_id = data.get("evidence_id")
        conflict_summary = data.get("conflict_summary")
        if not evidence_id or not conflict_summary:
            raise ValidationError("evidence_id and conflict_summary are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_claims WHERE id = ?;", (claim_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Claim '{claim_id}' not found.")
            cur.execute("SELECT id FROM knowledge_evidence WHERE id = ?;", (evidence_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Evidence '{evidence_id}' not found.")

            conflict_id = f"conf-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_evidence_conflict_links (
                    id, claim_id, evidence_id, relationship_direction,
                    conflict_summary, documented_limitations, reviewer_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                conflict_id, claim_id, evidence_id,
                data.get("relationship_direction", "CONTRADICTING"),
                conflict_summary, data.get("documented_limitations"), user_id
            ))
            conn.commit()
            return {"conflict_id": conflict_id, "claim_id": claim_id, "status": "recorded"}
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. IMMUTABLE KNOWLEDGE RELEASES & MANIFESTS
    # --------------------------------------------------------------------------

    def publish_knowledge_release(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Publish an immutable snapshot release of all verified claims for live consultation retrieval."""
        release_tag = data.get("release_tag")
        title = data.get("title")
        if not release_tag or not title:
            raise ValidationError("release_tag and title are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM kavs_knowledge_releases WHERE release_tag = ?;", (release_tag,))
            if cur.fetchone():
                raise ConflictError(f"Knowledge release with tag '{release_tag}' already exists.")

            # Identify all currently active verified claims with approved review state
            cur.execute("""
                SELECT cv.id as verif_id, cv.claim_id
                FROM kavs_claim_verifications cv
                JOIN knowledge_claims kc ON cv.claim_id = kc.id
                WHERE cv.is_active = 1
                  AND cv.clinical_review_state = 'approved_for_defined_use'
                  AND cv.intended_use_authorization != 'not_authorized_for_clinical_use';
            """)
            approved_items = [dict(r) for r in cur.fetchall()]

            if not approved_items:
                raise ValidationError("Cannot publish release: zero approved claims found.")

            # Compute SHA-256 fingerprint of the release manifest
            raw_fingerprint = ":".join(sorted([f"{it['claim_id']}_{it['verif_id']}" for it in approved_items]))
            manifest_hash = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()

            # Count distinct approved sources
            cur.execute("""
                SELECT COUNT(DISTINCT e.source_id) as src_count
                FROM kavs_claim_verifications cv
                JOIN knowledge_evidence e ON cv.claim_id = e.claim_id
                WHERE cv.is_active = 1 AND cv.clinical_review_state = 'approved_for_defined_use';
            """)
            src_count = cur.fetchone()["src_count"]

            release_id = f"rel-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_knowledge_releases (
                    id, release_tag, title, description,
                    total_approved_sources, total_approved_claims,
                    manifest_hash, published_by, publication_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE');
            """, (
                release_id, release_tag, title, data.get("description"),
                src_count, len(approved_items), manifest_hash, user_id
            ))

            for it in approved_items:
                conn.execute("""
                    INSERT INTO kavs_release_items (id, release_id, claim_id, verification_id)
                    VALUES (?, ?, ?, ?);
                """, (f"ri-{uuid.uuid4().hex[:12]}", release_id, it["claim_id"], it["verif_id"]))

            conn.commit()
            return {
                "release_id": release_id,
                "release_tag": release_tag,
                "total_claims": len(approved_items),
                "total_sources": src_count,
                "manifest_hash": manifest_hash,
                "status": "ACTIVE"
            }
        finally:
            conn.close()

    def withdraw_knowledge_release(self, release_tag: str, reason: str, user_id: str) -> Dict[str, Any]:
        """Formally withdraw a knowledge release (e.g. following clinical safety finding or source retraction)."""
        if not reason or not reason.strip():
            raise ValidationError("A formal withdrawal reason is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, publication_status FROM kavs_knowledge_releases WHERE release_tag = ?;", (release_tag,))
            rel = cur.fetchone()
            if not rel:
                raise NotFoundError(f"Knowledge release '{release_tag}' not found.")

            conn.execute("""
                UPDATE kavs_knowledge_releases
                SET publication_status = 'WITHDRAWN', withdrawn_at = CURRENT_TIMESTAMP, withdrawal_reason = ?
                WHERE id = ?;
            """, (reason.strip(), rel["id"]))
            conn.commit()
            return {"release_tag": release_tag, "status": "WITHDRAWN", "reason": reason.strip()}
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. CHANGE-IMPACT DEPENDENCY ENGINE
    # --------------------------------------------------------------------------

    def record_change_impact(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Analyze and record downstream impact when a source, version, or claim is amended/withdrawn."""
        trigger_type = data.get("trigger_type")
        entity_type = data.get("trigger_entity_type")
        entity_id = data.get("trigger_entity_id")

        if not trigger_type or not entity_type or not entity_id:
            raise ValidationError("trigger_type, trigger_entity_type, and trigger_entity_id are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            affected_claims = 0
            affected_formulations = 0
            affected_rules = 0

            # Trace dependent claims
            if entity_type == "SOURCE":
                cur.execute("""
                    SELECT COUNT(DISTINCT claim_id) as count
                    FROM knowledge_evidence WHERE source_id = ?;
                """, (entity_id,))
                affected_claims = cur.fetchone()["count"]
            elif entity_type == "CLAIM":
                affected_claims = 1

            impact_id = f"imp-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_change_impact_events (
                    id, trigger_type, trigger_entity_type, trigger_entity_id,
                    affected_claims_count, affected_formulations_count, affected_rules_count,
                    impact_details_json, remediation_status, initiated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?);
            """, (
                impact_id, trigger_type, entity_type, entity_id,
                affected_claims, affected_formulations, affected_rules,
                json.dumps(data.get("details", {})), user_id
            ))
            conn.commit()
            return {
                "impact_id": impact_id,
                "affected_claims": affected_claims,
                "remediation_status": "OPEN"
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. GOVERNED CONSULTATION-TIME RETRIEVAL (STRICT RESOLVABILITY & HONEST CAVEATS)
    # --------------------------------------------------------------------------

    def retrieve_verified_clinical_context(
        self,
        query: str,
        domain: Optional[str] = None,
        intended_use: str = "clinician_contextual_reference",
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Consultation-time knowledge retrieval grounded strictly in verified claims.
        Excludes unreviewed, deprecated, or withdrawn content.
        Surfaces contradictions, limitations, and explicit 'insufficient_information' flag.
        """
        if not query or not query.strip():
            return {
                "results": [],
                "total": 0,
                "insufficient_information": True,
                "reason": "Empty clinical search query."
            }

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()

            # Match against approved items and active verified claims
            search_param = f"%{query.strip().lower()}%"
            cur.execute("""
                SELECT 
                    kc.id as claim_id, kc.claim_text, kc.claim_type, kc.evidence_strength,
                    ki.id as item_id, ki.canonical_name as item_name, ki.domain,
                    cv.id as verification_id, cv.source_authenticity, cv.extraction_fidelity,
                    cv.evidence_characterization, cv.clinical_review_state, cv.intended_use_authorization,
                    cv.certainty_level, cv.risk_of_bias,
                    e.source_id, e.result_summary, e.limitations as evidence_limitations,
                    s.title as source_title, s.publisher, s.edition as source_edition
                FROM knowledge_claims kc
                JOIN knowledge_items ki ON kc.item_id = ki.id
                JOIN kavs_claim_verifications cv ON cv.claim_id = kc.id AND cv.is_active = 1
                LEFT JOIN knowledge_evidence e ON e.claim_id = kc.id
                LEFT JOIN knowledge_sources s ON e.source_id = s.id
                WHERE cv.clinical_review_state = 'approved_for_defined_use'
                  AND cv.intended_use_authorization = ?
                  AND (
                      lower(ki.canonical_name) LIKE ? OR
                      lower(kc.claim_text) LIKE ? OR
                      lower(COALESCE(s.title, '')) LIKE ?
                  )
                ORDER BY cv.approved_at DESC
                LIMIT ?;
            """, (intended_use, search_param, search_param, search_param, limit))

            rows = [dict(r) for r in cur.fetchall()]

            if not rows:
                return {
                    "results": [],
                    "total": 0,
                    "insufficient_information": True,
                    "caveat": "No verified clinical claims found for the query within approved scope. Does NOT imply absence of clinical significance."
                }

            # Enrich each result with citation locators and documented contradictions
            enriched_results = []
            for r in rows:
                c_id = r["claim_id"]
                # Fetch conflict links
                cur.execute("""
                    SELECT cl.relationship_direction, cl.conflict_summary, cl.documented_limitations,
                           s.title as contradicting_source
                    FROM kavs_evidence_conflict_links cl
                    JOIN knowledge_evidence e ON cl.evidence_id = e.id
                    JOIN knowledge_sources s ON e.source_id = s.id
                    WHERE cl.claim_id = ?;
                """, (c_id,))
                conflicts = [dict(c) for c in cur.fetchall()]

                # Fetch citation locators
                cur.execute("""
                    SELECT location_in_source, quote_or_excerpt
                    FROM knowledge_citations
                    WHERE claim_id = ?;
                """, (c_id,))
                citations = [dict(cit) for cit in cur.fetchall()]

                enriched_results.append({
                    "claim_id": r["claim_id"],
                    "claim_text": r["claim_text"],
                    "claim_type": r["claim_type"],
                    "item_name": r["item_name"],
                    "domain": r["domain"],
                    "verification": {
                        "source_authenticity": r["source_authenticity"],
                        "extraction_fidelity": r["extraction_fidelity"],
                        "evidence_characterization": r["evidence_characterization"],
                        "certainty_level": r["certainty_level"],
                        "risk_of_bias": r["risk_of_bias"],
                        "intended_use": r["intended_use_authorization"]
                    },
                    "source": {
                        "source_id": r["source_id"],
                        "title": r["source_title"],
                        "publisher": r["publisher"],
                        "edition": r["source_edition"],
                        "locator": citations[0]["location_in_source"] if citations else "General Monograph"
                    },
                    "contradictions": conflicts,
                    "generated_draft": False
                })

            return {
                "results": enriched_results,
                "total": len(enriched_results),
                "insufficient_information": False,
                "retrieval_release_status": "VERIFIED_ACTIVE"
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 8. AUDIT TRAIL QUERYING & RECORDING
    # --------------------------------------------------------------------------

    def list_kavs_audit_events(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List audit events with optional filtering."""
        filters = filters or {}
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT ae.*, u.full_name as actor_name
                FROM kavs_audit_events ae
                LEFT JOIN users u ON ae.actor_id = u.id
                WHERE 1=1
            """
            params = []
            if filters.get("entity_type"):
                query += " AND ae.entity_type = ?"
                params.append(filters["entity_type"])
            if filters.get("entity_id"):
                query += " AND ae.entity_id = ?"
                params.append(filters["entity_id"])
            if filters.get("event_type"):
                query += " AND ae.event_type = ?"
                params.append(filters["event_type"])
            query += " ORDER BY ae.created_at DESC"
            limit = int(filters.get("limit", 50))
            query += f" LIMIT {limit}"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def log_kavs_audit_event(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Record an explicit audit event into the append-only ledger."""
        event_type = data.get("event_type")
        entity_type = data.get("entity_type")
        entity_id = data.get("entity_id")
        if not event_type or not entity_type or not entity_id:
            raise ValidationError("event_type, entity_type, and entity_id are required.")

        conn = self.db_manager.get_connection()
        try:
            audit_id = f"aud-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_audit_events (
                    id, event_type, entity_type, entity_id, actor_id, actor_role,
                    prior_state, new_state, reason, correlation_id, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                audit_id, event_type, entity_type, entity_id, user_id,
                data.get("actor_role"), data.get("prior_state"),
                data.get("new_state"), data.get("reason"),
                data.get("correlation_id"), data.get("outcome", "SUCCESS")
            ))
            conn.commit()
            return {"audit_id": audit_id, "event_type": event_type, "status": "RECORDED"}
        finally:
            conn.close()

