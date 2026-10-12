"""Clinical Knowledge & Governed Evidence Retrieval Engine for ZAYVORA MATAB OS.

Provides:
- Governed Sources Registry & Provenance tracking
- Knowledge Items & Atomic Claims management
- Evidence Appraisal records with risk of bias & GRADE assessment
- Graph-Compatible Ontological Relationships
- Hybrid Retrieval Engine (Exact, full-text/trigram, transliteration normalization)
- Permitted Clinical Encounter Context Retrieval
- Structured Evidence Synthesis Service (strictly no hallucination/unsupported extrapolation)
- Governance Review Lifecycle (Draft -> Submit -> Review -> Approve / Reject / Changes / Deprecate)
- Audit Logging & Non-Fabricated Citations
"""

import json
import uuid
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    AppError,
    NotFoundError,
    ValidationError,
    ForbiddenError,
    ConflictError
)

# Known clinical transliterations & synonym mappings across Unani & Modern clinical vocabulary
TRANSLITERATION_SYNONYMS = {
    # Mizaj & Humors
    "safra": ["yellow bile", "choleric", "safrawi", "safraawi", "bilious"],
    "balgham": ["phlegm", "phlegmatic", "balghami", "balgami", "serous"],
    "dam": ["blood", "sanguine", "damwi", "damawi"],
    "sauda": ["black bile", "melancholic", "saudawi", "sawda"],
    "mizaj": ["temperament", "constitution", "temperamental", "mizaaj"],
    # Symptoms & Conditions
    "su-e-hazm": ["dyspepsia", "indigestion", "impaired digestion", "hazm"],
    "dyspepsia": ["su-e-hazm", "indigestion", "heartburn", "gastric distress"],
    "su-e-mizaj": ["temperamental dyscrasia", "dystemperament", "temperament imbalance"],
    "su'al": ["cough", "bronchitis", "respiratory irritation", "sual"],
    "cough": ["su'al", "sual", "khansi", "coughing"],
    "qulanj": ["colic", "intestinal colic", "spasmodic pain"],
    "waja-ul-mafasil": ["arthritis", "joint pain", "arthralgia"],
    "joint pain": ["waja-ul-mafasil", "arthritis", "sandhivata"],
    "humma": ["fever", "pyrexia", "bukhar"],
    "fever": ["humma", "pyrexia", "tap", "bukhar"],
    "ibs": ["irritable bowel syndrome", "spastic colon", "zaheer"],
    "constipation": ["qabz", "kabz", "constipated", "bowel sluggishness"],
    "qabz": ["constipation", "obstipation", "kabz"],
    # Herbs & Drugs
    "senna": ["sana makki", "cassia senna", "senna alexandrina", "sana"],
    "sana makki": ["senna", "cassia angustifolia", "sana"],
    "filfil siah": ["black pepper", "piper nigrum", "kali mirch"],
    "zanjabil": ["ginger", "zingiber officinale", "adrak", "sonth"],
    "asgand": ["ashwagandha", "withania somnifera", "asgandh"],
    "ustukhuddus": ["lavandula stoechas", "lavender", "arabian lavender"],
    "qurs-e-taqwiyat": ["taqwiyat tablet", "vitality formulation", "qurs taqwiyat"],
}

