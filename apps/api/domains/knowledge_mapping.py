"""Unani Clinical Knowledge Mapping, Relation-Type Registry, Versioned Organ-Axis Frameworks,
Cross-Disciplinary Concept Mappings, Relationship Conflicts, and Encounter Hypotheses.

Phase 20 Domain Engine for ZAYVORA MATAB OS.
Enforces non-negotiable knowledge principles:
- Absolute prohibition against hallucinated clinical relationships, associations, or causality.
- Controlled relation-type registry with typed constraints and review requirements.
- Provenance-bound relationship assertions; graph adjacency != proof of clinical evidence.
- No transitive clinical inference: paths between concepts do not synthesize new clinical facts.
- Strict isolation of Product Navigation Models (Organ-Axis) from verified clinical evidence.
- Cross-disciplinary mappings preserve mapping type; candidate equivalence is quarantined.
- Encounter-scoped case hypotheses remain protected patient clinical records and never write
  back to the global ontology knowledge graph.
- Relationship conflict tracking and formal adjudication queue.
"""

import json
import uuid
import re
import sqlite3
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime

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

VALID_RELATION_CLASSES: Set[str] = {
    "source_documentation", "terminology", "identity_crosswalk",
    "unani_knowledge", "modern_clinical", "product_navigation", "patient_specific"
}

VALID_RELATIONSHIP_LEVELS: Set[str] = {
    "ui_navigation_grouping", "classical_text", "clinician_authored_case_hypothesis",
    "reviewed_evidence_based", "research_hypothesis"
}

VALID_POLARITIES: Set[str] = {
    "supports", "refutes", "uncertain", "not_applicable"
}

VALID_RELATION_REVIEW_STATES: Set[str] = {
    "draft", "source_check_required", "expert_review_required",
    "approved_for_defined_use", "changes_requested", "disputed",
    "rejected", "deprecated", "withdrawn"
}

VALID_FRAMEWORK_TYPES: Set[str] = {
    "product_navigation_model", "traditional_model", "research_model", "clinical_model"
}

VALID_FRAMEWORK_REVIEW_STATES: Set[str] = {
    "draft", "under_review", "approved", "deprecated", "withdrawn"
}

VALID_APPROVED_USE_SCOPES: Set[str] = {
    "navigation_only", "clinician_contextual_reference", "clinical_decision_support"
}

VALID_MEMBERSHIP_TYPES: Set[str] = {
    "navigation_group", "source_documented_membership",
    "reviewed_clinical_membership", "research_hypothesis"
}

VALID_TARGET_SYSTEMS: Set[str] = {
    "ICD-11", "SNOMED-CT", "LOINC", "MeSH", "POWO", "OTHER"
}

VALID_MAPPING_TYPES: Set[str] = {
    "exact", "broader_than", "narrower_than", "related_to",
    "candidate_equivalence", "no_safe_mapping"
}

VALID_MAPPING_REVIEW_STATES: Set[str] = {
    "draft", "under_review", "approved", "disputed", "rejected"
}

VALID_CONFLICT_TYPES: Set[str] = {
    "source_disagreement", "identity_ambiguity", "interpretation_disagreement",
    "temporal_difference", "scope_mismatch", "other"
}

VALID_RESOLUTION_STATES: Set[str] = {
    "open", "under_review", "resolved_with_scope", "not_a_true_conflict", "unresolved"
}

VALID_HYPOTHESIS_STATUSES: Set[str] = {
    "active", "considered", "rejected", "resolved", "historical"
}


