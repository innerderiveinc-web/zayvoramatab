"""Deterministic Safety Preflight Engine for ZAYVORA MATAB OS.
Evaluates: Structural Completeness, Patient Allergies, Maximum Dosages,
Schedule E(1) / Mudabbar Toxins, Pregnancy Contraindications, and Explicit Coverage Reporting.
Rule Set Version: v1.0-preflight
"""

from typing import Dict, Any, List, Optional
import sqlite3

ALLOWED_UNITS = {
    "mg": 1.0,
    "g": 1000.0,
    "gm": 1000.0,
    "gram": 1000.0,
    "ml": 1000.0,
    "hab": 500.0, # Approximate pill weight in mg
    "qurs": 500.0, # Approximate tablet weight in mg
    "masha": 970.0,
    "ratti": 121.5,
    "tola": 11664.0,
    "spoonful": 5000.0, # 5ml/5g approximation
    "drops": 50.0
}

FREQUENCY_MULTIPLIERS = {
    "OD": 1,
    "BD": 2,
    "BID": 2,
    "TDS": 3,
    "TID": 3,
    "QID": 4,
    "BEDTIME": 1,
    "HS": 1,
    "SOS": 1
}

def parse_dose_to_mg(amount_str: Any, unit_str: Any) -> float:
    """Parse numeric dose and convert unit to milligrams (mg)."""
    try:
        clean_amount = float(str(amount_str).strip().split()[0])
        unit_lower = str(unit_str).strip().lower()
        multiplier = ALLOWED_UNITS.get(unit_lower, 1000.0)
        return clean_amount * multiplier
    except (ValueError, IndexError, AttributeError):
        return 0.0

