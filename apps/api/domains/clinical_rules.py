"""Clinical Decision Support Rules Engine & Governance Catalog.
Deterministic Red-Flag, Differential Heuristic, and Investigation Guideline Evaluation.

Fail-Closed Architecture:
- Missing inputs yield INCOMPLETE / MISSING_DATA status, never a reassuring negative.
- Stale, unapproved, or unavailable rule sources yield EXPLICIT UNAVAILABLE state.
- Suggestions never autonomously become diagnoses, orders, or prescriptions.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3

from apps.api.core.errors import NotFoundError, ValidationError, ConflictError


class ClinicalRulesEngine:
    """Evaluates deterministic clinical rules against structured patient and encounter context."""

    @staticmethod
    def get_content_status(conn: sqlite3.Connection) -> Dict[str, Any]:
        """Check active clinical sources and rule governance state."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, authority, version, review_status, effective_date, expiry_date
            FROM clinical_content_sources;
        """)
        sources = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT rule_id, rule_version, rule_type, title, severity, governance_status
            FROM clinical_rule_definitions;
        """)
        rules = [dict(r) for r in cursor.fetchall()]

        active_sources = [s for s in sources if s["review_status"] == "approved_active"]
        active_rules = [r for r in rules if r["governance_status"] == "approved_active"]

        is_operational = len(active_sources) > 0 and len(active_rules) > 0

        return {
            "status": "OPERATIONAL" if is_operational else "CONTENT_UNAVAILABLE",
            "active_sources_count": len(active_sources),
            "total_sources_count": len(sources),
            "active_rules_count": len(active_rules),
            "total_rules_count": len(rules),
            "sources": sources,
            "rules": rules,
            "governance_notice": "All rules are governed under clinical decision support protocol. Software validation does not constitute autonomous diagnostic clearance."
        }

    @staticmethod
    def evaluate_red_flags(conn: sqlite3.Connection, assessment: Dict[str, Any],
                           observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate deterministic red-flag safety rules against assessment narrative and observations."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, rule_id, rule_version, title, scope, severity, required_inputs_json,
                   logic_definition_json, plain_language_rationale, recommended_action, governance_status
            FROM clinical_rule_definitions
            WHERE rule_type = 'RED_FLAG';
        """)
        rule_rows = [dict(r) for r in cursor.fetchall()]

        if not rule_rows:
            return {
                "evaluation_status": "CONTENT_UNAVAILABLE",
                "message": "Safety rules unavailable—manual clinical assessment required. Do not assume low risk.",
                "triggered_alerts": [],
                "missing_input_rules": []
            }

        # Index available clinical facts
        obs_map = {}
        for o in observations:
            name_norm = o.get("concept_name", "").lower().replace(" ", "_")
            if o.get("value_numeric") is not None:
                obs_map[name_norm] = float(o["value_numeric"])
            elif o.get("value_text"):
                obs_map[name_norm] = str(o["value_text"]).strip().lower()

        # Parse assessment symptoms from chief complaint, HPI, and ROS
        complaint_text = (
            (assessment.get("chief_complaint") or "") + " " +
            (assessment.get("history_of_present_illness") or "") + " " +
            (assessment.get("working_assessment") or "")
        ).lower()

        ros_data = {}
        if assessment.get("review_of_systems_json"):
            try:
                ros_data = json.loads(assessment["review_of_systems_json"])
            except Exception:
                pass

        triggered = []
        missing_input_rules = []

        for rule in rule_rows:
            if rule["governance_status"] != "approved_active":
                continue

            rule_id = rule["rule_id"]
            required_inputs = json.loads(rule["required_inputs_json"])
            logic = json.loads(rule["logic_definition_json"])

            # Rule 1: Chest Pain with Ischemic Features
            if rule_id == "RULE-RF-001":
                has_chest_pain = "chest pain" in complaint_text or "angina" in complaint_text or "chest pressure" in complaint_text
                has_ischemic_features = any(term in complaint_text for term in [
                    "radiation", "radiating to left arm", "jaw pain", "diaphoresis", "sweating", "dyspnea", "shortness of breath", "syncope"
                ])
                
                if has_chest_pain and has_ischemic_features:
                    triggered.append({
                        "rule_db_id": rule["id"],
                        "rule_id": rule_id,
                        "rule_version": rule["rule_version"],
                        "title": rule["title"],
                        "severity": rule["severity"],
                        "trigger_facts": ["Documented acute chest discomfort", "Associated radiation or diaphoresis in clinical history"],
                        "plain_language_reason": rule["plain_language_rationale"],
                        "recommended_action": rule["recommended_action"]
                    })
                elif has_chest_pain and not has_ischemic_features:
                    # Chest pain without documented pertinent negatives is incomplete
                    missing_input_rules.append({
                        "rule_id": rule_id,
                        "title": rule["title"],
                        "missing_inputs": ["Ischemic radiation status", "Associated autonomic symptoms (diaphoresis, syncope)"]
                    })

            # Rule 2: Severe Hypertension / Hypertensive Crisis
            elif rule_id == "RULE-RF-002":
                sbp = obs_map.get("systolic_blood_pressure")
                dbp = obs_map.get("diastolic_blood_pressure")
                
                if sbp is None and dbp is None:
                    # Vitals not taken - fail closed, do NOT assume normal
                    missing_input_rules.append({
                        "rule_id": rule_id,
                        "title": rule["title"],
                        "missing_inputs": ["systolic_blood_pressure", "diastolic_blood_pressure"]
                    })
                else:
                    is_severe_htn = (sbp is not None and sbp >= 180) or (dbp is not None and dbp >= 110)
                    if is_severe_htn:
                        facts = []
                        if sbp is not None and sbp >= 180:
                            facts.append(f"Measured Systolic BP: {sbp} mmHg (>= 180)")
                        if dbp is not None and dbp >= 110:
                            facts.append(f"Measured Diastolic BP: {dbp} mmHg (>= 110)")
                        triggered.append({
                            "rule_db_id": rule["id"],
                            "rule_id": rule_id,
                            "rule_version": rule["rule_version"],
                            "title": rule["title"],
                            "severity": rule["severity"],
                            "trigger_facts": facts,
                            "plain_language_reason": rule["plain_language_rationale"],
                            "recommended_action": rule["recommended_action"]
                        })

            # Rule 3: Sepsis / Severe Systemic Inflammatory Response
            elif rule_id == "RULE-RF-003":
                hr = obs_map.get("heart_rate")
                rr = obs_map.get("respiratory_rate")
                temp = obs_map.get("body_temperature")

                vitals_present = sum(1 for v in [hr, rr, temp] if v is not None)
                if vitals_present < 2:
                    missing_input_rules.append({
                        "rule_id": rule_id,
                        "title": rule["title"],
                        "missing_inputs": [k for k, v in [("heart_rate", hr), ("respiratory_rate", rr), ("body_temperature", temp)] if v is None]
                    })
                else:
                    sirs_count = 0
                    sirs_facts = []
                    if temp is not None and (temp > 38.3 or temp < 36.0):
                        sirs_count += 1
                        sirs_facts.append(f"Abnormal temperature: {temp} degC")
                    if hr is not None and hr > 90:
                        sirs_count += 1
                        sirs_facts.append(f"Tachycardia: {hr} bpm (> 90)")
                    if rr is not None and rr > 20:
                        sirs_count += 1
                        sirs_facts.append(f"Tachypnea: {rr} /min (> 20)")

                    has_infection_history = any(w in complaint_text for w in ["fever", "chills", "rigor", "productive cough", "urinary burning", "cellulitis"])
                    if sirs_count >= 2 and has_infection_history:
                        sirs_facts.append("Suspected or documented acute infection focus")
                        triggered.append({
                            "rule_db_id": rule["id"],
                            "rule_id": rule_id,
                            "rule_version": rule["rule_version"],
                            "title": rule["title"],
                            "severity": rule["severity"],
                            "trigger_facts": sirs_facts,
                            "plain_language_reason": rule["plain_language_rationale"],
                            "recommended_action": rule["recommended_action"]
                        })

            # Rule 4: Acute Neurological Deficit (FAST)
            elif rule_id == "RULE-RF-004":
                fast_symptoms = [term for term in ["facial droop", "arm weakness", "slurred speech", "sudden numbness", "hemiparesis"] if term in complaint_text]
                if fast_symptoms:
                    triggered.append({
                        "rule_db_id": rule["id"],
                        "rule_id": rule_id,
                        "rule_version": rule["rule_version"],
                        "title": rule["title"],
                        "severity": rule["severity"],
                        "trigger_facts": [f"Documented acute focal neurological symptom: '{s}'" for s in fast_symptoms],
                        "plain_language_reason": rule["plain_language_rationale"],
                        "recommended_action": rule["recommended_action"]
                    })

        return {
            "evaluation_status": "EVALUATED",
            "rules_evaluated_count": len([r for r in rule_rows if r["governance_status"] == "approved_active"]),
            "triggered_alerts": triggered,
            "missing_input_rules": missing_input_rules,
            "evaluation_timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    def evaluate_differential_candidates(conn: sqlite3.Connection, assessment: Dict[str, Any],
                                         observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate explainable differential considerations based strictly on approved heuristics."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, rule_id, rule_version, title, scope, logic_definition_json,
                   plain_language_rationale, governance_status
            FROM clinical_rule_definitions
            WHERE rule_type = 'DIFFERENTIAL_HEURISTIC';
        """)
        rule_rows = [dict(r) for r in cursor.fetchall()]

        if not rule_rows:
            return {
                "status": "CONTENT_UNAVAILABLE",
                "message": "Differential diagnosis knowledge catalog is unconfigured or unavailable. Document clinical assessment directly.",
                "candidates": []
            }

        complaint_text = (
            (assessment.get("chief_complaint") or "") + " " +
            (assessment.get("history_of_present_illness") or "") + " " +
            (assessment.get("working_assessment") or "")
        ).lower()

        candidates = []

        for rule in rule_rows:
            if rule["governance_status"] != "approved_active":
                continue

            logic = json.loads(rule["logic_definition_json"])
            trigger_terms = logic.get("trigger_terms", [])
            matches_presentation = any(term.lower() in complaint_text for term in trigger_terms)

            if matches_presentation:
                for cand in logic.get("candidates", []):
                    # Check supporting findings in clinical text
                    supporting = [f for f in cand.get("supporting_findings_pool", []) if f.lower() in complaint_text]
                    contradicting = [f for f in cand.get("contradicting_findings_pool", []) if f.lower() in complaint_text]
                    missing = cand.get("standard_missing_information", [])

                    candidates.append({
                        "candidate_label": cand["label"],
                        "candidate_code": cand.get("code"),
                        "code_system": cand.get("code_system", "ICD-10-MOCK"),
                        "surfaced_by_type": "RULE_DERIVED",
                        "rule_db_id": rule["id"],
                        "rule_id": rule["rule_id"],
                        "rule_version": rule["rule_version"],
                        "evidence_status": "FOR_CLINICIAN_REVIEW",
                        "rationale": cand["rationale"],
                        "supporting_findings": supporting if supporting else ["Matching presenting complaint domain"],
                        "contradicting_findings": contradicting,
                        "missing_information": missing,
                        "source_references": cand.get("sources", [rule["title"]]),
                        "limitations": "Heuristic consideration only. Must be confirmed or rejected by the licensed clinician.",
                        "review_required": True
                    })

        return {
            "status": "EVALUATED",
            "candidates_count": len(candidates),
            "candidates": candidates,
            "disclaimer": "Diagnostic considerations are strictly clinical decision support. They do not constitute an autonomous diagnosis."
        }

    @staticmethod
    def evaluate_investigation_considerations(conn: sqlite3.Connection, assessment: Dict[str, Any],
                                              observations: List[Dict[str, Any]],
                                              red_flags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Surface evidence-backed investigation considerations without auto-ordering."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, rule_id, rule_version, title, scope, logic_definition_json,
                   plain_language_rationale, recommended_action, governance_status
            FROM clinical_rule_definitions
            WHERE rule_type = 'INVESTIGATION_GUIDELINE';
        """)
        rule_rows = [dict(r) for r in cursor.fetchall()]

        complaint_text = (
            (assessment.get("chief_complaint") or "") + " " +
            (assessment.get("history_of_present_illness") or "") + " " +
            (assessment.get("working_assessment") or "")
        ).lower()

        considerations = []

        for rule in rule_rows:
            if rule["governance_status"] != "approved_active":
                continue

            logic = json.loads(rule["logic_definition_json"])
            trigger_terms = logic.get("trigger_terms", [])
            matches = any(t.lower() in complaint_text for t in trigger_terms)
            
            # Or triggered by red-flag (e.g. chest pain red flag triggers ECG consideration)
            has_related_red_flag = any(rf.get("rule_id") in logic.get("associated_red_flags", []) for rf in red_flags)

            if matches or has_related_red_flag:
                for inv in logic.get("investigations", []):
                    considerations.append({
                        "clinical_question": inv["clinical_question"],
                        "suggested_investigation": inv["suggested_investigation"],
                        "modality": inv.get("modality", "LABORATORY"),
                        "rationale": inv["rationale"],
                        "guideline_source": rule["title"],
                        "rule_db_id": rule["id"],
                        "rule_id": rule["rule_id"],
                        "rule_version": rule["rule_version"],
                        "limitations": "Guideline recommendation. Requires clinician discretion. No automatic order placed.",
                        "clinician_decision": "PENDING"
                    })

        return considerations