class KnowledgeMappingEngine:
    """Core domain service for Unani Clinical Knowledge Mapping and Organ-Axis Governance."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)
        self.seed_default_relation_types()
        self.seed_default_frameworks()

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
    # 1. Controlled Relation-Type Registry
    # --------------------------------------------------------------------------

    def seed_default_relation_types(self) -> None:
        """Seed controlled core relation types idempotently."""
        defaults = [
            {
                "id": "rtr-classical-organ-assoc",
                "code": "classical_organ_association",
                "label": "Classical Organ Association",
                "definition": "Classical Unani textual functional, qualitative or sympathetic association between a clinical process or concept and a bodily organ.",
                "relation_class": "unani_knowledge",
                "subject_type_constraints_json": json.dumps(["unani_term", "clinical_process", "assessment_concept", "organ_or_structure"]),
                "object_type_constraints_json": json.dumps(["organ_or_structure"]),
                "directionality": "directed",
                "is_clinically_actionable": 0,
                "requires_source_assertion": 1,
                "required_reviewer_roles_json": json.dumps(["UNANI_SCHOLAR"]),
                "allowed_intended_uses_json": json.dumps(["clinician_contextual_reference", "educational_reference"]),
                "ui_display_label": "Classical Organ Association",
                "ui_warning_text": "Classical Unani textual association. Does not imply verified modern anatomical or neuro-gastroenterological causality."
            },
            {
                "id": "rtr-organ-axis-nav-member",
                "code": "organ_axis_navigation_member",
                "label": "Organ-Axis Navigation Member",
                "definition": "Product-level visual and organizational grouping member within an Organ-Axis framework.",
                "relation_class": "product_navigation",
                "subject_type_constraints_json": json.dumps(["organ_or_structure", "clinical_process", "unani_term"]),
                "object_type_constraints_json": json.dumps(["organ_or_structure", "clinical_process"]),
                "directionality": "directed",
                "is_clinically_actionable": 0,
                "requires_source_assertion": 0,
                "required_reviewer_roles_json": json.dumps(["UNANI_SCHOLAR", "CLINICAL_SPECIALIST", "ORG_ADMIN"]),
                "allowed_intended_uses_json": json.dumps(["clinician_contextual_reference", "navigation_only"]),
                "ui_display_label": "Navigation Group Member",
                "ui_warning_text": "Navigation/grouping model for workspace navigation only; not clinical evidence."
            },
            {
                "id": "rtr-indicated-for-mizaj",
                "code": "indicated_for_mizaj_condition",
                "label": "Indicated For Mizaj Condition",
                "definition": "Classical or evidence-based indication of an intervention for a specific Mizaj dystemperament (Su-e-Mizaj).",
                "relation_class": "unani_knowledge",
                "subject_type_constraints_json": json.dumps(["material", "ingredient", "formulation"]),
                "object_type_constraints_json": json.dumps(["unani_term", "clinical_process"]),
                "directionality": "directed",
                "is_clinically_actionable": 1,
                "requires_source_assertion": 1,
                "required_reviewer_roles_json": json.dumps(["UNANI_SCHOLAR", "CLINICAL_SPECIALIST"]),
                "allowed_intended_uses_json": json.dumps(["clinician_contextual_reference", "safety_firewall_rule"]),
                "ui_display_label": "Indicated For Condition",
                "ui_warning_text": "Clinical indication subject to patient-specific assessment and contraindication check."
            },
            {
                "id": "rtr-contraindicated-in",
                "code": "contraindicated_in",
                "label": "Contraindicated In",
                "definition": "Clinical or classical contraindication in specified physiological conditions, organs, or co-morbidities.",
                "relation_class": "unani_knowledge",
                "subject_type_constraints_json": json.dumps(["material", "ingredient", "formulation"]),
                "object_type_constraints_json": json.dumps(["unani_term", "clinical_process", "organ_or_structure"]),
                "directionality": "directed",
                "is_clinically_actionable": 1,
                "requires_source_assertion": 1,
                "required_reviewer_roles_json": json.dumps(["UNANI_SCHOLAR", "CLINICAL_SPECIALIST"]),
                "allowed_intended_uses_json": json.dumps(["safety_firewall_rule", "clinician_contextual_reference"]),
                "ui_display_label": "Contraindicated In",
                "ui_warning_text": "High-priority safety constraint."
            },
            {
                "id": "rtr-botanical-identity-cand",
                "code": "botanical_identity_candidate",
                "label": "Botanical Identity Candidate",
                "definition": "Candidate botanical taxonomic crosswalk from Unani Mufradat material to Latin binomial.",
                "relation_class": "identity_crosswalk",
                "subject_type_constraints_json": json.dumps(["material", "ingredient"]),
                "object_type_constraints_json": json.dumps(["external_concept"]),
                "directionality": "directed",
                "is_clinically_actionable": 0,
                "requires_source_assertion": 1,
                "required_reviewer_roles_json": json.dumps(["UNANI_SCHOLAR"]),
                "allowed_intended_uses_json": json.dumps(["educational_reference", "unapproved"]),
                "ui_display_label": "Botanical Candidate",
                "ui_warning_text": "Candidate equivalence. Unreviewed candidates must not be treated as confirmed identities."
            },
            {
                "id": "rtr-icd11-crosswalk",
                "code": "icd11_crosswalk",
                "label": "ICD-11 Crosswalk",
                "definition": "Cross-system mapping between Unani concept and ICD-11 entity code.",
                "relation_class": "identity_crosswalk",
                "subject_type_constraints_json": json.dumps(["unani_term", "clinical_process", "assessment_concept"]),
                "object_type_constraints_json": json.dumps(["external_concept"]),
                "directionality": "directed",
                "is_clinically_actionable": 0,
                "requires_source_assertion": 0,
                "required_reviewer_roles_json": json.dumps(["CLINICAL_SPECIALIST"]),
                "allowed_intended_uses_json": json.dumps(["clinician_contextual_reference", "educational_reference"]),
                "ui_display_label": "ICD-11 Mapping",
                "ui_warning_text": "Cross-system map. Not an assertion of complete biomedical pathology equivalence."
            },
            {
                "id": "rtr-snomed-crosswalk",
                "code": "snomed_crosswalk",
                "label": "SNOMED-CT Crosswalk",
                "definition": "Cross-system mapping between Unani concept and SNOMED-CT clinical term.",
                "relation_class": "identity_crosswalk",
                "subject_type_constraints_json": json.dumps(["unani_term", "clinical_process", "assessment_concept", "organ_or_structure"]),
                "object_type_constraints_json": json.dumps(["external_concept"]),
                "directionality": "directed",
                "is_clinically_actionable": 0,
                "requires_source_assertion": 0,
                "required_reviewer_roles_json": json.dumps(["CLINICAL_SPECIALIST"]),
                "allowed_intended_uses_json": json.dumps(["clinician_contextual_reference", "educational_reference"]),
                "ui_display_label": "SNOMED-CT Mapping",
                "ui_warning_text": "Cross-system map. SNOMED-CT concepts represent biomedical semantics."
            },
            {
                "id": "rtr-source-cites",
                "code": "source_cites",
                "label": "Source Cites Passage",
                "definition": "Formal relationship establishing that a clinical concept or assertion is documented in an exact text passage.",
                "relation_class": "source_documentation",
                "subject_type_constraints_json": json.dumps([]),
                "object_type_constraints_json": json.dumps([]),
                "directionality": "directed",
                "is_clinically_actionable": 0,
                "requires_source_assertion": 0,
                "required_reviewer_roles_json": json.dumps(["UNANI_SCHOLAR"]),
                "allowed_intended_uses_json": json.dumps(["clinician_contextual_reference", "educational_reference"]),
                "ui_display_label": "Source Citation",
                "ui_warning_text": None
            },
            {
                "id": "rtr-canonical-name",
                "code": "has_canonical_name",
                "label": "Has Canonical Name",
                "definition": "Lexical terminology relation specifying the preferred standard name.",
                "relation_class": "terminology",
                "subject_type_constraints_json": json.dumps([]),
                "object_type_constraints_json": json.dumps([]),
                "directionality": "directed",
                "is_clinically_actionable": 0,
                "requires_source_assertion": 0,
                "required_reviewer_roles_json": json.dumps(["UNANI_SCHOLAR"]),
                "allowed_intended_uses_json": json.dumps(["clinician_contextual_reference", "educational_reference"]),
                "ui_display_label": "Canonical Name",
                "ui_warning_text": None
            },
            {
                "id": "rtr-case-hypothesis",
                "code": "clinical_hypothesis_linked_to",
                "label": "Case Hypothesis Link",
                "definition": "Encounter-specific clinician hypothesis linking clinical observation to an ontology concept.",
                "relation_class": "patient_specific",
                "subject_type_constraints_json": json.dumps([]),
                "object_type_constraints_json": json.dumps([]),
                "directionality": "directed",
                "is_clinically_actionable": 1,
                "requires_source_assertion": 0,
                "required_reviewer_roles_json": json.dumps(["CLINICAL_SPECIALIST"]),
                "allowed_intended_uses_json": json.dumps(["clinician_contextual_reference"]),
                "ui_display_label": "Encounter Case Hypothesis",
                "ui_warning_text": "Patient encounter specific record. Never propagated to the global ontology."
            }
        ]

        conn = self.db_manager.get_connection()
        try:
            for item in defaults:
                conn.execute("""
                    INSERT OR IGNORE INTO relation_type_registry (
                        id, code, label, definition, relation_class,
                        subject_type_constraints_json, object_type_constraints_json,
                        directionality, is_clinically_actionable, requires_source_assertion,
                        required_reviewer_roles_json, allowed_intended_uses_json,
                        ui_display_label, ui_warning_text, version, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'APPROVED');
                """, (
                    item["id"], item["code"], item["label"], item["definition"], item["relation_class"],
                    item["subject_type_constraints_json"], item["object_type_constraints_json"],
                    item["directionality"], item["is_clinically_actionable"], item["requires_source_assertion"],
                    item["required_reviewer_roles_json"], item["allowed_intended_uses_json"],
                    item["ui_display_label"], item["ui_warning_text"]
                ))
            conn.commit()
        finally:
            conn.close()

    def list_relation_types(
        self,
        relation_class: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List registered relation types with optional filtering."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM relation_type_registry WHERE 1=1"
            params: List[Any] = []
            if relation_class:
                query += " AND relation_class = ?"
                params.append(relation_class)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY code ASC;"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["subject_type_constraints"] = json.loads(r.get("subject_type_constraints_json") or "[]")
                r["object_type_constraints"] = json.loads(r.get("object_type_constraints_json") or "[]")
                r["required_reviewer_roles"] = json.loads(r.get("required_reviewer_roles_json") or "[]")
                r["allowed_intended_uses"] = json.loads(r.get("allowed_intended_uses_json") or "[]")
            return rows
        finally:
            conn.close()

    def get_relation_type(self, code_or_id: str) -> Dict[str, Any]:
        """Fetch relation type by ID or code."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM relation_type_registry WHERE id = ? OR code = ?;", (code_or_id, code_or_id))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Relation type '{code_or_id}' not found.")
            res = dict(row)
            res["subject_type_constraints"] = json.loads(res.get("subject_type_constraints_json") or "[]")
            res["object_type_constraints"] = json.loads(res.get("object_type_constraints_json") or "[]")
            res["required_reviewer_roles"] = json.loads(res.get("required_reviewer_roles_json") or "[]")
            res["allowed_intended_uses"] = json.loads(res.get("allowed_intended_uses_json") or "[]")
            return res
        finally:
            conn.close()

    def create_relation_type(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Register a new controlled relation type."""
        code = data.get("code")
        label = data.get("label")
        definition = data.get("definition")
        r_class = data.get("relation_class")

        if not code or not label or not definition or not r_class:
            raise ValidationError("code, label, definition, and relation_class are required.")
        if r_class not in VALID_RELATION_CLASSES:
            raise ValidationError(f"Invalid relation_class '{r_class}'. Allowed: {sorted(list(VALID_RELATION_CLASSES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM relation_type_registry WHERE code = ?;", (code,))
            if cur.fetchone():
                raise ConflictError(f"Relation type code '{code}' already exists.")

            rel_id = data.get("id") or f"rtr-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO relation_type_registry (
                    id, code, label, definition, relation_class,
                    subject_type_constraints_json, object_type_constraints_json,
                    directionality, is_clinically_actionable, requires_source_assertion,
                    required_reviewer_roles_json, allowed_intended_uses_json,
                    ui_display_label, ui_warning_text, version, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
            """, (
                rel_id, code, label, definition, r_class,
                json.dumps(data.get("subject_type_constraints", [])),
                json.dumps(data.get("object_type_constraints", [])),
                data.get("directionality", "directed"),
                1 if data.get("is_clinically_actionable") else 0,
                1 if data.get("requires_source_assertion", True) else 0,
                json.dumps(data.get("required_reviewer_roles", ["UNANI_SCHOLAR"])),
                json.dumps(data.get("allowed_intended_uses", ["clinician_contextual_reference"])),
                data.get("ui_display_label", label),
                data.get("ui_warning_text"),
                data.get("status", "APPROVED")
            ))

            self._log_catalog_event(
                conn, "relation_type", rel_id, "CREATE", user_id,
                new_state={"id": rel_id, "code": code, "class": r_class},
                rationale="Registered new relation type in registry"
            )
            conn.commit()
            return self.get_relation_type(rel_id)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Provenance-Bound Relationship Assertions
    # --------------------------------------------------------------------------

    def create_relationship_assertion(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a provenance-bound relationship assertion between concepts.
        Non-negotiable rule: Substantive clinical relationships require assertion_id.
        """
        subject_id = data.get("subject_concept_id")
        predicate_ref = data.get("predicate_type_id") or data.get("predicate_code")
        object_id = data.get("object_concept_id")

        if not subject_id or not predicate_ref or not object_id:
            raise ValidationError("subject_concept_id, predicate_type_id (or predicate_code), and object_concept_id are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            # Verify subject concept
            cur.execute("SELECT id, concept_type, canonical_label FROM knowledge_concepts WHERE id = ?;", (subject_id,))
            sub_row = cur.fetchone()
            if not sub_row:
                raise NotFoundError(f"Subject concept '{subject_id}' not found.")

            # Verify object concept
            cur.execute("SELECT id, concept_type, canonical_label FROM knowledge_concepts WHERE id = ?;", (object_id,))
            obj_row = cur.fetchone()
            if not obj_row:
                raise NotFoundError(f"Object concept '{object_id}' not found.")

            # Verify predicate in registry
            cur.execute("SELECT * FROM relation_type_registry WHERE id = ? OR code = ?;", (predicate_ref, predicate_ref))
            pred_row = cur.fetchone()
            if not pred_row:
                raise NotFoundError(f"Predicate '{predicate_ref}' not found in relation_type_registry.")
            pred = dict(pred_row)

            # Check concept type constraints
            sub_constraints = json.loads(pred.get("subject_type_constraints_json") or "[]")
            if sub_constraints and sub_row["concept_type"] not in sub_constraints:
                raise ValidationError(
                    f"Subject concept type '{sub_row['concept_type']}' not permitted for predicate '{pred['code']}'. "
                    f"Allowed: {sub_constraints}"
                )

            obj_constraints = json.loads(pred.get("object_type_constraints_json") or "[]")
            if obj_constraints and obj_row["concept_type"] not in obj_constraints:
                raise ValidationError(
                    f"Object concept type '{obj_row['concept_type']}' not permitted for predicate '{pred['code']}'. "
                    f"Allowed: {obj_constraints}"
                )

            # Check provenance requirement
            assertion_id = data.get("assertion_id")
            rel_level = data.get("relationship_level", "classical_text")
            if rel_level not in VALID_RELATIONSHIP_LEVELS:
                raise ValidationError(f"Invalid relationship_level '{rel_level}'. Allowed: {sorted(list(VALID_RELATIONSHIP_LEVELS))}")

            if pred["requires_source_assertion"] and not assertion_id:
                raise ValidationError(
                    f"Predicate '{pred['code']}' requires an authentic source assertion (assertion_id). "
                    "Unprovenanced clinical relationships are prohibited."
                )

            if assertion_id:
                cur.execute("SELECT id, review_state FROM knowledge_assertions WHERE id = ?;", (assertion_id,))
                assert_row = cur.fetchone()
                if not assert_row:
                    raise NotFoundError(f"Provenance assertion '{assertion_id}' not found in knowledge_assertions.")

            rel_id = data.get("id") or f"rel-{uuid.uuid4().hex[:12]}"
            polarity = data.get("polarity", "supports")
            if polarity not in VALID_POLARITIES:
                raise ValidationError(f"Invalid polarity '{polarity}'. Allowed: {sorted(list(VALID_POLARITIES))}")

            review_state = data.get("review_state", "draft")
            if review_state not in VALID_RELATION_REVIEW_STATES:
                raise ValidationError(f"Invalid review_state '{review_state}'. Allowed: {sorted(list(VALID_RELATION_REVIEW_STATES))}")

            conn.execute("""
                INSERT INTO relationship_assertions (
                    id, subject_concept_id, predicate_type_id, object_concept_id,
                    assertion_id, relationship_level, scope, context,
                    qualifiers_json, polarity, valid_from, valid_to,
                    review_state, intended_use_approval, version, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
            """, (
                rel_id, subject_id, pred["id"], object_id,
                assertion_id, rel_level, data.get("scope", "global"),
                data.get("context"), json.dumps(data.get("qualifiers", {})),
                polarity, data.get("valid_from"), data.get("valid_to"),
                review_state, data.get("intended_use_approval", "unapproved"),
                user_id
            ))

            self._log_catalog_event(
                conn, "relationship_assertion", rel_id, "CREATE", user_id,
                new_state={"id": rel_id, "subject": subject_id, "predicate": pred["code"], "object": object_id, "level": rel_level},
                rationale="Created provenance-bound relationship assertion"
            )
            conn.commit()
            return self.get_relationship_assertion(rel_id)
        finally:
            conn.close()

    def get_relationship_assertion(self, relation_id: str) -> Dict[str, Any]:
        """Fetch relationship assertion with joined subject, predicate, and object labels."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT ra.*,
                       rtr.code as predicate_code, rtr.label as predicate_label, rtr.relation_class,
                       rtr.ui_display_label as predicate_ui_label, rtr.ui_warning_text,
                       rtr.is_clinically_actionable, rtr.required_reviewer_roles_json,
                       sc.canonical_label as subject_canonical_label, sc.concept_type as subject_concept_type,
                       oc.canonical_label as object_canonical_label, oc.concept_type as object_concept_type,
                       ka.source_quote_exact, ka.page_locator, ka.review_state as assertion_review_state
                FROM relationship_assertions ra
                JOIN relation_type_registry rtr ON ra.predicate_type_id = rtr.id
                JOIN knowledge_concepts sc ON ra.subject_concept_id = sc.id
                JOIN knowledge_concepts oc ON ra.object_concept_id = oc.id
                LEFT JOIN knowledge_assertions ka ON ra.assertion_id = ka.id
                WHERE ra.id = ?;
            """, (relation_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Relationship assertion '{relation_id}' not found.")
            res = dict(row)
            res["qualifiers"] = json.loads(res.get("qualifiers_json") or "{}")
            res["required_reviewer_roles"] = json.loads(res.get("required_reviewer_roles_json") or "[]")
            return res
        finally:
            conn.close()

    def list_relationship_assertions(
        self,
        subject_concept_id: Optional[str] = None,
        object_concept_id: Optional[str] = None,
        predicate_code: Optional[str] = None,
        review_state: Optional[str] = None,
        relationship_level: Optional[str] = None,
        approved_for_clinical: bool = False
    ) -> List[Dict[str, Any]]:
        """List relationship assertions matching filters."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT ra.*,
                       rtr.code as predicate_code, rtr.label as predicate_label, rtr.relation_class,
                       rtr.ui_display_label as predicate_ui_label, rtr.ui_warning_text,
                       rtr.is_clinically_actionable,
                       sc.canonical_label as subject_canonical_label, sc.concept_type as subject_concept_type,
                       oc.canonical_label as object_canonical_label, oc.concept_type as object_concept_type,
                       ka.source_quote_exact, ka.page_locator
                FROM relationship_assertions ra
                JOIN relation_type_registry rtr ON ra.predicate_type_id = rtr.id
                JOIN knowledge_concepts sc ON ra.subject_concept_id = sc.id
                JOIN knowledge_concepts oc ON ra.object_concept_id = oc.id
                LEFT JOIN knowledge_assertions ka ON ra.assertion_id = ka.id
                WHERE 1=1
            """
            params: List[Any] = []
            if subject_concept_id:
                query += " AND ra.subject_concept_id = ?"
                params.append(subject_concept_id)
            if object_concept_id:
                query += " AND ra.object_concept_id = ?"
                params.append(object_concept_id)
            if predicate_code:
                query += " AND rtr.code = ?"
                params.append(predicate_code)
            if review_state:
                query += " AND ra.review_state = ?"
                params.append(review_state)
            if relationship_level:
                query += " AND ra.relationship_level = ?"
                params.append(relationship_level)
            if approved_for_clinical:
                query += " AND ra.review_state = 'approved_for_defined_use' AND ra.relationship_level != 'ui_navigation_grouping'"

            query += " ORDER BY ra.created_at DESC;"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["qualifiers"] = json.loads(r.get("qualifiers_json") or "{}")
            return rows
        finally:
            conn.close()

    def review_relationship_assertion(
        self,
        relation_id: str,
        user_ctx: Dict[str, Any],
        new_state: str,
        rationale: str,
        intended_use_approval: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Review a relationship assertion with role check and decision recording.
        Enforces: ui_navigation_grouping cannot be approved for clinical_decision_support.
        """
        if new_state not in VALID_RELATION_REVIEW_STATES:
            raise ValidationError(f"Invalid review_state '{new_state}'. Allowed: {sorted(list(VALID_RELATION_REVIEW_STATES))}")
        if not rationale or not rationale.strip():
            raise ValidationError("Review rationale is mandatory.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT ra.*, rtr.required_reviewer_roles_json, rtr.code as predicate_code
                FROM relationship_assertions ra
                JOIN relation_type_registry rtr ON ra.predicate_type_id = rtr.id
                WHERE ra.id = ?;
            """, (relation_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Relationship assertion '{relation_id}' not found.")

            roles = set(user_ctx.get("roles", []))
            perms = set(user_ctx.get("permissions", []))
            required_roles = set(json.loads(existing["required_reviewer_roles_json"] or "[]"))

            # Role verification
            if required_roles and not (roles.intersection(required_roles) or "ORG_ADMIN" in roles or "SYSTEM_ADMIN" in roles):
                raise ForbiddenError(f"Review requires one of the following roles: {sorted(list(required_roles))}")

            # Safety check: ui_navigation_grouping cannot be approved for clinical decision support
            if new_state == "approved_for_defined_use":
                if existing["relationship_level"] == "ui_navigation_grouping" and intended_use_approval == "clinical_decision_support":
                    raise ValidationError("UI/navigation groupings cannot be approved for clinical_decision_support.")
                if not intended_use_approval:
                    intended_use_approval = "clinician_contextual_reference"

            conn.execute("""
                UPDATE relationship_assertions
                SET review_state = ?, intended_use_approval = ?, reviewed_by = ?,
                    reviewed_at = CURRENT_TIMESTAMP, decision_rationale = ?
                WHERE id = ?;
            """, (
                new_state,
                intended_use_approval if new_state == "approved_for_defined_use" else existing["intended_use_approval"],
                user_ctx["user_id"],
                rationale.strip(),
                relation_id
            ))

            self._log_catalog_event(
                conn, "relationship_assertion", relation_id, new_state.upper(), user_ctx["user_id"],
                prior_state={"review_state": existing["review_state"]},
                new_state={"review_state": new_state, "intended_use": intended_use_approval},
                rationale=rationale.strip()
            )
            conn.commit()
            return self.get_relationship_assertion(relation_id)
        finally:
            conn.close()

    def withdraw_relationship_assertion(
        self,
        relation_id: str,
        user_ctx: Dict[str, Any],
        rationale: str
    ) -> Dict[str, Any]:
        """Withdraw a relationship assertion permanently with rationale."""
        return self.review_relationship_assertion(relation_id, user_ctx, "withdrawn", rationale)

    # --------------------------------------------------------------------------
    # 3. Versioned Organ-Axis Frameworks & Memberships
    # --------------------------------------------------------------------------

    def seed_default_frameworks(self) -> None:
        """Seed standard product Organ-Axis navigation framework."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users ORDER BY created_at ASC LIMIT 1;")
            user_row = cur.fetchone()
            if not user_row:
                return
            admin_id = user_row[0] if isinstance(user_row, tuple) else user_row["id"]

            conn.execute("""
                INSERT OR IGNORE INTO organ_axis_frameworks (
                    id, name, version, framework_type, description, purpose, limitations,
                    source_basis_json, review_state, approved_use_scope, created_by
                ) VALUES (
                    'oaf-zayvora-axis-v1',
                    'ZAYVORA Standard Organ-Axis Model',
                    '1.0.0',
                    'product_navigation_model',
                    'Standard clinical workspace navigation and contextual functional grouping model organizing Unani organ relationships into functional axes.',
                    'Provides structured clinical consultation navigation and exploratory contextual reference for Unani practitioners.',
                    'Product navigation model only. An Organ-Axis link represents a classical conceptual or navigation grouping; it does NOT constitute modern clinical trial proof of causality or therapeutic efficacy.',
                    '[]',
                    'approved',
                    'navigation_only',
                    ?
                );
            """, (admin_id,))
            conn.commit()
        finally:
            conn.close()

    def create_framework(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Register a versioned Organ-Axis framework."""
        name = data.get("name")
        version = data.get("version", "1.0.0")
        f_type = data.get("framework_type", "product_navigation_model")
        description = data.get("description")
        purpose = data.get("purpose")
        limitations = data.get("limitations")

        if not name or not description or not purpose or not limitations:
            raise ValidationError("name, description, purpose, and limitations are required.")
        if f_type not in VALID_FRAMEWORK_TYPES:
            raise ValidationError(f"Invalid framework_type '{f_type}'. Allowed: {sorted(list(VALID_FRAMEWORK_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM organ_axis_frameworks WHERE name = ? AND version = ?;", (name, version))
            if cur.fetchone():
                raise ConflictError(f"Framework '{name}' version '{version}' already exists.")

            fw_id = data.get("id") or f"oaf-{uuid.uuid4().hex[:12]}"
            app_scope = data.get("approved_use_scope", "navigation_only")
            if f_type == "product_navigation_model" and app_scope == "clinical_decision_support":
                raise ValidationError("product_navigation_model frameworks cannot have approved_use_scope='clinical_decision_support'.")

            conn.execute("""
                INSERT INTO organ_axis_frameworks (
                    id, name, version, framework_type, description, purpose, limitations,
                    source_basis_json, review_state, approved_use_scope, effective_from,
                    effective_to, supersedes_id, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                fw_id, name, version, f_type, description, purpose, limitations,
                json.dumps(data.get("source_basis", [])),
                data.get("review_state", "draft"),
                app_scope,
                data.get("effective_from"), data.get("effective_to"),
                data.get("supersedes_id"), user_id
            ))

            self._log_catalog_event(
                conn, "organ_axis_framework", fw_id, "CREATE", user_id,
                new_state={"id": fw_id, "name": name, "version": version, "type": f_type},
                rationale="Registered new versioned Organ-Axis framework"
            )
            conn.commit()
            return self.get_framework(fw_id)
        finally:
            conn.close()

    def get_framework(self, framework_id: str) -> Dict[str, Any]:
        """Fetch framework details and list its axis memberships."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM organ_axis_frameworks WHERE id = ?;", (framework_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Framework '{framework_id}' not found.")
            res = dict(row)
            res["source_basis"] = json.loads(res.get("source_basis_json") or "[]")
            return res
        finally:
            conn.close()

    def list_frameworks(
        self,
        framework_type: Optional[str] = None,
        review_state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Organ-Axis frameworks with optional filtering."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM organ_axis_frameworks WHERE 1=1"
            params: List[Any] = []
            if framework_type:
                query += " AND framework_type = ?"
                params.append(framework_type)
            if review_state:
                query += " AND review_state = ?"
                params.append(review_state)
            query += " ORDER BY name ASC, version DESC;"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["source_basis"] = json.loads(r.get("source_basis_json") or "[]")
            return rows
        finally:
            conn.close()

    def publish_framework(
        self,
        framework_id: str,
        user_ctx: Dict[str, Any],
        review_state: str,
        approved_use_scope: str,
        rationale: str
    ) -> Dict[str, Any]:
        """Publish / approve an Organ-Axis framework."""
        if review_state not in VALID_FRAMEWORK_REVIEW_STATES:
            raise ValidationError(f"Invalid review_state '{review_state}'.")
        if approved_use_scope not in VALID_APPROVED_USE_SCOPES:
            raise ValidationError(f"Invalid approved_use_scope '{approved_use_scope}'.")
        if not rationale or not rationale.strip():
            raise ValidationError("Publication rationale is mandatory.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM organ_axis_frameworks WHERE id = ?;", (framework_id,))
            fw = cur.fetchone()
            if not fw:
                raise NotFoundError(f"Framework '{framework_id}' not found.")

            if fw["framework_type"] == "product_navigation_model" and approved_use_scope == "clinical_decision_support":
                raise ValidationError("product_navigation_model frameworks cannot be approved for clinical_decision_support.")

            conn.execute("""
                UPDATE organ_axis_frameworks
                SET review_state = ?, approved_use_scope = ?, reviewed_by = ?,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (review_state, approved_use_scope, user_ctx["user_id"], framework_id))

            self._log_catalog_event(
                conn, "organ_axis_framework", framework_id, review_state.upper(), user_ctx["user_id"],
                prior_state={"review_state": fw["review_state"]},
                new_state={"review_state": review_state, "scope": approved_use_scope},
                rationale=rationale.strip()
            )
            conn.commit()
            return self.get_framework(framework_id)
        finally:
            conn.close()

    def add_framework_membership(
        self,
        framework_id: str,
        data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Add a concept to an axis within an Organ-Axis framework.
        Enforces: Source-documented or reviewed-clinical memberships require assertion_id.
        """
        concept_id = data.get("concept_id")
        axis_name = data.get("axis_name")
        m_type = data.get("membership_type", "navigation_group")

        if not concept_id or not axis_name:
            raise ValidationError("concept_id and axis_name are required.")
        if m_type not in VALID_MEMBERSHIP_TYPES:
            raise ValidationError(f"Invalid membership_type '{m_type}'. Allowed: {sorted(list(VALID_MEMBERSHIP_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            # Verify framework
            cur.execute("SELECT id FROM organ_axis_frameworks WHERE id = ?;", (framework_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Framework '{framework_id}' not found.")

            # Verify concept
            cur.execute("SELECT id, canonical_label FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Concept '{concept_id}' not found.")

            assertion_id = data.get("assertion_id")
            if m_type in {"source_documented_membership", "reviewed_clinical_membership"} and not assertion_id:
                raise ValidationError(f"Membership type '{m_type}' requires a valid assertion_id link.")

            mem_id = data.get("id") or f"oam-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO organ_axis_memberships (
                    id, framework_id, concept_id, axis_name, membership_type,
                    assertion_id, display_order, review_state, limitations, version, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
            """, (
                mem_id, framework_id, concept_id, axis_name.upper(), m_type,
                assertion_id, data.get("display_order", 0),
                data.get("review_state", "draft"),
                data.get("limitations"), user_id
            ))

            self._log_catalog_event(
                conn, "organ_axis_membership", mem_id, "CREATE", user_id,
                new_state={"framework_id": framework_id, "concept_id": concept_id, "axis": axis_name.upper()},
                rationale="Added concept to Organ-Axis framework"
            )
            conn.commit()

            cur.execute("""
                SELECT oam.*, kc.canonical_label as concept_label, kc.concept_type
                FROM organ_axis_memberships oam
                JOIN knowledge_concepts kc ON oam.concept_id = kc.id
                WHERE oam.id = ?;
            """, (mem_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def list_framework_memberships(
        self,
        framework_id: str,
        axis_name: Optional[str] = None,
        review_state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List memberships for a framework."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT oam.*, kc.canonical_label as concept_label, kc.concept_type,
                       ka.source_quote_exact, ka.page_locator
                FROM organ_axis_memberships oam
                JOIN knowledge_concepts kc ON oam.concept_id = kc.id
                LEFT JOIN knowledge_assertions ka ON oam.assertion_id = ka.id
                WHERE oam.framework_id = ?
            """
            params: List[Any] = [framework_id]
            if axis_name:
                query += " AND oam.axis_name = ?"
                params.append(axis_name.upper())
            if review_state:
                query += " AND oam.review_state = ?"
                params.append(review_state)
            query += " ORDER BY oam.axis_name ASC, oam.display_order ASC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Cross-Disciplinary Concept Mappings (ICD-11, SNOMED, etc.)
    # --------------------------------------------------------------------------

    def create_concept_mapping(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a cross-system concept mapping.
        Preserves mapping type (exact, broader_than, candidate_equivalence, no_safe_mapping).
        Quarantines candidate equivalence from clinical decision support.
        """
        source_concept_id = data.get("source_concept_id")
        target_system = data.get("target_system")
        target_identifier = data.get("target_identifier")
        target_label = data.get("target_label")
        mapping_type = data.get("mapping_type", "related_to")

        if not source_concept_id or not target_system or not target_identifier or not target_label:
            raise ValidationError("source_concept_id, target_system, target_identifier, and target_label are required.")
        if target_system not in VALID_TARGET_SYSTEMS:
            raise ValidationError(f"Invalid target_system '{target_system}'. Allowed: {sorted(list(VALID_TARGET_SYSTEMS))}")
        if mapping_type not in VALID_MAPPING_TYPES:
            raise ValidationError(f"Invalid mapping_type '{mapping_type}'. Allowed: {sorted(list(VALID_MAPPING_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, canonical_label FROM knowledge_concepts WHERE id = ?;", (source_concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Source concept '{source_concept_id}' not found.")

            map_id = data.get("id") or f"cpm-{uuid.uuid4().hex[:12]}"
            review_state = data.get("review_state", "draft")

            conn.execute("""
                INSERT INTO concept_mappings (
                    id, source_concept_id, target_system, target_system_version,
                    target_identifier, target_label, mapping_type, mapping_scope,
                    limitations, evidence_assertion_id, review_state,
                    approved_intended_use, version, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
            """, (
                map_id, source_concept_id, target_system,
                data.get("target_system_version"), target_identifier, target_label,
                mapping_type, data.get("mapping_scope", "general"),
                data.get("limitations"), data.get("evidence_assertion_id"),
                review_state, data.get("approved_intended_use", "unapproved"),
                user_id
            ))

            self._log_catalog_event(
                conn, "concept_mapping", map_id, "CREATE", user_id,
                new_state={"id": map_id, "source": source_concept_id, "target_system": target_system, "target_id": target_identifier, "type": mapping_type},
                rationale="Registered cross-disciplinary concept mapping"
            )
            conn.commit()
            return self.get_concept_mapping(map_id)
        finally:
            conn.close()

    def get_concept_mapping(self, mapping_id: str) -> Dict[str, Any]:
        """Fetch cross-disciplinary concept mapping details."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT cm.*, kc.canonical_label as source_concept_label, kc.concept_type as source_concept_type,
                       ka.source_quote_exact, ka.page_locator
                FROM concept_mappings cm
                JOIN knowledge_concepts kc ON cm.source_concept_id = kc.id
                LEFT JOIN knowledge_assertions ka ON cm.evidence_assertion_id = ka.id
                WHERE cm.id = ?;
            """, (mapping_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Concept mapping '{mapping_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    def list_concept_mappings(
        self,
        source_concept_id: Optional[str] = None,
        target_system: Optional[str] = None,
        review_state: Optional[str] = None,
        mapping_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List cross-disciplinary mappings."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT cm.*, kc.canonical_label as source_concept_label, kc.concept_type as source_concept_type
                FROM concept_mappings cm
                JOIN knowledge_concepts kc ON cm.source_concept_id = kc.id
                WHERE 1=1
            """
            params: List[Any] = []
            if source_concept_id:
                query += " AND cm.source_concept_id = ?"
                params.append(source_concept_id)
            if target_system:
                query += " AND cm.target_system = ?"
                params.append(target_system)
            if review_state:
                query += " AND cm.review_state = ?"
                params.append(review_state)
            if mapping_type:
                query += " AND cm.mapping_type = ?"
                params.append(mapping_type)
            query += " ORDER BY cm.target_system ASC, cm.created_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def review_concept_mapping(
        self,
        mapping_id: str,
        user_ctx: Dict[str, Any],
        new_state: str,
        approved_intended_use: Optional[str] = None,
        rationale: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Review concept mapping.
        Enforces: candidate_equivalence cannot be approved for clinical_decision_support.
        """
        if new_state not in VALID_MAPPING_REVIEW_STATES:
            raise ValidationError(f"Invalid review_state '{new_state}'. Allowed: {sorted(list(VALID_MAPPING_REVIEW_STATES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM concept_mappings WHERE id = ?;", (mapping_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Concept mapping '{mapping_id}' not found.")

            if new_state == "approved":
                if existing["mapping_type"] == "candidate_equivalence" and approved_intended_use == "clinical_decision_support":
                    raise ValidationError("candidate_equivalence mappings cannot be approved for clinical_decision_support.")
                if not approved_intended_use:
                    approved_intended_use = "clinician_contextual_reference"

            conn.execute("""
                UPDATE concept_mappings
                SET review_state = ?, approved_intended_use = ?, reviewer_id = ?,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (
                new_state,
                approved_intended_use if new_state == "approved" else existing["approved_intended_use"],
                user_ctx["user_id"],
                mapping_id
            ))

            self._log_catalog_event(
                conn, "concept_mapping", mapping_id, new_state.upper(), user_ctx["user_id"],
                prior_state={"review_state": existing["review_state"]},
                new_state={"review_state": new_state, "intended_use": approved_intended_use},
                rationale=rationale
            )
            conn.commit()
            return self.get_concept_mapping(mapping_id)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Relationship Conflicts Adjudication
    # --------------------------------------------------------------------------

    def report_conflict(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Report a conflict between two assertions."""
        assertion_id = data.get("assertion_id")
        conflicting_id = data.get("conflicting_assertion_id")
        description = data.get("description")
        conflict_type = data.get("conflict_type", "source_disagreement")

        if not assertion_id or not conflicting_id or not description:
            raise ValidationError("assertion_id, conflicting_assertion_id, and description are required.")
        if conflict_type not in VALID_CONFLICT_TYPES:
            raise ValidationError(f"Invalid conflict_type '{conflict_type}'. Allowed: {sorted(list(VALID_CONFLICT_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_assertions WHERE id = ?;", (assertion_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Assertion '{assertion_id}' not found.")
            cur.execute("SELECT id FROM knowledge_assertions WHERE id = ?;", (conflicting_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Conflicting assertion '{conflicting_id}' not found.")

            conflict_id = data.get("id") or f"rcf-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO relationship_conflicts (
                    id, assertion_id, conflicting_assertion_id, conflict_type,
                    description, resolution_state
                ) VALUES (?, ?, ?, ?, ?, 'open');
            """, (conflict_id, assertion_id, conflicting_id, conflict_type, description))

            self._log_catalog_event(
                conn, "relationship_conflict", conflict_id, "OPEN", user_id,
                new_state={"id": conflict_id, "assert_1": assertion_id, "assert_2": conflicting_id, "type": conflict_type},
                rationale="Reported relationship assertion conflict"
            )
            conn.commit()
            return self.get_conflict(conflict_id)
        finally:
            conn.close()

    def get_conflict(self, conflict_id: str) -> Dict[str, Any]:
        """Fetch conflict details."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT rc.*,
                       a1.source_quote_exact as quote_1, a1.page_locator as locator_1,
                       a2.source_quote_exact as quote_2, a2.page_locator as locator_2
                FROM relationship_conflicts rc
                JOIN knowledge_assertions a1 ON rc.assertion_id = a1.id
                JOIN knowledge_assertions a2 ON rc.conflicting_assertion_id = a2.id
                WHERE rc.id = ?;
            """, (conflict_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Conflict '{conflict_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    def list_conflicts(
        self,
        resolution_state: Optional[str] = None,
        conflict_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List conflicts with optional filters."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM relationship_conflicts WHERE 1=1"
            params: List[Any] = []
            if resolution_state:
                query += " AND resolution_state = ?"
                params.append(resolution_state)
            if conflict_type:
                query += " AND conflict_type = ?"
                params.append(conflict_type)
            query += " ORDER BY created_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def adjudicate_conflict(
        self,
        conflict_id: str,
        user_ctx: Dict[str, Any],
        resolution_state: str,
        resolution_rationale: str
    ) -> Dict[str, Any]:
        """Adjudicate a relationship conflict."""
        if resolution_state not in VALID_RESOLUTION_STATES:
            raise ValidationError(f"Invalid resolution_state '{resolution_state}'. Allowed: {sorted(list(VALID_RESOLUTION_STATES))}")
        if not resolution_rationale or not resolution_rationale.strip():
            raise ValidationError("resolution_rationale is mandatory for conflict adjudication.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM relationship_conflicts WHERE id = ?;", (conflict_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Conflict '{conflict_id}' not found.")

            conn.execute("""
                UPDATE relationship_conflicts
                SET resolution_state = ?, resolution_rationale = ?,
                    resolved_by = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (resolution_state, resolution_rationale.strip(), user_ctx["user_id"], conflict_id))

            self._log_catalog_event(
                conn, "relationship_conflict", conflict_id, "ADJUDICATE", user_ctx["user_id"],
                prior_state={"resolution_state": existing["resolution_state"]},
                new_state={"resolution_state": resolution_state},
                rationale=resolution_rationale.strip()
            )
            conn.commit()
            return self.get_conflict(conflict_id)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. Encounter-Scoped Case Hypotheses (Protected Patient Clinical Record)
    # --------------------------------------------------------------------------

    def create_encounter_hypothesis(
        self,
        encounter_id: str,
        data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Record an encounter-scoped case hypothesis.
        Non-negotiable rule: Encounter hypotheses remain protected clinical patient
        data and are strictly isolated from the global ontology/knowledge graph.
        """
        concept_id = data.get("concept_id")
        rel_code = data.get("relation_type_code", "clinical_hypothesis_linked_to")
        hypo_text = data.get("hypothesis_text")

        if not concept_id or not hypo_text or not hypo_text.strip():
            raise ValidationError("concept_id and hypothesis_text are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            # Verify encounter exists
            cur.execute("SELECT id FROM encounters WHERE id = ?;", (encounter_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Encounter '{encounter_id}' not found.")

            # Verify concept exists
            cur.execute("SELECT id, canonical_label FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Concept '{concept_id}' not found.")

            hypo_id = data.get("id") or f"chl-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO case_hypothesis_links (
                    id, encounter_id, concept_id, relation_type_code,
                    clinical_note_reference, hypothesis_text, author_id,
                    status, supporting_observation_ids_json, referenced_assertion_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?);
            """, (
                hypo_id, encounter_id, concept_id, rel_code,
                data.get("clinical_note_reference"), hypo_text.strip(), user_id,
                json.dumps(data.get("supporting_observation_ids", [])),
                json.dumps(data.get("referenced_assertion_ids", []))
            ))
            conn.commit()

            cur.execute("""
                SELECT chl.*, kc.canonical_label as concept_label, kc.concept_type
                FROM case_hypothesis_links chl
                JOIN knowledge_concepts kc ON chl.concept_id = kc.id
                WHERE chl.id = ?;
            """, (hypo_id,))
            res = dict(cur.fetchone())
            res["supporting_observation_ids"] = json.loads(res.get("supporting_observation_ids_json") or "[]")
            res["referenced_assertion_ids"] = json.loads(res.get("referenced_assertion_ids_json") or "[]")
            return res
        finally:
            conn.close()

    def list_encounter_hypotheses(
        self,
        encounter_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List hypotheses for a given patient encounter."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = """
                SELECT chl.*, kc.canonical_label as concept_label, kc.concept_type
                FROM case_hypothesis_links chl
                JOIN knowledge_concepts kc ON chl.concept_id = kc.id
                WHERE chl.encounter_id = ?
            """
            params: List[Any] = [encounter_id]
            if status:
                query += " AND chl.status = ?"
                params.append(status)
            query += " ORDER BY chl.created_at ASC;"
            cur.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["supporting_observation_ids"] = json.loads(r.get("supporting_observation_ids_json") or "[]")
                r["referenced_assertion_ids"] = json.loads(r.get("referenced_assertion_ids_json") or "[]")
            return rows
        finally:
            conn.close()

    def update_encounter_hypothesis_status(
        self,
        hypothesis_id: str,
        encounter_id: str,
        status: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Update status of an encounter hypothesis (e.g. considered, resolved, rejected)."""
        if status not in VALID_HYPOTHESIS_STATUSES:
            raise ValidationError(f"Invalid status '{status}'. Allowed: {sorted(list(VALID_HYPOTHESIS_STATUSES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM case_hypothesis_links WHERE id = ? AND encounter_id = ?;", (hypothesis_id, encounter_id))
            if not cur.fetchone():
                raise NotFoundError(f"Hypothesis '{hypothesis_id}' not found in encounter '{encounter_id}'.")

            conn.execute("""
                UPDATE case_hypothesis_links
                SET status = ?
                WHERE id = ?;
            """, (status, hypothesis_id))
            conn.commit()

            cur.execute("""
                SELECT chl.*, kc.canonical_label as concept_label, kc.concept_type
                FROM case_hypothesis_links chl
                JOIN knowledge_concepts kc ON chl.concept_id = kc.id
                WHERE chl.id = ?;
            """, (hypothesis_id,))
            res = dict(cur.fetchone())
            res["supporting_observation_ids"] = json.loads(res.get("supporting_observation_ids_json") or "[]")
            res["referenced_assertion_ids"] = json.loads(res.get("referenced_assertion_ids_json") or "[]")
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. Bounded Graph Traversal & Querying Engine (No Transitive Inference)
    # --------------------------------------------------------------------------

    def traverse_knowledge_graph(
        self,
        concept_id: str,
        max_depth: int = 2,
        include_navigation: bool = False,
        clinical_mode: bool = True,
        target_concept_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Bounded, cycle-detected traversal from a start concept.
        Non-negotiable rules:
        - Strict depth limit (max 3).
        - Clinical mode only returns approved, non-disputed, non-withdrawn assertions.
        - UI/navigation edges are strictly isolated unless include_navigation=True.
        - NEVER synthesizes or infers a direct fact A -> C from A -> B -> C.
        """
        max_depth = min(max(1, max_depth), 3)

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, canonical_label, concept_type FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            root = cur.fetchone()
            if not root:
                raise NotFoundError(f"Concept '{concept_id}' not found.")

            nodes: Dict[str, Dict[str, Any]] = {root["id"]: dict(root)}
            edges: List[Dict[str, Any]] = []
            paths: List[List[str]] = []

            # BFS queue: (current_node_id, current_depth, current_path)
            queue: List[Tuple[str, int, List[str]]] = [(root["id"], 0, [root["id"]])]
            visited_edges: Set[str] = set()

            while queue:
                curr_id, depth, path = queue.pop(0)

                if depth >= max_depth:
                    continue

                # Query outward edges from curr_id
                query = """
                    SELECT ra.id, ra.subject_concept_id, ra.object_concept_id,
                           ra.relationship_level, ra.polarity, ra.review_state,
                           ra.intended_use_approval, ra.assertion_id,
                           rtr.code as predicate_code, rtr.label as predicate_label,
                           rtr.relation_class, rtr.ui_warning_text,
                           oc.id as target_id, oc.canonical_label as target_label, oc.concept_type as target_type,
                           ka.source_quote_exact, ka.page_locator
                    FROM relationship_assertions ra
                    JOIN relation_type_registry rtr ON ra.predicate_type_id = rtr.id
                    JOIN knowledge_concepts oc ON ra.object_concept_id = oc.id
                    LEFT JOIN knowledge_assertions ka ON ra.assertion_id = ka.id
                    WHERE ra.subject_concept_id = ?
                """
                params: List[Any] = [curr_id]

                if clinical_mode:
                    query += " AND ra.review_state = 'approved_for_defined_use' AND ra.polarity = 'supports'"
                    query += " AND ra.relationship_level != 'ui_navigation_grouping'"
                else:
                    query += " AND ra.review_state NOT IN ('rejected', 'withdrawn')"

                if not include_navigation:
                    query += " AND ra.relationship_level != 'ui_navigation_grouping' AND rtr.relation_class != 'product_navigation'"

                cur.execute(query, params)
                neighbors = cur.fetchall()

                for nb in neighbors:
                    edge_id = nb["id"]
                    target_id = nb["target_id"]

                    if edge_id in visited_edges:
                        continue
                    visited_edges.add(edge_id)

                    edge_dict = {
                        "id": edge_id,
                        "subject_concept_id": nb["subject_concept_id"],
                        "predicate_code": nb["predicate_code"],
                        "predicate_label": nb["predicate_label"],
                        "relation_class": nb["relation_class"],
                        "object_concept_id": target_id,
                        "relationship_level": nb["relationship_level"],
                        "review_state": nb["review_state"],
                        "polarity": nb["polarity"],
                        "assertion_id": nb["assertion_id"],
                        "source_quote_exact": nb["source_quote_exact"],
                        "page_locator": nb["page_locator"],
                        "ui_warning": nb["ui_warning_text"]
                    }
                    edges.append(edge_dict)

                    if target_id not in nodes:
                        nodes[target_id] = {
                            "id": target_id,
                            "canonical_label": nb["target_label"],
                            "concept_type": nb["target_type"]
                        }

                    new_path = path + [target_id]
                    paths.append(new_path)

                    if target_concept_id and target_id == target_concept_id:
                        # Reached requested target concept
                        pass
                    elif target_id not in path: # Avoid cycle loop
                        queue.append((target_id, depth + 1, new_path))

            return {
                "root_concept": dict(root),
                "nodes": list(nodes.values()),
                "edges": edges,
                "paths": paths,
                "traversal_warning": (
                    "Graph traversal represents individual asserted relationships only. "
                    "Adjacency or multi-step path reachability does NOT prove transitive clinical causality, "
                    "efficacy, or safety. Autonomous transitive inferences (A -> C) are prohibited."
                )
            }
        finally:
            conn.close()