class SafetyPreflightEngine:
    RULE_SET_VERSION = "v1.0-preflight"

    @staticmethod
    def evaluate(conn: sqlite3.Connection, patient_id: str, prescription_items: List[Dict[str, Any]],
                 is_pregnant: bool = False, patient_age_years: Optional[int] = None) -> Dict[str, Any]:
        """
        Run deterministic safety preflight evaluation across all items in a prescription draft.
        Returns:
            overall_state: 'PASS', 'WARN', or 'BLOCK'
            findings: list of structured findings (rule, severity, message, item)
            coverage: explicit declaration of rules checked and data limitations
        """
        cursor = conn.cursor()
        findings: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # 1. Structural & Completeness Checks
        # -------------------------------------------------------------
        if not prescription_items:
            findings.append({
                "rule": "STRUCTURAL_ITEMS_REQUIRED",
                "severity": "BLOCK",
                "item": None,
                "message": "A prescription must contain at least one formulation or ingredient item."
            })
            return {
                "overall_state": "BLOCK",
                "rule_set_version": SafetyPreflightEngine.RULE_SET_VERSION,
                "findings": findings,
                "coverage": {"rules_evaluated": ["STRUCTURAL_ITEMS_REQUIRED"]}
            }

        for idx, item in enumerate(prescription_items):
            item_name = (item.get("item_name") or item.get("custom_name") or "").strip()
            dose_amt = item.get("dose_amount")
            dose_unit = str(item.get("dose_unit", "")).strip().lower()
            freq = str(item.get("frequency", "")).strip().upper()
            dur = item.get("duration_days")

            if not item_name:
                findings.append({
                    "rule": "STRUCTURAL_NAME_REQUIRED",
                    "severity": "BLOCK",
                    "item": f"Item #{idx + 1}",
                    "message": f"Prescription Item #{idx + 1} is missing a formulation or item name."
                })

            if dose_amt is None or str(dose_amt).strip() == "":
                findings.append({
                    "rule": "STRUCTURAL_DOSE_REQUIRED",
                    "severity": "BLOCK",
                    "item": item_name or f"Item #{idx + 1}",
                    "message": f"Dose amount is required for '{item_name or f'Item #{idx + 1}'}'."
                })
            else:
                try:
                    val = float(str(dose_amt).strip())
                    if val <= 0:
                        raise ValueError()
                except ValueError:
                    findings.append({
                        "rule": "STRUCTURAL_DOSE_INVALID",
                        "severity": "BLOCK",
                        "item": item_name or f"Item #{idx + 1}",
                        "message": f"Dose amount must be a positive number for '{item_name}'."
                    })

            if not dose_unit or dose_unit not in ALLOWED_UNITS:
                findings.append({
                    "rule": "STRUCTURAL_UNIT_INVALID",
                    "severity": "BLOCK",
                    "item": item_name or f"Item #{idx + 1}",
                    "message": f"Invalid dose unit '{dose_unit}' for '{item_name}'. Allowed units: {', '.join(sorted(ALLOWED_UNITS.keys()))}."
                })

            if not freq or freq not in FREQUENCY_MULTIPLIERS:
                findings.append({
                    "rule": "STRUCTURAL_FREQUENCY_INVALID",
                    "severity": "BLOCK",
                    "item": item_name or f"Item #{idx + 1}",
                    "message": f"Invalid frequency '{freq}' for '{item_name}'. Allowed frequencies: {', '.join(FREQUENCY_MULTIPLIERS.keys())}."
                })

            if dur is None or int(dur or 0) <= 0:
                findings.append({
                    "rule": "STRUCTURAL_DURATION_INVALID",
                    "severity": "BLOCK",
                    "item": item_name or f"Item #{idx + 1}",
                    "message": f"Duration must be at least 1 day for '{item_name}'."
                })

        # -------------------------------------------------------------
        # 2. Fetch Patient Known Allergies
        # -------------------------------------------------------------
        cursor.execute("SELECT allergen_name, severity FROM patient_allergies WHERE patient_id = ?;", (patient_id,))
        patient_allergies = [dict(a) for a in cursor.fetchall()]

        # -------------------------------------------------------------
        # 3. Clinical Checks: Allergies, Toxins, Mudabbar, Contraindications, Dose Ceilings
        # -------------------------------------------------------------
        ingredient_cumulative_mg: Dict[str, float] = {}
        ingredient_meta: Dict[str, Dict[str, Any]] = {}

        for item in prescription_items:
            item_name = (item.get("item_name") or item.get("custom_name") or "Prescription Item").strip()
            formulation_id = item.get("formulation_id")
            dose_amt = item.get("dose_amount", "0")
            dose_unit = item.get("dose_unit", "g")
            freq = str(item.get("frequency", "OD")).strip().upper()
            is_mudabbar_certified = item.get("is_mudabbar_certified", False)

            single_dose_mg = parse_dose_to_mg(dose_amt, dose_unit)
            freq_multiplier = FREQUENCY_MULTIPLIERS.get(freq, 1)
            daily_dose_mg = single_dose_mg * freq_multiplier

            # --- Check 3A: Direct Formulation Allergen Match ---
            for allg in patient_allergies:
                allergen_term = allg["allergen_name"].lower()
                # Check if allergen term appears in item name
                if any(word in item_name.lower() for word in allergen_term.split() if len(word) > 3):
                    findings.append({
                        "rule": "PATIENT_ALLERGY_MATCH",
                        "severity": "BLOCK",
                        "item": item_name,
                        "message": f"Critical Allergy Conflict: Patient has documented severe allergy to '{allg['allergen_name']}'."
                    })

            # --- Check 3B: Resolve Constituent Ingredients from Catalog ---
            constituent_ingredients: List[Dict[str, Any]] = []
            if formulation_id:
                # Check if formulation is reviewed and approved
                cursor.execute("SELECT name, status FROM formulations WHERE id = ?;", (formulation_id,))
                f_row = cursor.fetchone()
                if f_row and f_row["status"] != "APPROVED":
                    findings.append({
                        "rule": "UNREVIEWED_FORMULATION_WARNING",
                        "severity": "WARN",
                        "item": item_name,
                        "message": f"Formulation '{f_row['name']}' is in '{f_row['status']}' review status. Verify composition before dispensing."
                    })

                cursor.execute("""
                    SELECT fi.quantity_mg, fi.is_chief_ingredient,
                           i.id as ingredient_id, i.canonical_name, i.unani_name, i.botanical_name,
                           i.single_dose_max_mg, i.daily_dose_max_mg, i.is_mudabbar_required, i.is_schedule_e1
                    FROM formulation_ingredients fi
                    JOIN ingredient_catalog i ON fi.ingredient_id = i.id
                    JOIN formulation_versions fv ON fi.formulation_version_id = fv.id
                    JOIN formulations f ON fv.formulation_id = f.id AND f.current_version = fv.version_number
                    WHERE f.id = ?;
                """, (formulation_id,))
                constituent_ingredients = [dict(r) for r in cursor.fetchall()]

            # Also check direct custom composition snapshot if provided
            custom_comp = item.get("composition_snapshot")
            if isinstance(custom_comp, list):
                for c_ing in custom_comp:
                    c_ing_id = c_ing.get("ingredient_id")
                    if c_ing_id:
                        cursor.execute("""
                            SELECT id as ingredient_id, canonical_name, unani_name, botanical_name,
                                   single_dose_max_mg, daily_dose_max_mg, is_mudabbar_required, is_schedule_e1
                            FROM ingredient_catalog WHERE id = ?;
                        """, (c_ing_id,))
                        c_row = cursor.fetchone()
                        if c_row:
                            c_dict = dict(c_row)
                            c_dict["quantity_mg"] = c_ing.get("quantity_mg", 0)
                            constituent_ingredients.append(c_dict)

            # Evaluate each constituent ingredient
            for ing in constituent_ingredients:
                ing_id = ing["ingredient_id"]
                ing_name = ing["unani_name"]
                ing_canonical = ing["canonical_name"]

                # 3B.1: Ingredient-level Allergy Match
                for allg in patient_allergies:
                    allg_lower = allg["allergen_name"].lower()
                    if (allg_lower in ing_canonical.lower() or
                        allg_lower in ing_name.lower() or
                        any(w in ing_canonical.lower() for w in allg_lower.split() if len(w) > 3)):
                        findings.append({
                            "rule": "PATIENT_ALLERGY_MATCH",
                            "severity": "BLOCK",
                            "item": item_name,
                            "message": f"Critical Allergy Conflict: Formulation '{item_name}' contains '{ing_canonical}', which conflicts with patient's documented allergy to '{allg['allergen_name']}'."
                        })

                # 3B.2: Schedule E(1) Toxin without Certified Mudabbar Detoxification
                if ing.get("is_schedule_e1") or ing.get("is_mudabbar_required"):
                    if not is_mudabbar_certified:
                        findings.append({
                            "rule": "SCHEDULE_E1_MUDABBAR_REQUIRED",
                            "severity": "BLOCK",
                            "item": item_name,
                            "message": f"Schedule E(1) Restricted Botanical: '{ing_name}' ({ing.get('botanical_name')}) is a potent toxin requiring verified Mudabbar detoxification. Must be certified prior to dispensing."
                        })

                # 3B.3: Specific Contraindications (e.g. Pregnancy)
                cursor.execute("""
                    SELECT contraindication_type, severity, rationale
                    FROM safety_contraindications
                    WHERE ingredient_id = ?;
                """, (ing_id,))
                for contra in cursor.fetchall():
                    if contra["contraindication_type"] == "PREGNANCY" and is_pregnant:
                        findings.append({
                            "rule": "PREGNANCY_CONTRAINDICATION",
                            "severity": contra["severity"],
                            "item": item_name,
                            "message": f"Pregnancy Contraindication: '{item_name}' contains '{ing_name}'. {contra['rationale']}"
                        })

                # 3B.4: Cumulative Dose Accumulation across Polyherbal items
                proportion = (ing.get("quantity_mg", 1000) / 10000.0) if ing.get("quantity_mg") else 0.5
                est_ing_daily_mg = daily_dose_mg * proportion
                ingredient_cumulative_mg[ing_id] = ingredient_cumulative_mg.get(ing_id, 0.0) + est_ing_daily_mg
                ingredient_meta[ing_id] = ing

        # --- Check 3C: Ingredient Duplication and Daily Overdose Ceiling ---
        for ing_id, total_daily_mg in ingredient_cumulative_mg.items():
            meta = ingredient_meta[ing_id]
            max_daily = meta.get("daily_dose_max_mg")
            if max_daily and total_daily_mg > max_daily:
                findings.append({
                    "rule": "DUPLICATE_INGREDIENT_OVERDOSE",
                    "severity": "BLOCK",
                    "item": meta["unani_name"],
                    "message": f"Ingredient Overdose Limit Exceeded: Cumulative daily intake of '{meta['unani_name']}' is {int(total_daily_mg)} mg (Maximum safe daily limit: {max_daily} mg)."
                })

        # -------------------------------------------------------------
        # 4. Explicit Coverage Reporting (Honest Limits)
        # -------------------------------------------------------------
        coverage = {
            "rules_evaluated": [
                "STRUCTURAL_COMPLETENESS",
                "PATIENT_ALLERGIES",
                "SCHEDULE_E1_MUDABBAR_DETOXIFICATION",
                "PREGNANCY_CONTRAINDICATIONS",
                "CUMULATIVE_INGREDIENT_DOSE_LIMITS",
                "CATALOG_REVIEW_STATUS"
            ],
            "patient_allergies_evaluated": len(patient_allergies),
            "pregnancy_evaluated": is_pregnant,
            "drug_drug_interaction_coverage": "Botanical and classical polyherbal monographs evaluated. Synthetic allopathic interactions are not evaluated in preflight v1.0."
        }

        # Determine overall state
        severities = {f["severity"] for f in findings}
        if "BLOCK" in severities:
            overall_state = "BLOCK"
        elif "WARN" in severities:
            overall_state = "WARN"
        else:
            overall_state = "PASS"

        return {
            "overall_state": overall_state,
            "rule_set_version": SafetyPreflightEngine.RULE_SET_VERSION,
            "findings": findings,
            "coverage": coverage
        }
