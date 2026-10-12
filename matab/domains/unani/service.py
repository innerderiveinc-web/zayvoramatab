"""Unani Assessment Domain: Mizaj, Ajnas-e-Ashara, Nabz, Baul/Baraz, and Asbab-e-Sittah."""

import uuid
import json
from typing import Dict, Any, List, Optional
import sqlite3
from matab.core.errors import ValidationError, NotFoundError

# Classical Mizaj attributes
MIZAJ_PROFILES = {
    "DAMWI": {"name": "Damwi (Sanguine)", "qualities": "Hot & Moist (Haar Ratab)", "humor": "Dam (Blood)"},
    "BALGHAMI": {"name": "Balghami (Phlegmatic)", "qualities": "Cold & Moist (Barid Ratab)", "humor": "Balgham (Phlegm)"},
    "SAFRAWI": {"name": "Safrawi (Choleric)", "qualities": "Hot & Dry (Haar Yabis)", "humor": "Safra (Yellow Bile)"},
    "SAUDAWI": {"name": "Saudawi (Melancholic)", "qualities": "Cold & Dry (Barid Yabis)", "humor": "Sauda (Black Bile)"},
    "MOTADIL": {"name": "Motadil (Equable)", "qualities": "Balanced / Harmonious", "humor": "Equilibrium"}
}

class UnaniService:
    @staticmethod
    def calculate_mizaj_scores(answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate quantitative distribution across the 4 Classical Unani Humors."""
        scores = {"dam": 0, "balgham": 0, "safra": 0, "sauda": 0}
        
        for ans in answers:
            scores["dam"] += ans.get("score_dam", 0)
            scores["balgham"] += ans.get("score_balgham", 0)
            scores["safra"] += ans.get("score_safra", 0)
            scores["sauda"] += ans.get("score_sauda", 0)
            
        total = sum(scores.values()) or 1
        percentages = {k: round((v / total) * 100, 1) for k, v in scores.items()}
        
        # Determine dominant and secondary
        sorted_humors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_humor, top_score = sorted_humors[0]
        second_humor, second_score = sorted_humors[1]
        
        humor_map = {
            "dam": "DAMWI",
            "balgham": "BALGHAMI",
            "safra": "SAFRAWI",
            "sauda": "SAUDAWI"
        }
        
        if top_score == second_score and top_score > 0:
            dominant_mizaj = "MOTADIL"
            secondary = f"{humor_map.get(top_humor)}-{humor_map.get(second_humor)}"
        elif top_score == 0:
            dominant_mizaj = "UNKNOWN"
            secondary = None
        else:
            dominant_mizaj = humor_map.get(top_humor, "UNKNOWN")
            secondary = humor_map.get(second_humor)
            
        return {
            "scores": scores,
            "percentages": percentages,
            "dominant_mizaj": dominant_mizaj,
            "secondary_mizaj": secondary,
            "profile": MIZAJ_PROFILES.get(dominant_mizaj, {"name": "Unknown", "qualities": "Pending Clinical Evaluation"})
        }

    @staticmethod
    def save_unani_assessment(conn: sqlite3.Connection, encounter_id: str, patient_id: str,
                              hakeem_id: str, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record or update Unani assessment for a patient encounter."""
        answers = assessment_data.get("questionnaire_responses", [])
        mizaj_calc = UnaniService.calculate_mizaj_scores(answers) if answers else {}
        
        dominant_mizaj = assessment_data.get("dominant_mizaj") or mizaj_calc.get("dominant_mizaj", "UNKNOWN")
        mizaj_secondary = assessment_data.get("mizaj_secondary") or mizaj_calc.get("secondary_mizaj")
        
        assessment_id = str(uuid.uuid4())
        
        conn.execute("""
            INSERT INTO unani_assessments 
            (id, encounter_id, patient_id, hakeem_id, dominant_mizaj, mizaj_secondary, su_e_mizaj_type,
             nabz_quality, baul_observations, baraz_observations, afaal_summary, asbab_sittah_assessment,
             clinical_interpretation, assessment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'FINAL');
        """, (
            assessment_id,
            encounter_id,
            patient_id,
            hakeem_id,
            dominant_mizaj,
            mizaj_secondary,
            assessment_data.get("su_e_mizaj_type", "NONE"),
            assessment_data.get("nabz_quality"),
            assessment_data.get("baul_observations"),
            assessment_data.get("baraz_observations"),
            assessment_data.get("afaal_summary"),
            json.dumps(assessment_data.get("asbab_sittah_assessment") or {}),
            assessment_data.get("clinical_interpretation")
        ))
        
        # Save questionnaire answers
        for ans in answers:
            conn.execute("""
                INSERT INTO mizaj_questionnaire_responses (id, assessment_id, question_key, selected_option, score_dam, score_balgham, score_safra, score_sauda)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                str(uuid.uuid4()),
                assessment_id,
                ans.get("question_key", "general"),
                ans.get("selected_option", ""),
                ans.get("score_dam", 0),
                ans.get("score_balgham", 0),
                ans.get("score_safra", 0),
                ans.get("score_sauda", 0)
            ))
            
        return {
            "id": assessment_id,
            "encounter_id": encounter_id,
            "dominant_mizaj": dominant_mizaj,
            "mizaj_secondary": mizaj_secondary,
            "mizaj_calculation": mizaj_calc,
            **assessment_data
        }
