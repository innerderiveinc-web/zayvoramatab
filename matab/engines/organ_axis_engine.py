"""
Organ-Axis Reflex Arc and Pathophysiological Progression Engine.

Codifies the classical Unani doctrine of:
1. 12 Canonical Organ Axes (A'za-e-Ra'eesa and subordinate functional networks)
2. Reflex Arcs (Mushaarakat-e-A'za) distinguishing root etiology from sympathetic secondary symptoms
3. Four Classical Causes (Asbab-e-Arba'a): Fa'il, Maddi, Suri, Tamami
4. Disease Progression Stages (Dawr-e-Marad): Ibtida, Tazayud, Intiha, Inhitat, with stage-appropriate Usool-e-Ilaj
"""
from __future__ import annotations

from typing import Any

CANONICAL_ORGAN_AXES: dict[str, dict[str, Any]] = {
    "dimagh-asab": {
        "name": "Brain & Nervous Axis (Dimagh wa Asab)",
        "governing_power": "Quwwat-e-Nafsaniyah (Psychic & Neurological Faculty)",
        "primary_organ": "Brain",
        "description": "Governs sensation, voluntary movement, cognition, sleep, and mental states.",
    },
    "qalb": {
        "name": "Cardiovascular Axis (Qalb wa Sharayeen)",
        "governing_power": "Quwwat-e-Haiwaniyah (Vital Faculty)",
        "primary_organ": "Heart",
        "description": "Source of innate heat (Hararat-e-Ghariziyah) and vital spirit (Ruh-e-Haiwani).",
    },
    "kabid-tihal": {
        "name": "Hepatosplenic Axis (Kabid wa Tihal)",
        "governing_power": "Quwwat-e-Tabi'iyah (Natural / Metabolic Faculty)",
        "primary_organ": "Liver",
        "description": "Seat of hematopoiesis, humor generation (Akhlat), and intermediate metabolism.",
    },
    "kulliya-masana": {
        "name": "Renovesical Axis (Kulliya wa Masana)",
        "governing_power": "Quwwat-e-Dafia (Expulsive & Excretory Faculty)",
        "primary_organ": "Kidneys",
        "description": "Governs fluid filtration, urinary excretion, and systemic humor balance.",
    },
    "meda-amaa": {
        "name": "Gastrointestinal Axis (Meda wa Ama'a)",
        "governing_power": "Quwwat-e-Hazima (Digestive Faculty)",
        "primary_organ": "Stomach",
        "description": "Governs ingestion, gastric concoction (Hazm-e-Midi), and intestinal absorption.",
    },
    "tanaffus": {
        "name": "Pulmonary Axis (A'za-e-Tanaffus)",
        "governing_power": "Quwwat-e-Nafsiyah / Tanaffusiyah (Respiratory Faculty)",
        "primary_organ": "Lungs",
        "description": "Provides clean atmospheric air (Naseem) to cool innate heat and ventilate the heart.",
    },
    "jinsi-tawallud": {
        "name": "Reproductive Axis (A'za-e-Tanasul)",
        "governing_power": "Quwwat-e-Tawalludiyah (Generative Faculty)",
        "primary_organ": "Gonads",
        "description": "Governs sexual vitality, hormonal balance, and lineage preservation.",
    },
    "jild-ashar": {
        "name": "Integumentary Axis (Jild wa Ash'ar)",
        "governing_power": "Quwwat-e-Ghazia & Dafia (Nutritive & Dermal Secretory Faculty)",
        "primary_organ": "Skin",
        "description": "Barrier defense, perspiration, tactile sensation, and superficial humor deposition.",
    },
    "mafasil-asab": {
        "name": "Musculoskeletal Axis (Mafasil wa Azam)",
        "governing_power": "Quwwat-e-Muharrika (Locomotor Faculty)",
        "primary_organ": "Joints & Bones",
        "description": "Structural framework, locomotion, synovial lubrication (Rutoobat-e-Mafasil).",
    },
    "baasira": {
        "name": "Ocular Axis (Basira)",
        "governing_power": "Quwwat-e-Basira (Visual Faculty)",
        "primary_organ": "Eyes",
        "description": "Vision, ocular humor clarity (Rutoobat-e-Baiza & Jalidiya).",
    },
    "saamiah-anf": {
        "name": "ENT / Otorhinolaryngological Axis (Uzn wa Anf)",
        "governing_power": "Quwwat-e-Hassasa (Special Sensory Faculty)",
        "primary_organ": "Ears & Nasopharynx",
        "description": "Auditory, olfactory, and upper airway filtration.",
    },
    "mizaj-am": {
        "name": "Constitutional Systemic Axis (Mizaj-e-Kulli)",
        "governing_power": "All faculties in equilibrium",
        "primary_organ": "Whole organism",
        "description": "Systemic constitutional balance, innate heat, and metabolic vitality.",
    },
}

