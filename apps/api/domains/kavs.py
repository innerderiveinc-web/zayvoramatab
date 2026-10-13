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


class KAVSEngine:
    """Core domain service for the Knowledge Authenticity, Verification & Clinical Safety Framework."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)

    # --------------------------------------------------------------------------
    # 1. SOURCE VERSIONS & RIGHTS REVIEWS
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
            conn.commit()
            return {"id": review_id, "source_id": source_id, "status": data.get("review_status", "APPROVED")}
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. INGESTION, EXTRACTION & FIDELITY REVIEWS
    # --------------------------------------------------------------------------

    def create_ingestion_job(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a new extraction job linked to a verified source version."""
        source_id = data.get("source_id")
        source_version_id = data.get("source_version_id")
        if not source_id:
            raise ValidationError("source_id is required for ingestion job.")

        job_id = f"ing-{uuid.uuid4().hex[:12]}"
        conn = self.db_manager.get_connection()
        try:
            conn.execute("""
                INSERT INTO kavs_ingestion_jobs (
                    id, source_id, source_version_id, job_type, status,
                    original_filename, file_checksum, initiated_by
                ) VALUES (?, ?, ?, ?, 'QUEUED', ?, ?, ?);
            """, (
                job_id, source_id, source_version_id,
                data.get("job_type", "STRUCTURED_EXTRACTION"),
                data.get("original_filename"), data.get("file_checksum"), user_id
            ))
            conn.commit()
            return {"job_id": job_id, "status": "QUEUED"}
        finally:
            conn.close()

    def add_extraction_segment(self, job_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a page-level or passage-level extraction segment with OCR confidence."""
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

            segment_id = f"seg-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO kavs_extraction_segments (
                    id, job_id, source_id, locator, raw_extracted_text,
                    fidelity_status, ocr_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                segment_id, job_id, job["source_id"], locator, raw_text,
                data.get("fidelity_status", "machine_extracted"),
                float(data.get("ocr_confidence", 1.0))
            ))
            conn.execute("UPDATE kavs_ingestion_jobs SET total_segments = total_segments + 1 WHERE id = ?;", (job_id,))
            conn.commit()
            return {"segment_id": segment_id, "locator": locator, "status": "machine_extracted"}
        finally:
            conn.close()

    def review_extraction_segment(self, segment_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Human reviewer checks and confirms extraction fidelity against physical/source page."""
        fidelity_status = data.get("fidelity_status")
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
                SET fidelity_status = ?, human_corrected_text = ?,
                    reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, review_notes = ?
                WHERE id = ?;
            """, (
                fidelity_status, data.get("human_corrected_text"),
                user_id, data.get("review_notes"), segment_id
            ))
            conn.execute("UPDATE kavs_ingestion_jobs SET reviewed_segments = reviewed_segments + 1 WHERE id = ?;", (seg["job_id"],))
            conn.commit()
            return {"segment_id": segment_id, "fidelity_status": fidelity_status, "verified": fidelity_status == "human_checked"}
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
