"""Modern Clinical Support Domain: Deterministic Red-Flag Triage & Diagnostic Suggestions."""

import uuid
from typing import Dict, Any, List, Optional
import sqlite3

RED_FLAG_RULES = [
    {
        "id": "RF-ACS",
        "keywords": ["chest pain", "angina", "sweating", "radiating to left arm", "heavy chest"],
        "severity": "CRITICAL",
        "title": "Possible Acute Coronary Syndrome (ACS)",
        "guidance": "Emergency referral required. Immediate ECG, Aspirin, and cardiac evaluation."
    },
    {
        "id": "RF-STROKE",
        "keywords": ["sudden weakness", "facial drooping", "slurred speech", "hemiparesis", "loss of vision"],
        "severity": "CRITICAL",
        "title": "Suspected Acute Cerebrovascular Event (Stroke)",
        "guidance": "Time-critical emergency. Immediate brain imaging and emergency tertiary transfer."
    },
    {
        "id": "RF-HYPERTENSIVE-CRISIS",
        "rule_fn": lambda v: v and v.get("systolic_bp", 0) >= 180 or (v and v.get("diastolic_bp", 0) >= 110),
        "severity": "URGENT",
        "title": "Hypertensive Crisis (Stage 3)",
        "guidance": "Evaluate for target organ damage (headache, chest pain, vision change). Urgent blood pressure stabilization."
    },
    {
        "id": "RF-SEPSIS",
        "rule_fn": lambda v: v and (v.get("temperature_f", 0) >= 102.5 and v.get("pulse_bpm", 0) >= 110),
        "severity": "URGENT",
        "title": "Suspected Severe Systemic Infection / SIRS",
        "guidance": "Assess hydration, source of infection, and hemodynamic stability."
    }
]

class ClinicalSupportService:
    @staticmethod
    def evaluate_red_flags(clinical_text: str, vitals: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Run deterministic clinical safety rules against patient notes and vitals."""
        alerts = []
        text_lower = (clinical_text or "").lower()
        
        for rule in RED_FLAG_RULES:
            triggered = False
            trigger_reason = ""
            
            if "keywords" in rule:
                matched_kws = [kw for kw in rule["keywords"] if kw in text_lower]
                if matched_kws:
                    triggered = True
                    trigger_reason = f"Identified warning keywords: {', '.join(matched_kws)}"
                    
            if "rule_fn" in rule and vitals:
                if rule["rule_fn"](vitals):
                    triggered = True
                    trigger_reason = "Vital sign thresholds breached critical limits."
                    
            if triggered:
                alerts.append({
                    "rule_id": rule["id"],
                    "severity": rule["severity"],
                    "title": rule["title"],
                    "guidance": rule["guidance"],
                    "reason": trigger_reason
                })
                
        return alerts

    @staticmethod
    def save_clinical_problems(conn: sqlite3.Connection, encounter_id: str, problems: List[Dict[str, Any]]) -> None:
        """Save confirmed modern diagnostic problems and ICD-10 candidates."""
        for p in problems:
            conn.execute("""
                INSERT INTO clinical_problems (id, encounter_id, problem_name, icd10_code, status, is_red_flag)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (
                str(uuid.uuid4()),
                encounter_id,
                p.get("problem_name", "").strip(),
                p.get("icd10_code"),
                p.get("status", "ACTIVE"),
                1 if p.get("is_red_flag") else 0
            ))
