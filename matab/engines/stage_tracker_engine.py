"""ZAYVORA MATAB OS — Longitudinal Recovery & Tanqiya-Tadeel Stage Journey Tracker.
Provides structured progression tracking across the classical 4-stage Unani treatment timeline:
1. NUZJ (Concoction / Maturation)
2. ISTIFRAGH / TANQIYA (Targeted Humoral Evacuation / Detoxification)
3. TADEEL (Temperamental & Metabolic Equilibrating)
4. TAQWIYAT (Target Organ Strengthening & Recurrence Prevention)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

STAGE_CHRONOLOGY = [
    {
        "stage_code": "STAGE_1_NUZJ",
        "stage_name": "Stage 1: Nuzj (Humoral Concoction / Maturation)",
        "typical_day_range": [1, 10],
        "classical_principle": "Inzaaj-e-Mawad-e-Ghaleeza (Ripening & liquefying thick morbid humors)",
        "therapeutic_goal": "Prepare morbid matter for safe evacuation without causing vascular or tissue tear.",
        "common_medicines": ["Munzij-e-Balgham", "Munzij-e-Sauda", "Munzij-e-Safra", "Sharbat Banafsha", "Joshanda Munzij"],
        "readiness_criteria": ["Urine sediment (Rasub) becomes thicker and settled", "Tongue coating becomes looser and softer", "Subjective sensation of lightness in abdomen"],
        "next_step": "Transition to Stage 2 (Tanqiya / Mushil) once concoction signs (Alaamaat-e-Nuzj) are confirmed."
    },
    {
        "stage_code": "STAGE_2_TANQIYA",
        "stage_name": "Stage 2: Tanqiya (Targeted Humoral Evacuation / Mushil)",
        "typical_day_range": [11, 15],
        "classical_principle": "Istifragh-e-Mawad-e-Fasida (Elimination of ripened morbid matter)",
        "therapeutic_goal": "Expel concocted humors via therapeutic purgation, emesis, or diaphoresis.",
        "common_medicines": ["Mushil-e-Balgham", "Mushil-e-Safra", "Itrifal Sanai", "Habbe Suranjan", "Hijama bil Shart"],
        "readiness_criteria": ["Evacuation completed smoothly without persistent tenesmus", "Pulse settles to moderate volume", "Absence of nausea or visceral colic"],
        "next_step": "Transition to Stage 3 (Tadeel) to prevent dehydration and organ weakness."
    },
    {
        "stage_code": "STAGE_3_TADEEL",
        "stage_name": "Stage 3: Tadeel (Normalisation & Metabolic Harmonization)",
        "typical_day_range": [16, 30],
        "classical_principle": "Tadeel-e-Mizaj-e-Uzw wa Badan (Restoring physiological humoral equilibrium)",
        "therapeutic_goal": "Restore natural heat (Hararat-e-Ghariziyyah) and correct secondary dyscrasia.",
        "common_medicines": ["Majoon Dabeed-ul-Ward", "Khamira Gaozaban", "Sharbat Anar Shirin", "Jawarish Kamooni"],
        "readiness_criteria": ["Normal appetite and digestion (Hazm-e-Saleh)", "Regular bowel movements without laxatives", "Restful sleep and clear mentation"],
        "next_step": "Transition to Stage 4 (Taqwiyat) for long-term constitutional stability."
    },
    {
        "stage_code": "STAGE_4_TAQWIYAT",
        "stage_name": "Stage 4: Taqwiyat (Organ Tonicity & Disease Prevention)",
        "typical_day_range": [31, 90],
        "classical_principle": "Taqwiyat-e-A'za-e-Ra'eesa (Strengthening Vital Organs: Brain, Heart, Liver)",
        "therapeutic_goal": "Fortify primary organ tissues to permanently prevent recurrence of morbid dyscrasia.",
        "common_medicines": ["Majoon Falasfa", "Khamira Marwareed", "Kushta Marjan", "Majoon Arad Khurma", "Laboob Kabeer"],
        "readiness_criteria": ["Full restoration of stamina (Quwwat-e-Badaniyah)", "Zero recurrence of primary symptoms under moderate diet challenge"],
        "next_step": "Maintenance via Asbab-e-Sittah healthy lifestyle."
    }
]

def calculate_patient_recovery_stage(first_visit_date_str: Optional[str] = None, visit_number: int = 1) -> Dict[str, Any]:
    """Calculate current clinical recovery stage based on treatment duration."""
    days_elapsed = 1
    if first_visit_date_str:
        try:
            d0 = datetime.strptime(first_visit_date_str[:10], "%Y-%m-%d")
            days_elapsed = max(1, (datetime.now() - d0).days)
        except Exception:
            days_elapsed = 1
            
    if days_elapsed <= 10:
        stage = STAGE_CHRONOLOGY[0]
    elif days_elapsed <= 15:
        stage = STAGE_CHRONOLOGY[1]
    elif days_elapsed <= 30:
        stage = STAGE_CHRONOLOGY[2]
    else:
        stage = STAGE_CHRONOLOGY[3]
        
    return {
        "treatment_day": days_elapsed,
        "visit_number": visit_number,
        "current_stage": stage,
        "all_stages": STAGE_CHRONOLOGY
    }
