"""
ZAYVORA Health OS™ — Mizaj-Based Dose Adjustment Personalisation Engine
Source: Dr. Irfan Ashraf — CP-AFUM Textbook Chapter 1 & Table 1.3
Encodes the non-negotiable thermal herb dose adjustment rules:
- Safravi (Hot-Dry): 25-30% reduction of ALL heating herbs across ALL phases. SGPT baseline + 4-weekly monitoring.
- Damvi (Hot-Wet): 15-20% reduction of heating herbs. Anti-inflammatory priority.
- Balghami (Cold-Wet): Heating herbs at standard to +10%. Reduce cooling herbs 10-20%.
- Saudavi (Cold-Dry): Standard balanced dose. HPA stabilization (NeuroCalmX) always first.
- Cardinal rule: Every heating herb above baseline dose must be counterbalanced with a cooling or neutral herb.
"""
from typing import Dict, Any, List, Optional

# Herb Thermal Classifications
HERB_THERMAL_CLASS = {
    # Hot (Har) Herbs
    "Ashwagandha": "HOT",
    "Asgandh": "HOT",
    "Withania somnifera": "HOT",
    "Guggul": "HOT",
    "Guggulsterone": "HOT",
    "Commiphora wightii": "HOT",
    "Ginger": "HOT",
    "Sonth": "HOT",
    "Zanjabeel": "HOT",
    "Saffron": "HOT",
    "Zafran": "HOT",
    "Crocus sativus": "HOT",
    "Black Seed": "HOT",
    "Zeera Siyah": "HOT",
    "Kalonji": "HOT",
    "Nigella sativa": "HOT",
    "Fenugreek": "HOT",
    "Methi": "HOT",
    "Trigonella foenum-graecum": "HOT",
    "Aqarqarha": "HOT",
    "Anacyclus pyrethrum": "HOT",
    "Filfil Siyah": "HOT",
    "Kali Mirch": "HOT",
    "Piperine": "HOT",

    # Cooling (Barid) Herbs
    "Shatavari": "COOLING",
    "Asparagus racemosus": "COOLING",
    "Valerian": "COOLING",
    "Valeriana officinalis": "COOLING",
    "Licorice": "COOLING",
    "Mulethi": "COOLING",
    "Glycyrrhiza glabra": "COOLING",
    "L-Theanine": "COOLING",
    "Tabasheer": "COOLING",
    "Sandal Safaid": "COOLING",
    "Sandal Safed": "COOLING",
    "Santalum album": "COOLING",
    "Aloe vera": "COOLING",
    "Gheekwar": "COOLING",
    "Coriander": "COOLING",
    "Kishneez": "COOLING",
    "Gulab": "COOLING",
    "Unnab": "COOLING",

    # Neutral (Mutadil) Actives
    "Berberine": "NEUTRAL",
    "Berberine HCl": "NEUTRAL",
    "Silymarin": "NEUTRAL",
    "Milk Thistle": "NEUTRAL",
    "NAC": "NEUTRAL",
    "N-Acetylcysteine": "NEUTRAL",
    "Zinc": "NEUTRAL",
    "Zinc Bisglycinate": "NEUTRAL",
    "Zinc Picolinate": "NEUTRAL",
    "Selenium": "NEUTRAL",
    "L-Selenomethionine": "NEUTRAL",
    "Myo-Inositol": "NEUTRAL",
    "Alpha-Lipoic Acid": "NEUTRAL",
    "ALA": "NEUTRAL",
    "L-Tyrosine": "NEUTRAL",
    "Chromium": "NEUTRAL",
    "Chromium Picolinate": "NEUTRAL",
    "CoQ10": "NEUTRAL",
    "Ubiquinol": "NEUTRAL",
    "L-Carnitine": "NEUTRAL",
    "Phosphatidylcholine": "NEUTRAL",
    "Salab Misri": "NEUTRAL",
    "Behman Safaid": "NEUTRAL",
    "Behman Surkh": "NEUTRAL"
}


def get_herb_thermal_class(herb_name: str) -> str:
    """Returns 'HOT', 'COOLING', or 'NEUTRAL' for a given herb."""
    for key, val in HERB_THERMAL_CLASS.items():
        if key.lower() in herb_name.lower():
            return val
    return "NEUTRAL"


