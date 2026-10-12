"""Modern Clinical Assessment Domain Service.
Handles structured clinical history, examination, typed observations/vitals,
deterministic safety preflight (red flags), differential decision support,
investigation considerations, clinician-confirmed problem lists, referrals,
and governed immutable electronic signing / amendments.
"""

import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3

from apps.api.core.errors import (
    NotFoundError, ValidationError, ConflictError, ForbiddenError
)
from apps.api.core.security import verify_pin
from apps.api.core.audit import log_audit_event
from apps.api.domains.clinical_rules import ClinicalRulesEngine

# Valid observation types and units
VALID_OBSERVATION_TYPES = {"VITAL_SIGN", "LABORATORY", "PHYSICAL_FINDING", "SYSTEM_REVIEW"}
VALID_SOURCE_TYPES = {"CLINICIAN_ENTERED", "PATIENT_REPORTED", "DEVICE_IMPORTED", "EXTERNAL_DOCUMENT"}
VALID_UNCERTAINTY_LEVELS = {"HIGH_CONFIDENCE", "MODERATE_CONFIDENCE", "PROVISIONAL", "UNCERTAIN", "NOT_ASSESSED"}
VALID_ALLERGIES_REVIEW_STATUS = {"NOT_RECORDED", "NOT_REVIEWED", "REVIEWED_NONE_REPORTED", "REVIEWED_ALLERGIES_RECORDED"}
VALID_PROBLEM_STATUSES = {"PROVISIONAL", "CONFIRMED", "RESOLVED", "RULED_OUT"}
VALID_REFERRAL_URGENCIES = {"ROUTINE", "URGENT", "EMERGENT"}
VALID_REFERRAL_INFORMED = {"INFORMED_AGREED", "INFORMED_REFUSED", "UNABLE_TO_INFORM", "NOT_DISCUSSED"}

# Reference ranges for common vital signs [Synthetic Governance Benchmark]
STANDARD_VITAL_RANGES = {
    "systolic_blood_pressure": {"unit": "mmHg", "low": 90.0, "high": 120.0, "provenance": "AHA/ACC 2017 Guidelines"},
    "diastolic_blood_pressure": {"unit": "mmHg", "low": 60.0, "high": 80.0, "provenance": "AHA/ACC 2017 Guidelines"},
    "heart_rate": {"unit": "bpm", "low": 60.0, "high": 100.0, "provenance": "Adult Resting Heart Rate Standard"},
    "respiratory_rate": {"unit": "/min", "low": 12.0, "high": 20.0, "provenance": "Adult Resting Respiration Standard"},
    "body_temperature": {"unit": "degC", "low": 36.1, "high": 37.2, "provenance": "Clinical Core Temperature Standard"},
    "oxygen_saturation": {"unit": "%", "low": 95.0, "high": 100.0, "provenance": "Pulse Oximetry Standard"},
    "fasting_blood_sugar": {"unit": "mg/dL", "low": 70.0, "high": 99.0, "provenance": "ADA 2024 Fasting Glucose Criteria"}
}