AXIS_BIOMARKER_MAP: dict[str, list[dict[str, str]]] = {
    "dimagh-asab": [
        {"biomarker": "Serum BDNF", "clinical_utility": "Neuroplasticity and neuronal resilience"},
        {"biomarker": "Morning Cortisol", "clinical_utility": "HPA axis arousal and psychological stress"},
        {"biomarker": "Plasma Homocysteine", "clinical_utility": "Cerebrovascular and neurodegenerative risk"},
    ],
    "qalb": [
        {"biomarker": "hs-CRP (High-Sensitivity C-Reactive Protein)", "clinical_utility": "Endothelial and microvascular inflammation"},
        {"biomarker": "Lipid Profile (LDL-C / HDL-C / TG)", "clinical_utility": "Vascular humor stagnation and atherogenesis"},
        {"biomarker": "NT-proBNP", "clinical_utility": "Ventricular wall stress and myocardial workload"},
    ],
    "kabid-tihal": [
        {"biomarker": "ALT / SGPT & AST / SGOT", "clinical_utility": "Hepatocellular integrity and Hazm-e-Kabidi efficiency"},
        {"biomarker": "Serum Bilirubin (Total & Direct)", "clinical_utility": "Biliary excretion and Safra clearance"},
        {"biomarker": "Serum Albumin", "clinical_utility": "Hepatic synthetic capacity (Quwwat-e-Mughayyira)"},
    ],
    "kulliya-masana": [
        {"biomarker": "Serum Creatinine & eGFR", "clinical_utility": "Glomerular filtration rate and Tanqiya-e-Kulwi"},
        {"biomarker": "Blood Urea Nitrogen (BUN)", "clinical_utility": "Nitrogenous waste excretion and catabolic balance"},
        {"biomarker": "Serum Uric Acid", "clinical_utility": "Purine metabolism and nephrolithiasis propensity"},
    ],
    "meda-amaa": [
        {"biomarker": "Fecal Calprotectin", "clinical_utility": "Intestinal mucosal barrier inflammation"},
        {"biomarker": "Serum Pepsinogen I/II Ratio", "clinical_utility": "Gastric acid output and mucosal concoction efficiency"},
        {"biomarker": "Zonulin", "clinical_utility": "Intestinal epithelial tight junction permeability"},
    ],
    "tanaffus": [
        {"biomarker": "Fractional Exhaled Nitric Oxide (FeNO)", "clinical_utility": "Eosinophilic airway inflammation"},
        {"biomarker": "Absolute Eosinophil Count (AEC)", "clinical_utility": "Allergic and humoral pulmonary hyperreactivity"},
        {"biomarker": "Serum Total IgE", "clinical_utility": "Atopic sensitization and airway hyperresponsiveness"},
    ],
    "mafasil-asab": [
        {"biomarker": "Serum Uric Acid", "clinical_utility": "Niqris (gouty arthritis) crystal deposition risk"},
        {"biomarker": "Erythrocyte Sedimentation Rate (ESR)", "clinical_utility": "Systemic musculoskeletal inflammatory activity"},
        {"biomarker": "Anti-CCP / RF", "clinical_utility": "Autoimmune articular damage differentiation"},
    ],
    "jinsi-tawallud": [
        {"biomarker": "Serum Total & Free Testosterone", "clinical_utility": "Gonadal vitality and anabolic vigor (Quwwat-e-Bah)"},
        {"biomarker": "Estradiol & Progesterone", "clinical_utility": "Endometrial cycle rhythm and reproductive humoral balance"},
    ],
    "jild-ashar": [
        {"biomarker": "Serum Ferritin & Zinc", "clinical_utility": "Follicular and dermal nutritional matrix"},
        {"biomarker": "Serum Total IgE", "clinical_utility": "Allergic eczema and cutis reactivity"},
    ],
    "mizaj-am": [
        {"biomarker": "Fasting Plasma Glucose & HbA1c", "clinical_utility": "Systemic metabolic heat and glycemic homeostasis"},
        {"biomarker": "Complete Blood Count (CBC)", "clinical_utility": "Hematopoietic vitality and humoral cellular balance"},
    ],
}

