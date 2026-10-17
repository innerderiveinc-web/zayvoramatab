"""ZAYVORA MATAB OS — Classical Musleh (Corrective) & Badraqa (Carrier Vehicle) Engine.
Enforces classical Unani principles where intense, evacuant, or irritant herbs require
a certified Musleh to nullify side effects, and a Badraqa to direct action to target organs.
"""

from typing import Dict, Any, List

# Classical Musleh (Correctives) Dictionary
MUSLEH_CATALOG = {
    "sana": {
        "herb_name": "Sana Makki (Cassia angustifolia / Senna)",
        "action": "Mushil-e-Safra wa Balgham (Strong Purgative)",
        "adverse_effect": "Kharash wa Maghas (Intestinal mucosal irritation & griping colic)",
        "musleh": "Roghan-e-Badam (Sweet Almond Oil), Badiyan (Aniseed / Fennel), or Gul-e-Surkh (Rose petals)",
        "dose_instruction": "Add 5ml Roghan Badam or 3g Saunf with decoction to prevent abdominal spasms."
    },
    "turbud": {
        "herb_name": "Turbud (Operculina turpethum)",
        "action": "Mushil-e-Balgham (Drastic phlegm evacuant)",
        "adverse_effect": "Nausea, griping colic, dehydration",
        "musleh": "Roghan-e-Badam Shirin or Zanjabeel (Dry Ginger)",
        "dose_instruction": "Administer only after roasting in Almond oil (Churab) with ginger."
    },
    "suranjan": {
        "herb_name": "Suranjan (Colchicum luteum)",
        "action": "Muhallil wa Musakkin-e-Waja-ul-Mafasil (Gout & Joint anti-inflammatory)",
        "adverse_effect": "Severe gastric distress, vomiting, diarrhea",
        "musleh": "Gond Katira (Tragacanth), Roghan-e-Zaitoon (Olive Oil), or Zafraan",
        "dose_instruction": "Always combine with Katira and honey to protect gastric lining."
    },
    "saqmonia": {
        "herb_name": "Saqmonia (Scammony / Convolvulus scammonia)",
        "action": "Mushil-e-Qawi (Extreme Hydragogue Purgative)",
        "adverse_effect": "Intestinal excoriation, hyper-purgation",
        "musleh": "Rabab-e-Seb (Apple jelly), Roghan-e-Badam, or Kateera",
        "dose_instruction": "Strict Mudabbar processing required; combine with Apple extract."
    },
    "azaraqi": {
        "herb_name": "Azaraqi / Kuchla (Strychnos nux-vomica)",
        "action": "Muqawwi-e-Asab (Intense Neuro-muscular stimulant)",
        "adverse_effect": "Muscular rigidity, toxicity, convulsions if raw",
        "musleh": "Taza Doodh (Fresh Cow's Milk), Roghan-e-Zard (Ghee), or Arq-e-Gaozaban",
        "dose_instruction": "Mudabbar in milk mandatory. Ceiling 60mg/day."
    },
    "halela": {
        "herb_name": "Halela Siyah / Zard (Terminalia chebula)",
        "action": "Muqawwi-e-Meda wa Dimagh, Tanqiya-e-Sauda",
        "adverse_effect": "Excessive dryness (Tajfeef) and astringency",
        "musleh": "Roghan-e-Badam or Desi Ghee",
        "dose_instruction": "Fry lightly in almond oil (Halela Parwada) to mitigate dryness."
    },
    "aftimoon": {
        "herb_name": "Aftimoon (Cuscuta reflexa / Dodder)",
        "action": "Mushil-e-Sauda (Specific Melancholic Evacuant)",
        "adverse_effect": "Mild nausea and dryness",
        "musleh": "Roghan-e-Badam Shirin or Sikanjabeen",
        "dose_instruction": "Never boil heavily; infuse in warm water with Roghan Badam."
    },
    "afiyoon": {
        "herb_name": "Afiyoon / Taryaq (Papaver somniferum)",
        "action": "Mukhaddir-e-Qawi (Potent Narcotic / Analgesic)",
        "adverse_effect": "Habituation, respiratory depression, constipation",
        "musleh": "Jundbedastar, Zafraan, or Sikanjabeen",
        "dose_instruction": "Narcotic monitoring mandatory; dose must not exceed 30mg."
    }
}