class ModernAssessmentService:
    """Manages the lifecycle and decision-support flow of Modern Clinical Assessments."""

    @staticmethod
    def create_assessment_draft(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                encounter_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new modern clinical assessment draft linked to an active encounter."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        # Validate encounter exists in organization
        cursor.execute("""
            SELECT e.id, e.organization_id, e.facility_id, e.patient_id, e.status, e.practitioner_id
            FROM encounters e
            WHERE e.id = ? AND e.organization_id = ?;
        """, (encounter_id, org_id))
        enc = cursor.fetchone()
        if not enc:
            raise NotFoundError(f"Encounter '{encounter_id}' not found in active organization.")
        if enc["status"] in ("COMPLETED", "CANCELLED"):
            raise ConflictError(f"Cannot create assessment for terminal encounter (status: {enc['status']}).")

        # Check existing active assessment for this encounter
        cursor.execute("""
            SELECT id FROM modern_clinical_assessments
            WHERE encounter_id = ? AND status = 'DRAFT' AND organization_id = ?;
        """, (encounter_id, org_id))
        existing_draft = cursor.fetchone()
        if existing_draft:
            return ModernAssessmentService.get_assessment_by_id(conn, user_ctx, existing_draft["id"])

        assessment_id = f"mca-{uuid.uuid4().hex[:12]}"
        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        today_date = datetime.utcnow().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO modern_clinical_assessments (
                id, organization_id, facility_id, patient_id, encounter_id,
                author_id, status, assessment_date, chief_complaint, history_of_present_illness,
                past_medical_history, surgical_history, family_history, personal_social_history,
                medication_history, allergies_review_status, review_of_systems_json,
                physical_examination_json, working_assessment, clinical_rationale,
                uncertainty_level, ai_drafted_notes, ai_draft_status, version_number,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, 'DRAFT', ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, 1,
                ?, ?
            );
        """, (
            assessment_id, org_id, enc["facility_id"], enc["patient_id"], encounter_id,
            user_ctx["user_id"], today_date,
            payload.get("chief_complaint"),
            payload.get("history_of_present_illness"),
            payload.get("past_medical_history"),
            payload.get("surgical_history"),
            payload.get("family_history"),
            payload.get("personal_social_history"),
            payload.get("medication_history"),
            payload.get("allergies_review_status", "NOT_REVIEWED"),
            json.dumps(payload.get("review_of_systems", {})) if isinstance(payload.get("review_of_systems"), dict) else payload.get("review_of_systems_json"),
            json.dumps(payload.get("physical_examination", {})) if isinstance(payload.get("physical_examination"), dict) else payload.get("physical_examination_json"),
            payload.get("working_assessment"),
            payload.get("clinical_rationale"),
            payload.get("uncertainty_level", "NOT_ASSESSED"),
            payload.get("ai_drafted_notes"),
            payload.get("ai_draft_status", "NONE"),
            now_dt, now_dt
        ))

        # Insert any initial observations if provided
        if payload.get("observations"):
            ModernAssessmentService._persist_observations(
                conn, user_ctx, assessment_id, enc["patient_id"], encounter_id, payload["observations"]
            )

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=enc["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_MODERN_ASSESSMENT_DRAFT_CREATED",
            resource_type="MODERN_CLINICAL_ASSESSMENT",
            resource_id=assessment_id,
            patient_id=enc["patient_id"],
            encounter_id=encounter_id,
            action_status="SUCCESS",
            description="Created modern clinical assessment draft."
        )

        return ModernAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)

    @staticmethod
    def get_assessment_by_id(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                             assessment_id: str) -> Dict[str, Any]:
        """Retrieve full structured assessment, observations, red flags, differentials, problems, and referrals."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT a.*, p.display_name as patient_name, p.mrn as patient_mrn,
                   u.full_name as author_name, f.name as facility_name
            FROM modern_clinical_assessments a
            JOIN patients p ON a.patient_id = p.id
            JOIN users u ON a.author_id = u.id
            JOIN facilities f ON a.facility_id = f.id
            WHERE a.id = ? AND a.organization_id = ?;
        """, (assessment_id, org_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Modern clinical assessment '{assessment_id}' not found.")

        result = dict(row)

        # Observations / Vitals
        cursor.execute("""
            SELECT * FROM clinical_observations
            WHERE assessment_id = ?
            ORDER BY measured_at ASC;
        """, (assessment_id,))
        result["observations"] = [dict(r) for r in cursor.fetchall()]

        # Clinical Problems
        cursor.execute("""
            SELECT * FROM clinical_problems
            WHERE assessment_id = ?
            ORDER BY is_primary DESC, created_at ASC;
        """, (assessment_id,))
        result["problems"] = [dict(r) for r in cursor.fetchall()]

        # Differential Candidates
        cursor.execute("""
            SELECT * FROM differential_candidates
            WHERE assessment_id = ?
            ORDER BY created_at ASC;
        """, (assessment_id,))
        diff_rows = [dict(r) for r in cursor.fetchall()]
        for d in diff_rows:
            d["supporting_findings"] = json.loads(d["supporting_findings_json"]) if d.get("supporting_findings_json") else []
            d["contradicting_findings"] = json.loads(d["contradicting_findings_json"]) if d.get("contradicting_findings_json") else []
            d["missing_information"] = json.loads(d["missing_information_json"]) if d.get("missing_information_json") else []
            d["source_references"] = json.loads(d["source_references_json"]) if d.get("source_references_json") else []
        result["differential_candidates"] = diff_rows

        # Red Flag Events
        cursor.execute("""
            SELECT * FROM red_flag_events
            WHERE assessment_id = ?
            ORDER BY created_at DESC;
        """, (assessment_id,))
        rf_rows = [dict(r) for r in cursor.fetchall()]
        for rf in rf_rows:
            rf["trigger_facts"] = json.loads(rf["trigger_facts_json"]) if rf.get("trigger_facts_json") else []
        result["red_flag_events"] = rf_rows

        # Investigation Considerations
        cursor.execute("""
            SELECT * FROM investigation_considerations
            WHERE assessment_id = ?
            ORDER BY created_at ASC;
        """, (assessment_id,))
        result["investigation_considerations"] = [dict(r) for r in cursor.fetchall()]

        # Referral Records
        cursor.execute("""
            SELECT * FROM referral_records
            WHERE assessment_id = ?
            ORDER BY created_at DESC;
        """, (assessment_id,))
        result["referrals"] = [dict(r) for r in cursor.fetchall()]

        # Amendments (if any)
        cursor.execute("""
            SELECT * FROM clinical_assessment_amendments
            WHERE assessment_id = ?
            ORDER BY prior_version_number ASC;
        """, (assessment_id,))
        result["amendments"] = [dict(r) for r in cursor.fetchall()]

        return result

    @staticmethod
    def get_assessment_by_encounter(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                    encounter_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve most recent assessment for a specific encounter."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT id FROM modern_clinical_assessments
            WHERE encounter_id = ? AND organization_id = ?
            ORDER BY version_number DESC, created_at DESC LIMIT 1;
        """, (encounter_id, org_id))
        row = cursor.fetchone()
        if not row:
            return None
        return ModernAssessmentService.get_assessment_by_id(conn, user_ctx, row["id"])

    @staticmethod
    def update_assessment_draft(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                assessment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update draft assessment with optimistic concurrency check."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT id, status, version_number, facility_id, patient_id, encounter_id
            FROM modern_clinical_assessments
            WHERE id = ? AND organization_id = ?;
        """, (assessment_id, org_id))
        current = cursor.fetchone()
        if not current:
            raise NotFoundError(f"Modern clinical assessment '{assessment_id}' not found.")
        if current["status"] != "DRAFT":
            raise ConflictError(f"Cannot edit assessment with status '{current['status']}'. Only DRAFT can be modified.")

        # Optimistic concurrency check
        client_version = payload.get("version_number")
        if client_version is not None and client_version != current["version_number"]:
            raise ConflictError(
                f"Concurrency conflict: Assessment has been modified (current version {current['version_number']}, provided {client_version})."
            )

        new_version = current["version_number"] + 1
        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE modern_clinical_assessments
            SET chief_complaint = COALESCE(?, chief_complaint),
                history_of_present_illness = COALESCE(?, history_of_present_illness),
                past_medical_history = COALESCE(?, past_medical_history),
                surgical_history = COALESCE(?, surgical_history),
                family_history = COALESCE(?, family_history),
                personal_social_history = COALESCE(?, personal_social_history),
                medication_history = COALESCE(?, medication_history),
                allergies_review_status = COALESCE(?, allergies_review_status),
                review_of_systems_json = COALESCE(?, review_of_systems_json),
                physical_examination_json = COALESCE(?, physical_examination_json),
                working_assessment = COALESCE(?, working_assessment),
                clinical_rationale = COALESCE(?, clinical_rationale),
                uncertainty_level = COALESCE(?, uncertainty_level),
                ai_drafted_notes = COALESCE(?, ai_drafted_notes),
                ai_draft_status = COALESCE(?, ai_draft_status),
                version_number = ?,
                updated_at = ?
            WHERE id = ?;
        """, (
            payload.get("chief_complaint"),
            payload.get("history_of_present_illness"),
            payload.get("past_medical_history"),
            payload.get("surgical_history"),
            payload.get("family_history"),
            payload.get("personal_social_history"),
            payload.get("medication_history"),
            payload.get("allergies_review_status"),
            json.dumps(payload.get("review_of_systems")) if isinstance(payload.get("review_of_systems"), dict) else payload.get("review_of_systems_json"),
            json.dumps(payload.get("physical_examination")) if isinstance(payload.get("physical_examination"), dict) else payload.get("physical_examination_json"),
            payload.get("working_assessment"),
            payload.get("clinical_rationale"),
            payload.get("uncertainty_level"),
            payload.get("ai_drafted_notes"),
            payload.get("ai_draft_status"),
            new_version,
            now_dt,
            assessment_id
        ))

        # Update observations if provided
        if "observations" in payload:
            ModernAssessmentService._persist_observations(
                conn, user_ctx, assessment_id, current["patient_id"], current["encounter_id"], payload["observations"]
            )

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=current["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_MODERN_ASSESSMENT_DRAFT_UPDATED",
            resource_type="MODERN_CLINICAL_ASSESSMENT",
            resource_id=assessment_id,
            patient_id=current["patient_id"],
            encounter_id=current["encounter_id"],
            action_status="SUCCESS",
            description=f"Updated modern assessment draft to version {new_version}."
        )

        return ModernAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)

    @staticmethod
    def _persist_observations(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                              assessment_id: str, patient_id: str, encounter_id: str,
                              observations_list: List[Dict[str, Any]]) -> None:
        """Validate and persist observations with units, source, and reference ranges."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        for obs in observations_list:
            obs_type = obs.get("observation_type", "VITAL_SIGN")
            if obs_type not in VALID_OBSERVATION_TYPES:
                raise ValidationError(f"Invalid observation_type '{obs_type}'.")

            concept_name = obs.get("concept_name", "").strip()
            if not concept_name:
                raise ValidationError("Observation must have a non-empty concept_name.")

            val_num = obs.get("value_numeric")
            val_txt = obs.get("value_text")
            unit = obs.get("unit", "").strip()

            if val_num is None and not val_txt:
                raise ValidationError(f"Observation '{concept_name}' must have either value_numeric or value_text.")

            # Validate numeric bounds and determine interpretation using benchmark ranges
            name_key = concept_name.lower().replace(" ", "_")
            ref_low = obs.get("reference_range_low")
            ref_high = obs.get("reference_range_high")
            ref_prov = obs.get("reference_range_provenance")
            interpretation = "UNKNOWN"

            if name_key in STANDARD_VITAL_RANGES:
                std = STANDARD_VITAL_RANGES[name_key]
                if not unit:
                    unit = std["unit"]
                elif unit != std["unit"]:
                    raise ValidationError(f"Unit mismatch for '{concept_name}': expected '{std['unit']}', got '{unit}'.")

                if ref_low is None:
                    ref_low = std["low"]
                if ref_high is None:
                    ref_high = std["high"]
                if not ref_prov:
                    ref_prov = std["provenance"]

            if val_num is not None:
                val_float = float(val_num)
                # Bounds check
                if val_float < 0 and unit not in ("degC", "degF"):
                    raise ValidationError(f"Negative measurement value '{val_float}' is invalid for '{concept_name}'.")

                if ref_low is not None and ref_high is not None:
                    if val_float < ref_low:
                        interpretation = "ABNORMAL_LOW"
                    elif val_float > ref_high:
                        interpretation = "ABNORMAL_HIGH"
                    else:
                        interpretation = "NORMAL"
                else:
                    ref_prov = "UNAVAILABLE"
                    interpretation = "UNKNOWN"

            obs_id = obs.get("id") or f"obs-{uuid.uuid4().hex[:12]}"
            source_type = obs.get("source_type", "CLINICIAN_ENTERED")
            if source_type not in VALID_SOURCE_TYPES:
                raise ValidationError(f"Invalid source_type '{source_type}'.")

            cursor.execute("""
                INSERT OR REPLACE INTO clinical_observations (
                    id, organization_id, patient_id, encounter_id, assessment_id,
                    observation_type, concept_code, concept_name, value_numeric, value_text,
                    unit, reference_range_low, reference_range_high, reference_range_provenance,
                    interpretation, source_type, source_provenance, measured_at, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                obs_id, org_id, patient_id, encounter_id, assessment_id,
                obs_type, obs.get("concept_code"), concept_name,
                val_num, val_txt, unit, ref_low, ref_high, ref_prov,
                interpretation, source_type, obs.get("source_provenance"),
                obs.get("measured_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                user_ctx["user_id"]
            ))

    @staticmethod
    def run_safety_checks(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                          assessment_id: str) -> Dict[str, Any]:
        """Run deterministic red-flag rules against the assessment and persist detected alerts."""
        assessment = ModernAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)
        eval_result = ClinicalRulesEngine.evaluate_red_flags(conn, assessment, assessment["observations"])

        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        # Persist triggered alerts
        persisted_alerts = []
        for alert in eval_result.get("triggered_alerts", []):
            alert_id = f"rfe-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO red_flag_events (
                    id, organization_id, assessment_id, encounter_id, patient_id,
                    rule_id, rule_version, severity, trigger_facts_json,
                    plain_language_reason, recommended_action, is_acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
            """, (
                alert_id, org_id, assessment_id, assessment["encounter_id"], assessment["patient_id"],
                alert["rule_db_id"], alert["rule_version"], alert["severity"],
                json.dumps(alert["trigger_facts"]), alert["plain_language_reason"], alert["recommended_action"]
            ))
            alert["id"] = alert_id
            alert["is_acknowledged"] = 0
            persisted_alerts.append(alert)

        eval_result["persisted_alerts"] = persisted_alerts

        # Also evaluate investigation considerations based on safety findings
        investigations = ClinicalRulesEngine.evaluate_investigation_considerations(
            conn, assessment, assessment["observations"], eval_result.get("triggered_alerts", [])
        )
        for inv in investigations:
            cursor.execute("""
                INSERT OR IGNORE INTO investigation_considerations (
                    id, assessment_id, clinical_question, suggested_investigation,
                    modality, rationale, guideline_source, rule_id, rule_version,
                    limitations, clinician_decision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING');
            """, (
                f"inv-{uuid.uuid4().hex[:12]}", assessment_id, inv["clinical_question"],
                inv["suggested_investigation"], inv["modality"], inv["rationale"],
                inv["guideline_source"], inv["rule_db_id"], inv["rule_version"],
                inv["limitations"]
            ))

        return eval_result

    @staticmethod
    def acknowledge_red_flag(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                             alert_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Acknowledge or document clinical action for a triggered red flag."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        action_taken = payload.get("clinician_action_taken")
        override_rationale = payload.get("override_rationale")
        if not action_taken and not override_rationale:
            raise ValidationError("Acknowledging a red flag requires documenting either clinician_action_taken or override_rationale.")

        cursor.execute("""
            SELECT id, assessment_id, severity, rule_version
            FROM red_flag_events
            WHERE id = ? AND organization_id = ?;
        """, (alert_id, org_id))
        alert = cursor.fetchone()
        if not alert:
            raise NotFoundError(f"Red flag alert '{alert_id}' not found.")

        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE red_flag_events
            SET is_acknowledged = 1,
                acknowledged_by = ?,
                acknowledged_at = ?,
                clinician_action_taken = ?,
                override_rationale = ?
            WHERE id = ?;
        """, (user_ctx["user_id"], now_dt, action_taken, override_rationale, alert_id))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=user_ctx.get("facility_id", "fac-central-opd"),
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_RED_FLAG_ACKNOWLEDGED",
            resource_type="RED_FLAG_EVENT",
            resource_id=alert_id,
            action_status="SUCCESS",
            description=f"Clinician acknowledged {alert['severity']} alert with action: {action_taken or override_rationale}."
        )

        return {"acknowledged": True, "alert_id": alert_id, "acknowledged_at": now_dt}

    @staticmethod
    def run_differential_support(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                 assessment_id: str) -> Dict[str, Any]:
        """Generate differential considerations and persist candidate records awaiting clinician review."""
        assessment = ModernAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)
        diff_result = ClinicalRulesEngine.evaluate_differential_candidates(
            conn, assessment, assessment["observations"]
        )

        if diff_result.get("status") == "CONTENT_UNAVAILABLE":
            return diff_result

        cursor = conn.cursor()
        persisted_candidates = []

        for cand in diff_result.get("candidates", []):
            cand_id = f"dfc-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO differential_candidates (
                    id, assessment_id, candidate_label, candidate_code, code_system,
                    surfaced_by_type, rule_id, rule_version, evidence_status, rationale,
                    supporting_findings_json, contradicting_findings_json, missing_information_json,
                    source_references_json, limitations, review_required, clinician_decision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'PENDING_REVIEW');
            """, (
                cand_id, assessment_id, cand["candidate_label"], cand.get("candidate_code"),
                cand.get("code_system", "ICD-10-MOCK"), cand["surfaced_by_type"],
                cand["rule_db_id"], cand["rule_version"], cand["evidence_status"], cand["rationale"],
                json.dumps(cand["supporting_findings"]), json.dumps(cand["contradicting_findings"]),
                json.dumps(cand["missing_information"]), json.dumps(cand["source_references"]),
                cand["limitations"]
            ))
            cand["id"] = cand_id
            cand["clinician_decision"] = "PENDING_REVIEW"
            persisted_candidates.append(cand)

        diff_result["candidates"] = persisted_candidates
        return diff_result

    @staticmethod
    def decide_differential_candidate(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                      candidate_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Clinician reviews a differential consideration: ACCEPT, REJECT, DEFER, or CONFIRM_AS_PROBLEM."""
        cursor = conn.cursor()
        decision = payload.get("decision")
        if decision not in ("ACCEPTED", "REJECTED", "DEFERRED", "CONFIRMED_AS_PROBLEM"):
            raise ValidationError(f"Invalid decision '{decision}'. Must be ACCEPTED, REJECTED, DEFERRED, or CONFIRMED_AS_PROBLEM.")

        cursor.execute("""
            SELECT d.*, a.organization_id, a.patient_id, a.encounter_id
            FROM differential_candidates d
            JOIN modern_clinical_assessments a ON d.assessment_id = a.id
            WHERE d.id = ? AND a.organization_id = ?;
        """, (candidate_id, user_ctx["organization_id"]))
        cand = cursor.fetchone()
        if not cand:
            raise NotFoundError(f"Differential candidate '{candidate_id}' not found.")

        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE differential_candidates
            SET clinician_decision = ?,
                clinician_rationale = ?,
                decided_by = ?,
                decided_at = ?
            WHERE id = ?;
        """, (decision, payload.get("rationale"), user_ctx["user_id"], now_dt, candidate_id))

        problem_id = None
        if decision == "CONFIRMED_AS_PROBLEM":
            # Add to problem list as clinician confirmed
            problem_id = f"prb-{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO clinical_problems (
                    id, organization_id, patient_id, encounter_id, assessment_id,
                    problem_title, code_system, code_value, coding_status,
                    status, is_primary, clinical_notes, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED_CODED', 'CONFIRMED', ?, ?, ?);
            """, (
                problem_id, cand["organization_id"], cand["patient_id"], cand["encounter_id"],
                cand["assessment_id"], cand["candidate_label"], cand["code_system"], cand["candidate_code"],
                1 if payload.get("is_primary") else 0,
                f"Confirmed by clinician from differential consideration. {payload.get('rationale') or ''}".strip(),
                user_ctx["user_id"]
            ))

        return {
            "candidate_id": candidate_id,
            "decision": decision,
            "confirmed_problem_id": problem_id,
            "decided_at": now_dt
        }

    @staticmethod
    def add_clinical_problem(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                             assessment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Manually author or update a clinical problem on the assessment problem list."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT id, patient_id, encounter_id
            FROM modern_clinical_assessments
            WHERE id = ? AND organization_id = ?;
        """, (assessment_id, org_id))
        assess = cursor.fetchone()
        if not assess:
            raise NotFoundError(f"Modern clinical assessment '{assessment_id}' not found.")

        problem_title = payload.get("problem_title", "").strip()
        if not problem_title:
            raise ValidationError("Clinical problem requires a non-empty problem_title.")

        status = payload.get("status", "PROVISIONAL")
        if status not in VALID_PROBLEM_STATUSES:
            raise ValidationError(f"Invalid problem status '{status}'. Must be one of {sorted(VALID_PROBLEM_STATUSES)}.")

        problem_id = f"prb-{uuid.uuid4().hex[:12]}"
        cursor.execute("""
            INSERT INTO clinical_problems (
                id, organization_id, patient_id, encounter_id, assessment_id,
                problem_title, code_system, code_value, coding_status,
                status, onset_date, is_primary, clinical_notes, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            problem_id, org_id, assess["patient_id"], assess["encounter_id"], assessment_id,
            problem_title, payload.get("code_system", "UNCODED"), payload.get("code_value"),
            "CONFIRMED_CODED" if payload.get("code_value") else "UNCODED",
            status, payload.get("onset_date"), 1 if payload.get("is_primary") else 0,
            payload.get("clinical_notes"), user_ctx["user_id"]
        ))

        return {
            "id": problem_id,
            "assessment_id": assessment_id,
            "problem_title": problem_title,
            "status": status
        }

    @staticmethod
    def decide_investigation_consideration(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                                           consideration_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Record clinician decision on an investigation consideration (ORDER_PLANNED, DEFERRED, NOT_INDICATED)."""
        cursor = conn.cursor()
        decision = payload.get("decision")
        if decision not in ("ORDER_PLANNED", "DEFERRED", "NOT_INDICATED", "PENDING"):
            raise ValidationError(f"Invalid decision '{decision}'.")

        cursor.execute("""
            SELECT id FROM investigation_considerations WHERE id = ?;
        """, (consideration_id,))
        if not cursor.fetchone():
            raise NotFoundError(f"Investigation consideration '{consideration_id}' not found.")

        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE investigation_considerations
            SET clinician_decision = ?,
                clinician_notes = ?,
                decided_by = ?,
                decided_at = ?
            WHERE id = ?;
        """, (decision, payload.get("notes"), user_ctx["user_id"], now_dt, consideration_id))

        return {"consideration_id": consideration_id, "decision": decision, "decided_at": now_dt}

    @staticmethod
    def create_referral_record(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                               assessment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Document clinical referral / escalation plan."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        cursor.execute("""
            SELECT id, facility_id, patient_id, encounter_id
            FROM modern_clinical_assessments
            WHERE id = ? AND organization_id = ?;
        """, (assessment_id, org_id))
        assess = cursor.fetchone()
        if not assess:
            raise NotFoundError(f"Modern clinical assessment '{assessment_id}' not found.")

        reason = payload.get("reason_for_referral", "").strip()
        specialty = payload.get("target_specialty", "").strip()
        handover = payload.get("handover_summary", "").strip()

        if not reason or not specialty or not handover:
            raise ValidationError("Referral requires reason_for_referral, target_specialty, and handover_summary.")

        urgency = payload.get("urgency", "ROUTINE")
        if urgency not in VALID_REFERRAL_URGENCIES:
            raise ValidationError(f"Invalid urgency '{urgency}'. Must be one of {sorted(VALID_REFERRAL_URGENCIES)}.")

        informed_status = payload.get("patient_informed_status", "INFORMED_AGREED")
        if informed_status not in VALID_REFERRAL_INFORMED:
            raise ValidationError(f"Invalid patient_informed_status '{informed_status}'.")

        ref_id = f"ref-{uuid.uuid4().hex[:12]}"
        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO referral_records (
                id, organization_id, facility_id, patient_id, encounter_id, assessment_id,
                reason_for_referral, target_specialty, destination_facility, urgency,
                handover_summary, patient_informed_status, patient_informed_notes,
                actual_status, author_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DOCUMENTED', ?, ?, ?);
        """, (
            ref_id, org_id, assess["facility_id"], assess["patient_id"], assess["encounter_id"], assessment_id,
            reason, specialty, payload.get("destination_facility"), urgency,
            handover, informed_status, payload.get("patient_informed_notes"),
            user_ctx["user_id"], now_dt, now_dt
        ))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=assess["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_REFERRAL_DOCUMENTED",
            resource_type="REFERRAL_RECORD",
            resource_id=ref_id,
            patient_id=assess["patient_id"],
            encounter_id=assess["encounter_id"],
            action_status="SUCCESS",
            description=f"Documented {urgency} referral to {specialty}."
        )

        return {
            "id": ref_id,
            "assessment_id": assessment_id,
            "urgency": urgency,
            "target_specialty": specialty,
            "actual_status": "DOCUMENTED"
        }

    @staticmethod
    def sign_assessment(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                        assessment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sign and lock modern clinical assessment with clinician credentials and SHA-256 fingerprint."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        # Permission check
        roles = user_ctx.get("roles", [])
        if "PRACTITIONER" not in roles and "ORG_ADMIN" not in roles and "CLINIC_ADMIN" not in roles:
            raise ForbiddenError("Only licensed practitioners or administrators may sign clinical assessments.")

        cursor.execute("""
            SELECT id, status, version_number, facility_id, patient_id, encounter_id, chief_complaint
            FROM modern_clinical_assessments
            WHERE id = ? AND organization_id = ?;
        """, (assessment_id, org_id))
        assess = cursor.fetchone()
        if not assess:
            raise NotFoundError(f"Modern clinical assessment '{assessment_id}' not found.")
        if assess["status"] != "DRAFT":
            raise ConflictError(f"Cannot sign assessment with status '{assess['status']}'. Already signed or amended.")

        # Re-authenticate PIN if supplied
        pin = payload.get("pin")
        if pin:
            cursor.execute("""
                SELECT digital_signature_pin_hash
                FROM practitioner_profiles
                WHERE user_id = ?;
            """, (user_ctx["user_id"],))
            prof = cursor.fetchone()
            if not prof or not prof["digital_signature_pin_hash"] or not verify_pin(pin, prof["digital_signature_pin_hash"]):
                raise ForbiddenError("Invalid clinician signature PIN.")

        # Fail-closed check: verify all EMERGENT / URGENT red flags have been acknowledged
        cursor.execute("""
            SELECT id, severity, plain_language_reason
            FROM red_flag_events
            WHERE assessment_id = ? AND is_acknowledged = 0 AND severity IN ('EMERGENT', 'URGENT');
        """, (assessment_id,))
        unacknowledged = cursor.fetchall()
        if unacknowledged and not payload.get("force_override"):
            unack_list = [f"[{r['severity']}] {r['plain_language_reason']}" for r in unacknowledged]
            raise ConflictError(
                f"Cannot sign assessment with unacknowledged critical red flags: {'; '.join(unack_list)}. "
                "Clinician must acknowledge alerts and document clinical action before sign-off."
            )

        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        full_data = ModernAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)
        snapshot_str = json.dumps(full_data, sort_keys=True, default=str)
        snapshot_hash = hashlib.sha256(snapshot_str.encode("utf-8")).hexdigest()

        cursor.execute("""
            UPDATE modern_clinical_assessments
            SET status = 'SIGNED',
                signed_at = ?,
                signed_by = ?,
                signature_hash = ?,
                signed_snapshot = ?,
                updated_at = ?
            WHERE id = ?;
        """, (now_dt, user_ctx["user_id"], snapshot_hash, snapshot_str, now_dt, assessment_id))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=assess["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=roles[0] if roles else "PRACTITIONER",
            event_type="CLINICAL_MODERN_ASSESSMENT_SIGNED",
            resource_type="MODERN_CLINICAL_ASSESSMENT",
            resource_id=assessment_id,
            patient_id=assess["patient_id"],
            encounter_id=assess["encounter_id"],
            action_status="SUCCESS",
            description=f"Clinician signed modern clinical assessment with digest {snapshot_hash[:16]}..."
        )

        return ModernAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)

    @staticmethod
    def amend_assessment(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                         assessment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create governed versioned amendment of a signed assessment without rewriting history."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        reason = payload.get("amendment_reason", "").strip()
        if not reason:
            raise ValidationError("Amending a signed clinical assessment requires a documented amendment_reason.")

        cursor.execute("""
            SELECT * FROM modern_clinical_assessments
            WHERE id = ? AND organization_id = ?;
        """, (assessment_id, org_id))
        prior = cursor.fetchone()
        if not prior:
            raise NotFoundError(f"Assessment '{assessment_id}' not found.")
        if prior["status"] not in ("SIGNED", "AMENDED"):
            raise ConflictError(f"Cannot amend assessment with status '{prior['status']}'. Only SIGNED records can be amended.")

        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Record amendment history row
        amend_id = f"amd-{uuid.uuid4().hex[:12]}"
        cursor.execute("""
            INSERT INTO clinical_assessment_amendments (
                id, assessment_id, prior_version_number, amendment_reason,
                amendment_notes, prior_snapshot, prior_snapshot_hash, amended_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            amend_id, assessment_id, prior["version_number"], reason,
            payload.get("amendment_notes"), prior["signed_snapshot"] or "{}",
            prior["signature_hash"] or "UNKNOWN", user_ctx["user_id"], now_dt
        ))

        new_version = prior["version_number"] + 1

        # Apply updates to editable narrative fields
        cursor.execute("""
            UPDATE modern_clinical_assessments
            SET status = 'AMENDED',
                working_assessment = COALESCE(?, working_assessment),
                clinical_rationale = COALESCE(?, clinical_rationale),
                uncertainty_level = COALESCE(?, uncertainty_level),
                version_number = ?,
                updated_at = ?
            WHERE id = ?;
        """, (
            payload.get("working_assessment"),
            payload.get("clinical_rationale"),
            payload.get("uncertainty_level"),
            new_version,
            now_dt,
            assessment_id
        ))

        # Recompute signed snapshot
        updated_data = ModernAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)
        new_snap_str = json.dumps(updated_data, sort_keys=True, default=str)
        new_hash = hashlib.sha256(new_snap_str.encode("utf-8")).hexdigest()

        cursor.execute("""
            UPDATE modern_clinical_assessments
            SET signed_snapshot = ?,
                signature_hash = ?
            WHERE id = ?;
        """, (new_snap_str, new_hash, assessment_id))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=prior["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_MODERN_ASSESSMENT_AMENDED",
            resource_type="MODERN_CLINICAL_ASSESSMENT",
            resource_id=assessment_id,
            patient_id=prior["patient_id"],
            encounter_id=prior["encounter_id"],
            action_status="SUCCESS",
            description=f"Amended assessment to v{new_version}. Reason: {reason}."
        )

        return ModernAssessmentService.get_assessment_by_id(conn, user_ctx, assessment_id)

    @staticmethod
    def cancel_assessment(conn: sqlite3.Connection, user_ctx: Dict[str, Any],
                          assessment_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel assessment draft with clinical rationale."""
        cursor = conn.cursor()
        org_id = user_ctx["organization_id"]

        reason = payload.get("cancellation_reason", "").strip()
        if not reason:
            raise ValidationError("Cancelling assessment requires a documented cancellation_reason.")

        cursor.execute("""
            SELECT id, status, facility_id, patient_id, encounter_id
            FROM modern_clinical_assessments
            WHERE id = ? AND organization_id = ?;
        """, (assessment_id, org_id))
        assess = cursor.fetchone()
        if not assess:
            raise NotFoundError(f"Assessment '{assessment_id}' not found.")
        if assess["status"] == "CANCELLED":
            raise ConflictError("Assessment is already cancelled.")

        now_dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE modern_clinical_assessments
            SET status = 'CANCELLED',
                cancellation_reason = ?,
                updated_at = ?
            WHERE id = ?;
        """, (reason, now_dt, assessment_id))

        log_audit_event(
            conn=conn,
            organization_id=org_id,
            facility_id=assess["facility_id"],
            actor_user_id=user_ctx["user_id"],
            actor_role=user_ctx.get("roles", ["PRACTITIONER"])[0],
            event_type="CLINICAL_MODERN_ASSESSMENT_CANCELLED",
            resource_type="MODERN_CLINICAL_ASSESSMENT",
            resource_id=assessment_id,
            patient_id=assess["patient_id"],
            encounter_id=assess["encounter_id"],
            action_status="SUCCESS",
            description=f"Cancelled assessment. Reason: {reason}."
        )

        return {"cancelled": True, "assessment_id": assessment_id, "cancellation_reason": reason}