REFLEX_ARCS: list[dict[str, Any]] = [
    {
        "id": "gastro-cephalic",
        "name": "Meda-o-Dimagh (Gastro-Cephalic Sympathy)",
        "primary_axis": "meda-amaa",
        "reflex_axis": "dimagh-asab",
        "classical_mechanism": "Ascending morbid gastric vapors (Bukharat-e-Radiya) irritate the meninges or cerebral faculties.",
        "trigger_keywords": ["headache after food", "suda midi", "vertigo", "gastric headache", "dyspepsia headache", "nausea headache", "postprandial fog"],
        "clinical_presentation": "Throbbing or heavy frontal/temporal headache preceded or accompanied by epigastric fullness, nausea, belching, or acid reflux.",
    },
    {
        "id": "cardio-cerebral",
        "name": "Qalb-o-Dimagh (Cardio-Cerebral Sympathy)",
        "primary_axis": "qalb",
        "reflex_axis": "dimagh-asab",
        "classical_mechanism": "Cardiac palpitation (Khafqan) and vital spirit agitation reflect upward, producing secondary anxiety, melancholic apprehension, and syncope.",
        "trigger_keywords": ["palpitation anxiety", "khafqan", "panic heart", "cardiac syncope", "chest flutter apprehension"],
        "clinical_presentation": "Paroxysmal tachycardia or palpitations immediately triggering severe psychic dread, claustrophobia, or lipothymia.",
    },
    {
        "id": "hepato-renal",
        "name": "Kabid-o-Kulliya (Hepato-Renal Sympathy)",
        "primary_axis": "kabid-tihal",
        "reflex_axis": "kulliya-masana",
        "classical_mechanism": "Hepatic venous stasis or metabolic intoxication impairs renal perfusion and fluid excretion.",
        "trigger_keywords": ["liver fluid retention", "jaundice oliguria", "portal edema", "swelling feet liver", "ascites kidney"],
        "clinical_presentation": "Abdominal fullness and hepatomegaly followed by secondary ankle edema, reduced urinary output, and dark urine.",
    },
    {
        "id": "gastro-pulmonary",
        "name": "Meda-o-Tanaffus (Gastro-Pulmonary Sympathy)",
        "primary_axis": "meda-amaa",
        "reflex_axis": "tanaffus",
        "classical_mechanism": "Excess gastric meteorism (Nafakh) exerts diaphragmatic upward pressure or cold phlegmatic vapors precipitate bronchospasm.",
        "trigger_keywords": ["breathless after meal", "asthma indigestion", "diq un nafas midi", "bloating cough", "stomach asthma"],
        "clinical_presentation": "Wheezing, nocturnal cough, or shortness of breath triggered or worsened immediately following heavy or flatulent meals.",
    },
    {
        "id": "hepato-articular",
        "name": "Kabid-o-Mafasil (Hepato-Articular Sympathy)",
        "primary_axis": "kabid-tihal",
        "reflex_axis": "mafasil-asab",
        "classical_mechanism": "Impaired liver digestion (Hazm-e-Kabidi) deposits unconcocted metabolic waste (Fuzalaat) into articular cavities.",
        "trigger_keywords": ["joint pain indigestion", "gout liver", "niqris kabid", "wajaul mafasil digestive"],
        "clinical_presentation": "Inflammatory arthritis or gout flare-ups coinciding with fatty dyspepsia, alcohol/meat excess, or sluggish hepatic clearance.",
    },
    {
        "id": "renovesical-gastro",
        "name": "Kulliya-o-Meda (Renovesical-Gastric Reflex)",
        "primary_axis": "kulliya-masana",
        "reflex_axis": "meda-amaa",
        "classical_mechanism": "Renal capsular distension and visceral sympathetic plexus irritation trigger violent reflex gastroparesis and emesis.",
        "trigger_keywords": ["renal colic vomiting", "kidney pain nausea", "flank pain vomiting", "colic emesis"],
        "clinical_presentation": "Acute unilateral flank pain radiating to groin accompanied by refractory nausea, vomiting, and abdominal guarding.",
    },
]


