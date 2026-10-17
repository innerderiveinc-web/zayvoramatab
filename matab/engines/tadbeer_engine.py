"""ZAYVORA MATAB OS — Classical Ilaj-bit-Tadbeer (Regimenal Therapy) Protocol Engine.
Provides standardized Unani clinical protocols, anatomical point locators, and scheduling
for Hijama (Cupping), Daluk (Massage), Fasd (Venesection), and Nutool (Irrigation).
"""

from typing import Dict, Any, List

TADBEER_MODALITIES = {
    "hijama": {
        "modality_name": "Hijama (Cupping Therapy)",
        "classical_classification": "Istifragh-e-Mawad-e-Damwiyyah (Sanguineous Evacuation)",
        "common_indications": [
            "Waja-ul-Mafasil (Arthritis & Joint pain)",
            "Irq-un-Nasa (Sciatica)",
            "Sudaa-e-Muzmin (Chronic Migraine / Headache)",
            "Hypertension & plethoric sanguineous congestion",
            "Myofascial pain syndrome and muscular spasm"
        ],
        "anatomical_points": [
            {"code": "C1", "name": "Al-Kahil (Interscapular / T1-T3)", "indication": "General systemic detoxification, upper back pain, asthma"},
            {"code": "C2", "name": "Al-Akhdayn (Lateral Neck / Behind Ears)", "indication": "Headaches, ear tinnitus, facial neuralgia, vertigo"},
            {"code": "C3", "name": "Hamaah / Yafookh (Vertex of Skull)", "indication": "Chronic migraine, mental heaviness, cognitive fogginess"},
            {"code": "C4", "name": "Al-Qatan (Lumbo-Sacral Spine)", "indication": "Lower back pain, sciatica, pelvic congestion"},
            {"code": "C5", "name": "Saqayn (Calves / Gastrocnemius)", "indication": "Leg cramps, varicose congestion, gout"}
        ],
        "pre_procedure_instructions": [
            "Patient must fast from solid food for at least 2 to 3 hours prior to procedure.",
            "Maintain adequate hydration with water, Arq-e-Gulab, or honey water.",
            "Check baseline blood pressure; avoid if systolic BP < 90 mmHg.",
            "Ensure skin is cleansed with antiseptic solution (Betadine / Chlorhexidine)."
        ],
        "post_procedure_instructions": [
            "Apply Roghan-e-Zaitoon (Olive oil) or Roghan-e-Kamila over micro-incisions.",
            "Avoid bathing or vigorous exertion for 24 hours.",
            "Avoid eating cold heavy dairy (curd, cold milk) or sour foods for 12 hours.",
            "Drink warm honey water (Maa-ul-Asal) to replenish vital tone."
        ]
    },
    "daluk": {
        "modality_name": "Daluk (Therapeutic Medical Massage)",
        "classical_classification": "Tas-kheen, Tahleel wa Taqwiyat-e-A'za",
        "types": [
            {"type_name": "Daluk-e-Sulb (Firm Massage)", "indication": "Organ tightening and muscle hardening (Taqwiyat-e-Lahm)"},
            {"type_name": "Daluk-e-Layyin (Gentle Massage)", "indication": "Sedative, pain-relieving, muscle relaxing (Tas-keen-e-Dard)"},
            {"type_name": "Daluk-e-Kaseer (Prolonged Massage)", "indication": "Resolving chronic induration, slimming & lipolysis (Tahleel-e-Balgham)"},
            {"type_name": "Daluk-e-Istedad (Preparatory Warm-up)", "indication": "Pre-exercise circulatory stimulation"}
        ],
        "recommended_oils": [
            {"oil_name": "Roghan-e-Surkh / Roghan Darchini", "indication": "Cold neuralgic pains, sciatica, paralysis (Laqwa/Falij)"},
            {"oil_name": "Roghan-e-Banafsha / Roghan Kahu", "indication": "Insomnia, burning sensation, nervous agitation"},
            {"oil_name": "Roghan-e-Zaitoon / Roghan Badam Shirin", "indication": "Dry Saudawi cachexia, skin dryness, general debility"}
        ]
    },
    "nutool": {
        "modality_name": "Nutool (Medicated Cephalic Irrigation / Douching)",
        "classical_classification": "Tas-keen wa Tadeel-e-Mizaj-e-Dimagh",
        "common_indications": ["Sahar (Insomnia)", "Sudaa (Severe Tension Headache)", "Mania / Malikhoolia (Anxiety/Depression)"],
        "decoction_formulas": [
            "Gul-e-Banafsha (10g) + Gul-e-Babuna (10g) + Tukhm-e-Kahu (10g) boiled in 1 liter water and poured warm over forehead.",
            "Kashk-aab (Barley broth) poured tepid over cranial vault for bilious insomnia."
        ]
    }
}

def get_recommended_tadbeer_protocols(primary_axis_id: str, dominant_mizaj: str) -> Dict[str, Any]:
    """Retrieve tailored Ilaj-bit-Tadbeer recommendations matching clinical picture."""
    clean_mizaj = (dominant_mizaj or "BALGHAMI").upper()
    axis = (primary_axis_id or "meda-amaa").lower()
    
    protocols = []
    
    # Joint / Musculo-Skeletal
    if "mafasil" in axis or "uroq" in axis or clean_mizaj in ["DAMWI", "BALGHAMI"]:
        protocols.append({
            "modality": "Hijama bil Shart (Wet Cupping)",
            "target_system": "Vascular / Musculo-Skeletal",
            "recommended_points": ["Al-Kahil (T1-T3)", "Al-Qatan (Lumbo-Sacral)"],
            "schedule": "3 sittings spaced 14-21 days apart on recommended classical lunar dates (17th, 19th, 21st of Hijri month)."
        })
        
    # Neurological / Headache / Mental
    if "dimagh" in axis or clean_mizaj in ["SAUDAWI", "SAFRAWI"]:
        protocols.append({
            "modality": "Nutool (Warm Herbal Pouring) & Daluk-e-Raas (Head Massage)",
            "target_system": "Neuro-Psychic (Quwwat-e-Nafsaniyah)",
            "recommended_oils": "Roghan Banafsha or Roghan Kahu applied tepid to vertex before bed.",
            "schedule": "Nightly for 7 to 10 consecutive days."
        })
        
    # General Daluk
    protocols.append({
        "modality": "Daluk-e-Mutadil (Balanced Body Massage)",
        "target_system": "Musculo-Cutaneous",
        "recommended_oils": "Roghan Badam Shirin or Roghan Zaitoon",
        "schedule": "2 to 3 times weekly before morning bath."
    })
    
    return {
        "dominant_mizaj": clean_mizaj,
        "organ_axis": axis,
        "recommended_tadbeer_list": protocols,
        "full_modality_catalog": TADBEER_MODALITIES
    }
