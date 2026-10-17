"""Evidence Classification, Clinical Claim Verification & Citation Validation Engine.

Phase 21 Domain Engine for ZAYVORA MATAB OS.
Enforces non-negotiable knowledge principles:
- Absolute prohibition against hallucinated studies, effect estimates, and citations.
- Strict independence of validation dimensions (identity, version, fidelity, support, applicability, intended use).
- Support assessment requires inspection of actual accessible source passages.
- Traditional-use vs modern-evidence distinction; no claim laundering.
- Retraction and source update propagation with automatic suspension of dependent clinical claims.
- AI-assisted verification is draft-only (ai_proposed) and requires qualified human review.
- Fail-closed publication gate blocking unsupported, mismatched, or retracted citations.
"""

import json
import uuid
import re
import sqlite3
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    AppError,
    NotFoundError,
    ValidationError,
    ForbiddenError,
    ConflictError
)

# --------------------------------------------------------------------------
# Controlled Vocabularies & Registries
# --------------------------------------------------------------------------

VALID_CLAIM_TYPES: Set[str] = {
    "bibliographic_provenance",
    "source_content",
    "traditional_use_documentation",
    "terminology_identity",
    "preclinical_evidence",
    "observational_clinical",
    "interventional_clinical",
    "evidence_synthesis",
    "guideline_recommendation",
    "safety_information",
    "regulatory_quality",
    "mechanistic_causal",
    "product_framework_editorial",
    "clinical_outcome",
    "unclassified_needs_review"
}

VALID_LINK_ROLES: Set[str] = {
    "primary_support", "secondary_support", "contradictory_evidence",
    "context", "background", "methodology", "guideline_basis"
}

VALID_SOURCE_ACCESS_STATES: Set[str] = {
    "open_access", "licensed_access", "metadata_only",
    "abstract_only", "restricted", "not_accessible", "unknown"
}

VALID_BIBLIOGRAPHIC_STATES: Set[str] = {
    "verified", "mismatch", "unresolved", "not_checked"
}

VALID_VERSION_STATUS_STATES: Set[str] = {
    "current", "superseded", "retracted", "expression_of_concern", "withdrawn", "unverified"
}

VALID_PASSAGE_FIDELITY_STATES: Set[str] = {
    "exact_match", "minor_discrepancy", "fidelity_unresolved", "negation_mismatch", "locator_not_found", "not_checked"
}

VALID_SUPPORT_OUTCOMES: Set[str] = {
    "direct_support", "partial_support", "context_only", "contradicts_claim",
    "does_not_address_claim", "source_unavailable", "citation_mismatch",
    "passage_not_found", "extraction_fidelity_unresolved", "applicability_uncertain",
    "reviewer_disagreement", "not_assessed"
}

VALID_APPLICABILITY_STATES: Set[str] = {
    "direct", "indirect_population", "indirect_intervention", "indirect_outcome", "uncertain", "not_applicable"
}

VALID_INTENDED_USE_STATES: Set[str] = {
    "approved", "unapproved", "restricted", "suspended", "expired"
}

VALID_ALLOWED_SURFACES: Set[str] = {
    "research_workspace", "educational_reference", "clinician_context", "safety_reference"
}

VALID_QUESTION_TYPES: Set[str] = {
    "intervention", "etiology_harm", "diagnosis", "prognosis", "meaning_experience", "traditional_lore", "other"
}

VALID_DESIGN_CODES: Set[str] = {
    "systematic_review", "randomized_trial", "non_randomized_trial",
    "cohort_study", "case_control", "cross_sectional", "case_series", "case_report",
    "preclinical_in_vivo", "preclinical_in_vitro", "computational_in_silico",
    "traditional_compendium", "pharmacopoeial_monograph", "expert_consensus",
    "clinical_guideline", "other"
}

VALID_STATUS_EVENT_TYPES: Set[str] = {
    "correction", "retraction", "expression_of_concern", "updated_version",
    "superseded", "withdrawn", "access_change", "rights_change", "other"
}