def deduce_organ_axes_and_reflexes(complaint: str, associated_symptoms: list[str] | None = None) -> dict[str, Any]:
    """Deduces the primary target organ axis and identifies cross-organ
    sympathies (Reflex Arcs / Mushaarakat).
    """
    text = (complaint + " " + " ".join(associated_symptoms or [])).lower()
    
    # 1. Detect active reflex arcs
    active_reflexes = []
    for arc in REFLEX_ARCS:
        if any(kw in text for kw in arc["trigger_keywords"]):
            active_reflexes.append(arc)

    # 2. Identify primary and secondary axes
    if active_reflexes:
        primary_axis_id = active_reflexes[0]["primary_axis"]
        secondary_axis_id = active_reflexes[0]["reflex_axis"]
        reflex_identified = True
    else:
        reflex_identified = False
        secondary_axis_id = None
        # Heuristic axis identification
        if any(w in text for w in ["joint", "knee", "backache", "arthritis", "gout", "mafasil", "sciatica", "stiffness"]):
            primary_axis_id = "mafasil-asab"
        elif any(w in text for w in ["headache", "migraine", "nerve", "stroke", "epilepsy", "memory", "dimagh", "vertigo"]):
            primary_axis_id = "dimagh-asab"
        elif any(w in text for w in ["heart", "palpitation", "chest", "qalb", "angina"]):
            primary_axis_id = "qalb"
        elif any(w in text for w in ["stomach", "dyspepsia", "gastric", "ulcer", "constipation", "diarrhea", "meda", "acid"]):
            primary_axis_id = "meda-amaa"
        elif any(w in text for w in ["cough", "asthma", "breath", "lung", "bronch", "phlegm", "tanaffus"]):
            primary_axis_id = "tanaffus"
        elif any(w in text for w in ["liver", "jaundice", "hepat", "kabid", "ascites"]):
            primary_axis_id = "kabid-tihal"
        elif any(w in text for w in ["kidney", "urine", "dysuria", "renal", "calculus", "bladder"]):
            primary_axis_id = "kulliya-masana"
        elif any(w in text for w in ["skin", "eczema", "psoriasis", "rash", "pruritus", "itching"]):
            primary_axis_id = "jild-ashar"
        else:
            primary_axis_id = "mizaj-am"

    primary_axis_info = CANONICAL_ORGAN_AXES.get(primary_axis_id, CANONICAL_ORGAN_AXES["mizaj-am"])
    secondary_axis_info = CANONICAL_ORGAN_AXES.get(secondary_axis_id) if secondary_axis_id else None

    return {
        "primary_axis": {
            "id": primary_axis_id,
            "name": primary_axis_info["name"],
            "governing_power": primary_axis_info["governing_power"],
            "primary_organ": primary_axis_info["primary_organ"],
            "description": primary_axis_info["description"],
        },
        "secondary_axis": {
            "id": secondary_axis_id,
            "name": secondary_axis_info["name"] if secondary_axis_info else None,
            "governing_power": secondary_axis_info["governing_power"] if secondary_axis_info else None,
        } if secondary_axis_id else None,
        "reflex_sympathy_identified": reflex_identified,
        "detected_reflex_arcs": active_reflexes,
    }


