"""Formulation Catalog Domain Service: Monograph Search, Versioning, Review Lifecycle, and Source Citations."""

import uuid
import re
from typing import Dict, Any, List, Optional, Tuple
import sqlite3
from apps.api.core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError
from apps.api.core.audit import log_audit_event

VALID_DOSAGE_FORMS = [
    "SAFOOF", "MAJOON", "SHARBAT", "HAB", "QURS",
    "KHAMIRA", "JOSHANDA", "ROGHAN", "ARQ", "ITRIFAL",
    "LAOOQ", "KUSHTA", "SUFOOF", "TILA"
]

VALID_FORMULATION_STATUSES = ["DRAFT", "UNDER_REVIEW", "APPROVED", "REJECTED", "RETIRED"]

class FormulationService:
    @staticmethod
    def get_clinical_sources(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Fetch all statutory and classical bibliographic sources."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, code, title, author_authority, edition, publication_year, legal_status, url_or_reference, verification_status
            FROM clinical_sources
            ORDER BY publication_year ASC, code ASC;
        """)
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_ingredients(conn: sqlite3.Connection, q: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search master ingredient catalog by canonical or Unani botanical name."""
        cursor = conn.cursor()
        if q and q.strip():
            clean_q = f"%{q.strip().lower()}%"
            cursor.execute("""
                SELECT i.id, i.canonical_name, i.unani_name, i.botanical_name, i.category,
                       i.temperament_mizaj, i.degree, i.single_dose_min_mg, i.single_dose_max_mg,
                       i.daily_dose_max_mg, i.is_mudabbar_required, i.is_schedule_e1, i.review_status,
                       s.code as source_code, s.title as source_title
                FROM ingredient_catalog i
                LEFT JOIN clinical_sources s ON i.source_id = s.id
                WHERE lower(i.canonical_name) LIKE ? OR lower(i.unani_name) LIKE ? OR lower(COALESCE(i.botanical_name, '')) LIKE ?
                ORDER BY i.unani_name ASC
                LIMIT ?;
            """, (clean_q, clean_q, clean_q, min(limit, 100)))
        else:
            cursor.execute("""
                SELECT i.id, i.canonical_name, i.unani_name, i.botanical_name, i.category,
                       i.temperament_mizaj, i.degree, i.single_dose_min_mg, i.single_dose_max_mg,
                       i.daily_dose_max_mg, i.is_mudabbar_required, i.is_schedule_e1, i.review_status,
                       s.code as source_code, s.title as source_title
                FROM ingredient_catalog i
                LEFT JOIN clinical_sources s ON i.source_id = s.id
                ORDER BY i.unani_name ASC
                LIMIT ?;
            """, (min(limit, 100),))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def search_formulations(conn: sqlite3.Connection, organization_id: str,
                             q: Optional[str] = None, dosage_form: Optional[str] = None,
                             status: Optional[str] = None, limit: int = 20, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """Search formulations scoped to organization with full monograph citations."""
        cursor = conn.cursor()
        conditions = ["f.organization_id = ?"]
        params: List[Any] = [organization_id]

        if dosage_form and dosage_form.strip():
            conditions.append("f.dosage_form = ?")
            params.append(dosage_form.strip().upper())

        if status and status.strip():
            conditions.append("f.status = ?")
            params.append(status.strip().upper())
        else:
            # Default to showing APPROVED and DRAFT formulations
            conditions.append("f.status != 'RETIRED'")

        if q and q.strip():
            clean_q = f"%{q.strip().lower()}%"
            conditions.append("""
                (
                    lower(f.name) LIKE ? OR
                    lower(f.code) LIKE ? OR
                    lower(COALESCE(f.transliteration, '')) LIKE ? OR
                    EXISTS (
                        SELECT 1 FROM formulation_synonyms s
                        WHERE s.formulation_id = f.id AND lower(s.synonym) LIKE ?
                    )
                )
            """)
            params.extend([clean_q, clean_q, clean_q, clean_q])

        where_clause = " AND ".join(conditions)

        cursor.execute(f"SELECT count(*) as total FROM formulations f WHERE {where_clause};", params)
        total = cursor.fetchone()["total"]

        query = f"""
            SELECT f.id, f.organization_id, f.code, f.name, f.transliteration, f.dosage_form,
                   f.current_version, f.status, f.created_at, f.updated_at,
                   v.id as active_version_id, v.standard_indication, v.standard_adult_dose,
                   v.source_locator, v.status as version_status,
                   s.code as source_code, s.title as source_title
            FROM formulations f
            LEFT JOIN formulation_versions v ON f.id = v.formulation_id AND f.current_version = v.version_number
            LEFT JOIN clinical_sources s ON v.classical_source_id = s.id
            WHERE {where_clause}
            ORDER BY f.name ASC
            LIMIT ? OFFSET ?;
        """
        params.extend([min(limit, 100), max(offset, 0)])
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

        # Attach chief ingredients preview
        for item in rows:
            v_id = item.get("active_version_id")
            if v_id:
                cursor.execute("""
                    SELECT fi.quantity_mg, fi.unit, fi.is_chief_ingredient,
                           i.canonical_name, i.unani_name, i.is_mudabbar_required, i.is_schedule_e1
                    FROM formulation_ingredients fi
                    JOIN ingredient_catalog i ON fi.ingredient_id = i.id
                    WHERE fi.formulation_version_id = ?
                    ORDER BY fi.is_chief_ingredient DESC, fi.sort_order ASC
                    LIMIT 4;
                """, (v_id,))
                item["ingredients_preview"] = [dict(r) for r in cursor.fetchall()]
            else:
                item["ingredients_preview"] = []

        return rows, total

    @staticmethod
    def get_formulation_by_id(conn: sqlite3.Connection, organization_id: str, formulation_id: str) -> Dict[str, Any]:
        """Fetch complete formulation detail with all version monographs and ingredients."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.organization_id, f.code, f.name, f.transliteration, f.dosage_form,
                   f.current_version, f.status, f.created_at, f.updated_at,
                   u.full_name as author_name
            FROM formulations f
            LEFT JOIN users u ON f.created_by = u.id
            WHERE f.id = ? AND f.organization_id = ?;
        """, (formulation_id, organization_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Formulation '{formulation_id}' not found.")
        formulation = dict(row)

        # Fetch versions
        cursor.execute("""
            SELECT v.id, v.formulation_id, v.version_number, v.preparation_method,
                   v.standard_indication, v.standard_adult_dose, v.classical_source_id,
                   v.source_locator, v.status, v.reviewed_by, v.reviewed_at, v.review_notes, v.created_at,
                   s.code as source_code, s.title as source_title, s.legal_status,
                   u.full_name as reviewer_name
            FROM formulation_versions v
            LEFT JOIN clinical_sources s ON v.classical_source_id = s.id
            LEFT JOIN users u ON v.reviewed_by = u.id
            WHERE v.formulation_id = ?
            ORDER BY v.version_number DESC;
        """, (formulation_id,))
        versions = [dict(r) for r in cursor.fetchall()]

        # Fetch ingredients for each version
        for ver in versions:
            cursor.execute("""
                SELECT fi.id, fi.quantity_mg, fi.unit, fi.is_chief_ingredient, fi.processing_notes, fi.sort_order,
                       i.id as ingredient_id, i.canonical_name, i.unani_name, i.botanical_name,
                       i.temperament_mizaj, i.degree, i.is_mudabbar_required, i.is_schedule_e1
                FROM formulation_ingredients fi
                JOIN ingredient_catalog i ON fi.ingredient_id = i.id
                WHERE fi.formulation_version_id = ?
                ORDER BY fi.is_chief_ingredient DESC, fi.sort_order ASC;
            """, (ver["id"],))
            ver["ingredients"] = [dict(r) for r in cursor.fetchall()]

        formulation["versions"] = versions
        # Point to current active version
        active_ver = next((v for v in versions if v["version_number"] == formulation["current_version"]), versions[0] if versions else None)
        formulation["active_version"] = active_ver

        return formulation

    @staticmethod
    def create_draft_formulation(conn: sqlite3.Connection, organization_id: str,
                                data: Dict[str, Any], actor_id: str,
                                request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Create a new formulation with initial draft version and ingredients."""
        name = data.get("name", "").strip()
        code = data.get("code", "").strip().upper()
        dosage_form = data.get("dosage_form", "").strip().upper()
        transliteration = data.get("transliteration", "").strip() or None

        if not name:
            raise ValidationError("Formulation name is required.", request_id=request_id)
        if not code:
            code = f"FORM-{uuid.uuid4().hex[:6].upper()}"
        if dosage_form not in VALID_DOSAGE_FORMS:
            raise ValidationError(f"Invalid dosage form '{dosage_form}'. Must be one of: {', '.join(VALID_DOSAGE_FORMS)}", request_id=request_id)

        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM formulations WHERE organization_id = ? AND code = ?;", (organization_id, code))
        if cursor.fetchone():
            raise ConflictError(f"Formulation code '{code}' already exists in organization.", request_id=request_id)

        formulation_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        # Insert formulation header
        conn.execute("""
            INSERT INTO formulations (id, organization_id, code, name, transliteration, dosage_form, current_version, status, created_by, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'DRAFT', ?, ?);
        """, (formulation_id, organization_id, code, name, transliteration, dosage_form, actor_id, actor_id))

        # Insert initial version
        conn.execute("""
            INSERT INTO formulation_versions (
                id, formulation_id, version_number, preparation_method, standard_indication,
                standard_adult_dose, classical_source_id, source_locator, status
            )
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, 'DRAFT');
        """, (
            version_id, formulation_id,
            data.get("preparation_method"), data.get("standard_indication"),
            data.get("standard_adult_dose"), data.get("classical_source_id"),
            data.get("source_locator")
        ))

        # Insert ingredients if provided
        ingredients = data.get("ingredients", [])
        for idx, ing in enumerate(ingredients):
            ing_id = ing.get("ingredient_id")
            q_mg = int(ing.get("quantity_mg", 0))
            is_chief = 1 if ing.get("is_chief_ingredient") else 0
            proc_notes = ing.get("processing_notes")
            if ing_id and q_mg > 0:
                conn.execute("""
                    INSERT INTO formulation_ingredients (id, formulation_version_id, ingredient_id, quantity_mg, is_chief_ingredient, processing_notes, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (str(uuid.uuid4()), version_id, ing_id, q_mg, is_chief, proc_notes, idx + 1))

        log_audit_event(
            conn=conn,
            action_type="FORMULATION_CREATED",
            target_entity_type="FORMULATION",
            target_entity_id=formulation_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"code": code, "name": name, "status": "DRAFT"}
        )

        return FormulationService.get_formulation_by_id(conn, organization_id, formulation_id)

    @staticmethod
    def submit_for_review(conn: sqlite3.Connection, organization_id: str, formulation_id: str,
                           actor_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Submit draft formulation version for clinical/editorial review."""
        form = FormulationService.get_formulation_by_id(conn, organization_id, formulation_id)
        if form["status"] not in ["DRAFT", "REJECTED"]:
            raise ConflictError(f"Cannot submit formulation in '{form['status']}' state for review.", request_id=request_id)

        conn.execute("UPDATE formulations SET status = 'UNDER_REVIEW', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (formulation_id,))
        conn.execute("UPDATE formulation_versions SET status = 'UNDER_REVIEW' WHERE formulation_id = ? AND version_number = ?;", (formulation_id, form["current_version"]))

        log_audit_event(
            conn=conn,
            action_type="FORMULATION_SUBMITTED_REVIEW",
            target_entity_type="FORMULATION",
            target_entity_id=formulation_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id
        )

        return FormulationService.get_formulation_by_id(conn, organization_id, formulation_id)

    @staticmethod
    def approve_formulation(conn: sqlite3.Connection, organization_id: str, formulation_id: str,
                            reviewer_id: str, notes: str = "", request_id: Optional[str] = None) -> Dict[str, Any]:
        """Approve a submitted formulation version for clinical prescribing."""
        form = FormulationService.get_formulation_by_id(conn, organization_id, formulation_id)
        active_ver = form["active_version"]
        if not active_ver:
            raise NotFoundError("Active formulation version not found.", request_id=request_id)

        conn.execute("UPDATE formulations SET status = 'APPROVED', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (formulation_id,))
        conn.execute("""
            UPDATE formulation_versions
            SET status = 'APPROVED', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, review_notes = ?
            WHERE id = ?;
        """, (reviewer_id, notes.strip(), active_ver["id"]))

        # Log review
        conn.execute("""
            INSERT INTO formulation_reviews (id, formulation_version_id, reviewer_id, decision, notes)
            VALUES (?, ?, ?, 'APPROVED', ?);
        """, (str(uuid.uuid4()), active_ver["id"], reviewer_id, notes.strip()))

        log_audit_event(
            conn=conn,
            action_type="FORMULATION_APPROVED",
            target_entity_type="FORMULATION",
            target_entity_id=formulation_id,
            organization_id=organization_id,
            actor_id=reviewer_id,
            outcome="SUCCESS",
            request_id=request_id,
            details={"version": active_ver["version_number"]}
        )

        return FormulationService.get_formulation_by_id(conn, organization_id, formulation_id)
