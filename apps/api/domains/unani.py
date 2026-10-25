"""Unani Assessment Domain: Mizaj, Ajnas-e-Ashara, Nabz, Organ-Axis, and Af'aal Cascade."""

import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3
from apps.api.core.errors import ValidationError, NotFoundError

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
        
        sorted_humors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_humor, top_score = sorted_humors[0]
        
        humor_map = {"dam": "DAMWI", "balgham": "BALGHAMI", "safra": "SAFRAWI", "sauda": "SAUDAWI"}
        dominant = humor_map.get(top_humor, "MOTADIL")
        
        return {
            "scores": scores,
            "percentages": percentages,
            "dominant_mizaj": dominant,
            "profile": MIZAJ_PROFILES.get(dominant, MIZAJ_PROFILES["MOTADIL"])
        }

    @staticmethod
    def create_assessment(conn: sqlite3.Connection, data: Dict[str, Any], assessor_id: str) -> Dict[str, Any]:
        """Record structured Mizaj and Nabz assessment."""
        assessment_id = f"uas-{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        scores_res = UnaniService.calculate_mizaj_scores(data.get("mizaj_answers", []))
        
        conn.execute("""
            INSERT INTO unani_assessments (
                id, patient_id, encounter_id, assessor_id, dominant_mizaj,
                mizaj_dam_score, mizaj_balgham_score, mizaj_safra_score, mizaj_sauda_score,
                nabz_rate, nabz_volume, nabz_strength, nabz_rhythm, organ_axis,
                clinical_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            assessment_id,
            data["patient_id"],
            data.get("encounter_id"),
            assessor_id,
            scores_res["dominant_mizaj"],
            scores_res["scores"]["dam"],
            scores_res["scores"]["balgham"],
            scores_res["scores"]["safra"],
            scores_res["scores"]["sauda"],
            data.get("nabz_rate"),
            data.get("nabz_volume"),
            data.get("nabz_strength"),
            data.get("nabz_rhythm"),
            data.get("organ_axis", "GASTRIC"),
            data.get("clinical_notes"),
            now,
            now
        ))
        
        return {
            "id": assessment_id,
            "dominant_mizaj": scores_res["dominant_mizaj"],
            "profile": scores_res["profile"],
            "percentages": scores_res["percentages"]
        }