def deduce_asbab_e_arbaa(
    complaint: str,
    temperament_context: dict[str, Any] | None = None,
    primary_axis_id: str = "mizaj-am",
) -> dict[str, str]:
    """Deduces the Four Classical Causes (Asbab-e-Arba'a) of the condition."""
    text = complaint.lower()
    temp = (temperament_context or {}).get("primary_temperament", "Mutadil")

    # Sabab-e-Fa'il (Active cause / Su-e-Mizaj)
    if "hot" in text or "burning" in text or "fever" in text or temp == "Safrawi":
        sabab_fail = "Su-e-Mizaj Har (Excessive Pathological Heat / Inflammation)"
    elif "cold" in text or "stiff" in text or temp == "Balghami":
        sabab_fail = "Su-e-Mizaj Barid (Excessive Pathological Cold / Slowed Kinetics)"
    elif "dry" in text or "rough" in text or temp == "Saudawi":
        sabab_fail = "Su-e-Mizaj Yabis (Excessive Pathological Dryness / Rigidity)"
    else:
        sabab_fail = "Su-e-Mizaj Ratab (Excessive Pathological Moisture / Effusion)"

    # Sabab-e-Maddi (Material / Humoral cause)
    if any(w in text for w in ["phlegm", "mucus", "numbness", "pallor", "cold swelling"]):
        sabab_maddi = "Khilt-e-Balgham Kham (Crude Unconcocted Phlegmatic Stagnation)"
    elif any(w in text for w in ["burning", "acid", "yellow", "bitter", "redness", "acute pain"]):
        sabab_maddi = "Khilt-e-Safra-e-Muharriq (Irritant Choler / Bilious Overflow)"
    elif any(w in text for w in ["chronic", "melancholy", "insomnia", "dark", "weight loss"]):
        sabab_maddi = "Khilt-e-Sauda-e-Ihtiraqi (Burnt Combustion Residue / Melancholic Deposit)"
    else:
        sabab_maddi = "Ghalba-e-Dam (Plethora / Sanguine Surcharge)"

    # Sabab-e-Suri (Structural / Morphological cause)
    if any(w in text for w in ["block", "obstruction", "colic", "constipation", "calculus"]):
        sabab_suri = "Sudda (Lumen Obstruction in Canals / Ducts / Vessels)"
    elif any(w in text for w in ["swelling", "edema", "tumor", "mass"]):
        sabab_suri = "Waram (Inflammatory Organ Enlargement / Effusion)"
    elif any(w in text for w in ["tear", "fracture", "ulcer", "wound"]):
        sabab_suri = "Tafarruq-e-Ittisal (Disruption of Tissue Continuity / Ulceration)"
    else:
        sabab_suri = "Su-e-Tarkeeb (Micro-structural Dyscrasia without gross rupture)"

    # Sabab-e-Tamami (Final / Faculty Consequence)
    if primary_axis_id == "dimagh-asab":
        sabab_tamami = "Zof-e-Quwwat-e-Nafsaniyah (Debility of Mental & Cognitive Execution)"
    elif primary_axis_id == "qalb":
        sabab_tamami = "Zof-e-Quwwat-e-Haiwaniyah (Impairment of Vital Heat Circulation)"
    elif primary_axis_id in ("kabid-tihal", "meda-amaa"):
        sabab_tamami = "Su-e-Hazm wa But-e-Inhidam (Digestive & Hematopoietic Inefficiency)"
    elif primary_axis_id == "kulliya-masana":
        sabab_tamami = "Ihtibas-e-Bawl wa Fuzalaat (Impairment of Renal Excretory Expulsion)"
    else:
        sabab_tamami = "Inhitaat-e-Quwwat-e-Mudabbira (Suppression of Innate Self-Healing Faculty)"

    return {
        "sabab_fail": sabab_fail,
        "sabab_maddi": sabab_maddi,
        "sabab_suri": sabab_suri,
        "sabab_tamami": sabab_tamami,
    }


