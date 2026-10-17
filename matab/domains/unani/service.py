"""Unani Assessment Domain: Mizaj, Ajnas-e-Ashara, Nabz, Organ-Axis, and Af'aal Cascade."""

import uuid
import json
from datetime import datetime
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
        """Record Unani assessment, invoking Organ-Axis and Af'aal Cascade engines seamlessly."""
        answers = assessment_data.get("questionnaire_responses", [])
        mizaj_calc = UnaniService.calculate_mizaj_scores(answers) if answers else {}
        
        dominant_mizaj = assessment_data.get("dominant_mizaj") or mizaj_calc.get("dominant_mizaj", "BALGHAMI")
        mizaj_secondary = assessment_data.get("mizaj_secondary") or mizaj_calc.get("secondary_mizaj", "SAUDAWI")
        su_e_mizaj = assessment_data.get("su_e_mizaj_type", "MADDI")
        nabz = assessment_data.get("nabz_quality", "MUTAWASSIT")
        interpretation = assessment_data.get("clinical_interpretation", "")

        # Run Organ-Axis and Af'aal Cascade engines
        from matab.engines.organ_axis_engine import deduce_organ_axes_and_reflexes
        from matab.engines.afaal_cascade_engine import evaluate_afaal_stage_recommendation

        axis_res = deduce_organ_axes_and_reflexes(interpretation or "General Systemic Dyspepsia")
        primary_axis = axis_res.get("primary_axis") or {
            "id": "meda-amaa",
            "name": "Gastro-Intestinal Axis (Meda wa Am'a)",
            "governing_power": "Quwwat-e-Hazima wa Dafia (Digestive & Expulsive Faculty)",
            "primary_organ": "Meda (Stomach)"
        }
        
        cascade_res = evaluate_afaal_stage_recommendation(
            mizaj_dominant=dominant_mizaj,
            organ_axis=primary_axis.get("name", "Gastro-Intestinal"),
            chronicity_months=2
        )

        rationale_payload = {
            "dominant_mizaj": dominant_mizaj,
            "secondary_mizaj": mizaj_secondary,
            "su_e_mizaj_type": su_e_mizaj,
            "nabz": {"quality": nabz},
            "active_12_axes": {primary_axis.get("id", "axis-1"): 4},
            "primary_axis": primary_axis,
            "secondary_axis": axis_res.get("secondary_axis"),
            "afaal_cascade": cascade_res,
            "calculation": mizaj_calc
        }

        assessment_id = f"uas-{uuid.uuid4().hex[:12]}"
        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Check existing table columns in unani_assessments
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(unani_assessments);")
        columns = [row[1] for row in cursor.fetchall()]

        if "organization_id" in columns:
            # Enterprise / Governed Schema
            org_id = assessment_data.get("organization_id", "org-matab-default")
            fac_id = assessment_data.get("facility_id", "fac-central-opd")
            
            # Fetch default template version if needed
            tmpl_ver_id = "ver-tmpl-unani-core-1"
            try:
                cursor.execute("SELECT id FROM unani_assessment_template_versions LIMIT 1;")
                t_row = cursor.fetchone()
                if t_row:
                    tmpl_ver_id = t_row[0]
            except Exception:
                pass

            conn.execute("""
                INSERT INTO unani_assessments 
                (id, organization_id, facility_id, patient_id, encounter_id, template_version_id,
                 author_id, status, assessment_date, dominant_mizaj, secondary_mizaj,
                 mizaj_rationale, mizaj_uncertainty, clinical_reasoning, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'FINALISED', date('now'), ?, ?, ?, 'HIGH_CONFIDENCE', ?, ?, ?);
            """, (
                assessment_id, org_id, fac_id, patient_id, encounter_id, tmpl_ver_id,
                hakeem_id, dominant_mizaj, mizaj_secondary,
                json.dumps(rationale_payload), interpretation, now_dt, now_dt
            ))
        else:
            # Standalone Simplified Schema
            conn.execute("""
                INSERT INTO unani_assessments 
                (id, encounter_id, patient_id, hakeem_id, dominant_mizaj, mizaj_secondary, su_e_mizaj_type,
                 nabz_quality, baul_observations, baraz_observations, afaal_summary, asbab_sittah_assessment,
                 clinical_interpretation, assessment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'FINAL');
            """, (
                assessment_id, encounter_id, patient_id, hakeem_id, dominant_mizaj, mizaj_secondary,
                su_e_mizaj, nabz, assessment_data.get("baul_observations"), assessment_data.get("baraz_observations"),
                cascade_res.get("stage_name", "Tanqiya"), json.dumps(rationale_payload), interpretation
            ))

        # Record in z_mai_assessment_records if table exists
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='z_mai_assessment_records';")
            if cursor.fetchone():
                z_id = f"zmai-{uuid.uuid4().hex[:12]}"
                conn.execute("""
                    INSERT INTO z_mai_assessment_records
                    (id, patient_id, encounter_id, dominant_mizaj, secondary_mizaj, primary_axis, secondary_axis, recommended_protocol_code, assessed_by, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    z_id, patient_id, encounter_id, dominant_mizaj, mizaj_secondary,
                    primary_axis.get("name"), str(axis_res.get("secondary_axis")),
                    cascade_res.get("recommended_stage"), hakeem_id, interpretation, now_dt
                ))
        except Exception as e:
            pass

        return {
            "id": assessment_id,
            "encounter_id": encounter_id,
            "dominant_mizaj": dominant_mizaj,
            "mizaj_secondary": mizaj_secondary,
            "primary_axis": primary_axis,
            "afaal_cascade": cascade_res,
            "mizaj_calculation": mizaj_calc,
            **assessment_data
        }
