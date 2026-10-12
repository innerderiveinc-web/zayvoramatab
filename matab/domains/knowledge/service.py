"""Knowledge and Formulary Domain: Governed Monographs, Mufradat, and Murakkabat."""

from typing import Dict, Any, List, Optional
import sqlite3
from matab.core.errors import NotFoundError

class KnowledgeService:
    @staticmethod
    def search_ingredients(conn: sqlite3.Connection, query: str = "") -> List[Dict[str, Any]]:
        """Search approved single herbs (Mufradat) catalog with statutory metadata."""
        cursor = conn.cursor()
        q = f"%{query.strip().lower()}%"
        cursor.execute("""
            SELECT i.id, i.canonical_name, i.unani_name, i.botanical_name, i.temperament_mizaj,
                   i.degree, i.single_dose_min_mg, i.single_dose_max_mg, i.daily_dose_max_mg,
                   i.is_mudabbar_required, i.is_schedule_e1,
                   ks.code as source_code, ks.title as source_title
            FROM ingredients i
            LEFT JOIN knowledge_sources ks ON i.source_id = ks.id
            WHERE lower(i.canonical_name) LIKE ? OR lower(i.unani_name) LIKE ? OR lower(i.botanical_name) LIKE ?
            ORDER BY i.canonical_name ASC;
        """, (q, q, q))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def search_formulations(conn: sqlite3.Connection, query: str = "") -> List[Dict[str, Any]]:
        """Search approved compound formulations (Murakkabat) catalog."""
        cursor = conn.cursor()
        q = f"%{query.strip().lower()}%"
        cursor.execute("""
            SELECT f.id, f.name, f.dosage_form, f.standard_indication, f.standard_adult_dose, f.is_verified,
                   ks.code as source_code, ks.title as source_title
            FROM formulations f
            LEFT JOIN knowledge_sources ks ON f.classical_source_id = ks.id
            WHERE lower(f.name) LIKE ? OR lower(f.standard_indication) LIKE ?
            ORDER BY f.name ASC;
        """, (q, q))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_formulation_details(conn: sqlite3.Connection, formulation_id: str) -> Dict[str, Any]:
        """Fetch full formulation record including constituent ingredients and contraindications."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.name, f.dosage_form, f.standard_indication, f.standard_adult_dose, f.is_verified,
                   ks.code as source_code, ks.title as source_title, ks.author_authority
            FROM formulations f
            LEFT JOIN knowledge_sources ks ON f.classical_source_id = ks.id
            WHERE f.id = ?;
        """, (formulation_id,))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Formulation '{formulation_id}' not found.")
            
        formulation = dict(row)
        
        # Load constituent ingredients
        cursor.execute("""
            SELECT fi.quantity_mg, fi.is_chief_ingredient,
                   i.id as ingredient_id, i.canonical_name, i.unani_name, i.botanical_name,
                   i.temperament_mizaj, i.degree, i.single_dose_max_mg, i.is_mudabbar_required, i.is_schedule_e1
            FROM formulation_ingredients fi
            JOIN ingredients i ON fi.ingredient_id = i.id
            WHERE fi.formulation_id = ?;
        """, (formulation_id,))
        formulation["ingredients"] = [dict(it) for it in cursor.fetchall()]
        
        return formulation