def analyze_dawr_e_marad(
    duration_days: int | None = None,
    symptom_acuity: str = "moderate",
    inflammatory_signs: bool = False,
) -> dict[str, Any]:
    """Analyzes the chronological stage of disease progression (Dawr-e-Marad)
    and prescribes the classical stage-specific therapeutic principle.
    """
    days = duration_days or 7

    if days <= 3 and symptom_acuity in ("mild", "moderate"):
        stage = "Ibtida (Inception / Prodrome)"
        stage_code = "ibtida"
        clinical_state = "Early humoral disturbance; morbid matter is localized and unmixed."
        usool_e_ilaj = "Tadeel-e-Mizaj (Temperament normalization) and protective dietary regimen (Parhez). Avoid harsh evacuation."
        therapeutic_priorities = [
            "Preserve innate heat (Hararat-e-Ghariziyah)",
            "Administer gentle correctives (Tadeel)",
            "Maintain restful Asbab Sittah hygiene",
        ]
    elif (3 < days <= 14) or (days > 14 and inflammatory_signs):
        stage = "Tazayud (Augmentation / Progression)"
        stage_code = "tazayud"
        clinical_state = "Morbid matter is spreading and actively reacting; concoction (Nujz) in progress."
        usool_e_ilaj = "Nujz-e-Khilt (Administering Munzij drugs to mature and liquefy the morbid humor for subsequent evacuation)."
        therapeutic_priorities = [
            "Administer Munzij-e-Balgham or Munzij-e-Safra",
            "Support hepatic and renal excretory channels",
            "Avoid premature violent purgation before complete concoction",
        ]
    elif symptom_acuity == "severe" or (days > 14 and not inflammatory_signs and days <= 30):
        stage = "Intiha (Acme / Peak Crisis)"
        stage_code = "intiha"
        clinical_state = "Maturity of morbid matter reached; maximum clinical crisis."
        usool_e_ilaj = "Tanqiya (Targeted Evacuation / Istifragh of concocted morbid humors via Mus-hilat, Hijama, or Fasd)."
        therapeutic_priorities = [
            "Perform active evacuation (Tanqiya-e-Kulli or Tanqiya-e-Juz'i)",
            "Prescribe classical Mus-hil formulation (e.g. Habb-e-Suranjan, Itrifal Ustukhuddus)",
            "Monitor patient strength and hydration closely",
        ]
    else:
        stage = "Inhitat (Decline / Convalescence)"
        stage_code = "inhitat"
        clinical_state = "Morbid matter expelled; patient enters recovery with residual tissue debility."
        usool_e_ilaj = "Taqwiyat-e-A'za (Organ Restorative & Tonification with Muqawwiyat and nutrient-dense Ghiza)."
        therapeutic_priorities = [
            "Administer Muqawwi-e-Dimagh or Muqawwi-e-Kabid (e.g. Majun Falasifa, Khamira Gaozaban)",
            "Prescribe restorative nutrition (Ghiza-e-Kaseer-ul-Taghziya)",
            "Gradual resumption of physical movement (Harkat-e-Badani)",
        ]

    return {
        "stage": stage,
        "stage_code": stage_code,
        "clinical_state": clinical_state,
        "usool_e_ilaj": usool_e_ilaj,
        "therapeutic_priorities": therapeutic_priorities,
    }


def map_axis_biomarkers(primary_axis_id: str, secondary_axis_id: str | None = None) -> dict[str, Any]:
    """Maps canonical laboratory biomarkers to primary and secondary reflex organ axes."""
    primary_markers = AXIS_BIOMARKER_MAP.get(primary_axis_id, AXIS_BIOMARKER_MAP["mizaj-am"])
    secondary_markers = AXIS_BIOMARKER_MAP.get(secondary_axis_id, []) if secondary_axis_id else []

    cross_talk_indicators = []
    if secondary_axis_id:
        cross_talk_indicators.append(
            f"Cross-axis correlation indicated: correlate primary {primary_axis_id} markers with reflex {secondary_axis_id} biomarkers."
        )

    return {
        "primary_axis_biomarkers": primary_markers,
        "reflex_axis_biomarkers": secondary_markers,
        "cross_talk_indicators": cross_talk_indicators,
    }


