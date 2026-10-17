"""Unani Ontology, Canonical Terminology, Mufradat & Murakkabat Structured Catalog.

Phase 19 Domain Engine for ZAYVORA MATAB OS.
Enforces non-negotiable knowledge principles:
- Absolute prohibition against hallucinated clinical concepts, dosages, and identities.
- Clear separation between concept identity and clinical assertions.
- Multi-script fidelity (Original script, transliteration, normalized text).
- Mufradat material identity ambiguity representation.
- Murakkabat source-specific formulations with preserved raw traditional notations.
- Graph edge non-inference: Relations require provenance assertions; adjacency != proof.
- Candidate equivalence and unapproved aliases strictly blocked from clinician-facing decision support.
- Append-only audit ledger of catalog change events.
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
# Controlled Vocabularies & Ontology Registries
# --------------------------------------------------------------------------

VALID_CONCEPT_TYPES: Set[str] = {
    "unani_term", "clinical_process", "organ_or_structure", "material",
    "ingredient", "formulation", "dosage_form", "preparation_method",
    "assessment_concept", "external_concept"
}

VALID_NAME_TYPES: Set[str] = {
    "source_name", "preferred_label", "synonym", "variant_spelling",
    "regional_name", "historical_name", "trade_name", "common_name",
    "scientific_name", "candidate_alias"
}

VALID_MATERIAL_CLASSES: Set[str] = {
    "botanical", "animal_derived", "mineral", "metal", "salt",
    "processed_material", "other", "unknown"
}

VALID_FORMULATION_CLASSES: Set[str] = {
    "majoon", "safoof", "sharbat", "hab", "qurs", "khamira",
    "joshanda", "roghan", "arq", "itrifal", "kushta", "marham", "tila", "unknown"
}

VALID_ASSERTION_SCOPES: Set[str] = {
    "identity", "terminology", "composition", "preparation",
    "historical", "traditional_use", "clinical", "safety", "regulatory", "other"
}

VALID_PREDICATES: Set[str] = {
    "has_mizaj", "has_action", "indicated_for", "contraindicated_in",
    "has_adverse_effect", "has_corrective", "has_substitute", "has_dose",
    "has_part", "prepared_by", "has_definition", "has_synonym",
    "composed_of", "variant_of", "classified_under", "associated_organ"
}

VALID_MAPPING_TYPES: Set[str] = {
    "exact", "broader_than", "narrower_than", "related_to",
    "candidate_equivalence", "no_safe_mapping"
}

VALID_INTENDED_USES: Set[str] = {
    "clinician_contextual_reference", "formulation_catalog_reference",
    "safety_firewall_rule", "educational_reference", "unapproved"
}

VALID_ASSERTION_REVIEW_STATES: Set[str] = {
    "draft", "source_check_required", "extraction_review_required",
    "expert_review_required", "changes_requested", "approved_for_defined_use",
    "rejected", "deprecated", "withdrawn"
}


class UnaniOntologyEngine:
    """Core domain service for Unani terminology, Mufradat/Murakkabat catalog, and knowledge assertions."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)

    # --------------------------------------------------------------------------
    # Utility Methods
    # --------------------------------------------------------------------------

    @staticmethod
    def normalize_text(text: Optional[str]) -> str:
        """Derive normalized text for search indexing without overwriting original wording."""
        if not text:
            return ""
        norm = text.lower().strip()
        # Strip Arabic/Urdu/Persian diacritics (harakat/aerab)
        norm = re.sub(r"[\u064B-\u065F\u0670]", "", norm)
        norm = re.sub(r"[^\w\s\-]", " ", norm)
        return re.sub(r"\s+", " ", norm).strip()

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
    # 1. Canonical Concepts Identity
    # --------------------------------------------------------------------------

    def create_concept(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Create a stable concept identity. Separates concept identity from clinical claims."""
        concept_type = data.get("concept_type")
        canonical_label = data.get("canonical_label")

        if not concept_type or concept_type not in VALID_CONCEPT_TYPES:
            raise ValidationError(f"Invalid concept_type '{concept_type}'. Allowed: {sorted(list(VALID_CONCEPT_TYPES))}")
        if not canonical_label or not canonical_label.strip():
            raise ValidationError("canonical_label is required and cannot be empty.")

        concept_id = data.get("id") or f"cpt-{uuid.uuid4().hex[:12]}"
        status = data.get("status", "draft")
        resolution_state = data.get("identity_resolution_state", "unresolved")

        conn = self.db_manager.get_connection()
        try:
            conn.execute("""
                INSERT INTO knowledge_concepts (
                    id, concept_type, canonical_label, definition_assertion_id,
                    status, identity_resolution_state, version, review_notes, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?);
            """, (
                concept_id, concept_type, canonical_label.strip(),
                data.get("definition_assertion_id"), status, resolution_state,
                data.get("review_notes"), user_id
            ))

            # Automatically register the preferred display name if provided
            preferred_name = data.get("preferred_name") or canonical_label.strip()
            name_id = f"cnm-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO concept_names (
                    id, concept_id, name_text_original, script, language_tag,
                    transliteration, normalized_search_text, name_type, review_state, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'preferred_label', 'draft', ?);
            """, (
                name_id, concept_id, preferred_name,
                data.get("script", "latin"), data.get("language_tag", "en"),
                data.get("transliteration"), self.normalize_text(preferred_name),
                user_id
            ))

            # Create review task
            task_id = f"crt-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO catalog_review_tasks (
                    id, entity_type, entity_id, task_type, priority, status, assigned_role
                ) VALUES (?, 'concept', ?, 'TERMINOLOGY_TRANSLITERATION', 'MEDIUM', 'PENDING', 'UNANI_SCHOLAR');
            """, (task_id, concept_id))

            # Log change event
            self._log_catalog_event(
                conn, "concept", concept_id, "CREATE", user_id,
                new_state={"id": concept_id, "type": concept_type, "label": canonical_label.strip()},
                rationale=data.get("review_notes") or "Created initial concept identity draft"
            )

            conn.commit()
            return self.get_concept(concept_id, include_unapproved=True)
        finally:
            conn.close()

    def get_concept(self, concept_id: str, include_unapproved: bool = False) -> Dict[str, Any]:
        """Fetch concept with names, material identity, formulation metadata, assertions, and crosswalks."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Knowledge concept '{concept_id}' not found.")
            concept = dict(row)

            # Names
            names_query = "SELECT * FROM concept_names WHERE concept_id = ?"
            params = [concept_id]
            if not include_unapproved:
                names_query += " AND review_state = 'approved'"
            names_query += " ORDER BY created_at ASC;"
            cur.execute(names_query, tuple(params))
            concept["names"] = [dict(r) for r in cur.fetchall()]

            # Material Identity (Mufradat)
            cur.execute("SELECT * FROM material_identity WHERE concept_id = ?;", (concept_id,))
            mat_row = cur.fetchone()
            concept["material_identity"] = dict(mat_row) if mat_row else None

            # Formulation (Murakkabat)
            cur.execute("SELECT * FROM catalog_formulations WHERE concept_id = ?;", (concept_id,))
            form_row = cur.fetchone()
            if form_row:
                form_dict = dict(form_row)
                cur.execute("""
                    SELECT fi.*, kc.canonical_label as material_label
                    FROM catalog_formulation_ingredients fi
                    LEFT JOIN knowledge_concepts kc ON fi.material_concept_id = kc.id
                    WHERE fi.formulation_id = ?
                    ORDER BY fi.sequence_index ASC, fi.created_at ASC;
                """, (form_dict["id"],))
                form_dict["ingredients"] = [dict(r) for r in cur.fetchall()]
                concept["formulation"] = form_dict
            else:
                concept["formulation"] = None

            # Assertions
            assert_query = "SELECT * FROM knowledge_assertions WHERE subject_concept_id = ?"
            assert_params = [concept_id]
            if not include_unapproved:
                assert_query += " AND review_state = 'approved_for_defined_use'"
            assert_query += " ORDER BY created_at ASC;"
            cur.execute(assert_query, tuple(assert_params))
            concept["assertions"] = [dict(r) for r in cur.fetchall()]

            # Relations
            rel_query = """
                SELECT cr.*, kc.canonical_label as object_label, kc.concept_type as object_type
                FROM concept_relations cr
                JOIN knowledge_concepts kc ON cr.object_concept_id = kc.id
                WHERE cr.subject_concept_id = ?
            """
            rel_params = [concept_id]
            if not include_unapproved:
                rel_query += " AND cr.status = 'approved'"
            rel_query += " ORDER BY cr.created_at ASC;"
            cur.execute(rel_query, tuple(rel_params))
            concept["relations"] = [dict(r) for r in cur.fetchall()]

            # Crosswalks
            cw_query = "SELECT * FROM external_identifier_crosswalks WHERE concept_id = ?"
            cw_params = [concept_id]
            if not include_unapproved:
                cw_query += " AND status = 'approved' AND mapping_type != 'candidate_equivalence'"
            cw_query += " ORDER BY system_label ASC;"
            cur.execute(cw_query, tuple(cw_params))
            concept["crosswalks"] = [dict(r) for r in cur.fetchall()]

            return concept
        finally:
            conn.close()

    def update_concept(self, concept_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Update concept identity with optimistic concurrency version check."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Knowledge concept '{concept_id}' not found.")

            # Concurrency check
            if "version" in data and data["version"] != existing["version"]:
                raise ConflictError(f"Version mismatch: current version is {existing['version']}, update submitted for version {data['version']}.")

            prior_state = dict(existing)
            new_label = data.get("canonical_label", existing["canonical_label"]).strip()
            new_status = data.get("status", existing["status"])
            new_resolution = data.get("identity_resolution_state", existing["identity_resolution_state"])
            new_notes = data.get("review_notes", existing["review_notes"])
            new_version = existing["version"] + 1

            conn.execute("""
                UPDATE knowledge_concepts
                SET canonical_label = ?, status = ?, identity_resolution_state = ?,
                    review_notes = ?, version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_label, new_status, new_resolution, new_notes, new_version, user_id, concept_id))

            new_state = {
                "id": concept_id, "canonical_label": new_label,
                "status": new_status, "identity_resolution_state": new_resolution, "version": new_version
            }
            self._log_catalog_event(
                conn, "concept", concept_id, "UPDATE", user_id,
                prior_state=prior_state, new_state=new_state,
                rationale=data.get("rationale") or "Updated concept metadata"
            )

            conn.commit()
            return self.get_concept(concept_id, include_unapproved=True)
        finally:
            conn.close()

    def list_concepts(self, filters: Optional[Dict[str, Any]] = None, include_unapproved: bool = False) -> List[Dict[str, Any]]:
        """List concepts with optional filtering."""
        filters = filters or {}
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM knowledge_concepts WHERE 1=1"
            params = []

            if not include_unapproved:
                query += " AND status = 'approved_identity'"
            elif filters.get("status"):
                query += " AND status = ?"
                params.append(filters["status"])

            if filters.get("concept_type"):
                query += " AND concept_type = ?"
                params.append(filters["concept_type"])

            if filters.get("identity_resolution_state"):
                query += " AND identity_resolution_state = ?"
                params.append(filters["identity_resolution_state"])

            query += " ORDER BY canonical_label ASC LIMIT ?;"
            params.append(int(filters.get("limit", 50)))

            cur.execute(query, tuple(params))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Multi-Script Concept Names & Aliases
    # --------------------------------------------------------------------------

    def add_concept_name(self, concept_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Add a name, alias, or transliteration. Preserves original script and wording."""
        name_text = data.get("name_text_original")
        if not name_text or not name_text.strip():
            raise ValidationError("name_text_original is required.")

        name_type = data.get("name_type", "synonym")
        if name_type not in VALID_NAME_TYPES:
            raise ValidationError(f"Invalid name_type '{name_type}'. Allowed: {sorted(list(VALID_NAME_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Concept '{concept_id}' not found.")

            name_id = data.get("id") or f"cnm-{uuid.uuid4().hex[:12]}"
            norm_text = self.normalize_text(name_text)

            conn.execute("""
                INSERT INTO concept_names (
                    id, concept_id, name_text_original, script, language_tag,
                    transliteration, transliteration_scheme, normalized_search_text,
                    name_type, source_passage_id, assertion_id, review_state, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?);
            """, (
                name_id, concept_id, name_text.strip(),
                data.get("script", "latin"), data.get("language_tag", "en"),
                data.get("transliteration"), data.get("transliteration_scheme"),
                norm_text, name_type, data.get("source_passage_id"),
                data.get("assertion_id"), user_id
            ))

            self._log_catalog_event(
                conn, "name", name_id, "CREATE", user_id,
                new_state={"id": name_id, "concept_id": concept_id, "text": name_text.strip(), "type": name_type},
                rationale=data.get("notes") or f"Added candidate {name_type}"
            )

            conn.commit()
            cur.execute("SELECT * FROM concept_names WHERE id = ?;", (name_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def review_concept_name(self, name_id: str, decision: str, user_id: str, rationale: str) -> Dict[str, Any]:
        """Approve, reject, or dispute a candidate name/alias."""
        if decision not in {"approved", "rejected", "disputed"}:
            raise ValidationError("Decision must be 'approved', 'rejected', or 'disputed'.")
        if not rationale or not rationale.strip():
            raise ValidationError("Review rationale is mandatory.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM concept_names WHERE id = ?;", (name_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Concept name '{name_id}' not found.")

            conn.execute("UPDATE concept_names SET review_state = ? WHERE id = ?;", (decision, name_id))
            self._log_catalog_event(
                conn, "name", name_id, decision.upper(), user_id,
                prior_state={"review_state": existing["review_state"]},
                new_state={"review_state": decision},
                rationale=rationale.strip()
            )

            conn.commit()
            cur.execute("SELECT * FROM concept_names WHERE id = ?;", (name_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Mufradat Material Identity (Single Substances with Ambiguity)
    # --------------------------------------------------------------------------

    def set_material_identity(self, concept_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Set or update single-drug material identity. Explicitly represents identity ambiguity."""
        material_class = data.get("material_class", "botanical")
        if material_class not in VALID_MATERIAL_CLASSES:
            raise ValidationError(f"Invalid material_class '{material_class}'. Allowed: {sorted(list(VALID_MATERIAL_CLASSES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Concept '{concept_id}' not found.")

            cur.execute("SELECT * FROM material_identity WHERE concept_id = ?;", (concept_id,))
            existing = cur.fetchone()

            mat_id = existing["id"] if existing else f"mat-{uuid.uuid4().hex[:12]}"
            id_status = data.get("identity_status", existing["identity_status"] if existing else "unresolved")

            if existing:
                conn.execute("""
                    UPDATE material_identity
                    SET material_class = ?, identity_status = ?, scientific_name = ?,
                        taxonomic_authority = ?, external_identifier = ?, plant_part_or_material_form = ?,
                        geographic_or_source_context = ?, processing_state = ?,
                        identity_evidence_assertion_id = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (
                    material_class, id_status, data.get("scientific_name"),
                    data.get("taxonomic_authority"), data.get("external_identifier"),
                    data.get("plant_part_or_material_form"), data.get("geographic_or_source_context"),
                    data.get("processing_state"), data.get("identity_evidence_assertion_id"),
                    user_id, mat_id
                ))
                action = "UPDATE"
            else:
                conn.execute("""
                    INSERT INTO material_identity (
                        id, concept_id, material_class, identity_status, scientific_name,
                        taxonomic_authority, external_identifier, plant_part_or_material_form,
                        geographic_or_source_context, processing_state, identity_evidence_assertion_id,
                        reviewed_by, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (
                    mat_id, concept_id, material_class, id_status,
                    data.get("scientific_name"), data.get("taxonomic_authority"),
                    data.get("external_identifier"), data.get("plant_part_or_material_form"),
                    data.get("geographic_or_source_context"), data.get("processing_state"),
                    data.get("identity_evidence_assertion_id"), user_id
                ))
                action = "CREATE"

            self._log_catalog_event(
                conn, "material", mat_id, action, user_id,
                new_state={"id": mat_id, "class": material_class, "status": id_status, "scientific_name": data.get("scientific_name")},
                rationale=data.get("rationale") or f"{action} material identity record"
            )

            conn.commit()
            cur.execute("SELECT * FROM material_identity WHERE id = ?;", (mat_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Murakkabat Formulation Catalog & Component Statements
    # --------------------------------------------------------------------------

    def create_catalog_formulation(self, concept_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Register a Murakkabat compound formulation from literature."""
        src_name = data.get("source_specific_name")
        if not src_name or not src_name.strip():
            raise ValidationError("source_specific_name is required.")

        f_class = data.get("formulation_class", "unknown")
        if f_class not in VALID_FORMULATION_CLASSES:
            raise ValidationError(f"Invalid formulation_class '{f_class}'. Allowed: {sorted(list(VALID_FORMULATION_CLASSES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Concept '{concept_id}' not found.")

            form_id = data.get("id") or f"cfl-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO catalog_formulations (
                    id, concept_id, formulation_class, source_specific_name,
                    source_edition_id, identity_status, dosage_form,
                    preparation_description_assertion_id, formula_version, status, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?);
            """, (
                form_id, concept_id, f_class, src_name.strip(),
                data.get("source_edition_id"), data.get("identity_status", "unresolved"),
                data.get("dosage_form"), data.get("preparation_description_assertion_id"),
                data.get("formula_version"), user_id
            ))

            self._log_catalog_event(
                conn, "formulation", form_id, "CREATE", user_id,
                new_state={"id": form_id, "name": src_name.strip(), "class": f_class},
                rationale="Registered new formulation catalog entry"
            )

            conn.commit()
            cur.execute("SELECT * FROM catalog_formulations WHERE id = ?;", (form_id,))
            res = dict(cur.fetchone())
            res["ingredients"] = []
            return res
        finally:
            conn.close()

    def add_formulation_ingredient(self, formulation_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Add a source-backed component statement to a formulation.
        Preserves original raw unit and notation (e.g. 'masha', '2 1/2 masha').
        Never coerces units without an approved conversion rule.
        """
        raw_name = data.get("source_component_name_original")
        if not raw_name or not raw_name.strip():
            raise ValidationError("source_component_name_original is required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM catalog_formulations WHERE id = ?;", (formulation_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Formulation '{formulation_id}' not found.")

            ing_id = data.get("id") or f"cfi-{uuid.uuid4().hex[:12]}"
            orig_unit = data.get("quantity_unit_original")
            norm_unit = data.get("quantity_unit_normalized")

            # Invariant: normalized unit requires explicit conversion approval
            if norm_unit and not data.get("conversion_rule_approved"):
                raise ValidationError("Normalized unit cannot be recorded without documented conversion_rule_approved.")

            conn.execute("""
                INSERT INTO catalog_formulation_ingredients (
                    id, formulation_id, material_concept_id, source_component_name_original,
                    source_passage_id, assertion_id, quantity_value, quantity_min, quantity_max,
                    quantity_unit_original, quantity_unit_normalized, quantity_expression_original,
                    quantity_basis, processing_instruction_assertion_id, component_identity_state,
                    quantity_review_state, sequence_index, reviewed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                ing_id, formulation_id, data.get("material_concept_id"), raw_name.strip(),
                data.get("source_passage_id"), data.get("assertion_id"),
                data.get("quantity_value"), data.get("quantity_min"), data.get("quantity_max"),
                orig_unit, norm_unit, data.get("quantity_expression_original"),
                data.get("quantity_basis", "unknown"), data.get("processing_instruction_assertion_id"),
                data.get("component_identity_state", "unresolved"),
                data.get("quantity_review_state", "unreviewed"),
                data.get("sequence_index"), user_id
            ))

            self._log_catalog_event(
                conn, "ingredient", ing_id, "CREATE", user_id,
                new_state={"id": ing_id, "name": raw_name.strip(), "unit": orig_unit},
                rationale="Added formulation ingredient statement"
            )

            conn.commit()
            cur.execute("SELECT * FROM catalog_formulation_ingredients WHERE id = ?;", (ing_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Provenance-Bound Knowledge Assertions
    # --------------------------------------------------------------------------

    def create_knowledge_assertion(self, subject_concept_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create an individual claim/assertion bound to an exact source passage locator.
        Tracks predicate, exact quote, language, script, scope, and review state.
        """
        predicate = data.get("predicate")
        if not predicate or predicate not in VALID_PREDICATES:
            raise ValidationError(f"Invalid predicate '{predicate}'. Allowed: {sorted(list(VALID_PREDICATES))}")

        scope = data.get("assertion_scope", "identity")
        if scope not in VALID_ASSERTION_SCOPES:
            raise ValidationError(f"Invalid assertion_scope '{scope}'. Allowed: {sorted(list(VALID_ASSERTION_SCOPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_concepts WHERE id = ?;", (subject_concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Subject concept '{subject_concept_id}' not found.")

            assert_id = data.get("id") or f"kas-{uuid.uuid4().hex[:12]}"
            source_passage_id = data.get("source_passage_id")
            exact_quote = data.get("source_quote_exact")

            # Non-negotiable: clinical claims require exact source passage link
            if scope in {"clinical", "safety", "composition"} and not source_passage_id:
                raise ValidationError(f"Assertions in scope '{scope}' must be linked to a valid source_passage_id.")

            conn.execute("""
                INSERT INTO knowledge_assertions (
                    id, subject_concept_id, predicate, object_concept_id, object_literal,
                    source_passage_id, source_quote_exact, source_language, source_script,
                    page_locator, section_locator, table_locator, figure_locator,
                    assertion_scope, interpretation_note, evidence_characterization,
                    review_state, approved_intended_use, version, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', 'unapproved', 1, ?);
            """, (
                assert_id, subject_concept_id, predicate,
                data.get("object_concept_id"), data.get("object_literal"),
                source_passage_id, exact_quote,
                data.get("source_language", "en"), data.get("source_script", "latin"),
                data.get("page_locator"), data.get("section_locator"),
                data.get("table_locator"), data.get("figure_locator"),
                scope, data.get("interpretation_note"),
                data.get("evidence_characterization", "traditional_description"),
                user_id
            ))

            # Create review task
            task_id = f"crt-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO catalog_review_tasks (
                    id, entity_type, entity_id, task_type, priority, status, assigned_role
                ) VALUES (?, 'assertion', ?, 'CLINICAL_ASSERTION', 'HIGH', 'PENDING', 'UNANI_SCHOLAR');
            """, (task_id, assert_id))

            self._log_catalog_event(
                conn, "assertion", assert_id, "CREATE", user_id,
                new_state={"id": assert_id, "predicate": predicate, "scope": scope},
                rationale="Created provenance-bound knowledge assertion draft"
            )

            conn.commit()
            cur.execute("SELECT * FROM knowledge_assertions WHERE id = ?;", (assert_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def review_knowledge_assertion(
        self,
        assertion_id: str,
        decision: str,
        user_id: str,
        intended_use: Optional[str] = None,
        rationale: str = ""
    ) -> Dict[str, Any]:
        """
        Review a knowledge assertion.
        Only approves for a defined intended use (e.g. clinician_contextual_reference).
        """
        if decision not in VALID_ASSERTION_REVIEW_STATES:
            raise ValidationError(f"Invalid review decision '{decision}'. Allowed: {sorted(list(VALID_ASSERTION_REVIEW_STATES))}")
        if not rationale or not rationale.strip():
            raise ValidationError("Review rationale is mandatory for assertion review.")

        if decision == "approved_for_defined_use":
            if not intended_use or intended_use not in VALID_INTENDED_USES or intended_use == "unapproved":
                raise ValidationError("approved_for_defined_use requires a valid approved_intended_use.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_assertions WHERE id = ?;", (assertion_id,))
            existing = cur.fetchone()
            if not existing:
                raise NotFoundError(f"Assertion '{assertion_id}' not found.")

            conn.execute("""
                UPDATE knowledge_assertions
                SET review_state = ?, approved_intended_use = ?, reviewer_id = ?,
                    reviewed_at = CURRENT_TIMESTAMP, decision_rationale = ?
                WHERE id = ?;
            """, (decision, intended_use if decision == "approved_for_defined_use" else "unapproved", user_id, rationale.strip(), assertion_id))

            self._log_catalog_event(
                conn, "assertion", assertion_id, decision.upper(), user_id,
                prior_state={"review_state": existing["review_state"]},
                new_state={"review_state": decision, "intended_use": intended_use},
                rationale=rationale.strip()
            )

            conn.commit()
            cur.execute("SELECT * FROM knowledge_assertions WHERE id = ?;", (assertion_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def withdraw_knowledge_assertion(self, assertion_id: str, user_id: str, reason: str) -> Dict[str, Any]:
        """Withdraw a knowledge assertion permanently."""
        return self.review_knowledge_assertion(assertion_id, "withdrawn", user_id, rationale=reason)

    # --------------------------------------------------------------------------
    # 6. Typed Concept Relations (Graph Edges with Non-Inference Rule)
    # --------------------------------------------------------------------------

    def create_concept_relation(
        self,
        subject_concept_id: str,
        predicate: str,
        object_concept_id: str,
        data: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Create a typed concept relation.
        Non-negotiable rule: Graph adjacency is NEVER proof of clinical evidence.
        Substantive clinical relationships MUST link to an approved knowledge_assertion.
        """
        if predicate not in VALID_PREDICATES:
            raise ValidationError(f"Invalid predicate '{predicate}'. Allowed: {sorted(list(VALID_PREDICATES))}")

        relation_class = data.get("relation_class", "terminology")
        assertion_id = data.get("assertion_id")

        if relation_class in {"clinical", "safety"} and not assertion_id:
            raise ValidationError(f"Relations in class '{relation_class}' require a supporting assertion_id. Adjacency != evidence.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_concepts WHERE id = ?;", (subject_concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Subject concept '{subject_concept_id}' not found.")
            cur.execute("SELECT id FROM knowledge_concepts WHERE id = ?;", (object_concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Object concept '{object_concept_id}' not found.")

            rel_id = data.get("id") or f"crl-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO concept_relations (
                    id, subject_concept_id, predicate, object_concept_id, assertion_id,
                    relation_class, status, directionality, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?);
            """, (
                rel_id, subject_concept_id, predicate, object_concept_id, assertion_id,
                relation_class, data.get("directionality", "directed"), user_id
            ))

            self._log_catalog_event(
                conn, "relation", rel_id, "CREATE", user_id,
                new_state={"id": rel_id, "predicate": predicate, "sub": subject_concept_id, "obj": object_concept_id},
                rationale="Created concept relation"
            )

            conn.commit()
            cur.execute("SELECT * FROM concept_relations WHERE id = ?;", (rel_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. Modern Taxonomy Crosswalks
    # --------------------------------------------------------------------------

    def add_external_crosswalk(self, concept_id: str, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Add an external taxonomy crosswalk (MeSH, SNOMED, IPNI, POWO).
        Preserves mapping type. Candidate equivalence is excluded from decision support.
        """
        sys_uri = data.get("system_uri")
        sys_label = data.get("system_label")
        ext_code = data.get("external_code")
        map_type = data.get("mapping_type", "related_to")

        if not sys_uri or not sys_label or not ext_code:
            raise ValidationError("system_uri, system_label, and external_code are required.")
        if map_type not in VALID_MAPPING_TYPES:
            raise ValidationError(f"Invalid mapping_type '{map_type}'. Allowed: {sorted(list(VALID_MAPPING_TYPES))}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM knowledge_concepts WHERE id = ?;", (concept_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Concept '{concept_id}' not found.")

            cw_id = data.get("id") or f"ecw-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO external_identifier_crosswalks (
                    id, concept_id, system_uri, system_label, external_code,
                    external_preferred_label, mapping_type, status, evidence_assertion_id,
                    reviewed_by, reviewed_at, review_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, CURRENT_TIMESTAMP, ?);
            """, (
                cw_id, concept_id, sys_uri, sys_label, ext_code,
                data.get("external_preferred_label"), map_type,
                data.get("evidence_assertion_id"), user_id, data.get("review_notes")
            ))

            self._log_catalog_event(
                conn, "crosswalk", cw_id, "CREATE", user_id,
                new_state={"id": cw_id, "system": sys_label, "code": ext_code, "type": map_type},
                rationale="Added external identifier crosswalk"
            )

            conn.commit()
            cur.execute("SELECT * FROM external_identifier_crosswalks WHERE id = ?;", (cw_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 8. Multi-Script Explainable Search Engine
    # --------------------------------------------------------------------------

    def search_catalog(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        is_clinician_facing: bool = True
    ) -> Dict[str, Any]:
        """
        Multi-script search across canonical labels, original text, and transliterations.
        Explainable results indicate exact field and match reason.
        Enforces safety rules:
        - Clinician search masks unapproved candidate aliases.
        - Disputed and unresolved identities carry explicit warnings.
        """
        filters = filters or {}
        norm_q = self.normalize_text(query)
        if not norm_q and not query:
            return {"results": [], "total": 0, "query": query}

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            results = []

            # Match across concept_names
            sql = """
                SELECT cn.*, kc.canonical_label, kc.concept_type, kc.status as concept_status,
                       kc.identity_resolution_state
                FROM concept_names cn
                JOIN knowledge_concepts kc ON cn.concept_id = kc.id
                WHERE 1=1
            """
            params = []

            if is_clinician_facing:
                # Clinician safety: require approved concept and approved name
                sql += " AND kc.status = 'approved_identity' AND cn.review_state = 'approved'"
                sql += " AND cn.name_type != 'candidate_alias'"
            else:
                if filters.get("review_state"):
                    sql += " AND cn.review_state = ?"
                    params.append(filters["review_state"])

            if filters.get("concept_type"):
                sql += " AND kc.concept_type = ?"
                params.append(filters["concept_type"])

            if filters.get("script"):
                sql += " AND cn.script = ?"
                params.append(filters["script"])

            sql += """
                AND (
                    cn.normalized_search_text LIKE ?
                    OR cn.name_text_original LIKE ?
                    OR cn.transliteration LIKE ?
                    OR kc.canonical_label LIKE ?
                )
                ORDER BY
                    CASE WHEN cn.normalized_search_text = ? THEN 1
                         WHEN kc.canonical_label = ? THEN 2
                         WHEN cn.normalized_search_text LIKE ? THEN 3
                         ELSE 4 END
                LIMIT ?;
            """
            like_q = f"%{norm_q}%"
            raw_like = f"%{query}%"
            params.extend([like_q, raw_like, like_q, like_q, norm_q, query, f"{norm_q}%", int(filters.get("limit", 25))])

            cur.execute(sql, tuple(params))
            rows = [dict(r) for r in cur.fetchall()]

            for r in rows:
                match_reasons = []
                if r["normalized_search_text"] == norm_q:
                    match_reasons.append("EXACT_NORMALIZED_MATCH")
                elif norm_q in r["normalized_search_text"]:
                    match_reasons.append("SUBSTRING_NORMALIZED_MATCH")

                if query.strip() in r["name_text_original"]:
                    match_reasons.append(f"ORIGINAL_SCRIPT_MATCH ({r['script']})")

                if r.get("transliteration") and norm_q in self.normalize_text(r["transliteration"]):
                    match_reasons.append("TRANSLITERATION_MATCH")

                results.append({
                    "concept_id": r["concept_id"],
                    "canonical_label": r["canonical_label"],
                    "concept_type": r["concept_type"],
                    "matched_name": r["name_text_original"],
                    "script": r["script"],
                    "language_tag": r["language_tag"],
                    "transliteration": r["transliteration"],
                    "name_type": r["name_type"],
                    "name_review_state": r["review_state"],
                    "identity_resolution_state": r["identity_resolution_state"],
                    "match_reasons": match_reasons,
                    "clinical_safety_warning": "UNRESOLVED_OR_DISPUTED_IDENTITY" if r["identity_resolution_state"] in {"unresolved", "disputed"} else None
                })

            return {
                "results": results,
                "total": len(results),
                "query": query,
                "clinician_facing": is_clinician_facing
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 9. Review Tasks & Audit Ledger
    # --------------------------------------------------------------------------

    def list_review_tasks(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List active catalog review tasks."""
        filters = filters or {}
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM catalog_review_tasks WHERE 1=1"
            params = []
            if filters.get("status"):
                query += " AND status = ?"
                params.append(filters["status"])
            if filters.get("task_type"):
                query += " AND task_type = ?"
                params.append(filters["task_type"])
            query += " ORDER BY created_at DESC LIMIT 50;"
            cur.execute(query, tuple(params))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def list_change_events(self, entity_type: Optional[str] = None, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve audit history for an entity or overall catalog."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM catalog_change_events WHERE 1=1"
            params = []
            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type)
            if entity_id:
                query += " AND entity_id = ?"
                params.append(entity_id)
            query += " ORDER BY created_at DESC LIMIT 100;"
            cur.execute(query, tuple(params))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