# Classical Badraqa (Carrier Vehicles) for Target Organs & Forms
BADRAQA_CATALOG = {
    "dimagh": {
        "organ": "Dimagh wa Asab (Brain & Nerves)",
        "preferred_badraqa": "Arq-e-Gaozaban (Borage Hydrosol) or Khamira Gaozaban",
        "rationale": "Directs active principles across blood-brain barrier and calms cerebral heat."
    },
    "qalb": {
        "organ": "Qalb wa Urooq (Heart & Circulation)",
        "preferred_badraqa": "Arq-e-Gulab (Rose water), Sharbat Seb (Apple syrup), or Arq-e-Baidmushk",
        "rationale": "Strengthens vital spirit (Rooh) and provides exhilarant (Mufarrih) action."
    },
    "jigar": {
        "organ": "Jigar wa Banqras (Liver & Spleen)",
        "preferred_badraqa": "Arq-e-Mako (Solanum nigrum) mixed with Arq-e-Kasni (Cichorium intybus)",
        "rationale": "Deobstruent (Mufattih Sudad) vehicle for hepatic parenchyma."
    },
    "meda": {
        "organ": "Meda wa Am'a (Stomach & GI)",
        "preferred_badraqa": "Aab-e-Neem Garm (Lukewarm water) or Sharbat Zanjabeel",
        "rationale": "Enhances gastric concoction without cooling digestive fire."
    },
    "kulya": {
        "organ": "Kulya wa Masana (Kidney & Urinary)",
        "preferred_badraqa": "Sharbat Bazoori Motadil or Arq-e-Badiyan",
        "rationale": "Diuretic (Mudirr-e-Baul) vehicle to flush urinary tract."
    },
    "general": {
        "organ": "Aam (General)",
        "preferred_badraqa": "Aab-e-Taza (Fresh water) or Shehad (Honey) water",
        "rationale": "Universal physiological carrier vehicle."
    }
}

def analyze_prescription_musleh_and_badraqa(items: List[Dict[str, Any]], primary_axis_id: str = "meda-amaa") -> Dict[str, Any]:
    """Scan prescribed items and suggest classical Musleh and Badraqa."""
    detected_musleh_alerts = []
    
    for it in items:
        name = (it.get("item_name") or it.get("custom_name") or "").lower()
        for k, v in MUSLEH_CATALOG.items():
            if k in name:
                detected_musleh_alerts.append({
                    "item_name": it.get("item_name") or it.get("custom_name"),
                    "herb_key": k,
                    "classical_musleh": v["musleh"],
                    "reason": v["adverse_effect"],
                    "clinical_advice": v["dose_instruction"]
                })
                break
                
    # Determine appropriate Badraqa
    axis_clean = (primary_axis_id or "meda-amaa").lower()
    if "dimagh" in axis_clean:
        badraqa = BADRAQA_CATALOG["dimagh"]
    elif "qalb" in axis_clean:
        badraqa = BADRAQA_CATALOG["qalb"]
    elif "jigar" in axis_clean or "kabid" in axis_clean:
        badraqa = BADRAQA_CATALOG["jigar"]
    elif "kulya" in axis_clean or "mithana" in axis_clean:
        badraqa = BADRAQA_CATALOG["kulya"]
    else:
        badraqa = BADRAQA_CATALOG["meda"]
        
    return {
        "musleh_alerts": detected_musleh_alerts,
        "recommended_badraqa": badraqa,
        "has_musleh_required": len(detected_musleh_alerts) > 0
    }