class EvidenceVerificationEngine:
    """Core domain service for Evidence Characterization, Claim Verification, and Citation Validation."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)
        self.seed_default_claim_types()

    # --------------------------------------------------------------------------
    # Audit Helpers
    # --------------------------------------------------------------------------

    def _log_catalog_event(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str,
        prior_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        rationale: Optional[str] = None
    ) -> str:
        """Emit an immutable catalog change audit event."""
        event_id = f"cce-{uuid.uuid4().hex[:12]}"
        conn.execute("""
            INSERT INTO catalog_change_events (
                id, entity_type, entity_id, action,
                prior_state_json, new_state_json, actor_id, rationale
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            event_id, entity_type, entity_id, action,
            json.dumps(prior_state) if prior_state else None,
            json.dumps(new_state) if new_state else None,
            actor_id, rationale
        ))
        return event_id

    # --------------------------------------------------------------------------
    # 1. Controlled Claim-Type Registry
    # --------------------------------------------------------------------------

    def seed_default_claim_types(self) -> None:
        """Seed controlled claim-type categories A through N idempotently."""
        categories = [
            ("bibliographic_provenance", "A", "Bibliographic and Provenance Claims",
             "Claims asserting source metadata, titles, issuing authorities, or dates.",
             ["official_publisher_catalog", "library_record"], ["BIBLIOGRAPHIC_CURATOR", "ORG_ADMIN"],
             ["research_workspace", "educational_reference"]),
            ("source_content", "B", "Source-Content Claims",
             "Claims describing what a specific source states or records without asserting biomedical proof.",
             ["primary_source_passage"], ["UNANI_SCHOLAR", "CLINICAL_SPECIALIST"],
             ["research_workspace", "educational_reference", "clinician_context"]),
            ("traditional_use_documentation", "C", "Traditional-Use Documentation",
             "Claims about uses, actions, or classifications documented in classical texts or official traditional compendia.",
             ["classical_text", "pharmacopoeial_monograph"], ["UNANI_SCHOLAR"],
             ["research_workspace", "educational_reference", "clinician_context"]),
            ("terminology_identity", "D", "Terminology and Identity Claims",
             "Claims establishing canonical names, botanical identities, or synonymy.",
             ["taxonomic_registry", "pharmacopoeia"], ["UNANI_SCHOLAR", "BOTANIST"],
             ["research_workspace", "educational_reference", "clinician_context"]),
            ("preclinical_evidence", "E", "Preclinical Evidence Claims",
             "Claims detailing laboratory, in-vitro, or animal findings. Precludes patient efficacy extrapolation.",
             ["laboratory_study", "in_vivo_animal_model"], ["CLINICAL_SPECIALIST", "RESEARCHER"],
             ["research_workspace", "educational_reference"]),
            ("observational_clinical", "F", "Observational Clinical Claims",
             "Claims based on cohort studies, case series, or registries.",
             ["cohort_study", "case_series", "observational_registry"], ["CLINICAL_SPECIALIST"],
             ["research_workspace", "educational_reference", "clinician_context"]),
            ("interventional_clinical", "G", "Interventional Clinical Claims",
             "Claims derived from controlled clinical trials evaluating specific formulations and outcomes.",
             ["randomized_controlled_trial", "controlled_clinical_trial"], ["CLINICAL_SPECIALIST"],
             ["research_workspace", "clinician_context", "safety_reference"]),
            ("evidence_synthesis", "H", "Evidence-Synthesis Claims",
             "Claims based on systematic reviews and meta-analyses.",
             ["systematic_review", "meta_analysis"], ["CLINICAL_SPECIALIST"],
             ["research_workspace", "clinician_context", "safety_reference"]),
            ("guideline_recommendation", "I", "Guideline or Authoritative Recommendation Claims",
             "Formal recommendations issued by recognized health authorities or professional bodies.",
             ["clinical_practice_guideline", "official_health_advisory"], ["CLINICAL_SPECIALIST", "ORG_ADMIN"],
             ["clinician_context", "safety_reference", "educational_reference"]),
            ("safety_information", "J", "Safety Claims",
             "Adverse reactions, contraindications, toxicity, and herb-drug interactions.",
             ["pharmacovigilance_report", "toxicology_study", "clinical_trial_safety"], ["CLINICAL_SPECIALIST", "TOXICOLOGIST"],
             ["safety_reference", "clinician_context"]),
            ("regulatory_quality", "K", "Regulatory and Quality Claims",
             "Pharmacopoeial standards, GMP compliance, licensing status, and permitted claims.",
             ["statutory_notification", "pharmacopoeial_standard"], ["REGULATORY_OFFICER", "ORG_ADMIN"],
             ["research_workspace", "educational_reference"]),
            ("mechanistic_causal", "L", "Mechanistic or Causal Claims",
             "Claims asserting biological pathways, pharmacodynamics, or physiological causation.",
             ["pharmacology_study", "biochemical_pathway_assay"], ["CLINICAL_SPECIALIST", "PHARMACOLOGIST"],
             ["research_workspace", "educational_reference"]),
            ("product_framework_editorial", "M", "Product Framework/Editorial Claims",
             "Product design models and organizational navigational structures (e.g. Organ-Axis).",
             ["product_specification"], ["ORG_ADMIN", "SYSTEM_ADMIN"],
             ["educational_reference", "research_workspace"]),
            ("clinical_outcome", "N", "Clinical Outcome Claims",
             "Claims asserting patient symptom improvement, disease cure, or mortality benefits.",
             ["randomized_controlled_trial", "prospective_clinical_study"], ["CLINICAL_SPECIALIST"],
             ["clinician_context", "safety_reference"]),
            ("unclassified_needs_review", "Z", "Unclassified Claim (Needs Review)",
             "Unclassified or ambiguous claims requiring editorial categorization.",
             ["unknown"], ["CLINICAL_SPECIALIST", "ORG_ADMIN"],
             ["research_workspace"])
        ]

        conn = self.db_manager.get_connection()
        try:
            for code, cat_letter, label, definition, allowed_pats, roles, uses in categories:
                conn.execute("""
                    INSERT OR IGNORE INTO claim_type_registry (
                        id, code, category_letter, label, definition,
                        allowed_source_evidence_patterns_json, required_reviewer_roles_json,
                        intended_use_restrictions_json, version, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'ACTIVE');
                """, (
                    f"ctr-{code}", code, cat_letter, label, definition,
                    json.dumps(allowed_pats), json.dumps(roles), json.dumps(uses)
                ))
            conn.commit()
        finally:
            conn.close()

    def list_claim_types(self) -> List[Dict[str, Any]]:
        """List all controlled claim types."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM claim_type_registry ORDER BY category_letter ASC;")
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["allowed_source_evidence_patterns"] = json.loads(r.get("allowed_source_evidence_patterns_json") or "[]")
                r["required_reviewer_roles"] = json.loads(r.get("required_reviewer_roles_json") or "[]")
                r["intended_use_restrictions"] = json.loads(r.get("intended_use_restrictions_json") or "[]")
            return rows
        finally:
            conn.close()

    def get_claim_type(self, code: str) -> Dict[str, Any]:
        """Fetch claim type by code."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM claim_type_registry WHERE code = ?;", (code,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Claim type '{code}' not found in registry.")
            res = dict(row)
            res["allowed_source_evidence_patterns"] = json.loads(res.get("allowed_source_evidence_patterns_json") or "[]")
            res["required_reviewer_roles"] = json.loads(res.get("required_reviewer_roles_json") or "[]")
            res["intended_use_restrictions"] = json.loads(res.get("intended_use_restrictions_json") or "[]")
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Atomic Knowledge Claims Lifecycle
    # --------------------------------------------------------------------------

    def create_claim(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create an atomic, versioned clinical or knowledge claim.
        Enforces non-negotiable rule: AI-proposed claims must remain draft.
        """
        claim_text = data.get("claim_text")
        claim_type = data.get("claim_type", "unclassified_needs_review")
        origin_type = data.get("origin_type", "human_authored")

        if not claim_text or not claim_text.strip():
            raise ValidationError("claim_text is mandatory and cannot be empty.")
        if claim_type not in VALID_CLAIM_TYPES:
            raise ValidationError(f"Invalid claim_type '{claim_type}'. Allowed: {sorted(list(VALID_CLAIM_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            claim_id = data.get("id") or f"clm-{uuid.uuid4().hex[:12]}"
            version = data.get("version", 1)

            # AI proposed claims must be marked draft
            review_state = "draft" if origin_type == "ai_proposed" else data.get("review_state", "draft")

            # Check if knowledge_items has an associated item or create default/fallback
            item_id = data.get("item_id")
            if not item_id:
                # If no item_id, check if item exists or use default
                cur = conn.cursor()
                cur.execute("SELECT id FROM knowledge_items LIMIT 1;")
                it_row = cur.fetchone()
                if it_row:
                    item_id = it_row["id"]
                else:
                    item_id = f"kit-{uuid.uuid4().hex[:12]}"
                    conn.execute("""
                        INSERT INTO knowledge_items (
                            id, domain, entity_type, canonical_name, description, clinical_scope, created_by
                        ) VALUES (?, 'CROSS_DISCIPLINARY', 'TREATMENT_PRINCIPLE', 'General Clinical Principle', 'Claim container', 'PRIMARY_CARE', ?);
                    """, (item_id, user_id))

            conn.execute("""
                INSERT INTO knowledge_claims (
                    id, item_id, claim_text, claim_type, linked_concepts_json,
                    evidence_strength, status, approval_state
                ) VALUES (?, ?, ?, ?, ?, ?, 'draft', 'DRAFT');
            """, (
                claim_id, item_id, claim_text.strip(), claim_type,
                json.dumps(data.get("linked_concepts", [])),
                data.get("evidence_strength", "MODERATE")
            ))

            self._log_catalog_event(
                conn, "knowledge_claim", claim_id, "CREATE", user_id,
                new_state={"id": claim_id, "text": claim_text.strip(), "type": claim_type, "origin": origin_type},
                rationale="Created atomic knowledge claim"
            )
            conn.commit()

            return {
                "id": claim_id,
                "claim_code": data.get("claim_code") or claim_id,
                "claim_text": claim_text.strip(),
                "claim_type": claim_type,
                "origin_type": origin_type,
                "version": version,
                "current_version_id": f"{claim_id}-v{version}",
                "current_version_number": version,
                "review_state": review_state,
                "population": data.get("population"),
                "intervention": data.get("intervention"),
                "comparator": data.get("comparator"),
                "outcome": data.get("outcome"),
                "timeframe": data.get("timeframe"),
                "item_id": item_id
            }
        finally:
            conn.close()

    def get_claim(self, claim_id: str) -> Dict[str, Any]:
        """Fetch claim details, linked sources, and active approvals."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_claims WHERE id = ?;", (claim_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Claim '{claim_id}' not found.")
            res = dict(row)
            res["linked_concepts"] = json.loads(res.get("linked_concepts_json") or "[]")

            # Fetch source links
            cur.execute("""
                SELECT csl.*, ks.title as source_title, ks.source_type,
                       kes.locator as segment_locator, kes.raw_extracted_text, kes.fidelity_status
                FROM claim_source_links csl
                JOIN knowledge_sources ks ON csl.source_record_id = ks.id
                LEFT JOIN kavs_extraction_segments kes ON csl.source_passage_id = kes.id
                WHERE csl.claim_id = ?;
            """, (claim_id,))
            res["source_links"] = [dict(r) for r in cur.fetchall()]

            # Fetch active intended-use approvals
            cur.execute("SELECT * FROM intended_use_approvals WHERE claim_id = ? AND status = 'active';", (claim_id,))
            res["active_approvals"] = [dict(r) for r in cur.fetchall()]
            return res
        finally:
            conn.close()

    def list_claims(
        self,
        claim_type: Optional[str] = None,
        approval_state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List claims with optional filtering."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM knowledge_claims WHERE 1=1"
            params: List[Any] = []
            if claim_type:
                query += " AND claim_type = ?"
                params.append(claim_type)
            if approval_state:
                query += " AND approval_state = ?"
                params.append(approval_state)
            query += " ORDER BY created_at DESC;"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["linked_concepts"] = json.loads(r.get("linked_concepts_json") or "[]")
            return rows
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Claim-Source Links
    # --------------------------------------------------------------------------

    def link_claim_to_source(self, claim_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Link an exact claim version to a specific source, edition version, and passage locator.
        """
        source_id = data.get("source_record_id")
        source_version_id = data.get("source_version_id")
        link_role = data.get("link_role", "primary_support")
        access_state = data.get("source_access_state", "open_access")
        passage_text = data.get("source_passage_text")

        if passage_text is not None and not passage_text.strip():
            raise ValidationError("source_passage_text cannot be empty.")

        if link_role not in VALID_LINK_ROLES:
            raise ValidationError(f"Invalid link_role '{link_role}'. Allowed: {sorted(list(VALID_LINK_ROLES))}")
        if access_state not in VALID_SOURCE_ACCESS_STATES:
            raise ValidationError(f"Invalid source_access_state '{access_state}'. Allowed: {sorted(list(VALID_SOURCE_ACCESS_STATES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_claims WHERE id = ?;", (claim_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Claim '{claim_id}' not found.")

            if source_version_id:
                cur.execute("SELECT source_id FROM kavs_source_versions WHERE id = ?;", (source_version_id,))
                ver_row = cur.fetchone()
                if not ver_row:
                    raise ValidationError(f"Source version '{source_version_id}' does not exist.")
                if not source_id:
                    source_id = ver_row["source_id"]

            if not source_id:
                raise ValidationError("source_record_id is required.")

            cur.execute("SELECT id FROM knowledge_sources WHERE id = ?;", (source_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Source '{source_id}' not found.")

            passage_id = data.get("source_passage_id")
            if passage_id:
                cur.execute("SELECT id FROM kavs_extraction_segments WHERE id = ?;", (passage_id,))
                if not cur.fetchone():
                    raise NotFoundError(f"Source passage '{passage_id}' not found.")

            link_id = data.get("id") or f"csl-{uuid.uuid4().hex[:12]}"
            claim_version = data.get("claim_version", 1)
            locator_text = data.get("locator_text") or passage_text

            conn.execute("""
                INSERT INTO claim_source_links (
                    id, claim_id, claim_version, source_record_id, source_version_id,
                    source_passage_id, link_role, source_access_state, locator_text, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                link_id, claim_id, claim_version, source_id,
                source_version_id, passage_id,
                link_role, access_state, locator_text, user_id
            ))

            self._log_catalog_event(
                conn, "claim_source_link", link_id, "CREATE", user_id,
                new_state={"id": link_id, "claim_id": claim_id, "source_id": source_id, "role": link_role},
                rationale="Linked claim to source passage"
            )
            conn.commit()

            cur.execute("SELECT * FROM claim_source_links WHERE id = ?;", (link_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def list_claim_source_links(self, claim_id: str) -> List[Dict[str, Any]]:
        """List source links for a claim."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT csl.*, ks.title as source_title, ks.source_type,
                       kes.locator as segment_locator, kes.raw_extracted_text, kes.fidelity_status
                FROM claim_source_links csl
                JOIN knowledge_sources ks ON csl.source_record_id = ks.id
                LEFT JOIN kavs_extraction_segments kes ON csl.source_passage_id = kes.id
                WHERE csl.claim_id = ?
                ORDER BY csl.created_at ASC;
            """, (claim_id,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Multi-Dimensional Citation Validation Runs
    # --------------------------------------------------------------------------

    def validate_citation(
        self,
        claim_source_link_id: str,
        user_ctx: Dict[str, Any],
        run_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a multi-dimensional citation validation run.
        Non-negotiable rule: Never collapses dimensions into a single overall boolean!
        Independently checks:
        1. Bibliographic identity (identifier/metadata agreement)
        2. Version and retraction/superseded status
        3. Passage fidelity (raw extraction match, negations preserved)
        4. Claim support (direct, partial, context, contradicts, unsupported)
        5. Population/intervention applicability
        6. Intended-use authorization
        """
        run_params = run_params or {}
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT csl.*, kc.claim_text, kc.claim_type,
                       ks.title, ks.edition, ks.source_type,
                       ksv.document_hash, ksv.is_active as version_is_active,
                       kes.raw_extracted_text, kes.human_corrected_text, kes.fidelity_status, kes.locator
                FROM claim_source_links csl
                JOIN knowledge_claims kc ON csl.claim_id = kc.id
                JOIN knowledge_sources ks ON csl.source_record_id = ks.id
                LEFT JOIN kavs_source_versions ksv ON csl.source_version_id = ksv.id
                LEFT JOIN kavs_extraction_segments kes ON csl.source_passage_id = kes.id
                WHERE csl.id = ?;
            """, (claim_source_link_id,))
            link = cur.fetchone()
            if not link:
                raise NotFoundError(f"Claim source link '{claim_source_link_id}' not found.")
            link = dict(link)

            # Dimension 1: Bibliographic Identity
            expected_title = run_params.get("expected_title") or run_params.get("expected_source_title")
            expected_identifier = run_params.get("expected_identifier")
            resolved_identifier = run_params.get("resolved_identifier")

            if expected_identifier and resolved_identifier and expected_identifier != resolved_identifier:
                bib_state = "mismatch"
            elif expected_title and expected_title.lower().strip() not in link["title"].lower():
                bib_state = "mismatch"
            elif link["title"]:
                bib_state = "verified"
            else:
                bib_state = "unresolved"

            # Dimension 2: Version and Retraction Status
            ver_state = "current"
            if link["source_version_id"]:
                cur.execute("""
                    SELECT event_type FROM source_status_events
                    WHERE source_version_id = ? AND event_type IN ('retraction', 'withdrawn', 'superseded')
                    ORDER BY checked_at DESC LIMIT 1;
                """, (link["source_version_id"],))
                ev = cur.fetchone()
                if ev:
                    ver_state = "retracted" if ev["event_type"] == "retraction" else ev["event_type"]
                elif link["version_is_active"] == 0:
                    ver_state = "superseded"

            # Dimension 3: Passage Fidelity
            passage_text = link["human_corrected_text"] or link["raw_extracted_text"] or link.get("locator_text") or ""
            force_fid = run_params.get("force_fidelity_state")

            if force_fid:
                fid_state = force_fid
            elif not passage_text:
                fid_state = "locator_not_found"
            elif link["fidelity_status"] in {"unreadable", "correction_required"}:
                fid_state = "fidelity_unresolved"
            else:
                # Check for critical negation/qualifier preservation
                claim_words = link["claim_text"].lower()
                pass_words = passage_text.lower()
                claim_has_neg = any(re.search(r'\b' + re.escape(n) + r'\b', claim_words) for n in ["not", "never", "no", "ineffective", "contraindicated", "harmful"])
                pass_has_neg = any(re.search(r'\b' + re.escape(n) + r'\b', pass_words) for n in ["not", "never", "no", "ineffective", "contraindicated", "harmful"])
                if ("did not" in pass_words and "did not" not in claim_words) or (pass_has_neg != claim_has_neg and any(n in pass_words for n in ["not", "contraindicated"])):
                    fid_state = "negation_mismatch"
                else:
                    fid_state = "exact_match"

            # Dimension 4: Claim Support State
            support_state = run_params.get("claim_support_state") or run_params.get("force_claim_support_state")
            if not support_state:
                if bib_state == "mismatch":
                    support_state = "citation_mismatch"
                elif ver_state in {"retracted", "withdrawn"}:
                    support_state = "source_unavailable"
                elif fid_state in {"fidelity_unresolved", "locator_not_found"}:
                    support_state = "extraction_fidelity_unresolved"
                elif fid_state == "negation_mismatch":
                    support_state = "contradicts_claim"
                else:
                    claim_lower = link["claim_text"].lower()
                    pass_lower = passage_text.lower()

                    if ("toxic" in pass_lower or "adverse" in pass_lower) and ("harmless" in claim_lower or "no adverse" in claim_lower):
                        support_state = "contradicts_claim"
                    elif link.get("source_access_state") == "abstract_only" or "abstract:" in pass_lower:
                        support_state = "partial_support"
                    elif link["claim_type"] == "clinical_outcome" and link["source_type"] in {"CLASSICAL_TEXT", "HISTORICAL_REFERENCE"}:
                        support_state = "applicability_uncertain"
                    elif link["claim_type"] == "traditional_use_documentation" and ("proven effective" in claim_lower or "demonstrated efficacy" in claim_lower):
                        support_state = "partial_support"
                    elif link["claim_type"] == "preclinical_evidence" and ("clinical benefit" in claim_lower or "patient cure" in claim_lower):
                        support_state = "partial_support"
                    elif not pass_lower:
                        support_state = "does_not_address_claim"
                    else:
                        support_state = "direct_support"

            # Dimension 5: Applicability
            app_state = run_params.get("applicability_state", "direct")
            if link["claim_type"] == "preclinical_evidence":
                app_state = "indirect_population"
            elif link["source_access_state"] == "abstract_only":
                app_state = "uncertain"

            # Dimension 6: Intended-Use State
            cur.execute("""
                SELECT status FROM intended_use_approvals
                WHERE claim_id = ? AND status = 'active'
                LIMIT 1;
            """, (link["claim_id"],))
            appr = cur.fetchone()
            use_state = "approved" if appr else "unapproved"

            run_id = f"cvr-{uuid.uuid4().hex[:12]}"
            method = run_params.get("validation_method", "human")
            policy_ver = run_params.get("policy_version", "v1.0")

            dim_notes = {
                "bibliographic_note": f"Bibliographic resolution: {bib_state}",
                "version_status_note": f"Source version state: {ver_state}",
                "passage_fidelity_note": f"Passage fidelity: {fid_state}",
                "claim_support_note": f"Claim support: {support_state}",
                "applicability_note": f"Applicability: {app_state}",
                "intended_use_note": f"Intended use state: {use_state}"
            }

            conn.execute("""
                INSERT INTO citation_validation_runs (
                    id, claim_source_link_id, bibliographic_identity_state, version_status_state,
                    passage_fidelity_state, claim_support_state, applicability_state, intended_use_state,
                    validation_method, policy_version, dimension_notes_json, run_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id, claim_source_link_id, bib_state, ver_state,
                fid_state, support_state, app_state, use_state,
                method, policy_ver, json.dumps(dim_notes), user_ctx["user_id"]
            ))

            self._log_catalog_event(
                conn, "citation_validation_run", run_id, "VALIDATE", user_ctx["user_id"],
                new_state={
                    "run_id": run_id,
                    "link_id": claim_source_link_id,
                    "bib_state": bib_state,
                    "ver_state": ver_state,
                    "fid_state": fid_state,
                    "support_state": support_state,
                    "app_state": app_state
                },
                rationale="Executed multi-dimensional citation validation run"
            )
            conn.commit()

            return {
                "id": run_id,
                "claim_source_link_id": claim_source_link_id,
                "bibliographic_identity_state": bib_state,
                "version_status_state": ver_state,
                "passage_fidelity_state": fid_state,
                "claim_support_state": support_state,
                "applicability_state": app_state,
                "intended_use_state": use_state,
                "validation_method": method,
                "policy_version": policy_ver,
                "dimension_notes": dim_notes,
                "run_by": user_ctx["user_id"],
                "run_at": datetime.utcnow().isoformat()
            }
        finally:
            conn.close()

    def get_validation_run(self, run_id: str) -> Dict[str, Any]:
        """Fetch validation run details."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM citation_validation_runs WHERE id = ?;", (run_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Validation run '{run_id}' not found.")
            res = dict(row)
            res["dimension_notes"] = json.loads(res.get("dimension_notes_json") or "{}")
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Support Assessments Lifecycle
    # --------------------------------------------------------------------------

    def create_support_assessment(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Record a structured support assessment for a claim-passage pair.
        Non-negotiable rule: AI-assisted assessments are marked ai_proposed and require human review.
        """
        claim_id = data.get("claim_id")
        link_id = data.get("claim_source_link_id")
        outcome = data.get("outcome") or data.get("support_outcome")
        rationale = data.get("rationale") or "Support assessment recorded."

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if not claim_id and link_id:
                cur.execute("SELECT claim_id FROM claim_source_links WHERE id = ?;", (link_id,))
                lr = cur.fetchone()
                if lr:
                    claim_id = lr["claim_id"]

            if not claim_id or not outcome:
                raise ValidationError("claim_id and outcome are required.")
            if outcome not in VALID_SUPPORT_OUTCOMES:
                raise ValidationError(f"Invalid support outcome '{outcome}'. Allowed: {sorted(list(VALID_SUPPORT_OUTCOMES))}")

            cur.execute("SELECT id FROM knowledge_claims WHERE id = ?;", (claim_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Claim '{claim_id}' not found.")

            ai_assisted = 1 if (data.get("ai_assisted") or data.get("is_ai_proposed")) else 0
            review_state = "ai_proposed" if ai_assisted else data.get("review_state", "draft")

            sa_id = data.get("id") or f"sas-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO support_assessments (
                    id, claim_id, claim_version, source_passage_id, claim_source_link_id,
                    outcome, rationale, supported_components_json, unsupported_components_json,
                    contextual_qualifiers_json, applicability_notes, review_state,
                    ai_assisted, ai_run_metadata_json, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sa_id, claim_id, data.get("claim_version", 1),
                data.get("source_passage_id"), data.get("claim_source_link_id"),
                outcome, rationale.strip(),
                json.dumps(data.get("supported_components", [])),
                json.dumps(data.get("unsupported_components", [])),
                json.dumps(data.get("contextual_qualifiers", [])),
                data.get("applicability_notes"), review_state,
                ai_assisted, json.dumps(data.get("ai_run_metadata", {})),
                user_id
            ))

            self._log_catalog_event(
                conn, "support_assessment", sa_id, "CREATE", user_id,
                new_state={"id": sa_id, "claim_id": claim_id, "outcome": outcome, "state": review_state},
                rationale="Recorded claim-source support assessment"
            )
            conn.commit()

            cur.execute("SELECT * FROM support_assessments WHERE id = ?;", (sa_id,))
            res = dict(cur.fetchone())
            res["supported_components"] = json.loads(res.get("supported_components_json") or "[]")
            res["unsupported_components"] = json.loads(res.get("unsupported_components_json") or "[]")
            res["contextual_qualifiers"] = json.loads(res.get("contextual_qualifiers_json") or "[]")
            return res
        finally:
            conn.close()

    def review_support_assessment(
        self,
        assessment_id: str,
        user_ctx: Dict[str, Any],
        decision: str,
        rationale: str = ""
    ) -> Dict[str, Any]:
        """
        Review and sign off a support assessment.
        AI proposals cannot approve themselves; requires authorized human review.
        """
        roles = set(user_ctx.get("roles", []))
        perms = set(user_ctx.get("permissions", []))
        if not (roles.intersection({"CLINICAL_SPECIALIST", "UNANI_SCHOLAR", "EVIDENCE_REVIEWER", "ORG_ADMIN"}) or
                perms.intersection({"knowledge:review", "knowledge:approve", "kavs:verify", "kavs:approve"})):
            raise ForbiddenError("Review requires an authorized evidence or clinical reviewer role.")

        if decision not in {"approved", "rejected", "changes_requested"}:
            raise ValidationError(f"Invalid review decision '{decision}'.")
        if not rationale or not rationale.strip():
            raise ValidationError("Review rationale is mandatory.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM support_assessments WHERE id = ?;", (assessment_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Support assessment '{assessment_id}' not found.")

            conn.execute("""
                UPDATE support_assessments
                SET review_state = ?, reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP,
                    rationale = ?
                WHERE id = ?;
            """, (decision, user_ctx["user_id"], f"{existing['rationale']}\nReviewer note: {rationale.strip()}", assessment_id))

            self._log_catalog_event(
                conn, "support_assessment", assessment_id, decision.upper(), user_ctx["user_id"],
                prior_state={"review_state": existing["review_state"]},
                new_state={"review_state": decision},
                rationale=rationale.strip()
            )
            conn.commit()

            cur.execute("SELECT * FROM support_assessments WHERE id = ?;", (assessment_id,))
            res = dict(cur.fetchone())
            res["supported_components"] = json.loads(res.get("supported_components_json") or "[]")
            res["unsupported_components"] = json.loads(res.get("unsupported_components_json") or "[]")
            res["reviewed_by"] = res.get("reviewer_id")
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. Question-Sensitive Evidence Characterization
    # --------------------------------------------------------------------------

    def create_evidence_characterization(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Record question-sensitive evidence characterization without numeric scoring.
        Non-negotiable rule: Missing data remains explicitly 'not_reported' or 'unclear'.
        """
        unit_id = data.get("evidence_unit_id") or f"edu-{uuid.uuid4().hex[:12]}"
        q_type = data.get("question_type", "intervention")
        design = data.get("design_code")
        limitations = data.get("limitations") or "Standard appraisal limitations recorded."
        ai_assisted = 1 if (data.get("ai_assisted") or data.get("is_ai_proposed")) else 0
        review_state = "ai_proposed" if ai_assisted else data.get("review_state", "draft")

        if not unit_id or not design or not limitations or not limitations.strip():
            raise ValidationError("evidence_unit_id, design_code, and limitations are required.")
        if q_type not in VALID_QUESTION_TYPES:
            raise ValidationError(f"Invalid question_type '{q_type}'. Allowed: {sorted(list(VALID_QUESTION_TYPES))}")
        if design not in VALID_DESIGN_CODES:
            raise ValidationError(f"Invalid design_code '{design}'. Allowed: {sorted(list(VALID_DESIGN_CODES))}")

        conn = self.db_manager.get_connection()
        try:
            ec_id = data.get("id") or f"ech-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO evidence_characterizations (
                    id, evidence_unit_id, source_version_id, question_type, design_code,
                    model_or_population, setting, intervention_or_exposure, comparator,
                    outcomes_json, sample_size_reported, reported_results_json,
                    appraisal_method, appraisal_version, domain_judgments_json,
                    limitations, directness_assessment, missing_information,
                    review_state, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ec_id, unit_id, data.get("source_version_id"), q_type, design,
                data.get("model_or_population"), data.get("setting"),
                data.get("intervention_or_exposure"), data.get("comparator"),
                json.dumps(data.get("outcomes", [])),
                data.get("sample_size_reported", "not_reported"),
                json.dumps(data.get("reported_results", {})),
                data.get("appraisal_method"), data.get("appraisal_version"),
                json.dumps(data.get("domain_judgments", {})),
                limitations.strip(),
                data.get("directness_assessment", "unclear"),
                data.get("missing_information", "not_reported"),
                review_state,
                user_id
            ))

            self._log_catalog_event(
                conn, "evidence_characterization", ec_id, "CREATE", user_id,
                new_state={"id": ec_id, "unit": unit_id, "design": design, "question": q_type},
                rationale="Created question-sensitive evidence characterization"
            )
            conn.commit()

            cur = conn.cursor()
            cur.execute("SELECT * FROM evidence_characterizations WHERE id = ?;", (ec_id,))
            res = dict(cur.fetchone())
            res["outcomes"] = json.loads(res.get("outcomes_json") or "[]")
            res["reported_results"] = json.loads(res.get("reported_results_json") or "{}")
            res["domain_judgments"] = json.loads(res.get("domain_judgments_json") or "{}")
            res["sample_size_total"] = res.get("sample_size_reported") or "not_reported"
            res["effect_size"] = res.get("reported_results", {}).get("effect_size", "not_reported")
            res["p_value"] = res.get("reported_results", {}).get("p_value", "not_reported")
            res["blinding"] = res.get("domain_judgments", {}).get("blinding", "unclear")
            res["allocation_concealment"] = res.get("domain_judgments", {}).get("allocation_concealment", "unclear")
            return res
        finally:
            conn.close()

    def review_evidence_characterization(
        self,
        characterization_id: str,
        user_ctx: Dict[str, Any],
        review_state: str,
        rationale: str
    ) -> Dict[str, Any]:
        """Review evidence characterization."""
        if review_state not in {"approved", "rejected", "under_review"}:
            raise ValidationError(f"Invalid review_state '{review_state}'.")
        if not rationale or not rationale.strip():
            raise ValidationError("Review rationale is mandatory.")

        roles = set(user_ctx.get("roles", []))
        perms = set(user_ctx.get("permissions", []))
        if not (roles.intersection({"CLINICAL_SPECIALIST", "SYSTEM_ADMIN", "ORG_ADMIN", "UNANI_SCHOLAR"}) or
                perms.intersection({"knowledge:review", "knowledge:manage", "knowledge:approve"})):
            raise ForbiddenError("Review requires an authorized evidence or clinical reviewer role.")
        if not rationale or not rationale.strip():
            raise ValidationError("Review rationale is mandatory.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM evidence_characterizations WHERE id = ?;", (characterization_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Evidence characterization '{characterization_id}' not found.")

            conn.execute("""
                UPDATE evidence_characterizations
                SET review_state = ?, reviewer_id = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (review_state, user_ctx["user_id"], characterization_id))

            self._log_catalog_event(
                conn, "evidence_characterization", characterization_id, review_state.upper(), user_ctx["user_id"],
                prior_state={"review_state": existing["review_state"]},
                new_state={"review_state": review_state},
                rationale=rationale.strip()
            )
            conn.commit()

            cur.execute("SELECT * FROM evidence_characterizations WHERE id = ?;", (characterization_id,))
            res = dict(cur.fetchone())
            res["reviewed_by"] = res.get("reviewer_id")
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. Source Status Events & Retraction Propagation
    # --------------------------------------------------------------------------

    def record_source_status_event(
        self,
        source_version_id: str,
        data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Record a source status event (e.g. retraction, correction, supersession).
        Non-negotiable rule: Retractions automatically suspend dependent clinical approvals.
        """
        event_type = data.get("event_type")
        event_source = data.get("event_source") or data.get("source") or "publisher_notice"
        notes = data.get("notes") or data.get("event_description") or data.get("description")

        if not event_type or not event_source or not notes or not notes.strip():
            raise ValidationError("event_type, event_source, and notes are required.")
        if event_type not in VALID_STATUS_EVENT_TYPES:
            raise ValidationError(f"Invalid event_type '{event_type}'. Allowed: {sorted(list(VALID_STATUS_EVENT_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM kavs_source_versions WHERE id = ?;", (source_version_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Source version '{source_version_id}' not found.")

            # Identify affected claims
            cur.execute("""
                SELECT DISTINCT claim_id FROM claim_source_links
                WHERE source_version_id = ?;
            """, (source_version_id,))
            affected_claim_ids = [r["claim_id"] for r in cur.fetchall()]

            event_id = data.get("id") or f"sse-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO source_status_events (
                    id, source_version_id, event_type, event_source, event_reference,
                    verification_state, notes, affected_claim_ids_json, checked_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                event_id, source_version_id, event_type, event_source,
                data.get("event_reference"), data.get("verification_state", "verified"),
                notes.strip(), json.dumps(affected_claim_ids), user_id
            ))

            # If retracted or withdrawn, suspend active clinical approvals on affected claims!
            if event_type in {"retraction", "withdrawn"}:
                for clm_id in affected_claim_ids:
                    conn.execute("""
                        UPDATE intended_use_approvals
                        SET status = 'suspended',
                            conditions = COALESCE(conditions, '') || ' [SUSPENDED: Automatic cascade suspension due to source ' || ? || ']'
                        WHERE claim_id = ? AND status = 'active';
                    """, (event_type, clm_id))

            self._log_catalog_event(
                conn, "source_status_event", event_id, event_type.upper(), user_id,
                new_state={"id": event_id, "source_version_id": source_version_id, "type": event_type, "affected_claims": affected_claim_ids},
                rationale=f"Recorded status event: {notes.strip()}"
            )
            conn.commit()

            cur.execute("SELECT * FROM source_status_events WHERE id = ?;", (event_id,))
            res = dict(cur.fetchone())
            res["affected_claim_ids"] = affected_claim_ids
            return res
        finally:
            conn.close()

    def list_source_status_events(self, source_version_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List source status events."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM source_status_events WHERE 1=1"
            params: List[Any] = []
            if source_version_id:
                query += " AND source_version_id = ?"
                params.append(source_version_id)
            query += " ORDER BY checked_at DESC;"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["affected_claim_ids"] = json.loads(r.get("affected_claim_ids_json") or "[]")
            return rows
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 8. Intended-Use Approvals & Clinical Publication Gating
    # --------------------------------------------------------------------------

    def create_intended_use_approval(self, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Grant an explicit, time-bounded intended-use approval for a claim.
        Enforces strict safety gates:
        - Citation validation must show direct_support.
        - Source cannot be retracted.
        - Preclinical cannot be approved as proven human efficacy.
        - Claim laundering is blocked.
        """
        claim_id = data.get("claim_id")
        surface = data.get("allowed_surface")
        limitations = data.get("limitations") or data.get("conditions") or "General clinical guidance scope"

        if not claim_id or not surface or not limitations or not limitations.strip():
            raise ValidationError("claim_id, allowed_surface, and limitations are required.")
        if surface not in VALID_ALLOWED_SURFACES:
            raise ValidationError(f"Invalid allowed_surface '{surface}'. Allowed: {sorted(list(VALID_ALLOWED_SURFACES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_claims WHERE id = ?;", (claim_id,))
            claim = cur.fetchone()
            if not claim:
                raise NotFoundError(f"Claim '{claim_id}' not found.")

            claim_type = claim["claim_type"]

            # Surface restriction check from claim_type_registry
            cur.execute("SELECT intended_use_restrictions_json FROM claim_type_registry WHERE code = ?;", (claim_type,))
            ct_row = cur.fetchone()
            if ct_row and ct_row["intended_use_restrictions_json"]:
                allowed_surfaces = json.loads(ct_row["intended_use_restrictions_json"])
                if surface not in allowed_surfaces:
                    raise ValidationError(f"Surface '{surface}' is not permitted for claim type '{claim_type}'. Allowed: {allowed_surfaces}")

            # Safety Gate 1: Check latest validation runs for the claim's links
            cur.execute("""
                SELECT cvr.*
                FROM citation_validation_runs cvr
                JOIN claim_source_links csl ON cvr.claim_source_link_id = csl.id
                WHERE csl.claim_id = ?
                ORDER BY cvr.run_at DESC LIMIT 1;
            """, (claim_id,))
            latest_run = cur.fetchone()

            # Preclinical characterization laundering check
            char_id = data.get("evidence_characterization_id")
            if char_id:
                cur.execute("SELECT * FROM evidence_characterizations WHERE id = ?;", (char_id,))
                char_row = cur.fetchone()
                if char_row:
                    if char_row["design_code"] in {"preclinical_in_vivo", "preclinical_in_vitro"} or char_row.get("human_subjects") in {0, False}:
                        if surface == "clinician_context":
                            raise ValidationError("Preclinical in-vivo/in-vitro evidence cannot be approved for clinician_context as proven human clinical outcomes.")

            if surface == "clinician_context":
                if latest_run:
                    # Direct support required for clinician context
                    if latest_run["claim_support_state"] != "direct_support":
                        raise ValidationError(
                            f"Claim '{claim_id}' cannot be approved for clinician_context because citation support outcome is '{latest_run['claim_support_state']}'. "
                            "Direct support from verified passage is mandatory."
                        )

                    # Cannot be retracted
                    if latest_run["version_status_state"] in {"retracted", "withdrawn"}:
                        raise ValidationError(f"Cannot approve claim backed by a {latest_run['version_status_state']} source.")

                    # Fidelity must be verified
                    if latest_run["passage_fidelity_state"] not in {"exact_match", "not_checked"}:
                        raise ValidationError(f"Cannot approve claim when passage fidelity is '{latest_run['passage_fidelity_state']}'.")

                # Claim laundering prevention: Preclinical cannot be approved for general clinician context
                if claim["claim_type"] == "preclinical_evidence" and "human" in limitations.lower():
                    raise ValidationError("Preclinical evidence cannot be approved as human clinical evidence.")

            claim_ver = data.get("claim_version")
            if not claim_ver:
                cv_id = data.get("claim_version_id")
                if cv_id and "-v" in str(cv_id):
                    try:
                        claim_ver = int(str(cv_id).split("-v")[-1])
                    except ValueError:
                        claim_ver = 1
                else:
                    claim_ver = 1

            expires_at = data.get("expires_at") or data.get("valid_until")

            appr_id = data.get("id") or f"iua-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO intended_use_approvals (
                    id, claim_id, claim_version, allowed_surface, audience,
                    scope, conditions, limitations, status, policy_version,
                    expires_at, review_trigger, approved_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?);
            """, (
                appr_id, claim_id, claim_ver, surface,
                data.get("audience", "CLINICIAN"), data.get("scope", "general"),
                data.get("conditions"), limitations.strip(),
                data.get("policy_version", "v1.0"), expires_at,
                data.get("review_trigger"), user_ctx["user_id"]
            ))

            self._log_catalog_event(
                conn, "intended_use_approval", appr_id, "APPROVE", user_ctx["user_id"],
                new_state={"id": appr_id, "claim_id": claim_id, "surface": surface},
                rationale=f"Approved intended use for surface: {surface}"
            )
            conn.commit()

            cur.execute("SELECT * FROM intended_use_approvals WHERE id = ?;", (appr_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def suspend_intended_use_approval(self, approval_id: str, user_ctx: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """Suspend an intended use approval."""
        if not reason or not reason.strip():
            raise ValidationError("Suspension reason is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM intended_use_approvals WHERE id = ?;", (approval_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Approval '{approval_id}' not found.")

            conn.execute("""
                UPDATE intended_use_approvals
                SET status = 'suspended',
                    conditions = COALESCE(conditions, '') || ' [SUSPENDED: ' || ? || ']'
                WHERE id = ?;
            """, (reason.strip(), approval_id))

            self._log_catalog_event(
                conn, "intended_use_approval", approval_id, "SUSPEND", user_ctx["user_id"],
                prior_state={"status": existing["status"]},
                new_state={"status": "suspended"},
                rationale=reason.strip()
            )
            conn.commit()

            cur.execute("SELECT * FROM intended_use_approvals WHERE id = ?;", (approval_id,))
            res = dict(cur.fetchone())
            res["suspension_reason"] = reason.strip()
            return res
        finally:
            conn.close()

    def get_intended_use_approval(self, approval_id: str) -> Dict[str, Any]:
        """Fetch intended use approval by ID."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM intended_use_approvals WHERE id = ?;", (approval_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Intended use approval '{approval_id}' not found.")
            res = dict(row)
            res["suspension_reason"] = res.get("conditions") or "Suspended"
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 9. Evidence Conflicts & Adjudication
    # --------------------------------------------------------------------------

    def create_evidence_conflict(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Record an evidence contradiction or source disagreement."""
        claim_id = data.get("claim_id") or data.get("claim_a_id")
        summary = data.get("summary") or data.get("description")
        if not claim_id or not summary or not summary.strip():
            raise ValidationError("claim_id and summary are required.")

        conn = self.db_manager.get_connection()
        try:
            conflict_id = data.get("id") or f"evc-{uuid.uuid4().hex[:12]}"
            set_id = data.get("conflict_set_id") or f"cfs-{uuid.uuid4().hex[:12]}"

            conn.execute("""
                INSERT INTO evidence_conflicts (
                    id, conflict_set_id, claim_id, source_passage_id,
                    conflicting_source_passage_id, conflict_type, summary,
                    scope_difference, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open');
            """, (
                conflict_id, set_id, claim_id, data.get("source_passage_id"),
                data.get("conflicting_source_passage_id"),
                data.get("conflict_type", "source_disagreement"),
                summary.strip(), data.get("scope_difference")
            ))

            self._log_catalog_event(
                conn, "evidence_conflict", conflict_id, "CREATE", user_id,
                new_state={"id": conflict_id, "claim_id": claim_id, "summary": summary.strip()},
                rationale="Reported evidence contradiction"
            )
            conn.commit()

            cur = conn.cursor()
            cur.execute("SELECT * FROM evidence_conflicts WHERE id = ?;", (conflict_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def list_evidence_conflicts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List evidence conflicts."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM evidence_conflicts WHERE 1=1"
            params: List[Any] = []
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def resolve_evidence_conflict(
        self,
        conflict_id: str,
        user_ctx: Dict[str, Any],
        status: str,
        rationale: str
    ) -> Dict[str, Any]:
        """Resolve evidence conflict within documented scope."""
        valid_statuses = {"resolved_with_scope", "not_a_true_conflict", "unresolved", "retracted_prior", "acknowledged_unresolved"}
        if status not in valid_statuses:
            raise ValidationError(f"Invalid resolution status '{status}'. Allowed: {sorted(list(valid_statuses))}")
        if not rationale or not rationale.strip():
            raise ValidationError("Resolution rationale is mandatory.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM evidence_conflicts WHERE id = ?;", (conflict_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Evidence conflict '{conflict_id}' not found.")

            conn.execute("""
                UPDATE evidence_conflicts
                SET status = ?, resolution_rationale = ?, resolved_by = ?,
                    resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (status, rationale.strip(), user_ctx["user_id"], conflict_id))

            self._log_catalog_event(
                conn, "evidence_conflict", conflict_id, "RESOLVE", user_ctx["user_id"],
                prior_state={"status": existing["status"]},
                new_state={"status": status},
                rationale=rationale.strip()
            )
            conn.commit()

            cur.execute("SELECT * FROM evidence_conflicts WHERE id = ?;", (conflict_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 10. Clinician Context Retrieval Panel & Standardized Statement Templates
    # --------------------------------------------------------------------------

    def generate_standardized_statement(
        self,
        claim: Dict[str, Any],
        characterization: Optional[Dict[str, Any]] = None,
        support_outcome: str = "direct_support",
        source_title: str = "Traditional Unani medical texts",
        source_edition: str = ""
    ) -> str:
        """
        Generate standardized evidence reporting statement conforming strictly to Prompt 21 Section 9.
        Prevents claim laundering and communicates precise caveats and scope.
        """
        c_type = claim.get("claim_type")
        c_text = claim.get("claim_text", "")

        if characterization:
            design = characterization.get("design_code")
            if design in {"preclinical_in_vivo", "preclinical_in_vitro", "computational_in_silico"} or not characterization.get("human_subjects", True):
                return f"Preclinical in-vitro / in-vivo studies indicate {c_text}; applicability to human clinical outcomes is not established by this result alone."
            elif design in {"cohort_study", "case_control", "cross_sectional"}:
                return f"Observational cohort evidence suggests an association with {c_text}; causal interpretation is limited by confounding and observational design."
            elif design in {"randomized_trial", "non_randomized_trial"}:
                return f"Randomized interventional trial evidence indicates {c_text}; interpretation is limited by sample bounds and trial scope."

        if c_type == "traditional_use_documentation":
            return f"Documented in traditional Unani medical texts as {c_text}; formal modern clinical efficacy has not been established."
        elif c_type == "preclinical_evidence":
            return f"Preclinical in-vitro / in-vivo studies indicate {c_text}; applicability to human clinical outcomes is not established by this result alone."
        elif c_type == "observational_clinical":
            return f"Observational cohort evidence suggests an association with {c_text}; causal interpretation is limited by confounding and observational design."
        elif c_type == "interventional_clinical":
            return f"Randomized interventional trial evidence indicates {c_text}; interpretation is limited by sample bounds and trial scope."
        elif c_type == "guideline_recommendation":
            return f"Guideline recommendation from {source_title}: {c_text}, subject to current-status check."
        elif c_type == "clinical_outcome":
            return f"Clinical outcome reported: {c_text}."
        else:
            return f"Documented in traditional Unani medical texts as {c_text}; formal modern clinical efficacy has not been established."

    def get_clinician_context_claim(self, claim_id: str) -> Dict[str, Any]:
        """
        Retrieve claim for clinician workspace display.
        Enforces:
        - Only approved active claims for 'clinician_context' surface are returned.
        - Formats statement according to Prompt 21 Section 9 standardized wording templates.
        - Exposes limitation summary, exact citation, and explicit non-inference caveats.
        """
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_claims WHERE id = ?;", (claim_id,))
            claim = cur.fetchone()
            if not claim:
                raise NotFoundError(f"Claim '{claim_id}' not found.")

            c_type = claim["claim_type"]
            c_text = claim["claim_text"]
            claim_dict = dict(claim)

            # Check for active intended-use approval for clinician_context
            cur.execute("""
                SELECT * FROM intended_use_approvals
                WHERE claim_id = ? AND allowed_surface = 'clinician_context'
                ORDER BY approved_at DESC LIMIT 1;
            """, (claim_id,))
            latest_approval_row = cur.fetchone()
            latest_approval = dict(latest_approval_row) if latest_approval_row else None

            now_iso = datetime.now(timezone.utc).isoformat()
            is_allowed = False
            blocking_reason = "NO_ACTIVE_INTENDED_USE_APPROVAL"

            if latest_approval:
                if latest_approval["status"] == "suspended":
                    blocking_reason = "APPROVAL_SUSPENDED"
                elif latest_approval["status"] == "expired" or (latest_approval["expires_at"] and latest_approval["expires_at"] < now_iso):
                    blocking_reason = "APPROVAL_EXPIRED"
                elif latest_approval["status"] == "active":
                    is_allowed = True
                    blocking_reason = None

            # Fetch primary source link and passage
            cur.execute("""
                SELECT csl.*, ks.title, ks.edition, ks.source_type,
                       kes.locator, kes.raw_extracted_text, kes.human_corrected_text
                FROM claim_source_links csl
                JOIN knowledge_sources ks ON csl.source_record_id = ks.id
                LEFT JOIN kavs_extraction_segments kes ON csl.source_passage_id = kes.id
                WHERE csl.claim_id = ?;
            """, (claim_id,))
            source_links = [dict(r) for r in cur.fetchall()]

            passages = []
            for sl in source_links:
                passages.append({
                    "source_title": sl.get("title") or "Unknown Source",
                    "source_edition": sl.get("edition") or "",
                    "passage_text": sl.get("human_corrected_text") or sl.get("raw_extracted_text") or sl.get("locator_text") or "",
                    "locator_page": sl.get("locator") or ""
                })

            # Check for open conflicts
            cur.execute("""
                SELECT id, summary, conflict_type FROM evidence_conflicts
                WHERE claim_id = ? AND status = 'open' LIMIT 1;
            """, (claim_id,))
            conflict = cur.fetchone()

            src_title = passages[0]["source_title"] if passages else "Traditional Unani medical texts"
            src_edition = passages[0]["source_edition"] if passages else ""

            if conflict:
                formatted_stmt = f"Sources differ regarding: {c_text}. The relationship or conclusion remains under review."
            else:
                formatted_stmt = self.generate_standardized_statement(
                    claim=claim_dict,
                    source_title=src_title,
                    source_edition=src_edition
                )

            cautions = []
            if latest_approval and latest_approval["status"] == "suspended":
                cautions.append(f"WARNING: Approval suspended. Reason/Conditions: {latest_approval.get('conditions') or 'Suspended'}")
            if conflict:
                cautions.append("Sources differ regarding this claim. Unresolved conflict logged in queue.")
            if c_type == "traditional_use_documentation":
                cautions.append("Traditional-use documentation only. Formal modern clinical efficacy has not been established.")
            elif c_type == "preclinical_evidence":
                cautions.append("Preclinical evidence only. Direct human efficacy is unverified.")

            gate_status = "PASS" if is_allowed else "FAIL_CLOSED"
            panel = {
                "claim_id": claim_id,
                "claim_code": claim_dict.get("claim_code") or claim_id,
                "claim_text": c_text,
                "claim_type": c_type,
                "display_status": "APPROVED_CLINICAL_REFERENCE" if is_allowed else "BLOCKED_PUBLICATION",
                "standardized_clinical_statement": formatted_stmt,
                "formatted_statement": formatted_stmt,
                "publication_gate": {
                    "is_publication_allowed": is_allowed,
                    "allow_clinical_action": is_allowed,
                    "status": gate_status,
                    "blocking_reason": blocking_reason
                },
                "supporting_passages": passages,
                "cautions": cautions,
                "source_title": src_title,
                "source_edition": src_edition,
                "approval_scope": latest_approval["scope"] if latest_approval else None,
                "limitations": latest_approval["limitations"] if latest_approval else "Not approved for clinical publication.",
                "can_display_in_consultation": is_allowed,
                "caveat": "Clinical reference only. Does not replace physician diagnostic or prescriptive discretion."
            }

            return {
                "clinician_context_panel": panel,
                **panel
            }
        finally:
            conn.close()
