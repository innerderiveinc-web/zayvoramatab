"""
ZAYVORA HEALTH OS v5.0 — Afaal Cascade Clinical Engine
Codifies the classical Unani 4-stage therapeutic progression:
1. Tanqiya (Targeted Evacuation / Cleansing of Morbid Humors)
2. Tahleel (Resolution / Dissolution of Congestion & Inflammation)
3. Taqwiyaat (Restoration & Strengthening of Target Organs)
4. Hifz (Preservation & Maintenance of Innate Temperament Balance)
"""

from __future__ import annotations

from typing import Any


AFAAL_STAGES = {
    "TANQIYA": {
        "stage_number": 1,
        "name": "Tanqiya (Targeted Humoral Evacuation & Detoxification)",
        "classical_principle": "Istifragh-e-Mawad-e-Fasida (Elimination of Morbid Matter)",
        "description": "Preparation of morbid humors via concoction (Nujz) followed by organ-specific evacuation.",
        "standard_duration_days": 7,
        "primary_modalities": [
            "Munzaj wa Mus-hil (Concoctive & Evacuative Pharmacotherapy)",
            "Hijama (Wet / Dry Cupping for local stasis)",
            "Fasd (Venesection for plethoric sanguineous congestion)",
            "Qai / Huqna (Emesis or Medicated Enema for alimentary evacuation)",
        ],
        "monitoring_criteria": [
            "Reduction in tongue coating thickness (Lisan)",
            "Softening and settling of pulse volume (Nabz)",
            "Improvement in morning heaviness and joint stiffness",
        ],
    },
    "TAHLEEL": {
        "stage_number": 2,
        "name": "Tahleel (Resolution & Dissolution of Inflammation)",
        "classical_principle": "Tahleel-e-Auram wa Riyah (Dissolution of Swelling & Gaseous Stasis)",
        "description": "Resolution of localized inflammatory exudates, phlegmatic effusion, and peri-articular congestion.",
        "standard_duration_days": 14,
        "primary_modalities": [
            "Natool (Warm Medicated Decoction Irrigation)",
            "Zimad (Anti-inflammatory Medicated Poultice / Paste)",
            "Dalak Layyin (Gentle Emollient Massage with Warming Oils)",
            "Oral Muhallil (Resolvent) Formulations (e.g. Majun Suranjan, Hab-e-Guggal)",
        ],
        "monitoring_criteria": [
            "Decrease in localized synovial effusion and swelling",
            "Relief from tenderness on joint palpation",
            "Increase in degrees of active joint flexion",
        ],
    },
    "TAQWIYAAT": {
        "stage_number": 3,
        "name": "Taqwiyaat (Target & Master Organ Restoration)",
        "classical_principle": "Taqwiyat-e-A'za-e-Dha'eefah (Strengthening of Weakened Target Organs)",
        "description": "Rebuilding tissue resilience, metabolic tone, and functional strength to prevent recurrent humoral deposition.",
        "standard_duration_days": 28,
        "primary_modalities": [
            "Muqawwiyat-e-A'za (Organ-specific Tonics: Majun, Safoof, Khamira)",
            "Riyazat-e-Khafifa (Supervised Gentle Joint Mobilization Exercises)",
            "Nutritive Warming Broths (Maa-ul-Lahm, Harira)",
            "Corrective Musleh Combinations (Gum Acacia / Kateera)",
        ],
        "monitoring_criteria": [
            "Restoration of muscular grip strength and gait stability",
            "Sustained reduction in VAS pain score (<3/10)",
            "Normalization of inflammatory biomarkers (hs-CRP / ESR)",
        ],
    },
    "HIFZ": {
        "stage_number": 4,
        "name": "Hifz (Preservation & Long-Term Health Maintenance)",
        "classical_principle": "Hifzan-e-Sihhat (Preservation of Innate Equilibrium / Homeostasis)",
        "description": "Sustaining innate temperament equilibrium (Mizaj-e-Asli) and preventing disease recurrence via Asbab-e-Sittah.",
        "standard_duration_days": 90,
        "primary_modalities": [
            "Tadbeer-e-Asbab-e-Sittah (Regulation of 6 Essential Lifestyle Determinants)",
            "Seasonal Dietary Regimens (Tadbeer-e-Fusool: warming foods in winter)",
            "Riyazat-e-Motadila (Regular moderate daily physical exercise)",
            "Low-dose adaptogenic Rasayana / Muqawwi formulations",
        ],
        "monitoring_criteria": [
            "Zero symptom relapse over 3 consecutive months",
            "High compliance with personalized dietary parhez (>85%)",
            "Optimal sleep quality and mental tranquility (Nafsaniyah)",
        ],
    },
}


def evaluate_afaal_stage_recommendation(
    mizaj_dominant: str,
    organ_axis: str,
    chronicity_months: int = 1,
    current_stage: str | None = None,
    symptom_severity: str = "MODERATE",
) -> dict[str, Any]:
    """
    Evaluates clinical context and recommends the appropriate Afaal Cascade stage.
    Clinician retains absolute authority to approve or adjust the stage.
    """
    # Progression logic
    if current_stage == "TANQIYA":
        recommended_stage = "TAHLEEL"
        rationale = "Initial humoral evacuation completed. Progressing to resolution of localized inflammatory exudate."
    elif current_stage == "TAHLEEL":
        recommended_stage = "TAQWIYAAT"
        rationale = "Inflammatory effusion resolved. Initiating tissue strengthening and organ tonification."
    elif current_stage == "TAQWIYAAT":
        recommended_stage = "HIFZ"
        rationale = "Organ tone restored. Transitioning to long-term health preservation and lifestyle maintenance."
    elif current_stage == "HIFZ":
        recommended_stage = "HIFZ"
        rationale = "Patient remains in maintenance phase with stable equilibrium."
    else:
        # Initial presentation
        if symptom_severity in ["SEVERE", "ACUTE_EXACERBATION"] or chronicity_months < 3:
            recommended_stage = "TANQIYA"
            rationale = (
                f"Active humoral dyscrasia ({mizaj_dominant}) along {organ_axis} axis indicates primary "
                "need for concoction (Nujz) and evacuation (Tanqiya) of accumulated morbid matter."
            )
        elif symptom_severity == "MODERATE":
            recommended_stage = "TAHLEEL"
            rationale = (
                f"Subacute presentation in {organ_axis} axis. Primary clinical goal is resolution of local tissue "
                "congestion and pain relief via topical Tadbeer and resolvent formulations."
            )
        else:
            recommended_stage = "TAQWIYAAT"
            rationale = "Mild chronic impairment without acute effusion; indicated for organ tonification."

    stage_info = AFAAL_STAGES[recommended_stage]

    return {
        "recommended_stage": recommended_stage,
        "stage_number": stage_info["stage_number"],
        "stage_name": stage_info["name"],
        "classical_principle": stage_info["classical_principle"],
        "clinical_rationale": rationale,
        "standard_duration_days": stage_info["standard_duration_days"],
        "primary_modalities": stage_info["primary_modalities"],
        "monitoring_criteria": stage_info["monitoring_criteria"],
        "clinician_approval_required": True,
        "auto_assigned": False,
    }
