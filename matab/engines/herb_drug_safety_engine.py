"""ZAYVORA MATAB OS — Integrative Herb-Drug Interaction & Schedule E(1) Toxic Botanical Guard.
Protects practitioners against dangerous cross-system interactions (e.g. Mulethi with BP drugs,
Guggulu/Zafraan with blood thinners) and enforces statutory Schedule E(1) detoxification rules.
"""

from typing import Dict, Any, List, Optional

# Integrative Cross-System Rules
CROSS_SYSTEM_RULES = [
    {
        "id": "INT-BP-MULETHI",
        "condition": lambda dx, meds: any(k in dx.lower() for k in ["hypertension", "high bp", "htn"]) or any(k in meds.lower() for k in ["amlodipine", "telmisartan", "losartan", "atenolol", "enalapril"]),
        "unani_trigger": ["mulethi", "asl-us-soos", "aslussoos", "glycyrrhiza", "licorice"],
        "severity": "WARN",
        "title": "Hypertension vs Asl-us-Soos (Mulethi) Interaction",
        "clinical_guidance": "Mulethi contains glycyrrhizin which inhibits 11-beta-HSD2, causing pseudoaldosteronism, sodium retention, potassium wasting, and arterial BP spikes. Avoid or restrict to <500mg/day."
    },
    {
        "id": "INT-ANTICOAG-GUGGULU",
        "condition": lambda dx, meds: any(k in dx.lower() for k in ["thrombosis", "dvt", "stent", "cad"]) or any(k in meds.lower() for k in ["warfarin", "aspirin", "clopidogrel", "ecospirin", "heparin"]),
        "unani_trigger": ["muqil", "guggulu", "zafraan", "saffron", "lahsun", "garlic extract"],
        "severity": "WARN",
        "title": "Antiplatelet/Anticoagulant Hemorrhagic Risk",
        "clinical_guidance": "High-dose Muqil, Zafraan, or concentrated Garlic possesses antiplatelet / fibrinolytic properties, synergistically elevating bleeding time when combined with modern anticoagulants. Monitor INR/bleeding."
    },
    {
        "id": "INT-DIABETES-HYPOGLYCEMIA",
        "condition": lambda dx, meds: any(k in dx.lower() for k in ["diabetes", "dm2", "t2d", "high sugar"]) or any(k in meds.lower() for k in ["metformin", "glimepiride", "insulin", "vildagliptin", "empagliflozin"]),
        "unani_trigger": ["jamun", "karela", "gurmar", "methi", "kushta baiza murgh", "kushta jast"],
        "severity": "INFO",
        "title": "Synergistic Hypoglycemic Potentiation",
        "clinical_guidance": "Potent Unani hypoglycemic formulations will compound the effects of prescription antidiabetic drugs. Instruct patient to closely self-monitor blood glucose (SMBG) to avoid hypoglycemia."
    },
    {
        "id": "INT-SEDATIVE-NARCOTIC",
        "condition": lambda dx, meds: any(k in meds.lower() for k in ["alprazolam", "clonazepam", "diazepam", "zolpidem", "escitalopram", "sertraline"]),
        "unani_trigger": ["afiyoon", "opium", "bhang", "cannabis", "khashkhash", "asgandh high-dose"],
        "severity": "BLOCK",
        "title": "Potentiated Central Nervous System Depression",
        "clinical_guidance": "Concomitant use of classical narcotics or sedatives with modern benzodiazepines/hypnotics induces excessive CNS and respiratory depression. Requires immediate dosage reduction or omission."
    }
]

# Schedule E(1) Statutory Ceiling and Mudabbar Rules
SCHEDULE_E1_BOTANICALS = {
    "azaraqi": {
        "canonical_name": "Azaraqi (Kuchla / Strychnos nux-vomica)",
        "max_single_dose_mg": 65.0,
        "max_daily_dose_mg": 130.0,
        "mudabbar_mandatory": True,
        "detox_method": "Shodhan / Mudabbar in Cow's Milk or Cow's Ghee for 7 days",
        "schedule": "Schedule E(1) - AYUSH Drug Rules"
    },
    "shingraf": {
        "canonical_name": "Shingraf (Cinnabar / Red Mercuric Sulphide)",
        "max_single_dose_mg": 30.0,
        "max_daily_dose_mg": 60.0,
        "mudabbar_mandatory": True,
        "detox_method": "Trituration in Ginger juice (Aab-e-Zanjabeel) for 7 cycles",
        "schedule": "Schedule E(1) - Toxic Mineral Compound"
    },
    "sammulfar": {
        "canonical_name": "Samm-ul-Far (Sankhiya / Arsenic Trioxide)",
        "max_single_dose_mg": 2.0,
        "max_daily_dose_mg": 4.0,
        "mudabbar_mandatory": True,
        "detox_method": "Strict boiling in Dol Yantra with milk / plant juices",
        "schedule": "Schedule E(1) - Lethal Mineral"
    },
    "bhang": {
        "canonical_name": "Bhang / Qinnab (Cannabis sativa)",
        "max_single_dose_mg": 250.0,
        "max_daily_dose_mg": 500.0,
        "mudabbar_mandatory": True,
        "detox_method": "Boiling in Babool bark decoction and washing in cold water",
        "schedule": "Schedule E(1) - Regulated Narcotic Plant"
    },
    "afiyoon": {
        "canonical_name": "Afiyoon / Taryaq (Papaver somniferum)",
        "max_single_dose_mg": 30.0,
        "max_daily_dose_mg": 60.0,
        "mudabbar_mandatory": True,
        "detox_method": "Dissolution in Rose water and sun-evaporation (Taryaq-e-Afiyoon)",
        "schedule": "Schedule E(1) - NDPS Regulated"
    }
}

def evaluate_integrative_and_toxic_safety(
    prescribed_items: List[Dict[str, Any]],
    patient_diagnoses: str = "",
    current_allopathic_meds: str = ""
) -> List[Dict[str, Any]]:
    """Scan items for dangerous herb-drug clashes and Schedule E(1) boundaries."""
    findings = []
    
    # 1. Herb-Drug Interactions
    for rule in CROSS_SYSTEM_RULES:
        if rule["condition"](patient_diagnoses or "", current_allopathic_meds or ""):
            # Check if any prescribed item matches unani_trigger
            for it in prescribed_items:
                it_name = (it.get("item_name") or it.get("custom_name") or "").lower()
                if any(trig in it_name for trig in rule["unani_trigger"]):
                    findings.append({
                        "rule_id": rule["id"],
                        "severity": rule["severity"],
                        "item": it.get("item_name") or it.get("custom_name"),
                        "title": rule["title"],
                        "message": rule["clinical_guidance"]
                    })
                    break
                    
    # 2. Schedule E(1) Checks
    for it in prescribed_items:
        it_name = (it.get("item_name") or it.get("custom_name") or "").lower()
        for bot_key, meta in SCHEDULE_E1_BOTANICALS.items():
            if bot_key in it_name:
                findings.append({
                    "rule_id": f"SCH-E1-{bot_key.upper()}",
                    "severity": "WARN",
                    "item": it.get("item_name") or it.get("custom_name"),
                    "title": f"Schedule E(1) Botanical: {meta['canonical_name']}",
                    "message": f"Statutory requirement: Must use {meta['detox_method']}. Daily dose ceiling: {meta['max_daily_dose_mg']}mg."
                })
                break
                
    return findings