def run_complete_organ_axis_analysis(
    complaint: str,
    associated_symptoms: list[str] | None = None,
    duration_days: int | None = None,
    symptom_acuity: str = "moderate",
    inflammatory_signs: bool = False,
    temperament_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Master orchestrator generating full Unani pathophysiological assessment."""
    axis_analysis = deduce_organ_axes_and_reflexes(complaint, associated_symptoms)
    primary_id = axis_analysis["primary_axis"]["id"]
    secondary_id = axis_analysis["secondary_axis"]["id"] if axis_analysis.get("secondary_axis") else None

    asbab = deduce_asbab_e_arbaa(complaint, temperament_context, primary_id)
    dawr = analyze_dawr_e_marad(duration_days, symptom_acuity, inflammatory_signs)
    biomarkers = map_axis_biomarkers(primary_id, secondary_id)

    return {
        "complaint": complaint,
        "organ_axes": axis_analysis,
        "asbab_e_arbaa": asbab,
        "dawr_e_marad": dawr,
        "biomarker_cross_talk": biomarkers,
    }



# Integration with ZAYVORA Master Knowledge System
try:
    from services.knowledge.app.data.organ_axes_master import (
        ORGAN_AXES_CATALOG as MASTER_12_AXES_CATALOG,
        score_organ_axes as master_score_organ_axes,
        get_all_axes as master_get_all_axes,
        get_axis_by_id as master_get_axis_by_id,
    )
    from services.knowledge.app.data.protocols_master import (
        get_protocol_for_axis as master_get_protocol_for_axis,
        get_protocol_by_id as master_get_protocol_by_id,
    )
except ImportError:
    MASTER_12_AXES_CATALOG = {}
    master_score_organ_axes = None
    master_get_all_axes = None
    master_get_axis_by_id = None
    master_get_protocol_for_axis = None
    master_get_protocol_by_id = None


def score_canonical_12_axes(scores: dict[str, int]) -> dict[str, Any]:
    """
    Scores patient condition against the 12 canonical organ axes (0-5 scale).
    Determines Primary Axis (treated Phase 1) and Secondary Axis (treated Phase 2).
    """
    if master_score_organ_axes:
        return master_score_organ_axes(scores)
    return {"scores": scores, "error": "organ_axes_master not imported"}


def get_canonical_axis_details(axis_id: str) -> dict[str, Any] | None:
    """Returns detailed catalog data for a canonical organ axis."""
    if master_get_axis_by_id:
        return master_get_axis_by_id(axis_id)
    return None


# =====================================================================
# CP-AFUM / AFUF 6-AXIS SYSTEMS BIOLOGY & 5 PRIORITY RULES
# Source: Dr. Irfan Ashraf — CP-AFUM Textbook Chapter 2 & Table 2.1
# =====================================================================

CP_AFUM_6_AXES = {
    "gut-liver": {
        "id": "gut-liver",
        "name": "Gut-Liver Axis",
        "systems": "Intestinal microbiome -> Portal vein -> Hepatic Phase 1 & 2 detox",
        "primary_conditions": ["PCOS (indirect)", "Acne", "Chronic Fatigue", "Fatty Liver / NAFLD", "IBS"],
        "key_biomarkers": ["SGPT (ALT)", "GGT", "hs-CRP", "SGOT/SGPT (de Ritis ratio)"],
        "hero_product": "LiverPrime Core™ (mandatory in ALL cases Phase 1)"
    },
    "liver-pancreas": {
        "id": "liver-pancreas",
        "name": "Liver-Pancreas Axis",
        "systems": "Hepatic glucose output (HGO) <-> Pancreatic insulin secretion <-> AMPK signaling",
        "primary_conditions": ["Type 2 Diabetes", "Obesity", "Insulin Resistance", "Metabolic Syndrome", "NAFLD"],
        "key_biomarkers": ["HbA1c", "Fasting Insulin", "HOMA-IR", "SGPT", "TG/HDL ratio"],
        "hero_product": "MetaboCore Elite™"
    },
    "gut-ovarian": {
        "id": "gut-ovarian",
        "name": "Gut-Ovarian Axis",
        "systems": "Estrobolome (β-glucuronidase) -> Estrogen recycling -> GnRH -> LH/FSH -> Ovarian theca/granulosa cells",
        "primary_conditions": ["PCOS", "Ovulatory dysfunction", "Estrogen dominance", "Infertility", "Cycle irregularity"],
        "key_biomarkers": ["LH:FSH ratio", "AMH", "Estradiol", "SHBG", "Fasting Insulin"],
        "hero_product": "OvaSync™"
    },
    "liver-testicular": {
        "id": "liver-testicular",
        "name": "Liver-Testicular Axis",
        "systems": "Hepatic sex hormone metabolism (SHBG) -> Sertoli cell function -> Spermatogenesis / Leydig cell testosterone",
        "primary_conditions": ["Male infertility", "Oligospermia", "Asthenozoospermia", "Low Testosterone", "High DFI"],
        "key_biomarkers": ["Semen Analysis", "Total Testosterone", "SHBG", "SGPT", "FSH", "LH", "DFI"],
        "hero_product": "ManiVital Pro™"
    },
    "thyroid-neuro": {
        "id": "thyroid-neuro",
        "name": "Thyroid-Neuro Axis",
        "systems": "Hypothalamic TRH -> Pituitary TSH -> Thyroid T4 -> Hepatic T4->T3 conversion (60%) -> Neurological function",
        "primary_conditions": ["Hypothyroidism", "Subclinical thyroid dysfunction", "Brain fog", "Metabolic slowness", "Hashimoto's"],
        "key_biomarkers": ["TSH", "Free T3", "Free T4", "Anti-TPO", "Selenium"],
        "hero_product": "ThyroMet Axis™"
    },
    "hpa-axis": {
        "id": "hpa-axis",
        "name": "HPA Axis",
        "systems": "Hypothalamic CRH -> Pituitary ACTH -> Adrenal cortisol -> Autonomic NS -> Gut-brain feedback loop",
        "primary_conditions": ["Anxiety", "Insomnia", "Burnout", "IBS", "Adrenal fatigue", "Stress-related infertility"],
        "key_biomarkers": ["Cortisol AM/PM", "DHEA-S", "Cortisol:DHEAS ratio", "PSQI", "PHQ-9"],
        "hero_product": "NeuroCalmX™"
    }
}


def evaluate_five_axis_priority_rules(
    sgpt: float,
    hs_crp: float,
    has_hpa_dysregulation: bool,
    has_thyroid_dysfunction: bool,
    active_axes: list[str]
) -> dict[str, Any]:
    """
    Evaluates the 5 Non-Negotiable Axis Priority Rules from CP-AFUM Chapter 2:
    - Rule 1: Gut-Liver Rule: SGPT >45 U/L or hs-CRP >3 mg/L mandates Phase 1 Gut-Liver treatment first.
    - Rule 2: HPA-First Rule: HPA must be stabilized before gonadal, metabolic, or thyroid correction.
    - Rule 3: Thyroid-HPA Rule: Thyroid dysfunction coexisting with HPA is treated after (not with) HPA.
    - Rule 4: Two-Axis Limit: Maximum 2 primary axes addressed in Phase 2.
    - Rule 5: Liver-Phase Rule: LiverPrime Core present in Phase 1 and 50% maintenance in Phase 2.
    """
    decisions = []
    
    # Rule 1: Gut-Liver Rule
    gut_liver_mandatory = (sgpt > 45.0 or hs_crp > 3.0)
    if gut_liver_mandatory:
        decisions.append({
            "rule": "Rule 1 (The Gut-Liver Rule)",
            "status": "TRIGGERED",
            "action": "Mandatory Phase 1 (LiverPrime Core) before any axis-specific correction. No exceptions.",
            "rationale": f"SGPT={sgpt} U/L or hs-CRP={hs_crp} mg/L indicates hepatic/systemic inflammation that blocks Phase 2 bioactivation."
        })
    else:
        decisions.append({
            "rule": "Rule 1 (The Gut-Liver Rule)",
            "status": "CLEARED",
            "action": "Baseline hepatic and inflammatory markers within acceptable limits."
        })

    # Rule 2: HPA-First Rule
    hpa_first = False
    if has_hpa_dysregulation:
        hpa_first = True
        decisions.append({
            "rule": "Rule 2 (The HPA-First Rule)",
            "status": "TRIGGERED",
            "action": "HPA axis must be stabilized (NeuroCalmX in Phase 1) before gonadal, metabolic, or thyroid axis correction.",
            "rationale": "Cortisol suppresses LH/FSH, TSH, and insulin sensitivity simultaneously. Treating other axes first is filling a leaking bucket."
        })

    # Rule 3: Thyroid-HPA Rule
    if has_thyroid_dysfunction and has_hpa_dysregulation:
        decisions.append({
            "rule": "Rule 3 (The Thyroid-HPA Rule)",
            "status": "TRIGGERED",
            "action": "Treat HPA axis FIRST. Re-evaluate thyroid after HPA stability; apparent subclinical hypothyroid may normalize.",
            "rationale": "Elevated cortisol suppresses TSH directly via hypothalamic somatostatin."
        })

    # Rule 4: Two-Axis Limit
    ranked_axes = active_axes[:2]
    deferred_axes = active_axes[2:]
    decisions.append({
        "rule": "Rule 4 (The Two-Axis Limit)",
        "status": "ENFORCED",
        "phase_2_primary_axes": ranked_axes,
        "deferred_tertiary_axes": deferred_axes,
        "rationale": "No more than two primary axes should be addressed in Phase 2. Tertiary axes frequently resolve through cascade reversal."
    })

    # Rule 5: Liver-Phase Rule
    decisions.append({
        "rule": "Rule 5 (The Liver-Phase Rule)",
        "status": "ENFORCED",
        "phase_1": "LiverPrime Core at full therapeutic dose",
        "phase_2": "LiverPrime Core continues at 50% maintenance dose alongside hero product",
        "rationale": "The liver is the gateway for herbal bioavailability. Continuous liver support prevents metabolic rebound."
    })

    return {
        "gut_liver_mandatory": gut_liver_mandatory,
        "hpa_stabilization_first": hpa_first,
        "priority_axes_phase_2": ranked_axes,
        "deferred_axes": deferred_axes,
        "rules_evaluation": decisions
    }
