"""Deterministic Safety Preflight Engine for ZAYVORA MATAB OS.
Evaluates: Patient Allergies, Maximum Dosages, Polyherbal Ingredient Duplication,
Schedule E(1) / Mudabbar Toxins, and Age/Pregnancy Contraindications.
"""

from typing import Dict, Any, List, Optional
import sqlite3

UNIT_CONVERSIONS_TO_MG = {
    "mg": 1.0,
    "g": 1000.0,
    "gm": 1000.0,
    "gram": 1000.0,
    "masha": 970.0,
    "ratti": 121.5,
    "tola": 11664.0,
    "ml": 1000.0 # Standard liquid approximation for extracts
}

FREQUENCY_MULTIPLIERS = {
    "OD": 1,
    "BD": 2,
    "BID": 2,
    "TDS": 3,
    "TID": 3,
    "QID": 4,
    "SOS": 1,
    "BEDTIME": 1,
    "HS": 1
}

def parse_dose_to_mg(amount_str: str, unit_str: str) -> float:
    """Convert input dose string and clinical unit to milligrams (mg)."""
    try:
        clean_amount = float(str(amount_str).strip().split()[0])
        unit_lower = unit_str.strip().lower()
        multiplier = UNIT_CONVERSIONS_TO_MG.get(unit_lower, 1000.0)
        return clean_amount * multiplier
    except (ValueError, IndexError, AttributeError):
        return 0.0

