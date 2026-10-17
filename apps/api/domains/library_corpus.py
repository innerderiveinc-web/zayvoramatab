"""ZAYVORA MATAB OS — Grand Classical Library & Corpus Service.

Enables full-text querying across:
1. 1,593 Standard Unani Terms (UMA code, Unani term, English equivalent, definition, source)
2. 250 Single Herbs (Mufradat) with Mizaj, Afaal, Muzir, Musleh, and Badal
3. 14 Classical & Modern Herb-Drug Interactions
4. Classical Canon Books (Al-Qanun, Al-Hawi, Kamil al-Sina'ah, Makhzan-ul-Adwiya)
"""

import sqlite3
from typing import Dict, Any, List, Optional

class LibraryCorpusService:
    """Core domain service for Grand Classical Corpus in Matab OS."""

    @classmethod
    def search_standard_terms(cls, conn: sqlite3.Connection, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        q_wild = f"%{query.strip()}%"
        cur.execute("""
            SELECT uma_code, unani_term, english_equivalent, definition, source
            FROM unani_standard_terms
            WHERE unani_term LIKE ? OR english_equivalent LIKE ? OR definition LIKE ? OR uma_code LIKE ?
            LIMIT ?
        """, (q_wild, q_wild, q_wild, q_wild, limit))
        
        cols = ["code", "unani_term", "english_equivalent", "definition", "source"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    @classmethod
    def search_mufradat(cls, conn: sqlite3.Connection, query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        q_wild = f"%{(query or '').strip()}%"
        cur.execute("""
            SELECT id, canonical_name_latin, canonical_name_urdu, canonical_name_arabic, 
                   canonical_name_english, botanical_name, plant_part_used, mizaj_primary_quality, mizaj_degree, 
                   historical_dose, therapeutic_actions, clinical_indications, contraindications,
                   adverse_effects_muzir, musleh_correctives, badal_substitutes, badraqa_anupan,
                   famous_compounds_murakkabat, phytochemical_constituents, herb_drug_interactions,
                   upi_monograph_ref, synonyms_vernacular, is_schedule_e1_poison, mandatory_mudabbar, mudabbar_protocol
            FROM zkb_mufradat
            WHERE ? = '' OR canonical_name_latin LIKE ? OR canonical_name_urdu LIKE ? OR botanical_name LIKE ? 
               OR canonical_name_english LIKE ? OR therapeutic_actions LIKE ? OR clinical_indications LIKE ?
               OR synonyms_vernacular LIKE ?
            ORDER BY canonical_name_english ASC
            LIMIT ?
        """, (query.strip(), q_wild, q_wild, q_wild, q_wild, q_wild, q_wild, q_wild, limit))
        
        cols = [
            "id", "latin", "urdu", "arabic", "english", "botanical", "part_used",
            "mizaj_quality", "mizaj_degree", "dosage", "actions", "indications",
            "contraindications", "muzir", "musleh", "badal", "anupan", "compounds",
            "phytochemicals", "interactions", "upi_ref", "synonyms", "is_schedule_e1",
            "mandatory_mudabbar", "mudabbar_protocol"
        ]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    @classmethod
    def get_mufrad_detail(cls, conn: sqlite3.Connection, herb_id: str) -> Optional[Dict[str, Any]]:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, canonical_name_latin, canonical_name_urdu, canonical_name_arabic, 
                   canonical_name_english, botanical_name, upi_code, origin_category, plant_part_used, 
                   mizaj_primary_quality, mizaj_degree, is_schedule_e1_poison, mandatory_mudabbar, 
                   mudabbar_protocol, historical_dose, approved_single_dose_max_grams, approved_daily_dose_max_grams, 
                   therapeutic_actions, badal_substitutes, musleh_correctives, pregnancy_status, 
                   lactation_status, pediatric_status, geriatric_status, evidence_level, 
                   current_lifecycle_state, safe_for_ai, synonyms_vernacular, clinical_indications, 
                   contraindications, adverse_effects_muzir, badraqa_anupan, famous_compounds_murakkabat, 
                   phytochemical_constituents, herb_drug_interactions, upi_monograph_ref
            FROM zkb_mufradat
            WHERE id = ? OR LOWER(canonical_name_english) = LOWER(?) OR LOWER(botanical_name) LIKE LOWER(?)
            LIMIT 1
        """, (herb_id, herb_id, f"%{herb_id}%"))
        row = cur.fetchone()
        if not row:
            return None

        cols = [
            "id", "latin", "urdu", "arabic", "english", "botanical", "upi_code", "origin_category",
            "part_used", "mizaj_quality", "mizaj_degree", "is_schedule_e1", "mandatory_mudabbar",
            "mudabbar_protocol", "historical_dose", "single_dose_max_g", "daily_dose_max_g",
            "therapeutic_actions", "badal_substitutes", "musleh_correctives", "pregnancy_status",
            "lactation_status", "pediatric_status", "geriatric_status", "evidence_level",
            "lifecycle_state", "safe_for_ai", "synonyms_vernacular", "clinical_indications",
            "contraindications", "adverse_effects_muzir", "badraqa_anupan", "famous_compounds_murakkabat",
            "phytochemical_constituents", "herb_drug_interactions", "upi_monograph_ref"
        ]
        return dict(zip(cols, row))

    @classmethod
    def list_classical_sources(cls, conn: sqlite3.Connection) -> Dict[str, Any]:
        cur = conn.cursor()
        cur.execute("SELECT id, name_latin, name_arabic, era_gregorian, bio_summary FROM source_authors")
        authors = [
            {"id": r[0], "name": r[1], "arabic": r[2], "era": r[3], "bio": r[4]}
            for r in cur.fetchall()
        ]

        cur.execute("SELECT id, title_short, title_original, language_primary, publication_era_ce FROM source_books")
        books = [
            {"id": r[0], "title": r[1], "original": r[2], "lang": r[3], "era": r[4]}
            for r in cur.fetchall()
        ]

        cur.execute("SELECT id, herb_name, drug_name, interaction_severity, clinical_manifestation, management_guideline FROM zkb_drug_interactions")
        interactions = [
            {"id": r[0], "herb": r[1], "drug": r[2], "severity": r[3], "manifestation": r[4], "guideline": r[5]}
            for r in cur.fetchall()
        ]

        return {
            "canonical_authors": authors,
            "canonical_books": books,
            "verified_interactions": interactions
        }
