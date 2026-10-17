"""Data Quality, Missing-Information Detection & Clinical Workflow Intelligence Engine.

Phase 24 implementation for ZAYVORA MATAB OS.
Enforces deterministic validation, missingness state classification, field freshness,
provenance tracking, conflict reconciliation, and role-routed remediation guidance.
"""

import json
import uuid
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.audit import log_audit_event
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    SafetyBlockedError,
    ConflictError,
)

# Canonical Missingness States (Prompt 24 Non-Negotiable)
MISSINGNESS_STATES = {
    "MISSING",              # Mandatory clinical or administrative item absent
    "UNKNOWN",              # Actively documented by clinician or patient as unknown
    "NOT_RECORDED",         # Optional item omitted
    "NOT_ASSESSED",         # Clinician purposefully did not assess during this visit
    "DECLINED_BY_PATIENT",  # Patient explicitly declined to disclose or permit examination
    "NOT_APPLICABLE",       # Clinically inappropriate for this patient's profile/context
    "UNAVAILABLE"           # Historical external records inaccessible
}

ALLOWED_REMEDIATION_ROLES = {"FRONT_DESK", "TRIAGE_NURSE", "CLINICIAN", "PHARMACIST", "ADMIN"}


class DataQualityEngine:
    """Core domain engine for data quality, missingness classification, freshness, and workflow intelligence."""

    ENGINE_VERSION = "v1.0-deterministic"

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)

    # --------------------------------------------------------------------------
    # 1. Governed Rule Registry & Freshness Policies
    # --------------------------------------------------------------------------

    def list_rules(self, active_only: bool = True, scope_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List versioned data quality rules."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM dq_rule_registry WHERE 1=1"
            params: List[Any] = []
            if active_only:
                query += " AND is_active = 1"
            if scope_type:
                query += " AND scope_type = ?"
                params.append(scope_type)
            query += " ORDER BY severity DESC, rule_code ASC;"
            cur.execute(query, params)
            rules = []
            for r in cur.fetchall():
                rule = dict(r)
                rule["field_paths"] = json.loads(rule.get("field_paths_json") or "[]")
                rule["rule_logic"] = json.loads(rule.get("rule_logic_json") or "{}")
                rules.append(rule)
            return rules
        finally:
            conn.close()

    def get_rule(self, rule_code: str) -> Dict[str, Any]:
        """Fetch a specific rule by code."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM dq_rule_registry WHERE rule_code = ?;", (rule_code,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Data quality rule '{rule_code}' not found.")
            rule = dict(row)
            rule["field_paths"] = json.loads(rule.get("field_paths_json") or "[]")
            rule["rule_logic"] = json.loads(rule.get("rule_logic_json") or "{}")
            return rule
        finally:
            conn.close()

    def list_freshness_policies(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List clinical data freshness policies."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM dq_freshness_policies WHERE 1=1"
            if active_only:
                query += " AND is_active = 1"
            query += " ORDER BY max_age_hours ASC;"
            cur.execute(query)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def evaluate_freshness(self, field_name: str, recorded_at_str: str) -> Dict[str, Any]:
        """Evaluate if an observation exceeds maximum permitted age."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM dq_freshness_policies WHERE field_name = ? AND is_active = 1 LIMIT 1;", (field_name,))
            policy = cur.fetchone()
            if not policy:
                return {"has_policy": False, "is_stale": False}

            pol_dict = dict(policy)
            max_hours = pol_dict["max_age_hours"]

            # Parse recorded_at
            try:
                rec_dt = datetime.fromisoformat(recorded_at_str.replace("Z", "+00:00"))
            except Exception:
                rec_dt = datetime.strptime(recorded_at_str.split(".")[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            if rec_dt.tzinfo is None:
                rec_dt = rec_dt.replace(tzinfo=timezone.utc)

            age = now - rec_dt
            age_hours = age.total_seconds() / 3600.0
            is_stale = age_hours > max_hours

            return {
                "has_policy": True,
                "policy_code": pol_dict["policy_code"],
                "max_age_hours": max_hours,
                "age_hours": round(age_hours, 1),
                "is_stale": is_stale,
                "stale_severity": pol_dict["stale_severity"],
                "clinical_rationale": pol_dict["clinical_rationale"]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Granular Field Provenance
    # --------------------------------------------------------------------------

    def record_field_provenance(
        self,
        organization_id: str,
        entity_type: str,
        entity_id: str,
        field_name: str,
        field_value: Any,
        recorded_by: str,
        source_stream: str,
        unit: Optional[str] = None,
        recorded_at: Optional[str] = None,
        freshness_policy_code: Optional[str] = None,
        source_encounter_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record the source stream, unit, and capture context of an individual clinical value."""
        if source_stream not in {'PATIENT_REPORTED', 'CLINICIAN_OBSERVED', 'DEVICE_VITAL', 'EXTERNAL_RECORD'}:
            raise ValidationError(f"Invalid source_stream: '{source_stream}'")

        conn = self.db_manager.get_connection()
        try:
            prov_id = f"prov-{uuid.uuid4().hex[:12]}"
            ts = recorded_at or datetime.now(timezone.utc).isoformat()
            val_str = json.dumps(field_value) if isinstance(field_value, (dict, list)) else str(field_value)

            conn.execute("""
                INSERT INTO dq_field_provenance (
                    id, organization_id, entity_type, entity_id, field_name, field_value,
                    unit, recorded_at, recorded_by, source_stream, source_encounter_id, freshness_policy_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                prov_id, organization_id, entity_type, entity_id, field_name, val_str,
                unit, ts, recorded_by, source_stream, source_encounter_id, freshness_policy_code
            ))
            conn.commit()
            return {
                "provenance_id": prov_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "field_name": field_name,
                "recorded_at": ts,
                "source_stream": source_stream
            }
        finally:
            conn.close()

    def get_field_provenance(self, entity_type: str, entity_id: str, field_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve audit history and provenance of fields for an entity."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM dq_field_provenance WHERE entity_type = ? AND entity_id = ?"
            params: List[Any] = [entity_type, entity_id]
            if field_name:
                query += " AND field_name = ?"
                params.append(field_name)
            query += " ORDER BY recorded_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Deterministic Data Quality & Missingness Evaluation
    # --------------------------------------------------------------------------

    def evaluate_data_quality(
        self,
        patient_id: str,
        encounter_id: Optional[str] = None,
        scope_type: str = "ENCOUNTER",
        trigger: str = "MANUAL",
        user_ctx: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes deterministic rules over patient, encounter, assessments, and prescriptions.
        Synthesizes atomic findings with explicit missingness states and routed remediations.
        """
        user_ctx = user_ctx or {"user_id": "system", "organization_id": "org-matab-default", "role": "CLINICIAN"}
        org_id = user_ctx.get("organization_id", "org-matab-default")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()

            # 1. Fetch Patient
            cur.execute("SELECT * FROM patients WHERE id = ? AND organization_id = ?;", (patient_id, org_id))
            pat_row = cur.fetchone()
            if not pat_row:
                raise NotFoundError(f"Patient '{patient_id}' not found.")
            patient = dict(pat_row)

            # 2. Fetch Encounter (if provided)
            encounter = None
            if encounter_id:
                cur.execute("SELECT * FROM encounters WHERE id = ? AND organization_id = ?;", (encounter_id, org_id))
                enc_row = cur.fetchone()
                if not enc_row:
                    raise NotFoundError(f"Encounter '{encounter_id}' not found.")
                encounter = dict(enc_row)

            # 3. Fetch Modern Assessment & Vitals
            modern_assessment = None
            if encounter_id:
                cur.execute("""
                    SELECT * FROM modern_clinical_assessments
                    WHERE encounter_id = ? AND organization_id = ?
                    ORDER BY created_at DESC LIMIT 1;
                """, (encounter_id, org_id))
                m_row = cur.fetchone()
                if m_row:
                    modern_assessment = dict(m_row)

            # 4. Fetch Unani Assessment
            unani_assessment = None
            if encounter_id:
                cur.execute("""
                    SELECT * FROM unani_assessments
                    WHERE encounter_id = ? AND organization_id = ?
                    ORDER BY created_at DESC LIMIT 1;
                """, (encounter_id, org_id))
                u_row = cur.fetchone()
                if u_row:
                    unani_assessment = dict(u_row)

            # 5. Fetch Active Prescription
            prescription = None
            rx_items = []
            if encounter_id:
                cur.execute("""
                    SELECT * FROM prescriptions
                    WHERE encounter_id = ? AND organization_id = ? AND status != 'CANCELLED'
                    ORDER BY created_at DESC LIMIT 1;
                """, (encounter_id, org_id))
                rx_row = cur.fetchone()
                if rx_row:
                    prescription = dict(rx_row)
                    cur.execute("SELECT * FROM prescription_items WHERE prescription_id = ?;", (prescription["id"],))
                    rx_items = [dict(it) for it in cur.fetchall()]

            # 6. Fetch Duplicate Candidates
            cur.execute("""
                SELECT COUNT(*) as count FROM patient_duplicate_candidates
                WHERE (patient_id_a = ? OR patient_id_b = ?) AND status = 'PENDING_REVIEW';
            """, (patient_id, patient_id))
            pending_duplicates = cur.fetchone()["count"]

            # Evaluate Findings
            findings: List[Dict[str, Any]] = []

            # Rule: DQ-PAT-PHONE
            cur.execute("""
                SELECT contact_value FROM patient_contacts
                WHERE patient_id = ? AND contact_type IN ('PHONE', 'WHATSAPP')
                ORDER BY is_preferred DESC LIMIT 1;
            """, (patient_id,))
            contact_row = cur.fetchone()
            phone = (contact_row["contact_value"] if contact_row else patient.get("phone") or "").strip()

            if not phone:
                findings.append({
                    "rule_code": "DQ-PAT-PHONE",
                    "category": "PRESENCE",
                    "severity": "WARNING",
                    "field_path": "patients.phone",
                    "missingness_state": "MISSING",
                    "finding_summary": "Patient primary phone number is missing.",
                    "explanation": "No contact number recorded in demographic profile or patient contacts.",
                    "clinical_implication": "Care continuity notices, prescription alerts, and tele-followup cannot reach patient.",
                    "remediation_role": "FRONT_DESK"
                })

            # Rule: DQ-PAT-DOB
            dob = (patient.get("date_of_birth") or patient.get("dob") or "").strip()
            age_years = patient.get("estimated_age") or patient.get("age_years")
            if not dob and (age_years is None or age_years == 0):
                findings.append({
                    "rule_code": "DQ-PAT-DOB",
                    "category": "PRESENCE",
                    "severity": "WARNING",
                    "field_path": "patients.dob",
                    "missingness_state": "MISSING",
                    "finding_summary": "Patient date of birth and age are missing.",
                    "explanation": "Neither precise date of birth nor estimated age years recorded.",
                    "clinical_implication": "Pediatric/geriatric dosage limits and age-band contraindications cannot be computed safely.",
                    "remediation_role": "FRONT_DESK"
                })

            # Rule: DQ-DUPLICATE-PATIENT-FLAG
            if pending_duplicates > 0:
                findings.append({
                    "rule_code": "DQ-DUPLICATE-PATIENT-FLAG",
                    "category": "IDENTITY",
                    "severity": "WARNING",
                    "field_path": "patients.duplicate_candidates",
                    "missingness_state": None,
                    "finding_summary": f"Patient record has {pending_duplicates} unresolved duplicate candidate match(es).",
                    "explanation": "Deterministic matching detected potential existing chart with matching phone or identity.",
                    "clinical_implication": "Risk of fragmented clinical history and missed allergy alerts across duplicate records.",
                    "remediation_role": "FRONT_DESK"
                })

            # Encounter-Specific Checks
            if encounter:
                enc_status = encounter.get("status", "")

                # Rule: DQ-ENC-CHIEF-COMPLAINT
                chief_complaint = ""
                if modern_assessment:
                    chief_complaint = (modern_assessment.get("chief_complaint") or "").strip()
                if not chief_complaint and unani_assessment:
                    chief_complaint = (unani_assessment.get("chief_complaint") or "").strip()

                if enc_status in ["in_consultation", "assessment_in_progress", "treatment_planning", "ready_to_finalize"] and not chief_complaint:
                    findings.append({
                        "rule_code": "DQ-ENC-CHIEF-COMPLAINT",
                        "category": "PRESENCE",
                        "severity": "BLOCKER",
                        "field_path": "encounters.chief_complaint",
                        "missingness_state": "MISSING",
                        "finding_summary": "Consultation chief complaint is not documented.",
                        "explanation": "Neither Modern nor Unani clinical assessment lane contains a recorded chief complaint.",
                        "clinical_implication": "A clinical consultation cannot be concluded or signed without documenting the patient's presenting problem.",
                        "remediation_role": "CLINICIAN"
                    })

                # Rule: DQ-WORKFLOW-ARRIVED-TRIAGE
                if enc_status == "arrived" and not modern_assessment:
                    findings.append({
                        "rule_code": "DQ-WORKFLOW-ARRIVED-TRIAGE",
                        "category": "WORKFLOW_PREREQUISITE",
                        "severity": "INFO",
                        "field_path": "encounters.vitals",
                        "missingness_state": "NOT_RECORDED",
                        "finding_summary": "Patient has arrived but triage vitals have not been captured.",
                        "explanation": "Encounter status is 'arrived' without recorded triage observations.",
                        "clinical_implication": "Prompt vitals capture assists in spotting urgent hypertensive or febrile red flags prior to consultation.",
                        "remediation_role": "TRIAGE_NURSE"
                    })

                # Vitals Extraction from Modern Assessment or Clinical Observations
                sys_bp = modern_assessment.get("systolic_bp") if modern_assessment else None
                dia_bp = modern_assessment.get("diastolic_bp") if modern_assessment else None
                pulse = (modern_assessment.get("pulse_rate") or modern_assessment.get("heart_rate")) if modern_assessment else None
                temp_val = modern_assessment.get("temperature") if modern_assessment else None
                temp_unit = modern_assessment.get("temperature_unit") if modern_assessment else None

                cur.execute("""
                    SELECT concept_name, concept_code, value_numeric, value_text, unit
                    FROM clinical_observations
                    WHERE encounter_id = ? AND observation_type = 'VITAL_SIGN';
                """, (encounter_id,))
                for obs in cur.fetchall():
                    c_name = (obs["concept_name"] or "").lower()
                    c_code = (obs["concept_code"] or "").upper()
                    if "systolic" in c_name or c_code == "BP_SYSTOLIC":
                        sys_bp = obs["value_numeric"]
                    elif "diastolic" in c_name or c_code == "BP_DIASTOLIC":
                        dia_bp = obs["value_numeric"]
                    elif "heart rate" in c_name or "pulse" in c_name or c_code in ["PULSE", "HEART_RATE"]:
                        pulse = obs["value_numeric"]
                    elif "temperature" in c_name or c_code == "BODY_TEMP":
                        temp_val = obs["value_numeric"]
                        temp_unit = obs["unit"] or temp_unit

                # Check BP Order
                if sys_bp is not None and dia_bp is not None:
                    try:
                        s_val = float(sys_bp)
                        d_val = float(dia_bp)
                        if s_val <= d_val:
                            findings.append({
                                "rule_code": "DQ-VITALS-BP-ORDER",
                                "category": "CONSISTENCY",
                                "severity": "CRITICAL",
                                "field_path": "vitals.blood_pressure",
                                "missingness_state": None,
                                "finding_summary": f"Systolic BP ({s_val} mmHg) is not greater than Diastolic BP ({d_val} mmHg).",
                                "explanation": "Physiologically inverted blood pressure readings detected.",
                                "clinical_implication": "Inverted blood pressure measurements compromise clinical risk stratification and hypertension screening.",
                                "conflicting_values": [{"systolic": s_val, "diastolic": d_val}],
                                "remediation_role": "TRIAGE_NURSE"
                            })
                    except (ValueError, TypeError):
                        pass

                # Check Pulse Range
                if pulse is not None:
                    try:
                        p_val = float(pulse)
                        if p_val < 30 or p_val > 220:
                            findings.append({
                                "rule_code": "DQ-VITALS-PULSE-RANGE",
                                "category": "VALIDITY",
                                "severity": "WARNING",
                                "field_path": "vitals.pulse_rate",
                                "missingness_state": None,
                                "finding_summary": f"Pulse rate ({p_val} bpm) is outside plausible physiological range (30-220 bpm).",
                                "explanation": "Value falls outside standard human survival bounds.",
                                "clinical_implication": "Suspected measurement error or transcription typo.",
                                "remediation_role": "TRIAGE_NURSE"
                            })
                    except (ValueError, TypeError):
                        pass

                # Check Temp Unit
                if temp_val is not None:
                    unit_clean = (str(temp_unit or "")).strip().upper()
                    if unit_clean not in ["C", "F", "CELSIUS", "FAHRENHEIT"]:
                        findings.append({
                            "rule_code": "DQ-VITALS-TEMP-UNIT",
                            "category": "VALIDITY",
                            "severity": "WARNING",
                            "field_path": "vitals.temperature_unit",
                            "missingness_state": "MISSING",
                            "finding_summary": f"Body temperature recorded ({temp_val}) without a valid unit (C or F).",
                            "explanation": f"Unrecognized temperature unit '{temp_unit}'.",
                            "clinical_implication": "Ambiguity between 38°C (fever) and 38°F (severe hypothermia).",
                            "remediation_role": "TRIAGE_NURSE"
                        })

                # Unani Assessment Checks
                if unani_assessment:
                    mizaj = unani_assessment.get("mizaj_primary") or unani_assessment.get("mizaj")
                    if not mizaj:
                        findings.append({
                            "rule_code": "DQ-UNANI-MIZAJ-PRESENCE",
                            "category": "PRESENCE",
                            "severity": "WARNING",
                            "field_path": "unani_assessment.mizaj_primary",
                            "missingness_state": "MISSING",
                            "finding_summary": "Unani clinical assessment is active but primary Mizaj is unclassified.",
                            "explanation": "Unani consultation record lacks documented Mizaj classification.",
                            "clinical_implication": "Mizaj is fundamental to Usul-e-Ilaj formulation selection and Ilaj-bil-Ghiza prescription.",
                            "remediation_role": "CLINICIAN"
                        })

                # Prescription Items Instructions Checks
                if prescription and rx_items:
                    for item in rx_items:
                        inst = (item.get("instructions") or "").strip()
                        dosage = (item.get("dose_amount") or item.get("dosage") or "").strip()
                        freq = (item.get("frequency") or "").strip()
                        if not inst and (not dosage or not freq):
                            item_label = item.get("item_name") or item.get("formulation_name") or "Item"
                            findings.append({
                                "rule_code": "DQ-RX-SIG-PRESENCE",
                                "category": "PRESENCE",
                                "severity": "BLOCKER",
                                "field_path": f"prescriptions.items[{item.get('id')}]",
                                "missingness_state": "MISSING",
                                "finding_summary": f"Prescription item '{item_label}' missing dosage and administration instructions (Sig).",
                                "explanation": "Item has neither dosage instructions nor frequency specified.",
                                "clinical_implication": "Patients cannot safely administer prescribed medicines without clear posology and administration route.",
                                "remediation_role": "CLINICIAN"
                            })

            # Persist Evaluation Run
            eval_id = f"dq-eval-{uuid.uuid4().hex[:12]}"
            target_ver = encounter.get("version", 1) if encounter else 1
            blockers_count = sum(1 for f in findings if f["severity"] == "BLOCKER")
            facility_id = encounter.get("facility_id") if encounter else None

            conn.execute("""
                INSERT INTO dq_evaluations (
                    id, organization_id, facility_id, encounter_id, patient_id, scope_type,
                    target_version, evaluation_trigger, findings_count, blockers_count, evaluated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                eval_id, org_id, facility_id, encounter_id, patient_id, scope_type,
                target_ver, trigger, len(findings), blockers_count, user_ctx.get("user_id", "system")
            ))

            # Persist Findings
            persisted_findings: List[Dict[str, Any]] = []
            for f in findings:
                f_id = f"dq-find-{uuid.uuid4().hex[:12]}"
                conf_json = json.dumps(f.get("conflicting_values", []))
                conn.execute("""
                    INSERT INTO dq_findings (
                        id, evaluation_id, encounter_id, patient_id, rule_code, category, severity,
                        field_path, missingness_state, finding_summary, explanation, clinical_implication,
                        conflicting_values_json, remediation_role, remediation_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN');
                """, (
                    f_id, eval_id, encounter_id, patient_id, f["rule_code"], f["category"], f["severity"],
                    f["field_path"], f.get("missingness_state"), f["finding_summary"], f["explanation"],
                    f.get("clinical_implication"), conf_json, f["remediation_role"]
                ))
                f_record = dict(f)
                f_record["id"] = f_id
                f_record["evaluation_id"] = eval_id
                f_record["remediation_status"] = "OPEN"
                persisted_findings.append(f_record)

            conn.commit()

            # Group findings by role for transparent remediation
            by_role: Dict[str, List[Dict[str, Any]]] = {}
            for pf in persisted_findings:
                by_role.setdefault(pf["remediation_role"], []).append(pf)

            return {
                "evaluation_id": eval_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "findings_count": len(persisted_findings),
                "blockers_count": blockers_count,
                "warnings_count": sum(1 for f in persisted_findings if f["severity"] == "WARNING"),
                "critical_count": sum(1 for f in persisted_findings if f["severity"] == "CRITICAL"),
                "findings": persisted_findings,
                "remediations_by_role": by_role,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Findings Retrieval & Clinician Resolution
    # --------------------------------------------------------------------------

    def list_findings(
        self,
        encounter_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        remediation_status: Optional[str] = None,
        remediation_role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List data quality findings with optional filters."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM dq_findings WHERE 1=1"
            params: List[Any] = []
            if encounter_id:
                query += " AND encounter_id = ?"
                params.append(encounter_id)
            if patient_id:
                query += " AND patient_id = ?"
                params.append(patient_id)
            if remediation_status:
                query += " AND remediation_status = ?"
                params.append(remediation_status)
            if remediation_role:
                query += " AND remediation_role = ?"
                params.append(remediation_role)
            query += " ORDER BY severity DESC, created_at DESC;"
            cur.execute(query, params)
            findings = []
            for r in cur.fetchall():
                f = dict(r)
                f["conflicting_values"] = json.loads(f.get("conflicting_values_json") or "[]")
                f["resolution_details"] = json.loads(f.get("resolution_details_json") or "{}")
                findings.append(f)
            return findings
        finally:
            conn.close()

    def get_finding(self, finding_id: str) -> Dict[str, Any]:
        """Fetch single finding by ID."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM dq_findings WHERE id = ?;", (finding_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Finding '{finding_id}' not found.")
            f = dict(row)
            f["conflicting_values"] = json.loads(f.get("conflicting_values_json") or "[]")
            f["resolution_details"] = json.loads(f.get("resolution_details_json") or "{}")
            return f
        finally:
            conn.close()

    def resolve_finding(
        self,
        finding_id: str,
        action: str,
        user_ctx: Dict[str, Any],
        reason: Optional[str] = None,
        resolution_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Records human remediation of a data quality finding.
        action in: RESOLVED, ACKNOWLEDGED_WITH_REASON, DEFERRED
        """
        if action not in ["RESOLVED", "ACKNOWLEDGED_WITH_REASON", "DEFERRED"]:
            raise ValidationError(f"Invalid resolution action: '{action}'")

        if action in ["ACKNOWLEDGED_WITH_REASON", "DEFERRED"] and not reason:
            raise ValidationError("Clinical justification/reason is required to acknowledge or defer a finding.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM dq_findings WHERE id = ?;", (finding_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Finding '{finding_id}' not found.")
            finding = dict(row)

            # Blockers cannot be deferred
            if finding["severity"] == "BLOCKER" and action == "DEFERRED":
                raise SafetyBlockedError("BLOCKER findings cannot be deferred; they must be actively resolved or clinically justified.")

            now = datetime.now(timezone.utc).isoformat()
            user_id = user_ctx.get("user_id", "system")
            details = resolution_details or {}
            if reason:
                details["reason"] = reason

            conn.execute("""
                UPDATE dq_findings
                SET remediation_status = ?,
                    resolved_by = ?,
                    resolved_at = ?,
                    resolution_details_json = ?
                WHERE id = ?;
            """, (action, user_id, now, json.dumps(details), finding_id))
            conn.commit()

            log_audit_event(
                conn=conn,
                organization_id=user_ctx.get("organization_id", "default"),
                actor_id=user_id,
                actor_role=user_ctx.get("role", "CLINICIAN"),
                event_type="DQ_FINDING_RESOLVED",
                resource_type="dq_finding",
                resource_id=finding_id,
                action="UPDATE",
                details={"action": action, "reason": reason}
            )

            return {
                "finding_id": finding_id,
                "remediation_status": action,
                "resolved_by": user_id,
                "resolved_at": now,
                "reason": reason
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Clinician Conflict Reconciliation
    # --------------------------------------------------------------------------

    def reconcile_conflict(
        self,
        patient_id: str,
        field_name: str,
        conflict_summary: str,
        options_evaluated: List[Dict[str, Any]],
        selected_value: Any,
        clinician_rationale: str,
        user_ctx: Dict[str, Any],
        encounter_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records human-driven reconciliation of conflicting clinical data sources.
        Never auto-overwrites with latest timestamp or AI similarity.
        """
        if not clinician_rationale or len(clinician_rationale.strip()) < 5:
            raise ValidationError("A substantive clinician rationale is required for conflict reconciliation.")

        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system")
        rec_id = f"dq-rec-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        sel_val_str = json.dumps(selected_value) if isinstance(selected_value, (dict, list)) else str(selected_value)

        conn = self.db_manager.get_connection()
        try:
            conn.execute("""
                INSERT INTO dq_reconciliation_decisions (
                    id, organization_id, patient_id, encounter_id, field_name, conflict_summary,
                    options_evaluated_json, selected_value, clinician_rationale, reconciled_by, reconciled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                rec_id, org_id, patient_id, encounter_id, field_name, conflict_summary,
                json.dumps(options_evaluated), sel_val_str, clinician_rationale, user_id, now
            ))

            # Mark any open findings matching this field as RESOLVED
            if encounter_id:
                conn.execute("""
                    UPDATE dq_findings
                    SET remediation_status = 'RESOLVED',
                        resolved_by = ?,
                        resolved_at = ?,
                        resolution_details_json = ?
                    WHERE encounter_id = ? AND field_path LIKE ? AND remediation_status = 'OPEN';
                """, (
                    user_id, now,
                    json.dumps({"reconciliation_decision_id": rec_id, "rationale": clinician_rationale}),
                    encounter_id, f"%{field_name}%"
                ))

            conn.commit()

            log_audit_event(
                conn=conn,
                organization_id=org_id,
                actor_id=user_id,
                actor_role=user_ctx.get("role", "CLINICIAN"),
                event_type="DQ_CONFLICT_RECONCILED",
                resource_type="dq_reconciliation",
                resource_id=rec_id,
                action="CREATE",
                details={"field_name": field_name, "selected_value": sel_val_str, "rationale": clinician_rationale}
            )

            return {
                "reconciliation_id": rec_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "field_name": field_name,
                "selected_value": selected_value,
                "clinician_rationale": clinician_rationale,
                "reconciled_by": user_id,
                "reconciled_at": now
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. Workflow Readiness Check
    # --------------------------------------------------------------------------

    def check_dq_readiness(self, encounter_id: str, user_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluates whether all data-quality blockers and prerequisites are satisfied for encounter sign-off.
        """
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM dq_findings
                WHERE encounter_id = ? AND remediation_status = 'OPEN';
            """, (encounter_id,))
            open_findings = [dict(r) for r in cur.fetchall()]

            blockers = [f for f in open_findings if f["severity"] == "BLOCKER"]
            criticals = [f for f in open_findings if f["severity"] == "CRITICAL"]
            warnings = [f for f in open_findings if f["severity"] == "WARNING"]

            is_ready = len(blockers) == 0

            return {
                "encounter_id": encounter_id,
                "is_ready": is_ready,
                "open_blockers_count": len(blockers),
                "open_criticals_count": len(criticals),
                "open_warnings_count": len(warnings),
                "blocking_reasons": [b["finding_summary"] for b in blockers],
                "open_findings": open_findings
            }
        finally:
            conn.close()