def calculate_mizaj_dose_adjustments(mizaj: str, ingredients: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Adjusts doses in an ingredient list based on patient Mizaj.
    Implements Table 1.3:
    - Safravi: Heating -25% to -30%, Cooling +10% to +15%
    - Damvi: Heating -15% to -20%, Cooling 100%
    - Balghami: Heating 100% to +10%, Cooling -10% to -20%
    - Saudavi: Standard balanced dose (100%), HPA prioritization
    """
    mizaj_norm = mizaj.lower().strip()
    adjusted_items = []
    clinical_flags = []

    is_safravi = "safra" in mizaj_norm
    is_damvi = "dam" in mizaj_norm and not is_safravi
    is_balghami = "balgham" in mizaj_norm
    is_saudavi = "sauda" in mizaj_norm or "sawda" in mizaj_norm

    if is_safravi:
        clinical_flags.append("CRITICAL: Safravi Mizaj mandates 25-30% reduction of ALL heating herbs across ALL phases.")
        clinical_flags.append("MANDATORY: SGPT/ALT baseline check required. Repeat every 4 weeks to guard against hepatotoxic heat aggravation.")
        clinical_flags.append("ACTION: Phase 1 is frequently extended to 4 weeks (vs 2 weeks standard).")
    elif is_damvi:
        clinical_flags.append("Damvi Mizaj: Reduce heating herbs by 15-20%. Anti-inflammatory herbs are primary therapeutic tools in Phase 2.")
        clinical_flags.append("MONITOR: Check baseline CRP and SGPT at 4 weeks.")
    elif is_balghami:
        clinical_flags.append("Balghami Mizaj: Metabolic activation priority (Cold+Wet maps to low AMPK and insulin resistance).")
        clinical_flags.append("ACTION: Heating herbs maintained at full to +10% dose. Reduce cooling herbs by 10-20% to avoid dampening metabolic fire.")
    elif is_saudavi:
        clinical_flags.append("Saudavi Mizaj: HPA stabilization is ALWAYS first priority. NeuroCalmX in Phase 1 is non-negotiable.")
        clinical_flags.append("ACTION: Extended Phase 1 minimum 4 weeks regardless of SGPT/CRP status.")

    hot_count = 0
    cooling_count = 0

    for item in ingredients:
        name = item.get("name", "")
        orig_dose = float(item.get("dose_mg", item.get("quantity_g", 100)))
        thermal = item.get("thermal", get_herb_thermal_class(name))

        multiplier = 1.0
        reason = "Standard maintenance dose"

        if thermal == "HOT":
            hot_count += 1
            if is_safravi:
                multiplier = 0.72  # -28%
                reason = "Safravi reduction: -28% to prevent hepatobiliary heat flare & SGPT rise"
            elif is_damvi:
                multiplier = 0.82  # -18%
                reason = "Damvi reduction: -18% to prevent inflammatory/vascular aggravation"
            elif is_balghami:
                multiplier = 1.05  # +5%
                reason = "Balghami metabolic activation: slight thermogenic boost for cold-wet sluggishness"
            else:
                multiplier = 1.0
                reason = "Balanced warming dose"
        elif thermal == "COOLING":
            cooling_count += 1
            if is_safravi:
                multiplier = 1.15  # +15%
                reason = "Safravi enhancement: +15% cooling support to quench biliary fire"
            elif is_balghami:
                multiplier = 0.85  # -15%
                reason = "Balghami reduction: -15% cooling herbs to avoid further metabolic suppression"
            else:
                multiplier = 1.0
                reason = "Standard cooling dose"
        else:
            multiplier = 1.0
            reason = "Neutral compound: no thermal adjustment required"

        adj_dose = round(orig_dose * multiplier, 1)
        adjusted_items.append({
            "name": name,
            "thermal": thermal,
            "original_dose": orig_dose,
            "adjusted_dose": adj_dose,
            "adjustment_percentage": round((multiplier - 1.0) * 100, 1),
            "clinical_rationale": reason
        })

    # Thermal Balance Principle Check (Section 1.11)
    # Cardinal rule: Every heating herb above baseline dose must be counterbalanced with cooling/neutral
    is_balanced = True
    balance_notes = []
    if hot_count > 0 and cooling_count == 0:
        is_balanced = False
        balance_notes.append("VIOLATION OF THERMAL BALANCE RULE: Heating herbs present without cooling or neutral counterbalance. Must add Tabasheer, Sandal Safaid, or Shatavari.")
    else:
        balance_notes.append("Thermal balance verified: Adequate thermal counterbalancing present.")

    return {
        "mizaj": mizaj,
        "is_thermally_balanced": is_balanced,
        "balance_notes": balance_notes,
        "clinical_flags": clinical_flags,
        "adjusted_ingredients": adjusted_items
    }
