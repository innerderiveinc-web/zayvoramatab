"""Modern Clinical Support Domain: Deterministic Red-Flag Triage & Diagnostic Suggestions."""

import uuid
from typing import Dict, Any, List, Optional
import sqlite3

RED_FLAG_RULES = [
    {
        "id": "RF-ACS",
        "keywords": ["chest pain", "angina", "sweating", "radiating to left arm", "heavy chest"],
        "severity": "CRITICAL",
        "title": "Possible Acute Coronary Syndrome (ACS)",
        "guidance": "Emergency referral required. Immediate ECG, Aspirin, and cardiac evaluation."
    },
    {
        "id": "RF-STROKE",
        "keywords": ["sudden weakness", "facial drooping", "slurred speech", "hemiparesis", "loss of vision"],
        "severity": "CRITICAL",
        "title": "Suspected Acute Cerebrovascular Event (Stroke)",
        "guidance": "Time-critical emergency. Immediate brain imaging and emergency tertiary transfer."
    },
    {
        "id": "RF-HYPERTENSIVE-CRISIS",
        "rule_fn": lambda v: v and v.get("systolic_bp", 0) >= 180 or (v and v.get("diastolic_bp", 0) >= 110),
        "severity": "URGENT",
        "title": "Hypertensive Crisis (Stage 3)",
        "guidance": "Evaluate for target organ damage (headache, chest pain, vision change). Urgent blood pressure stabilization."
    },
    {
        "id": "RF-SEPSIS",
        "rule_fn": lambda v: v and (v.get("temperature_f", 0) >= 102.5 and v.get("pulse_bpm", 0) >= 110),
        "severity": "URGENT",
        "title": "Suspected Severe Systemic Infection / SIRS",
        "guidance": "Assess hydration, source of infection, and hemodynamic stability."
    }
]

class ClinicalSupportService:
    @staticmethod
    def evaluate_red_flags(clinical_text: str, vitals: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Run deterministic clinical safety rules against patient notes and vitals."""
        alerts = []
        text_lower = (clinical_text or "").lower()
        
        for rule in RED_FLAG_RULES:
            triggered = False
            trigger_reason = ""
            
            if "keywords" in rule:
                matched_kws = [kw for kw in rule["keywords"] if kw in text_lower]
                if matched_kws:
                    triggered = True
                    trigger_reason = f"Identified warning keywords: {', '.join(matched_kws)}"
                    
            if "rule_fn" in rule and vitals:
                if rule["rule_fn"](vitals):
                    triggered = True
                    trigger_reason = "Vital sign thresholds breached critical limits."
                    
            if triggered:
                alerts.append({
                    "rule_id": rule["id"],
                    "severity": rule["severity"],
                    "title": rule["title"],
                    "guidance": rule["guidance"],
                    "reason": trigger_reason
                })
                
        return alerts

    @staticmethod
    def save_clinical_problems(conn: sqlite3.Connection, encounter_id: str, problems: List[Dict[str, Any]]) -> None:
        """Save confirmed modern diagnostic problems and ICD-10 candidates."""
        for p in problems:
            conn.execute("""
                INSERT INTO clinical_problems (id, encounter_id, problem_name, icd10_code, status, is_red_flag)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (
                str(uuid.uuid4()),
                encounter_id,
                p.get("problem_name", "").strip(),
                p.get("icd10_code"),
                p.get("status", "ACTIVE"),
                1 if p.get("is_red_flag") else 0
            ))

    @staticmethod
    def get_clinical_intelligence(
        complaint: str = '',
        symptoms: Optional[List[str]] = None,
        dominant_mizaj: Optional[str] = None,
        su_e_mizaj_type: Optional[str] = None,
        nabz_quality: Optional[str] = None,
        vitals: Optional[Dict[str, Any]] = None,
        patient_age: Optional[int] = None,
        current_season: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compute unified cross-epistemological intelligence: Organ-Axis, Af'aal Cascade, Mizaj refinement, and Red Flags."""
        combined_text = f"{complaint or ''} {' '.join(symptoms or [])}"
        red_flags = ClinicalSupportService.evaluate_red_flags(combined_text, vitals)
        
        # 1. Organ-Axis deduction
        from matab.engines.organ_axis_engine import deduce_organ_axes_and_reflexes
        axis_data = deduce_organ_axes_and_reflexes(complaint or 'General Malaise', symptoms or [])
        primary_axis = axis_data.get('primary_axis') or {
            'id': 'meda-amaa',
            "name": "Gastro-Intestinal Axis (Meda wa Am'a)",
            'governing_power': 'Quwwat-e-Hazima wa Dafia (Digestive & Expulsive Faculty)',
            'primary_organ': 'Meda (Stomach)'
        }
        secondary_axis = axis_data.get('secondary_axis')
        
        # 2. Af'aal Cascade recommendation
        from matab.engines.afaal_cascade_engine import evaluate_afaal_stage_recommendation
        mizaj_clean = dominant_mizaj or 'Balghami'
        axis_name_clean = primary_axis.get('name', 'Gastro-Intestinal')
        cascade_data = evaluate_afaal_stage_recommendation(
            mizaj_dominant=mizaj_clean,
            organ_axis=axis_name_clean,
            chronicity_months=2,
            current_stage=None,
            symptom_severity='MODERATE'
        )
        
        stage_name = cascade_data.get('stage_name', 'Tadeel-e-Mizaj')
        principle = cascade_data.get('classical_principle', 'Tadeel-e-Mizaj wa Tanqiya')
        suggested_usul = f"{stage_name}: {principle} targeting {primary_axis.get('name', 'Affected Axis')}."
        
        # 4. Generate Diet & Parhez Sheet
        from matab.engines.diet_parhez_engine import generate_diet_parhez_sheet
        diet_data = generate_diet_parhez_sheet(
            dominant_mizaj=mizaj_clean,
            primary_axis_id=primary_axis.get('id', 'meda-amaa'),
            su_e_mizaj_type=su_e_mizaj_type or 'MADDI'
        )

        # 5. Ilaj-bit-Tadbeer Regimenal Recommendation
        from matab.engines.tadbeer_engine import get_recommended_tadbeer_protocols
        tadbeer_data = get_recommended_tadbeer_protocols(
            primary_axis_id=primary_axis.get('id', 'meda-amaa'),
            dominant_mizaj=mizaj_clean
        )

        # 6. Longitudinal Stage Tracking
        from matab.engines.stage_tracker_engine import calculate_patient_recovery_stage
        recovery_stage = calculate_patient_recovery_stage(visit_number=1)

        return {
            'red_flags': red_flags,
            'has_critical_red_flag': any(rf['severity'] == 'CRITICAL' for rf in red_flags),
            'primary_axis': primary_axis,
            'secondary_axis': secondary_axis,
            'reflex_sympathy': axis_data.get('reflex_sympathy_identified', False),
            'afaal_cascade': cascade_data,
            'diet_parhez': diet_data,
            'tadbeer_protocols': tadbeer_data,
            'recovery_stage': recovery_stage,
            'suggested_usul_e_ilaj': suggested_usul,
            'mizaj_dominant': mizaj_clean,
            'su_e_mizaj_type': su_e_mizaj_type or 'MADDI',
            'nabz_quality': nabz_quality or 'MUTAWASSIT'
        }
