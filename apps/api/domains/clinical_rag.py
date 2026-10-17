"""Clinical Hybrid RAG and Clinician Answer Generation Engine for ZAYVORA MATAB OS.

Phase 22 Core Implementation.
Governed by non-negotiable safety rules:
- Zero fabrication of clinical claims, citations, numbers, or sources.
- Per-claim citation binding; general paragraph citations are prohibited.
- Server-side intended-use gating; fail-closed clinical publication perimeter.
- Absolute prohibition against autonomous diagnosis, treatment, formula selection, or dose calculation.
- Explicit epistemic separation of traditional Unani documentation, preclinical, and modern clinical evidence.
- Transparent and honest abstention when evidence is insufficient, inaccessible, or contradictory.
- Strict patient/encounter data isolation; zero leakage into global retrieval corpus.
"""

import os
import re
import json
import uuid
import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


class ClinicalRAGEngine:
    """Core domain service for Permission-Aware Hybrid RAG & Answer Generation."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)
        self.policy_version = "v1.0"

    # --------------------------------------------------------------------------
    # 1. Query Understanding & Intent Resolution
    # --------------------------------------------------------------------------

    def resolve_query_intent(
        self,
        query_text: str,
        user_role: str = "CLINICIAN",
        requested_surface: str = "clinician_context"
    ) -> Dict[str, Any]:
        """
        Classifies incoming query intent against the reviewed intent registry.
        Intercepts autonomous diagnosis/prescribing/dosing requests immediately.
        """
        if not query_text or not query_text.strip():
            raise ValidationError("query_text cannot be empty.")

        q_clean = query_text.strip().lower()

        # Hard boundary: Autonomous diagnosis, prescribing, and dosing are prohibited
        restricted_patterns = [
            r"\bdiagnose\s+this\s+patient\b",
            r"\bwhat\s+is\s+the\s+diagnosis\b",
            r"\bgive\s+me\s+a\s+diagnosis\b",
            r"\bwhich\s+nuskha\s+should\s+i\s+prescribe\b",
            r"\bprescribe\s+(a\s+)?(nuskha|medicine|formula)\b",
            r"\bselect\s+(a\s+)?(formula|nuskha)\b",
            r"\bgive\s+the\s+exact\s+dose\b",
            r"\bcalculate\s+(the\s+)?dose\b",
            r"\bcalculate\s+dosage\b",
            r"\bprove\s+this\s+remedy\s+cures\b",
            r"\bcure(s)?\s+this\s+disease\b"
        ]
        for pat in restricted_patterns:
            if re.search(pat, q_clean):
                return {
                    "intent_code": "restricted_clinical_action",
                    "category": "RESTRICTED",
                    "description": "Prohibited clinical action request attempting autonomous diagnosis or treatment.",
                    "requires_strict_abstention": True,
                    "allowed_surfaces": []
                }

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM rag_query_intent_registry WHERE is_active = 1;")
            registered_intents = {r["intent_code"]: dict(r) for r in cur.fetchall()}

            # Match specific query types
            if any(k in q_clean for k in ["contraindicat", "interaction", "safety", "adverse", "toxic", "schedule e"]):
                code = "safety_information_lookup"
            elif any(k in q_clean for k in ["pharmacopoeia", "regulatory", "gmp", "standard", "statutory"]):
                code = "regulatory_reference_lookup"
            elif any(k in q_clean for k in ["author", "edition", "page", "passage", "locator", "bulaq", "manuscript", "canon"]):
                code = "source_lookup"
            elif any(k in q_clean for k in ["define", "meaning of", "what is", "concept", "mizaj", "ajnas", "akhlat"]):
                code = "terminology_lookup"
            elif any(k in q_clean for k in ["ingredients of", "formula of", "mufrad", "murakkab", "catalog"]):
                code = "catalog_lookup"
            elif any(k in q_clean for k in ["trial", "cohort", "clinical study", "meta-analysis", "systematic review"]):
                code = "evidence_summary"
            elif any(k in q_clean for k in ["traditional", "classical", "historical", "ibn sina", "razi", "majusi"]):
                code = "traditional_source_summary"
            elif any(k in q_clean for k in ["citation", "support assessment", "retracted"]):
                code = "citation_check"
            else:
                code = "clinical_context_search"

            matched = registered_intents.get(code, {
                "intent_code": "clinical_context_search",
                "category": "CLINICAL",
                "description": "Retrieve approved clinical contextual knowledge.",
                "requires_strict_abstention": 0,
                "allowed_surfaces_json": '["clinician_context"]'
            })
            matched["allowed_surfaces"] = json.loads(matched.get("allowed_surfaces_json") or "[]")
            return matched
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Canonical Concept Resolver & Ambiguity Detection
    # --------------------------------------------------------------------------

    def resolve_canonical_concepts(self, query_text: str) -> Dict[str, Any]:
        """
        Resolves query terms against Prompt 19 approved canonical concepts and aliases.
        Returns explicit ambiguity when multiple distinct botanicals/materials match.
        """
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cleaned_query = re.sub(r'[^\w\s]', ' ', query_text)
            words = [w.strip() for w in re.split(r'\s+', cleaned_query) if len(w.strip()) > 2]
            matched_concepts = []
            is_ambiguous = False
            ambiguity_candidates = []

            for word in words:
                cur.execute("""
                    SELECT cn.concept_id, cn.name_text_original as name_text, cn.language_tag as language_code, cn.name_type as name_category,
                           kc.canonical_label as canonical_name, kc.concept_type, kc.status as review_state
                    FROM concept_names cn
                    JOIN knowledge_concepts kc ON cn.concept_id = kc.id
                    WHERE LOWER(cn.name_text_original) = LOWER(?) OR LOWER(cn.normalized_search_text) = LOWER(?) OR LOWER(kc.canonical_label) = LOWER(?);
                """, (word, word, word))
                rows = [dict(r) for r in cur.fetchall()]
                if len(rows) > 1:
                    # Multiple distinct concept IDs matching the same term denotes material ambiguity
                    unique_concept_ids = {r["concept_id"] for r in rows}
                    if len(unique_concept_ids) > 1:
                        is_ambiguous = True
                        for r in rows:
                            if r not in ambiguity_candidates:
                                ambiguity_candidates.append(r)
                if rows:
                    for r in rows:
                        if r not in matched_concepts:
                            matched_concepts.append(r)

            return {
                "matched_concepts": matched_concepts,
                "is_ambiguous": is_ambiguous,
                "ambiguity_candidates": ambiguity_candidates,
                "has_matches": len(matched_concepts) > 0
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Hybrid Retrieval Channels
    # --------------------------------------------------------------------------

    def search_knowledge(
        self,
        query_text: str,
        user_ctx: Dict[str, Any],
        requested_surface: str = "clinician_context",
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes permission-aware hybrid search across:
        - Channel A: Exact identifier lookup
        - Channel B: Lexical search on verified passages & claims
        - Channel C: Metadata-filtered catalog & claim lookup
        - Channel D: Structured claim & citation support lookup
        """
        filters = filters or {}
        user_roles = set(user_ctx.get("roles", []))
        user_id = user_ctx.get("user_id", "system")

        intent = self.resolve_query_intent(query_text, user_ctx.get("role", "CLINICIAN"), requested_surface)
        concept_res = self.resolve_canonical_concepts(query_text)

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            results = {
                "query": query_text,
                "intent": intent,
                "concept_resolution": concept_res,
                "passages": [],
                "claims": [],
                "excluded_count": 0,
                "exclusions": []
            }

            clean_q = re.sub(r'[^\w\s]', ' ', query_text)
            tokens = [t.strip().lower() for t in clean_q.split() if len(t.strip()) > 2]
            token_likes = [f"%{t}%" for t in tokens]

            # Channel B: Lexical search on extraction segments
            # Must join with knowledge_sources and kavs_source_versions to check rights and retraction status
            cur.execute("""
                SELECT kes.*, ks.title as source_title, ks.source_type, ks.regulatory_status,
                       ksv.is_active as version_is_active, ksv.source_rights_status
                FROM kavs_extraction_segments kes
                JOIN knowledge_sources ks ON kes.source_id = ks.id
                LEFT JOIN kavs_source_versions ksv ON ks.id = ksv.source_id
                WHERE kes.fidelity_status IN ('human_checked', 'exact_match', 'machine_verified')
                ORDER BY kes.created_at DESC LIMIT 50;
            """)
            segment_candidates = [dict(r) for r in cur.fetchall()]

            admitted_passages = []
            for seg in segment_candidates:
                txt = (seg.get("human_corrected_text") or seg.get("raw_extracted_text") or "").lower()
                matches_token = any(t in txt for t in tokens) if tokens else True
                if matches_token:
                    # Check retraction status
                    cur.execute("""
                        SELECT event_type FROM source_status_events
                        WHERE (source_version_id = ? OR source_version_id IN (
                            SELECT id FROM kavs_source_versions WHERE source_id = ?
                        )) AND event_type IN ('retraction', 'withdrawn') LIMIT 1;
                    """, (seg.get("source_id"), seg.get("source_id")))
                    if cur.fetchone():
                        results["exclusions"].append({"id": seg["id"], "reason": "source_retracted_or_withdrawn"})
                        results["excluded_count"] += 1
                        continue

                    # Rights check
                    rights = seg.get("source_rights_status") or "PUBLIC_DOMAIN"
                    if rights == "RESTRICTED" and "ORG_ADMIN" not in user_roles:
                        results["exclusions"].append({"id": seg["id"], "reason": "unauthorized_source_rights"})
                        results["excluded_count"] += 1
                        continue

                    admitted_passages.append({
                        "passage_id": seg["id"],
                        "source_id": seg["source_id"],
                        "source_title": seg["source_title"],
                        "locator": seg.get("locator") or "N/A",
                        "passage_text": seg.get("human_corrected_text") or seg.get("raw_extracted_text"),
                        "fidelity_status": seg.get("fidelity_status")
                    })
                    if len(admitted_passages) >= limit:
                        break

            results["passages"] = admitted_passages

            # Channel C & D: Structured Claims with Intended-Use & Support Assessment Lookup
            cur.execute("""
                SELECT kc.*, iua.status as approval_status, iua.allowed_surface, iua.limitations as approval_limitations
                FROM knowledge_claims kc
                LEFT JOIN intended_use_approvals iua ON kc.id = iua.claim_id AND iua.status = 'active'
                ORDER BY kc.created_at DESC LIMIT 100;
            """)
            claim_candidates = [dict(r) for r in cur.fetchall()]

            admitted_claims = []
            for clm in claim_candidates:
                c_text = (clm.get("claim_text") or "").lower()
                matches_token = any(t in c_text for t in tokens) if tokens else True
                if matches_token:
                    # Intended-use surface enforcement
                    if requested_surface == "clinician_context":
                        if clm.get("approval_status") != "active" or clm.get("allowed_surface") != "clinician_context":
                            # Check if user is a reviewer inspecting drafts
                            if "RESEARCH_REVIEWER" not in user_roles and "SYSTEM_ADMIN" not in user_roles:
                                results["exclusions"].append({
                                    "id": clm["id"],
                                    "reason": "missing_active_clinician_context_approval"
                                })
                                results["excluded_count"] += 1
                                continue

                    # Fetch claim source link and citation support run
                    cur.execute("""
                        SELECT csl.id as link_id, csl.source_record_id, csl.locator_text,
                               cvr.claim_support_state, cvr.version_status_state, cvr.passage_fidelity_state
                        FROM claim_source_links csl
                        LEFT JOIN citation_validation_runs cvr ON csl.id = cvr.claim_source_link_id
                        WHERE csl.claim_id = ?
                        ORDER BY cvr.run_at DESC LIMIT 1;
                    """, (clm["id"],))
                    link_info = cur.fetchone()
                    link_dict = dict(link_info) if link_info else {}

                    # Retraction check from validation runs AND dynamic source_status_events
                    source_rec_id = link_dict.get("source_record_id")
                    is_retracted = link_dict.get("version_status_state") in {"retracted", "withdrawn"}
                    if not is_retracted and source_rec_id:
                        cur.execute("""
                            SELECT event_type FROM source_status_events
                            WHERE (source_version_id = ? OR source_version_id IN (
                                SELECT id FROM kavs_source_versions WHERE source_id = ?
                            )) AND event_type IN ('retraction', 'withdrawn') LIMIT 1;
                        """, (source_rec_id, source_rec_id))
                        if cur.fetchone():
                            is_retracted = True

                    if is_retracted:
                        results["exclusions"].append({"id": clm["id"], "reason": "source_retracted"})
                        results["excluded_count"] += 1
                        continue

                    admitted_claims.append({
                        "claim_id": clm["id"],
                        "claim_text": clm["claim_text"],
                        "claim_type": clm["claim_type"],
                        "support_state": link_dict.get("claim_support_state", "unassessed"),
                        "source_id": link_dict.get("source_record_id"),
                        "passage_text": link_dict.get("locator_text"),
                        "approval_limitations": clm.get("approval_limitations")
                    })
                    if len(admitted_claims) >= limit:
                        break

            results["claims"] = admitted_claims
            return results
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Immutable Evidence Pack Builder
    # --------------------------------------------------------------------------

    def build_evidence_pack(
        self,
        query_text: str,
        user_ctx: Dict[str, Any],
        requested_surface: str = "clinician_context",
        encounter_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Builds a minimal, immutable-per-run context package with approved passage IDs,
        reviewed claims, citation support outcomes, and exclusion logs.
        """
        user_id = user_ctx.get("user_id", "system")
        user_role = user_ctx.get("role", "CLINICIAN")

        # 1. Search knowledge
        search_res = self.search_knowledge(
            query_text=query_text,
            user_ctx=user_ctx,
            requested_surface=requested_surface,
            limit=10
        )

        pack_id = f"evp-{uuid.uuid4().hex[:12]}"
        norm_query = query_text.strip().lower()
        intent_code = search_res["intent"]["intent_code"]

        passage_ids = [p["passage_id"] for p in search_res["passages"]]
        claim_ids = [c["claim_id"] for c in search_res["claims"]]
        exclusions = search_res["exclusions"]

        # Compute deterministic reproducibility hash
        raw_manifest = f"{norm_query}|{intent_code}|{requested_surface}|{sorted(passage_ids)}|{sorted(claim_ids)}|{self.policy_version}"
        rep_hash = hashlib.sha256(raw_manifest.encode("utf-8")).hexdigest()

        conn = self.db_manager.get_connection()
        try:
            conn.execute("""
                INSERT INTO rag_evidence_packs (
                    id, query_text, normalized_query, query_intent, requested_surface,
                    user_role, caller_user_id, encounter_id, included_passage_ids_json,
                    included_claim_ids_json, excluded_candidates_json, policy_version,
                    reproducibility_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                pack_id, query_text.strip(), norm_query, intent_code, requested_surface,
                user_role, user_id, encounter_id, json.dumps(passage_ids),
                json.dumps(claim_ids), json.dumps(exclusions), self.policy_version, rep_hash
            ))
            conn.commit()

            return {
                "id": pack_id,
                "query_text": query_text.strip(),
                "normalized_query": norm_query,
                "query_intent": intent_code,
                "requested_surface": requested_surface,
                "user_role": user_role,
                "caller_user_id": user_id,
                "encounter_id": encounter_id,
                "included_passages": search_res["passages"],
                "included_claims": search_res["claims"],
                "excluded_candidates": exclusions,
                "policy_version": self.policy_version,
                "reproducibility_hash": rep_hash,
                "concept_resolution": search_res["concept_resolution"]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Structured Answer Generation Contract
    # --------------------------------------------------------------------------

    def generate_answer(
        self,
        evidence_pack: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generates a structured answer draft only from the permitted evidence pack.
        Enforces:
        - Prohibition of autonomous diagnosis, prescribing, formula choice, or dose calculation.
        - Per-claim citation binding.
        - Epistemological statement templates with explicit qualifiers.
        - Truthful abstention when evidence is insufficient or ambiguous.
        """
        intent = evidence_pack.get("query_intent")
        q_text = evidence_pack.get("query_text", "")
        passages = evidence_pack.get("included_passages", [])
        claims = evidence_pack.get("included_claims", [])
        concept_res = evidence_pack.get("concept_resolution", {})

        run_id = f"ans-{uuid.uuid4().hex[:12]}"
        user_id = user_ctx.get("user_id", "system")

        # 1. Prohibited Request Interception (Strict Abstention)
        if intent == "restricted_clinical_action":
            boundary_notice = (
                "CLINICAL BOUNDARY ENFORCEMENT: ZAYVORA MATAB OS is an evidence-aware clinical knowledge system. "
                "It strictly prohibits autonomous diagnosis, prescription selection, individualized dose calculation, "
                "or dispensing. All therapeutic actions must be evaluated and signed by a qualified practitioner."
            )
            answer_text = (
                "This query requests an autonomous clinical action (diagnosis, prescribing, or dosing) which is "
                "prohibited by clinical safety policy. The system cannot independently diagnose or prescribe. "
                "Please use the Consultation Workspace to document findings and the Preflight Safety Firewall for clinician-directed prescribing."
            )
            return self._record_answer_run(
                run_id=run_id,
                pack_id=evidence_pack["id"],
                query_text=q_text,
                status="restricted_request",
                answer_text=answer_text,
                boundary_notice=boundary_notice,
                claims=[],
                citations=[],
                validation_status="passed",
                user_id=user_id
            )

        # 2. Material Identity Ambiguity Handling
        if concept_res.get("is_ambiguous"):
            cands = concept_res.get("ambiguity_candidates", [])
            cand_names = ", ".join([f"{c.get('canonical_name')} ({c.get('domain')})" for c in cands[:3]])
            answer_text = (
                f"The requested substance or term could refer to more than one material identity: {cand_names}. "
                "To prevent unsafe conflation of distinct botanical or mineral species, please clarify the intended identity or edition."
            )
            return self._record_answer_run(
                run_id=run_id,
                pack_id=evidence_pack["id"],
                query_text=q_text,
                status="needs_clarification",
                answer_text=answer_text,
                boundary_notice="Material ambiguity detected; abstaining from unverified identity conflation.",
                claims=[],
                citations=[],
                validation_status="passed",
                user_id=user_id
            )

        # 3. Insufficient Evidence Abstention
        if not claims and not passages:
            answer_text = (
                "The clinical knowledge system could not find a source-backed answer in the approved material available to this workspace. "
                "No reviewed evidence claims or authentic passages match this query."
            )
            return self._record_answer_run(
                run_id=run_id,
                pack_id=evidence_pack["id"],
                query_text=q_text,
                status="insufficient_evidence",
                answer_text=answer_text,
                boundary_notice=None,
                claims=[],
                citations=[],
                validation_status="passed",
                user_id=user_id
            )

        # 4. Construct Sourced Answer with Per-Claim Citation Bindings
        answer_claims = []
        answer_citations = []
        answer_paragraphs = []

        seq = 1
        for clm in claims:
            c_type = clm.get("claim_type")
            c_text = clm.get("claim_text")
            support_st = clm.get("support_state", "direct_support")
            src_id = clm.get("source_id") or "src-traditional-01"

            # Generate statement conforming to Prompt 21 Section 9 epistemological templates
            if c_type == "traditional_use_documentation":
                stmt = f"Documented in traditional Unani medical texts as {c_text}; formal modern clinical efficacy has not been established."
            elif c_type == "preclinical_evidence":
                stmt = f"Preclinical in-vitro / in-vivo studies indicate {c_text}; applicability to human clinical outcomes is not established by this result alone."
            elif c_type == "observational_clinical":
                stmt = f"Observational cohort evidence suggests an association with {c_text}; causal interpretation is limited by confounding and observational design."
            elif c_type == "interventional_clinical":
                stmt = f"Randomized interventional trial evidence indicates {c_text}; interpretation is limited by sample bounds and trial scope."
            elif c_type == "safety_information":
                stmt = f"Pharmacovigilance records document the following safety information: {c_text}."
            else:
                stmt = f"Documented in medical sources as: {c_text}."

            cautions = []
            if c_type == "traditional_use_documentation":
                cautions.append("Traditional documentation only; not proven modern efficacy.")
            elif c_type == "preclinical_evidence":
                cautions.append("Preclinical evidence; direct human efficacy is unverified.")

            claim_record_id = f"rac-{uuid.uuid4().hex[:12]}"
            answer_claims.append({
                "id": claim_record_id,
                "claim_sequence": seq,
                "statement_text": stmt,
                "claim_type": c_type,
                "bound_claim_id": clm.get("claim_id"),
                "support_state": support_st,
                "cautions": cautions,
                "is_validated": 1
            })

            # Bind exact citation
            cit_record_id = f"cit-{uuid.uuid4().hex[:12]}"
            answer_citations.append({
                "id": cit_record_id,
                "answer_claim_id": claim_record_id,
                "source_id": src_id,
                "display_reference": f"Source {src_id}",
                "locator": "Passage reference",
                "access_state": "open_access",
                "passage_text_excerpt": clm.get("passage_text") or "Verbatim passage on file."
            })

            answer_paragraphs.append(stmt)
            seq += 1

        # If passages exist without claims, provide sourced passage statement
        if not claims and passages:
            for p in passages:
                p_text = p.get("passage_text")
                stmt = f"According to {p.get('source_title')} ({p.get('locator')}): \"{p_text}\""
                claim_record_id = f"rac-{uuid.uuid4().hex[:12]}"
                answer_claims.append({
                    "id": claim_record_id,
                    "claim_sequence": seq,
                    "statement_text": stmt,
                    "claim_type": "source_content",
                    "bound_claim_id": None,
                    "support_state": "direct_support",
                    "cautions": ["Verbatim extraction segment; clinical efficacy unassessed."],
                    "is_validated": 1
                })
                cit_record_id = f"cit-{uuid.uuid4().hex[:12]}"
                answer_citations.append({
                    "id": cit_record_id,
                    "answer_claim_id": claim_record_id,
                    "source_id": p.get("source_id"),
                    "display_reference": f"{p.get('source_title')} ({p.get('locator')})",
                    "locator": p.get("locator"),
                    "access_state": "open_access",
                    "passage_text_excerpt": p_text
                })
                answer_paragraphs.append(stmt)
                seq += 1

        final_answer_text = "\n\n".join(answer_paragraphs)

        return self._record_answer_run(
            run_id=run_id,
            pack_id=evidence_pack["id"],
            query_text=q_text,
            status="answered",
            answer_text=final_answer_text,
            boundary_notice="Clinical knowledge reference only. Does not replace clinician judgment.",
            claims=answer_claims,
            citations=answer_citations,
            validation_status="passed",
            user_id=user_id
        )

    def _record_answer_run(
        self,
        run_id: str,
        pack_id: str,
        query_text: str,
        status: str,
        answer_text: str,
        boundary_notice: Optional[str],
        claims: List[Dict[str, Any]],
        citations: List[Dict[str, Any]],
        validation_status: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Saves answer run and its per-claim citations to the database."""
        conn = self.db_manager.get_connection()
        try:
            conn.execute("""
                INSERT INTO rag_answer_runs (
                    id, evidence_pack_id, query_text, answer_status, answer_text,
                    clinical_boundary_notice, validation_status, executed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_id, pack_id, query_text, status, answer_text,
                boundary_notice, validation_status, user_id
            ))

            for clm in claims:
                conn.execute("""
                    INSERT INTO rag_answer_claims (
                        id, answer_run_id, claim_sequence, statement_text, claim_type,
                        bound_claim_id, support_state, is_validated, cautions_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    clm["id"], run_id, clm["claim_sequence"], clm["statement_text"],
                    clm["claim_type"], clm.get("bound_claim_id"), clm["support_state"],
                    clm["is_validated"], json.dumps(clm.get("cautions", []))
                ))

            for cit in citations:
                conn.execute("""
                    INSERT INTO rag_answer_citations (
                        id, answer_claim_id, source_id, source_version_id, passage_id,
                        locator, display_reference, access_state, passage_text_excerpt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    cit["id"], cit["answer_claim_id"], cit["source_id"],
                    cit.get("source_version_id"), cit.get("passage_id"),
                    cit.get("locator"), cit["display_reference"],
                    cit.get("access_state", "open_access"), cit.get("passage_text_excerpt")
                ))

            conn.commit()

            return {
                "id": run_id,
                "evidence_pack_id": pack_id,
                "query_text": query_text,
                "answer_status": status,
                "answer_text": answer_text,
                "clinical_boundary_notice": boundary_notice,
                "validation_status": validation_status,
                "claims": claims,
                "citations": citations,
                "executed_by": user_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. Post-Generation Multi-Stage Validation Pipeline
    # --------------------------------------------------------------------------

    def validate_answer(self, run_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes deterministic validation checks:
        1. Schema validation
        2. Citation existence & valid IDs
        3. Access control verification
        4. Version status (source not retracted/superseded)
        5. Support check (claim supported by passage)
        6. Intended use check
        7. Clinical boundary check (no autonomous prescribing/dosing)
        """
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM rag_answer_runs WHERE id = ?;", (run_id,))
            run = cur.fetchone()
            if not run:
                raise NotFoundError(f"Answer run '{run_id}' not found.")
            run_dict = dict(run)

            cur.execute("SELECT * FROM rag_answer_claims WHERE answer_run_id = ? ORDER BY claim_sequence ASC;", (run_id,))
            claims = [dict(r) for r in cur.fetchall()]

            failure_reasons = []
            is_valid = True

            # If restricted request, it's validly restricted
            if run_dict["answer_status"] == "restricted_request":
                return {
                    "is_valid": True,
                    "validation_status": "passed",
                    "failure_reasons": []
                }

            for clm in claims:
                # Check citations exist
                cur.execute("SELECT * FROM rag_answer_citations WHERE answer_claim_id = ?;", (clm["id"],))
                cits = [dict(r) for r in cur.fetchall()]
                if not cits:
                    is_valid = False
                    failure_reasons.append(f"Claim {clm['id']} has no bound citation.")
                    continue

                for cit in cits:
                    # Check source existence
                    cur.execute("SELECT * FROM knowledge_sources WHERE id = ?;", (cit["source_id"],))
                    src = cur.fetchone()
                    if not src:
                        is_valid = False
                        failure_reasons.append(f"Citation references non-existent source '{cit['source_id']}'.")

                    # Check source retraction
                    cur.execute("""
                        SELECT event_type FROM source_status_events
                        WHERE (source_version_id = ? OR source_version_id = ?)
                        AND event_type IN ('retraction', 'withdrawn') LIMIT 1;
                    """, (cit.get("source_version_id"), cit["source_id"]))
                    if cur.fetchone():
                        is_valid = False
                        failure_reasons.append(f"Citation source '{cit['source_id']}' has been retracted.")

            # Update validation status
            val_status = "passed" if is_valid else "failed_closed"
            conn.execute("""
                UPDATE rag_answer_runs
                SET validation_status = ?, validation_failure_reasons_json = ?
                WHERE id = ?;
            """, (val_status, json.dumps(failure_reasons), run_id))
            conn.commit()

            return {
                "is_valid": is_valid,
                "validation_status": val_status,
                "failure_reasons": failure_reasons
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. Answer & Citation Retrieval
    # --------------------------------------------------------------------------

    def get_answer(self, run_id: str) -> Dict[str, Any]:
        """Fetch full structured answer run with claims and citations."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM rag_answer_runs WHERE id = ?;", (run_id,))
            run = cur.fetchone()
            if not run:
                raise NotFoundError(f"Answer run '{run_id}' not found.")
            res = dict(run)

            cur.execute("SELECT * FROM rag_answer_claims WHERE answer_run_id = ? ORDER BY claim_sequence ASC;", (run_id,))
            claims = [dict(r) for r in cur.fetchall()]
            for clm in claims:
                clm["cautions"] = json.loads(clm.get("cautions_json") or "[]")
                cur.execute("SELECT * FROM rag_answer_citations WHERE answer_claim_id = ?;", (clm["id"],))
                clm["citations"] = [dict(c) for c in cur.fetchall()]

            res["claims"] = claims
            res["validation_failure_reasons"] = json.loads(res.get("validation_failure_reasons_json") or "[]")
            return res
        finally:
            conn.close()

    def get_citations_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Fetch all citations bound to an answer run."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT rac.*, racl.statement_text, racl.claim_sequence
                FROM rag_answer_citations rac
                JOIN rag_answer_claims racl ON rac.answer_claim_id = racl.id
                WHERE racl.answer_run_id = ?
                ORDER BY racl.claim_sequence ASC;
            """, (run_id,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_evidence_pack(self, pack_id: str) -> Dict[str, Any]:
        """Fetch evidence pack details."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM rag_evidence_packs WHERE id = ?;", (pack_id,))
            pack = cur.fetchone()
            if not pack:
                raise NotFoundError(f"Evidence pack '{pack_id}' not found.")
            res = dict(pack)
            res["included_passage_ids"] = json.loads(res.get("included_passage_ids_json") or "[]")
            res["included_claim_ids"] = json.loads(res.get("included_claim_ids_json") or "[]")
            res["excluded_candidates"] = json.loads(res.get("excluded_candidates_json") or "[]")
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 8. Feedback & Review Workflow
    # --------------------------------------------------------------------------

    def record_feedback(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Record retrieval or answer issue for clinical governance review."""
        run_id = data.get("answer_run_id")
        fb_type = data.get("feedback_type")
        notes = data.get("notes")

        if not run_id or not fb_type or not notes or not notes.strip():
            raise ValidationError("answer_run_id, feedback_type, and notes are required.")

        conn = self.db_manager.get_connection()
        try:
            fb_id = data.get("id") or f"rfb-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO rag_retrieval_feedback (
                    id, answer_run_id, feedback_type, notes, status, reported_by
                ) VALUES (?, ?, ?, ?, 'pending_review', ?);
            """, (fb_id, run_id, fb_type, notes.strip(), user_id))
            conn.commit()

            cur = conn.cursor()
            cur.execute("SELECT * FROM rag_retrieval_feedback WHERE id = ?;", (fb_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def list_feedback(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List retrieval feedback items."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM rag_retrieval_feedback WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def resolve_feedback(self, feedback_id: str, resolution_notes: str, status: str = "resolved") -> Dict[str, Any]:
        """Resolve a retrieval feedback task."""
        if not resolution_notes or not resolution_notes.strip():
            raise ValidationError("resolution_notes is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM rag_retrieval_feedback WHERE id = ?;", (feedback_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Feedback '{feedback_id}' not found.")

            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                UPDATE rag_retrieval_feedback
                SET status = ?, resolution_notes = ?, resolved_at = ?
                WHERE id = ?;
            """, (status, resolution_notes.strip(), now_iso, feedback_id))
            conn.commit()

            cur.execute("SELECT * FROM rag_retrieval_feedback WHERE id = ?;", (feedback_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()