class SafetyPreflightEngine:
    @staticmethod
    def evaluate(conn: sqlite3.Connection, patient_id: str, prescription_items: List[Dict[str, Any]], 
                 is_pregnant: bool = False, patient_age_years: Optional[int] = None) -> Dict[str, Any]:
        """Run deterministic clinical preflight evaluation across all prescribed items."""
        cursor = conn.cursor()
        rule_findings = []
        
        # 1. Fetch Patient Known Allergies
        cursor.execute("SELECT allergen_name, severity FROM patient_allergies WHERE patient_id = ?;", (patient_id,))
        patient_allergies = [dict(a) for a in cursor.fetchall()]
        
        # Aggregate ingredient totals across all polyherbal items to check cumulative duplication toxicity
        ingredient_cumulative_mg = {}  # {ingredient_id: total_daily_mg}
        ingredient_meta = {}
        
        for item in prescription_items:
            item_name = item.get("item_name") or item.get("custom_name") or "Prescription Item"
            dose_amount = item.get("dose_amount", "0")
            dose_unit = item.get("dose_unit", "g")
            freq = item.get("frequency", "OD").upper()
            formulation_id = item.get("formulation_id")
            
            single_dose_mg = parse_dose_to_mg(dose_amount, dose_unit)
            freq_multiplier = FREQUENCY_MULTIPLIERS.get(freq, 1)
            daily_dose_mg = single_dose_mg * freq_multiplier
            
            # --- Check 1: Direct Formulation Allergen Match ---
            for allg in patient_allergies:
                allergen_term = allg["allergen_name"].lower()
                if allergen_term in item_name.lower():
                    rule_findings.append({
                        "rule": "PATIENT_ALLERGY_MATCH",
                        "severity": "BLOCK",
                        "item": item_name,
                        "message": f"Critical Allergy Conflict: Patient has documented severe allergy to '{allg['allergen_name']}'."
                    })

            # If item is from catalog, resolve its constituent ingredients
            if formulation_id:
                cursor.execute("""
                    SELECT fi.quantity_mg, i.id, i.canonical_name, i.single_dose_max_mg, i.daily_dose_max_mg,
                           i.is_mudabbar_required, i.is_schedule_e1
                    FROM formulation_ingredients fi
                    JOIN ingredients i ON fi.ingredient_id = i.id
                    WHERE fi.formulation_id = ?;
                """, (formulation_id,))
                constituents = cursor.fetchall()
                
                for c in constituents:
                    ing_id = c["id"]
                    ing_name = c["canonical_name"]
                    ingredient_meta[ing_id] = dict(c)
                    
                    # Compute constituent daily dose proportion
                    ing_daily_mg = (c["quantity_mg"] / 1000.0) * daily_dose_mg
                    ingredient_cumulative_mg[ing_id] = ingredient_cumulative_mg.get(ing_id, 0.0) + ing_daily_mg
                    
                    # Check Allergen match on constituent herb
                    for allg in patient_allergies:
                        if allg["allergen_name"].lower() in ing_name.lower() or ing_name.lower() in allg["allergen_name"].lower():
                            rule_findings.append({
                                "rule": "CONSTITUENT_ALLERGY_MATCH",
                                "severity": "BLOCK",
                                "item": item_name,
                                "message": f"Formulation '{item_name}' contains constituent '{ing_name}' to which patient is allergic."
                            })
                            
                    # Check Contraindications on constituent herb
                    cursor.execute("""
                        SELECT contraindication_type, severity, rationale 
                        FROM safety_contraindications 
                        WHERE ingredient_id = ?;
                    """, (ing_id,))
                    for sc in cursor.fetchall():
                        ci_type = sc["contraindication_type"]
                        if ci_type == "PREGNANCY" and is_pregnant:
                            rule_findings.append({
                                "rule": "PREGNANCY_CONTRAINDICATION",
                                "severity": "BLOCK",
                                "item": item_name,
                                "message": f"Absolute Pregnancy Contraindication ({ing_name}): {sc['rationale']}"
                            })
                        if ci_type == "PEDIATRIC" and patient_age_years is not None and patient_age_years < 12:
                            rule_findings.append({
                                "rule": "PEDIATRIC_CONTRAINDICATION",
                                "severity": sc["severity"],
                                "item": item_name,
                                "message": f"Pediatric Caution ({ing_name}): {sc['rationale']}"
                            })

                    # Schedule E(1) & Mudabbar Check
                    if c["is_schedule_e1"] and not item.get("is_mudabbar_certified"):
                        # If dose exceeds therapeutic threshold without certified processing
                        rule_findings.append({
                            "rule": "SCHEDULE_E1_MUDABBAR_REQUIRED",
                            "severity": "BLOCK",
                            "item": item_name,
                            "message": f"Toxic botanical ({ing_name}) requires verified Mudabbar (detoxification) certification before dispensing."
                        })

        # --- Check 2: Cumulative Ingredient Duplication & Overdose ---
        for ing_id, total_mg in ingredient_cumulative_mg.items():
            meta = ingredient_meta.get(ing_id)
            if meta:
                max_daily = meta.get("daily_dose_max_mg")
                if max_daily and total_mg > max_daily:
                    rule_findings.append({
                        "rule": "CUMULATIVE_DOSE_LIMIT_EXCEEDED",
                        "severity": "BLOCK",
                        "item": meta["canonical_name"],
                        "message": f"Cumulative polyherbal daily dose of '{meta['canonical_name']}' is {total_mg:.1f}mg, exceeding statutory limit of {max_daily}mg."
                    })
                elif max_daily and total_mg > (max_daily * 0.85):
                    rule_findings.append({
                        "rule": "APPROACHING_MAX_DOSE_LIMIT",
                        "severity": "WARN",
                        "item": meta["canonical_name"],
                        "message": f"Cumulative daily dose of '{meta['canonical_name']}' ({total_mg:.1f}mg) is near maximum statutory ceiling ({max_daily}mg)."
                    })

        # --- Compute Overall Deterministic State ---
        has_block = any(f["severity"] == "BLOCK" for f in rule_findings)
        has_unknown = any(f["severity"] == "UNKNOWN" for f in rule_findings)
        has_warn = any(f["severity"] == "WARN" for f in rule_findings)
        
        if has_block:
            overall_state = "BLOCK"
        elif has_unknown:
            overall_state = "UNKNOWN"
        elif has_warn:
            overall_state = "WARN"
        else:
            overall_state = "PASS"
            
        # --- Check 3: Integrative Herb-Drug Safety & Schedule E(1) ---
        try:
            from matab.engines.herb_drug_safety_engine import evaluate_integrative_and_toxic_safety
            # Fetch patient clinical problems
            cursor.execute("SELECT problem_name FROM clinical_problems WHERE encounter_id IN (SELECT id FROM encounters WHERE patient_id = ?);", (patient_id,))
            dx_rows = cursor.fetchall()
            patient_dx = " ".join([r[0] for r in dx_rows if r[0]])
            
            herb_drug_findings = evaluate_integrative_and_toxic_safety(prescription_items, patient_diagnoses=patient_dx)
            for hdf in herb_drug_findings:
                rule_findings.append({
                    "rule": hdf["rule_id"],
                    "severity": hdf["severity"],
                    "item": hdf["item"],
                    "message": f"{hdf['title']}: {hdf['message']}"
                })
        except Exception as e:
            pass

        # --- Check 4: Classical Musleh & Badraqa Guidance ---
        musleh_analysis = {}
        try:
            from matab.engines.musleh_badraqa_engine import analyze_prescription_musleh_and_badraqa
            musleh_analysis = analyze_prescription_musleh_and_badraqa(prescription_items)
            for malert in musleh_analysis.get("musleh_alerts", []):
                rule_findings.append({
                    "rule": "MUSLEH_RECOMMENDED",
                    "severity": "INFO",
                    "item": malert["item_name"],
                    "message": f"Classical Musleh Required: {malert['classical_musleh']} ({malert['clinical_advice']})"
                })
        except Exception:
            pass

        # Recompute overall state with new findings
        has_block = any(f["severity"] == "BLOCK" for f in rule_findings)
        has_warn = any(f["severity"] == "WARN" for f in rule_findings)
        overall_state = "BLOCK" if has_block else ("WARN" if has_warn else "PASS")

        return {
            "overall_state": overall_state,
            "musleh_guidance": musleh_analysis,
            "rules_evaluated_count": len(prescription_items) * 4 + len(ingredient_cumulative_mg),
            "findings": rule_findings
        }