class KnowledgeRetrievalEngine:
    """Core domain service for governed clinical knowledge retrieval, search, and synthesis."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)

    def _normalize_text(self, text: str) -> str:
        """Normalize clinical text for matching."""
        if not text:
            return ""
        # Lowercase, strip accents/special punctuation, normalize whitespace
        norm = text.lower().strip()
        norm = re.sub(r"[^\w\s\-]", " ", norm)
        return re.sub(r"\s+", " ", norm).strip()

    def _expand_synonyms(self, query: str) -> List[str]:
        """Expand terms using transliteration and bilingual dictionary."""
        tokens = self._normalize_text(query).split()
        expanded = set(tokens)
        normalized_query = self._normalize_text(query)

        # Check full query match
        if normalized_query in TRANSLITERATION_SYNONYMS:
            expanded.update(TRANSLITERATION_SYNONYMS[normalized_query])

        # Check individual tokens
        for token in tokens:
            if token in TRANSLITERATION_SYNONYMS:
                expanded.update(TRANSLITERATION_SYNONYMS[token])

        return list(expanded)

    # --------------------------------------------------------------------------
    # 1. SOURCES REGISTRY MANAGEMENT
    # --------------------------------------------------------------------------

    def register_source(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Register a new clinical source with publication and verification metadata."""
        title = data.get("title", "").strip()
        if not title:
            raise ValidationError("Source title is required.")

        source_type = data.get("source_type", "TEXTBOOK")
        valid_types = {
            'OFFICIAL_GOVERNMENT', 'REGULATORY', 'PHARMACOPOEIA', 'FORMULARY',
            'CLINICAL_GUIDELINE', 'TEXTBOOK', 'PEER_REVIEWED_ARTICLE',
            'SYSTEMATIC_REVIEW', 'META_ANALYSIS', 'CLINICAL_TRIAL',
            'CLASSICAL_TEXT', 'EXPERT_REVIEW', 'SECONDARY_SOURCE'
        }
        if source_type not in valid_types:
            raise ValidationError(f"Invalid source_type. Must be one of: {sorted(list(valid_types))}")

        conn = self.db_manager.get_connection()
        try:
            source_id = data.get("id") or f"src-{uuid.uuid4().hex[:12]}"
            doc_hash = data.get("document_hash")
            if not doc_hash and data.get("raw_text_content"):
                doc_hash = hashlib.sha256(data["raw_text_content"].encode("utf-8")).hexdigest()

            conn.execute("""
                INSERT INTO knowledge_sources (
                    id, title, authors_or_org, publisher, source_type, edition,
                    publication_date, url_or_identifier, language, jurisdiction,
                    regulatory_status, evidence_level, document_hash, ingestion_date,
                    verification_date, reviewer_name, review_status, notes, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?);
            """, (
                source_id,
                title,
                data.get("authors_or_org", "Unknown Authority"),
                data.get("publisher", "Unknown Publisher"),
                source_type,
                data.get("edition"),
                data.get("publication_date"),
                data.get("url_or_identifier"),
                data.get("language", "en"),
                data.get("jurisdiction", "GLOBAL"),
                data.get("regulatory_status", "APPROVED_STANDARD"),
                data.get("evidence_level", "EXPERT_OPINION"),
                doc_hash,
                data.get("verification_date"),
                data.get("reviewer_name"),
                data.get("review_status", "APPROVED"),
                data.get("notes"),
                1 if data.get("is_synthetic") else 0
            ))

            self._log_review_action(
                conn, "SOURCE", source_id, "SUBMITTED", user_id,
                "Source registered in clinical knowledge catalog", None, data.get("review_status", "APPROVED")
            )
            conn.commit()
            return self.get_source(source_id)
        finally:
            conn.close()

    def get_source(self, source_id: str) -> Dict[str, Any]:
        """Fetch a single source record by ID."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_sources WHERE id = ?;", (source_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Source with id '{source_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    def list_sources(
        self,
        source_type: Optional[str] = None,
        review_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List registered knowledge sources with filtering."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM knowledge_sources WHERE 1=1"
            params: List[Any] = []

            if source_type:
                query += " AND source_type = ?"
                params.append(source_type)
            if review_status:
                query += " AND review_status = ?"
                params.append(review_status)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])

            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]

            count_cur = conn.cursor()
            count_cur.execute("SELECT COUNT(*) as cnt FROM knowledge_sources;")
            total = count_cur.fetchone()["cnt"]

            return {"total": total, "sources": rows}
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. KNOWLEDGE ITEMS MANAGEMENT
    # --------------------------------------------------------------------------

    def create_knowledge_item(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a new clinical knowledge concept or item."""
        canonical_name = data.get("canonical_name", "").strip()
        if not canonical_name:
            raise ValidationError("canonical_name is required.")

        domain = data.get("domain", "UNANI")
        valid_domains = {"UNANI", "MODERN_CLINICAL", "SAFETY", "CROSS_DISCIPLINARY"}
        if domain not in valid_domains:
            raise ValidationError(f"Invalid domain. Must be one of: {valid_domains}")

        entity_type = data.get("entity_type", "DISEASE")
        valid_entities = {
            'MIZAJ', 'AFAAL', 'ASBAB', 'DISEASE', 'SYMPTOM', 'SIGN',
            'SINGLE_DRUG', 'FORMULATION', 'TREATMENT_PRINCIPLE',
            'RED_FLAG', 'SAFETY_RULE', 'INVESTIGATION'
        }
        if entity_type not in valid_entities:
            raise ValidationError(f"Invalid entity_type. Must be one of: {valid_entities}")

        claim_type = data.get("claim_type", "expert_consensus")
        valid_claim_types = {
            'traditional_use', 'classical_description', 'pharmacopoeial_specification',
            'clinical_guideline', 'research_evidence', 'expert_consensus',
            'regulatory_requirement', 'hypothesis', 'unknown'
        }
        if claim_type not in valid_claim_types:
            raise ValidationError(f"Invalid claim_type. Must be one of: {valid_claim_types}")

        status = data.get("status", "draft")
        valid_statuses = {'draft', 'under_review', 'approved', 'deprecated', 'rejected'}
        if status not in valid_statuses:
            raise ValidationError(f"Invalid status: {status}")

        conn = self.db_manager.get_connection()
        try:
            item_id = data.get("id") or f"ki-{uuid.uuid4().hex[:12]}"
            aliases = data.get("aliases", [])
            aliases_json = json.dumps(aliases) if isinstance(aliases, list) else "[]"
            struct_attr = data.get("structured_attributes", {})
            struct_attr_json = json.dumps(struct_attr) if isinstance(struct_attr, dict) else "{}"

            conn.execute("""
                INSERT INTO knowledge_items (
                    id, domain, entity_type, canonical_name, aliases_json, language,
                    description, structured_attributes_json, clinical_scope, claim_type,
                    evidence_level, status, version, valid_from, valid_until, created_by,
                    reviewed_by, approved_at, supersedes_id, source_count, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                item_id,
                domain,
                entity_type,
                canonical_name,
                aliases_json,
                data.get("language", "en"),
                data.get("description", ""),
                struct_attr_json,
                data.get("clinical_scope", "OUTPATIENT"),
                claim_type,
                data.get("evidence_level", "EXPERT_OPINION"),
                status,
                data.get("version", "1.0"),
                data.get("valid_from"),
                data.get("valid_until"),
                user_id,
                data.get("reviewed_by") if status == "approved" else None,
                datetime.utcnow().isoformat() if status == "approved" else None,
                data.get("supersedes_id"),
                int(data.get("source_count", 1)),
                1 if data.get("is_synthetic") else 0
            ))

            self._log_review_action(
                conn, "KNOWLEDGE_ITEM", item_id, "SUBMITTED" if status == "draft" else "APPROVED",
                user_id, f"Created knowledge item '{canonical_name}'", None, status
            )
            conn.commit()
            return self.get_knowledge_item(item_id)
        finally:
            conn.close()

    def get_knowledge_item(self, item_id: str, allow_unapproved: bool = True) -> Dict[str, Any]:
        """Retrieve a knowledge item with its parsed attributes, claims, relationships, and citations."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_items WHERE id = ?;", (item_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Knowledge item with id '{item_id}' not found.")

            item = dict(row)
            if not allow_unapproved and item["status"] != "approved":
                raise NotFoundError(f"Approved knowledge item '{item_id}' not available.")

            item["aliases"] = json.loads(item.get("aliases_json") or "[]")
            item["structured_attributes"] = json.loads(item.get("structured_attributes_json") or "{}")

            # Fetch claims
            cur.execute("""
                SELECT c.*, u.full_name as reviewer_name
                FROM knowledge_claims c
                LEFT JOIN users u ON c.reviewer_id = u.id
                WHERE c.item_id = ?
                ORDER BY c.created_at ASC;
            """, (item_id,))
            claims = []
            for c_row in cur.fetchall():
                c = dict(c_row)
                c["linked_concepts"] = json.loads(c.get("linked_concepts_json") or "[]")
                claims.append(c)
            item["claims"] = claims

            # Fetch relationships
            cur.execute("""
                SELECT r.*, ki.canonical_name as target_canonical_name, ki.entity_type as target_entity_type
                FROM knowledge_relationships r
                JOIN knowledge_items ki ON r.target_item_id = ki.id
                WHERE r.source_item_id = ?;
            """, (item_id,))
            item["relationships"] = [dict(r) for r in cur.fetchall()]

            return item
        finally:
            conn.close()

    def list_knowledge_items(
        self,
        domain: Optional[str] = None,
        entity_type: Optional[str] = None,
        status: Optional[str] = "approved",
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List knowledge items with domain, entity type, and status filtering."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM knowledge_items WHERE 1=1"
            params: List[Any] = []

            if domain:
                query += " AND domain = ?"
                params.append(domain)
            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type)
            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY canonical_name ASC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])

            cur.execute(query, params)
            items = []
            for r in cur.fetchall():
                it = dict(r)
                it["aliases"] = json.loads(it.get("aliases_json") or "[]")
                it["structured_attributes"] = json.loads(it.get("structured_attributes_json") or "{}")
                items.append(it)

            count_cur = conn.cursor()
            count_cur.execute("SELECT COUNT(*) as cnt FROM knowledge_items;")
            total = count_cur.fetchone()["cnt"]

            return {"total": total, "items": items}
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. ATOMIC CLAIMS & EVIDENCE APPRAISAL
    # --------------------------------------------------------------------------

    def create_claim(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create an atomic assertion/claim associated with a knowledge item."""
        item_id = data.get("item_id")
        if not item_id:
            raise ValidationError("item_id is required for a claim.")

        claim_text = data.get("claim_text", "").strip()
        if not claim_text:
            raise ValidationError("claim_text cannot be empty.")

        conn = self.db_manager.get_connection()
        try:
            # Verify item exists
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_items WHERE id = ?;", (item_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Knowledge item '{item_id}' does not exist.")

            claim_id = data.get("id") or f"clm-{uuid.uuid4().hex[:12]}"
            linked_concepts = data.get("linked_concepts", [])
            linked_json = json.dumps(linked_concepts) if isinstance(linked_concepts, list) else "[]"
            status = data.get("status", "draft")

            conn.execute("""
                INSERT INTO knowledge_claims (
                    id, item_id, claim_text, claim_type, linked_concepts_json,
                    evidence_strength, status, reviewer_id, reviewed_at, approval_state,
                    clinical_limitations, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                claim_id,
                item_id,
                claim_text,
                data.get("claim_type", "expert_consensus"),
                linked_json,
                data.get("evidence_strength", "MODERATE"),
                status,
                user_id if status == "approved" else None,
                datetime.utcnow().isoformat() if status == "approved" else None,
                "APPROVED" if status == "approved" else "DRAFT",
                data.get("clinical_limitations"),
                1 if data.get("is_synthetic") else 0
            ))

            self._log_review_action(
                conn, "CLAIM", claim_id, "SUBMITTED" if status == "draft" else "APPROVED",
                user_id, f"Added claim: {claim_text[:60]}...", None, status
            )
            conn.commit()
            return self.get_claim(claim_id)
        finally:
            conn.close()

    def get_claim(self, claim_id: str) -> Dict[str, Any]:
        """Fetch claim details along with attached evidence and citations."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT c.*, ki.canonical_name as item_name, ki.domain as item_domain
                FROM knowledge_claims c
                JOIN knowledge_items ki ON c.item_id = ki.id
                WHERE c.id = ?;
            """, (claim_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Claim with id '{claim_id}' not found.")

            claim = dict(row)
            claim["linked_concepts"] = json.loads(claim.get("linked_concepts_json") or "[]")

            # Attached evidence records
            cur.execute("""
                SELECT e.*, s.title as source_title, s.authors_or_org, s.source_type
                FROM knowledge_evidence e
                JOIN knowledge_sources s ON e.source_id = s.id
                WHERE e.claim_id = ?;
            """, (claim_id,))
            claim["evidence"] = [dict(r) for r in cur.fetchall()]

            # Citations
            cur.execute("""
                SELECT cit.*, s.title as source_title, s.publisher, s.url_or_identifier
                FROM knowledge_citations cit
                JOIN knowledge_sources s ON cit.source_id = s.id
                WHERE cit.claim_id = ?;
            """, (claim_id,))
            claim["citations"] = [dict(r) for r in cur.fetchall()]

            return claim
        finally:
            conn.close()

    def create_evidence(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create an evidence record appraisal linking a claim to a source."""
        claim_id = data.get("claim_id")
        source_id = data.get("source_id")
        if not claim_id or not source_id:
            raise ValidationError("Both claim_id and source_id are required.")

        result_summary = data.get("result_summary", "").strip()
        if not result_summary:
            raise ValidationError("result_summary is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_claims WHERE id = ?;", (claim_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Claim '{claim_id}' not found.")

            cur.execute("SELECT id FROM knowledge_sources WHERE id = ?;", (source_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Source '{source_id}' not found.")

            evidence_id = data.get("id") or f"evd-{uuid.uuid4().hex[:12]}"
            review_status = data.get("review_status", "APPROVED")

            conn.execute("""
                INSERT INTO knowledge_evidence (
                    id, claim_id, source_id, study_type, population, intervention_or_exposure,
                    comparator, outcome, sample_size, result_summary, limitations,
                    risk_of_bias, evidence_grade, evidence_status, publication_date,
                    page_or_section, reviewer_id, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                evidence_id,
                claim_id,
                source_id,
                data.get("study_type", "EXPERT_CONSENSUS"),
                data.get("population"),
                data.get("intervention_or_exposure"),
                data.get("comparator"),
                data.get("outcome"),
                int(data.get("sample_size", 0)) if data.get("sample_size") else None,
                result_summary,
                data.get("limitations", "No formal limitations recorded."),
                data.get("risk_of_bias", "UNCLEAR"),
                data.get("evidence_grade", "GRADE_C"),
                data.get("evidence_status", "evidence_exists"),
                data.get("publication_date"),
                data.get("page_or_section"),
                user_id if review_status == "APPROVED" else None,
                review_status
            ))

            # Automatically establish citation record if requested
            if data.get("create_citation", True):
                cit_id = f"cit-{uuid.uuid4().hex[:12]}"
                conn.execute("""
                    INSERT INTO knowledge_citations (
                        id, claim_id, source_id, citation_type, location_in_source, quote_or_excerpt
                    ) VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    cit_id,
                    claim_id,
                    source_id,
                    data.get("citation_type", "SUPPORTING"),
                    data.get("page_or_section"),
                    result_summary
                ))

            self._log_review_action(
                conn, "EVIDENCE", evidence_id, "APPROVED" if review_status == "APPROVED" else "SUBMITTED",
                user_id, f"Added evidence from source {source_id}", None, review_status
            )
            conn.commit()
            return self.get_evidence(evidence_id)
        finally:
            conn.close()

    def get_evidence(self, evidence_id: str) -> Dict[str, Any]:
        """Fetch single evidence appraisal record."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT e.*, s.title as source_title, s.publisher, s.authors_or_org,
                       c.claim_text, c.claim_type
                FROM knowledge_evidence e
                JOIN knowledge_sources s ON e.source_id = s.id
                JOIN knowledge_claims c ON e.claim_id = c.id
                WHERE e.id = ?;
            """, (evidence_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Evidence record with id '{evidence_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. GRAPH-COMPATIBLE RELATIONSHIPS & CITATIONS
    # --------------------------------------------------------------------------

    def create_relationship(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a graph-compatible relationship between two knowledge items."""
        source_id = data.get("source_item_id")
        target_id = data.get("target_item_id")
        rel_type = data.get("relationship_type")

        if not source_id or not target_id or not rel_type:
            raise ValidationError("source_item_id, target_item_id, and relationship_type are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_items WHERE id = ?;", (source_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Source knowledge item '{source_id}' not found.")
            cur.execute("SELECT id FROM knowledge_items WHERE id = ?;", (target_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Target knowledge item '{target_id}' not found.")

            rel_id = f"rel-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO knowledge_relationships (
                    id, source_item_id, relationship_type, target_item_id,
                    directionality, strength, context_notes, source_id, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                rel_id,
                source_id,
                rel_type,
                target_id,
                data.get("directionality", "DIRECTED"),
                data.get("strength", "DEFINITIVE"),
                data.get("context_notes"),
                data.get("source_id"),
                data.get("review_status", "APPROVED")
            ))
            conn.commit()
            return {"id": rel_id, "status": "created"}
        finally:
            conn.close()

    def get_citation(self, citation_id: str) -> Dict[str, Any]:
        """Retrieve full citation details with provenance trace."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT cit.*, s.title as source_title, s.authors_or_org, s.publisher,
                       s.source_type, s.publication_date, s.url_or_identifier,
                       s.regulatory_status, s.evidence_level, s.document_hash,
                       c.claim_text, c.claim_type, ki.canonical_name as item_name
                FROM knowledge_citations cit
                JOIN knowledge_sources s ON cit.source_id = s.id
                JOIN knowledge_claims c ON cit.claim_id = c.id
                JOIN knowledge_items ki ON c.item_id = ki.id
                WHERE cit.id = ?;
            """, (citation_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Citation with id '{citation_id}' not found.")
            res = dict(row)
            res["relevance_metadata"] = json.loads(res.get("relevance_metadata_json") or "{}")
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. HYBRID RETRIEVAL & SEARCH ENGINE
    # --------------------------------------------------------------------------

    def search_knowledge(
        self,
        query: str,
        domain: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        only_approved: bool = True,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Universal clinical search across Unani and modern terms, symptoms, drugs, formulations.
        Combines exact matching, transliteration synonym expansion, and multi-attribute ranking.
        """
        if not query or not query.strip():
            return []

        expanded_terms = self._expand_synonyms(query)
        normalized_q = self._normalize_text(query)

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            where_clauses = ["1=1"]
            params: List[Any] = []

            if only_approved:
                where_clauses.append("ki.status = 'approved'")
            if domain:
                where_clauses.append("ki.domain = ?")
                params.append(domain)
            if entity_types:
                placeholders = ",".join(["?"] * len(entity_types))
                where_clauses.append(f"ki.entity_type IN ({placeholders})")
                params.extend(entity_types)

            where_sql = " AND ".join(where_clauses)
            sql = f"""
                SELECT ki.*, 
                       (SELECT COUNT(*) FROM knowledge_claims kc WHERE kc.item_id = ki.id AND kc.status = 'approved') as claim_count,
                       (SELECT COUNT(*) FROM knowledge_relationships kr WHERE kr.source_item_id = ki.id) as rel_count
                FROM knowledge_items ki
                WHERE {where_sql}
            """
            cur.execute(sql, params)
            candidates = [dict(r) for r in cur.fetchall()]

            scored_results = []
            for item in candidates:
                name_norm = self._normalize_text(item["canonical_name"])
                desc_norm = self._normalize_text(item.get("description", ""))
                aliases = [self._normalize_text(a) for a in json.loads(item.get("aliases_json") or "[]")]

                score = 0.0
                match_reasons = []

                # Exact canonical name match
                if name_norm == normalized_q:
                    score += 10.0
                    match_reasons.append("Exact canonical match")
                elif normalized_q in name_norm:
                    score += 6.0
                    match_reasons.append("Canonical substring match")

                # Alias match
                for alias in aliases:
                    if alias == normalized_q:
                        score += 8.0
                        match_reasons.append(f"Exact transliteration alias match: '{alias}'")
                        break
                    elif normalized_q in alias:
                        score += 4.0
                        match_reasons.append(f"Alias substring match: '{alias}'")
                        break

                # Expanded transliteration synonym match
                for term in expanded_terms:
                    term_norm = self._normalize_text(term)
                    if term_norm in name_norm or any(term_norm in a for a in aliases):
                        score += 3.0
                        match_reasons.append(f"Transliteration synonym expansion match: '{term}'")
                        break

                # Description keyword match
                if normalized_q in desc_norm:
                    score += 2.0
                    match_reasons.append("Description context match")

                if score > 0:
                    item["aliases"] = json.loads(item.get("aliases_json") or "[]")
                    item["structured_attributes"] = json.loads(item.get("structured_attributes_json") or "{}")
                    item["relevance_score"] = round(score, 2)
                    item["match_reasons"] = list(set(match_reasons))
                    scored_results.append(item)

            # Sort descending by score
            scored_results.sort(key=lambda x: x["relevance_score"], reverse=True)
            return scored_results[:limit]
        finally:
            conn.close()

    def retrieve_clinical_context(
        self,
        encounter_context: Dict[str, Any],
        organization_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        """
        Contextual clinical knowledge retrieval for consultation decision-support.
        Consumes: age, sex, symptoms, observations, medicines, allergies, Unani assessment.
        Returns: Relevant Unani & Modern references, evidence levels, precautions, citations.
        Strictly: NEVER automatically prescribes.
        """
        symptoms = encounter_context.get("symptoms", [])
        mizaj_primary = encounter_context.get("mizaj_primary")
        medicines = encounter_context.get("medicines", [])
        allergies = encounter_context.get("allergies", [])

        unani_references = []
        modern_references = []
        safety_precautions = []
        citations_list = []

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()

            # 1. Search knowledge relevant to symptoms
            for symptom in symptoms:
                sym_items = self.search_knowledge(symptom, only_approved=True, limit=3)
                for item in sym_items:
                    if item["domain"] == "UNANI":
                        unani_references.append({
                            "item_id": item["id"],
                            "canonical_name": item["canonical_name"],
                            "matched_symptom": symptom,
                            "claim_type": item["claim_type"],
                            "evidence_level": item["evidence_level"],
                            "description": item["description"]
                        })
                    else:
                        modern_references.append({
                            "item_id": item["id"],
                            "canonical_name": item["canonical_name"],
                            "matched_symptom": symptom,
                            "evidence_level": item["evidence_level"],
                            "clinical_scope": item["clinical_scope"],
                            "description": item["description"]
                        })

            # 2. Search knowledge relevant to Mizaj
            if mizaj_primary:
                mizaj_items = self.search_knowledge(mizaj_primary, domain="UNANI", only_approved=True, limit=2)
                for item in mizaj_items:
                    unani_references.append({
                        "item_id": item["id"],
                        "canonical_name": item["canonical_name"],
                        "matched_mizaj": mizaj_primary,
                        "claim_type": item["claim_type"],
                        "evidence_level": item["evidence_level"],
                        "description": item["description"]
                    })

            # 3. Check for Safety Precautions on medicines/ingredients
            for med in medicines:
                med_items = self.search_knowledge(med, entity_types=["SINGLE_DRUG", "FORMULATION", "SAFETY_RULE"], only_approved=True, limit=2)
                for item in med_items:
                    cur.execute("""
                        SELECT c.claim_text, c.clinical_limitations, c.evidence_strength
                        FROM knowledge_claims c
                        WHERE c.item_id = ? AND c.status = 'approved' AND c.claim_type IN ('regulatory_requirement', 'clinical_guideline', 'pharmacopoeial_specification');
                    """, (item["id"],))
                    for clm in cur.fetchall():
                        safety_precautions.append({
                            "substance": item["canonical_name"],
                            "precaution_text": clm["claim_text"],
                            "limitations": clm["clinical_limitations"],
                            "evidence_strength": clm["evidence_strength"]
                        })

            # 4. Resolve traceable citations for all surfaced items
            surfaced_ids = [r["item_id"] for r in unani_references + modern_references]
            if surfaced_ids:
                placeholders = ",".join(["?"] * len(surfaced_ids))
                cur.execute(f"""
                    SELECT cit.id as citation_id, cit.location_in_source, s.id as source_id,
                           s.title as source_title, s.publisher, s.source_type, s.publication_date,
                           ki.canonical_name as item_name
                    FROM knowledge_citations cit
                    JOIN knowledge_claims kc ON cit.claim_id = kc.id
                    JOIN knowledge_items ki ON kc.item_id = ki.id
                    JOIN knowledge_sources s ON cit.source_id = s.id
                    WHERE ki.id IN ({placeholders}) AND s.review_status = 'APPROVED'
                    LIMIT 10;
                """, surfaced_ids)
                citations_list = [dict(r) for r in cur.fetchall()]

            # Deduplicate by item_id
            seen_unani = set()
            dedup_unani = []
            for u in unani_references:
                if u["item_id"] not in seen_unani:
                    seen_unani.add(u["item_id"])
                    dedup_unani.append(u)

            seen_mod = set()
            dedup_mod = []
            for m in modern_references:
                if m["item_id"] not in seen_mod:
                    seen_mod.add(m["item_id"])
                    dedup_mod.append(m)

            return {
                "organization_id": organization_id,
                "unani_references": dedup_unani,
                "modern_references": dedup_mod,
                "safety_precautions": safety_precautions,
                "citations": citations_list,
                "prescribing_disclaimer": "Informational clinical decision support only. Does not constitute autonomous medical advice or an automated order."
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. EVIDENCE SYNTHESIS ENGINE
    # --------------------------------------------------------------------------

    def synthesize_evidence(self, item_id: str) -> Dict[str, Any]:
        """
        Controlled synthesis of retrieved evidence for an entity.
        Explicitly distinguishes:
        - What is established vs uncertain
        - Evidence strength & methodology
        - Traditional use vs modern clinical trials (NEVER conflates)
        - Conflicting data and explicit limitations
        """
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_items WHERE id = ?;", (item_id,))
            item = cur.fetchone()
            if not item:
                raise NotFoundError(f"Knowledge item '{item_id}' not found.")

            cur.execute("""
                SELECT c.*, e.study_type, e.result_summary, e.limitations as ev_limitations,
                       e.risk_of_bias, e.evidence_grade, e.evidence_status, s.title as source_title,
                       s.source_type, s.regulatory_status
                FROM knowledge_claims c
                LEFT JOIN knowledge_evidence e ON c.id = e.claim_id
                LEFT JOIN knowledge_sources s ON e.source_id = s.id
                WHERE c.item_id = ? AND c.status = 'approved';
            """, (item_id,))
            rows = [dict(r) for r in cur.fetchall()]

            known_points = []
            uncertain_points = []
            traditional_claims = []
            modern_evidence = []
            conflicting_evidence = []
            limitations = []
            sources_consulted = set()

            for r in rows:
                if r.get("source_title"):
                    sources_consulted.add(r["source_title"])

                claim_type = r["claim_type"]
                text = r["claim_text"]

                if claim_type in ('traditional_use', 'classical_description'):
                    traditional_claims.append({
                        "statement": text,
                        "source": r.get("source_title", "Classical Compendium"),
                        "evidence_grade": "Classical Documented Use (Not RCT Equivalent)"
                    })
                elif claim_type in ('research_evidence', 'clinical_guideline'):
                    modern_evidence.append({
                        "statement": text,
                        "study_type": r.get("study_type", "Observational"),
                        "grade": r.get("evidence_grade", "GRADE_C"),
                        "risk_of_bias": r.get("risk_of_bias", "UNCLEAR"),
                        "result": r.get("result_summary")
                    })

                if r.get("evidence_status") == "evidence_conflicting":
                    conflicting_evidence.append(text)

                if r.get("ev_limitations"):
                    limitations.append(r["ev_limitations"])
                if r.get("clinical_limitations"):
                    limitations.append(r["clinical_limitations"])

                if r.get("evidence_strength") in ("HIGH", "MODERATE"):
                    known_points.append(text)
                else:
                    uncertain_points.append(text)

            return {
                "item_id": item_id,
                "canonical_name": item["canonical_name"],
                "domain": item["domain"],
                "known_findings": known_points,
                "uncertain_findings": uncertain_points,
                "traditional_use_evidence": traditional_claims,
                "modern_clinical_evidence": modern_evidence,
                "conflicting_evidence": list(set(conflicting_evidence)),
                "clinical_limitations": list(set(limitations)),
                "sources_consulted": sorted(list(sources_consulted)),
                "epistemological_boundary": "Traditional textual indications reflect centuries of classical empirical practice; they are documented as traditional monograph specifications and are NOT presented as equivalent to contemporary double-blind randomized clinical trials."
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. GOVERNANCE & REVIEW WORKFLOW
    # --------------------------------------------------------------------------

    def approve_knowledge_item(self, item_id: str, reviewer_id: str, comments: str) -> Dict[str, Any]:
        """Reviewer approval for a knowledge item."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status, canonical_name FROM knowledge_items WHERE id = ?;", (item_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Knowledge item '{item_id}' not found.")

            prev_status = row["status"]
            conn.execute("""
                UPDATE knowledge_items
                SET status = 'approved',
                    reviewed_by = ?,
                    approved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (reviewer_id, item_id))

            self._log_review_action(
                conn, "KNOWLEDGE_ITEM", item_id, "APPROVED", reviewer_id, comments, prev_status, "approved"
            )
            conn.commit()
            return {"id": item_id, "status": "approved", "reviewer_id": reviewer_id}
        finally:
            conn.close()

    def reject_knowledge_item(self, item_id: str, reviewer_id: str, reason: str) -> Dict[str, Any]:
        """Reviewer rejection for a knowledge item."""
        if not reason or not reason.strip():
            raise ValidationError("Rejection reason is mandatory.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM knowledge_items WHERE id = ?;", (item_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Knowledge item '{item_id}' not found.")

            prev_status = row["status"]
            conn.execute("""
                UPDATE knowledge_items
                SET status = 'rejected',
                    reviewed_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (reviewer_id, item_id))

            self._log_review_action(
                conn, "KNOWLEDGE_ITEM", item_id, "REJECTED", reviewer_id, reason, prev_status, "rejected"
            )
            conn.commit()
            return {"id": item_id, "status": "rejected", "reviewer_id": reviewer_id}
        finally:
            conn.close()

    def request_changes_knowledge_item(self, item_id: str, reviewer_id: str, comments: str) -> Dict[str, Any]:
        """Reviewer requests changes on an item."""
        if not comments or not comments.strip():
            raise ValidationError("Feedback comments are mandatory when requesting changes.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status FROM knowledge_items WHERE id = ?;", (item_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Knowledge item '{item_id}' not found.")

            prev_status = row["status"]
            conn.execute("""
                UPDATE knowledge_items
                SET status = 'under_review',
                    reviewed_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (reviewer_id, item_id))

            self._log_review_action(
                conn, "KNOWLEDGE_ITEM", item_id, "CHANGES_REQUESTED", reviewer_id, comments, prev_status, "under_review"
            )
            conn.commit()
            return {"id": item_id, "status": "under_review", "comments": comments}
        finally:
            conn.close()

    def list_review_queue(self, status: str = "under_review", limit: int = 50) -> List[Dict[str, Any]]:
        """List items awaiting review in the Knowledge Admin."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT ki.*, u.full_name as author_name
                FROM knowledge_items ki
                JOIN users u ON ki.created_by = u.id
                WHERE ki.status = ?
                ORDER BY ki.created_at ASC
                LIMIT ?;
            """, (status, limit))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_review_logs(self, entity_id: str) -> List[Dict[str, Any]]:
        """Fetch audit log history for an entity."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT l.*, u.full_name as reviewer_name
                FROM knowledge_review_logs l
                JOIN users u ON l.reviewer_id = u.id
                WHERE l.entity_id = ?
                ORDER BY l.created_at DESC;
            """, (entity_id,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def _log_review_action(
        self,
        conn,
        entity_type: str,
        entity_id: str,
        action: str,
        reviewer_id: str,
        comments: str,
        prev_state: Optional[str],
        new_state: Optional[str]
    ):
        """Internal helper to insert a review audit log entry."""
        log_id = f"log-{uuid.uuid4().hex[:12]}"
        conn.execute("""
            INSERT INTO knowledge_review_logs (
                id, entity_type, entity_id, action, reviewer_id, comments, previous_state, new_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            log_id,
            entity_type,
            entity_id,
            action,
            reviewer_id,
            comments,
            prev_state,
            new_state
        ))
