"""
Post-Pilot Evaluation, Adoption Scorecard & Scale Decision Domain Engine
ZAYVORA MATAB OS — Independent Standalone Product
"""

import os
import json
import uuid
import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.audit import log_audit_event


class EvaluationStateError(Exception):
    """Raised when an operation is invalid for current evaluation state."""
    pass


class ExpansionGateBlockedError(Exception):
    """Raised when expansion is blocked by unresolved safety or gate failures."""
    def __init__(self, blockers: List[str]):
        self.blockers = blockers
        super().__init__(f"Expansion proposal blocked: {'; '.join(blockers)}")


class RetestEvidenceMissingError(Exception):
    """Raised when attempting to close an action without mandatory retest evidence."""
    pass


# Default Core Pre-Agreed Metric Specifications
DEFAULT_METRIC_DEFINITIONS = [
    # A. Workflow Usability
    {
        "code": "MET-USAB-01",
        "name": "Encounter Workflow Completion Rate",
        "domain_category": "WORKFLOW_USABILITY",
        "definition": "Percentage of initiated clinical encounters completed through finalization or signing",
        "numerator_definition": "Encounters transitioned to COMPLETED or SIGNED",
        "denominator_definition": "Total clinical encounters created (excluding test/training records)",
        "data_source": "encounters table",
        "calculation_method": "(completed_encounters / total_encounters) * 100",
        "exclusions": "Status CANCELLED within 60s, dry-run synthetic migrations",
        "baseline_target": "85.0%",
        "threshold_target": "90.0%",
        "version": "1.0",
        "owner_role": "PRODUCT_OPERATIONS"
    },
    {
        "code": "MET-USAB-02",
        "name": "Consultation Duration Benchmark",
        "domain_category": "WORKFLOW_USABILITY",
        "definition": "Average duration in minutes from consultation start to signature completion",
        "numerator_definition": "Sum of consultation elapsed minutes across signed consultations",
        "denominator_definition": "Count of completed signed consultations",
        "data_source": "consultation_workspace_sessions / encounters",
        "calculation_method": "total_duration_minutes / count_signed_consultations",
        "exclusions": "Consultations left open overnight or paused > 2 hours",
        "baseline_target": "12.0 mins",
        "threshold_target": "15.0 mins max",
        "version": "1.0",
        "owner_role": "PRODUCT_OPERATIONS"
    },
    # B. Reliability
    {
        "code": "MET-REL-01",
        "name": "Encounter Save Success Rate",
        "domain_category": "RELIABILITY",
        "definition": "Ratio of successful clinical save transactions to total save attempts",
        "numerator_definition": "Encounter save attempts committed without SQL rollback",
        "denominator_definition": "Total save API invocations",
        "data_source": "audit_logs (ENCOUNTER_SAVED vs ENCOUNTER_SAVE_FAILED)",
        "calculation_method": "(successful_saves / total_save_attempts) * 100",
        "exclusions": "Client network dropouts before reaching gateway",
        "baseline_target": "99.0%",
        "threshold_target": "99.9%",
        "version": "1.0",
        "owner_role": "SECURITY_PRIVACY"
    },
    {
        "code": "MET-REL-02",
        "name": "Prescription Document Generation Success",
        "domain_category": "RELIABILITY",
        "definition": "Percentage of signed prescriptions with valid immutable hash and non-empty document",
        "numerator_definition": "Signed prescriptions with verified sha256_hash and valid document payload",
        "denominator_definition": "Total signed prescriptions",
        "data_source": "prescriptions table",
        "calculation_method": "(valid_prescriptions / signed_prescriptions) * 100",
        "exclusions": "Drafts aborted before signature PIN prompt",
        "baseline_target": "99.5%",
        "threshold_target": "100.0%",
        "version": "1.0",
        "owner_role": "PRODUCT_OPERATIONS"
    },
    # C. Clinical Workflow Integrity
    {
        "code": "MET-CLIN-01",
        "name": "Authorized Clinician PIN Signing Rate",
        "domain_category": "CLINICAL_INTEGRITY",
        "definition": "Proportion of finalized clinical orders signed via human clinician PIN with audit trail",
        "numerator_definition": "Prescriptions with non-null signed_by_user_id and audit signature event",
        "denominator_definition": "Total finalized prescriptions",
        "data_source": "prescriptions & audit_logs",
        "calculation_method": "(signed_orders / finalized_orders) * 100",
        "exclusions": "None",
        "baseline_target": "100.0%",
        "threshold_target": "100.0%",
        "version": "1.0",
        "owner_role": "CLINICAL_GOVERNANCE"
    },
    {
        "code": "MET-CLIN-02",
        "name": "Patient-Encounter Linkage Integrity",
        "domain_category": "CLINICAL_INTEGRITY",
        "definition": "Rate of encounter and clinical document records strictly verified against patient MRN",
        "numerator_definition": "Encounters with valid active foreign key to patients table",
        "denominator_definition": "Total encounters registered",
        "data_source": "encounters and patients tables",
        "calculation_method": "(linked_records / total_records) * 100",
        "exclusions": "None",
        "baseline_target": "100.0%",
        "threshold_target": "100.0%",
        "version": "1.0",
        "owner_role": "CLINICAL_GOVERNANCE"
    },
    # D. Safety and Governance
    {
        "code": "MET-SAFE-01",
        "name": "Schedule E(1) Mudabbar Compliance Rate",
        "domain_category": "SAFETY_GOVERNANCE",
        "definition": "Rate of Schedule E(1) toxic herbs flagged with mandatory detox verification",
        "numerator_definition": "Toxic herb orders requiring and passing Mudabbar detoxification check",
        "denominator_definition": "Total toxic herb orders evaluated in preflight",
        "data_source": "clinical_safety_incident_queue / safety_preflight",
        "calculation_method": "(verified_mudabbar_items / total_schedule_e1_items) * 100",
        "exclusions": "Non-toxic herbal teas and dietary items",
        "baseline_target": "100.0%",
        "threshold_target": "100.0%",
        "version": "1.0",
        "owner_role": "CLINICAL_GOVERNANCE"
    },
    {
        "code": "MET-SAFE-02",
        "name": "Unresolved Safety Findings Count",
        "domain_category": "SAFETY_GOVERNANCE",
        "definition": "Number of open or unresolved clinical safety incidents pending review",
        "numerator_definition": "Count of items in clinical_safety_incident_queue with status PENDING_REVIEW",
        "denominator_definition": "N/A (discrete count)",
        "data_source": "clinical_safety_incident_queue",
        "calculation_method": "count_pending_safety_incidents",
        "exclusions": "Resolved or dismissed incidents",
        "baseline_target": "0",
        "threshold_target": "0",
        "version": "1.0",
        "owner_role": "CLINICAL_GOVERNANCE"
    },
    # E. Training and Adoption
    {
        "code": "MET-ADOPT-01",
        "name": "Staff Training Curriculum Pass Rate",
        "domain_category": "TRAINING_ADOPTION",
        "definition": "Percentage of enrolled clinic staff who achieved required passing exam score (>=80%)",
        "numerator_definition": "Enrollments with status PASSED and score >= 80",
        "denominator_definition": "Total staff training enrollments",
        "data_source": "staff_training_enrollments",
        "calculation_method": "(passed_enrollments / total_enrollments) * 100",
        "exclusions": "Exempt guest observers",
        "baseline_target": "90.0%",
        "threshold_target": "100.0%",
        "version": "1.0",
        "owner_role": "PRODUCT_OPERATIONS"
    },
    {
        "code": "MET-ADOPT-02",
        "name": "Onboarding Stage Completion Rate",
        "domain_category": "TRAINING_ADOPTION",
        "definition": "Percentage of 13-stage facility onboarding checklist items marked COMPLETED with evidence",
        "numerator_definition": "Checklist stages with status COMPLETED and evidence_notes",
        "denominator_definition": "Total 13 checklist stages per facility",
        "data_source": "facility_onboarding_checklists",
        "calculation_method": "(completed_stages / 13) * 100",
        "exclusions": "Formally waived stages with written justification",
        "baseline_target": "92.0%",
        "threshold_target": "100.0%",
        "version": "1.0",
        "owner_role": "PRODUCT_OPERATIONS"
    },
    # F. Support and Operations
    {
        "code": "MET-SUPP-01",
        "name": "Open P0 / P1 Support Ticket Count",
        "domain_category": "SUPPORT_OPERATIONS",
        "definition": "Total count of unresolved critical (SEV_1_CRITICAL) or high (SEV_2_HIGH) support tickets",
        "numerator_definition": "Active tickets with severity in (SEV_1_CRITICAL, SEV_2_HIGH) and status != CLOSED",
        "denominator_definition": "N/A (discrete count)",
        "data_source": "pilot_support_tickets",
        "calculation_method": "count_open_p0_p1_tickets",
        "exclusions": "Tickets resolved and awaiting user sign-off",
        "baseline_target": "0",
        "threshold_target": "0",
        "version": "1.0",
        "owner_role": "PRODUCT_OPERATIONS"
    },
    {
        "code": "MET-SUPP-02",
        "name": "Zero-Downtime Backup Exercise Verification",
        "domain_category": "SUPPORT_OPERATIONS",
        "definition": "Evidence of successful hot database VACUUM INTO drill within review window",
        "numerator_definition": "Verified backup drills executed",
        "denominator_definition": "1 (mandatory drill)",
        "data_source": "evidence_inventory_items (category BACKUP_RESTORE_EXERCISE)",
        "calculation_method": "boolean verification (1 or 0)",
        "exclusions": "None",
        "baseline_target": "1",
        "threshold_target": "1",
        "version": "1.0",
        "owner_role": "SECURITY_PRIVACY"
    },
    # G. Communications / Integrations (Enabled only)
    {
        "code": "MET-INT-01",
        "name": "ABDM & FHIR Contract Test Harness Pass Rate",
        "domain_category": "COMMUNICATIONS_INTEGRATIONS",
        "definition": "Contractual schema validity rate for generated FHIR R4 bundles and ABDM request harnesses",
        "numerator_definition": "Valid FHIR bundles passing structural schema validation without error",
        "denominator_definition": "Total exported FHIR bundles during review window",
        "data_source": "interop_export_logs / unit test reports",
        "calculation_method": "(valid_bundles / total_bundles) * 100",
        "exclusions": "Simulated malformed payload tests",
        "baseline_target": "100.0%",
        "threshold_target": "100.0%",
        "version": "1.0",
        "owner_role": "SECURITY_PRIVACY"
    },
    # H. Clinical Outcomes (Descriptive Monitoring Only)
    {
        "code": "MET-OUT-01",
        "name": "Descriptive Symptom Follow-up Recording Completeness",
        "domain_category": "CLINICAL_OUTCOMES",
        "definition": "Completeness of follow-up outcome recordings (Descriptive monitoring only; does not infer clinical efficacy)",
        "numerator_definition": "Follow-up tasks completed with recorded outcome or symptom score",
        "denominator_definition": "Total scheduled follow-up tasks due in window",
        "data_source": "follow_up_plans / patient_communications",
        "calculation_method": "(completed_followups / total_due_followups) * 100",
        "exclusions": "Patients who explicitly opted out of follow-up communication",
        "baseline_target": "60.0%",
        "threshold_target": "75.0%",
        "version": "1.0",
        "owner_role": "CLINICAL_GOVERNANCE"
    }
]


class PostPilotEvaluationEngine:
    """Core domain orchestrator for Post-Pilot Evaluation, Adoption Scorecard & Scale Decision."""

    def __init__(self, db_path: Optional[str] = None):
        self.manager = DatabaseConnection(db_path)
        self._ensure_default_metric_definitions()

    def _ensure_default_metric_definitions(self) -> None:
        """Seed default pre-agreed metric definitions if not present."""
        conn = self.manager.get_connection()
        try:
            for met in DEFAULT_METRIC_DEFINITIONS:
                met_id = f"mdef-{met['code'].lower().replace('_', '-')}"
                conn.execute("""
                    INSERT OR IGNORE INTO metric_definitions (
                        id, code, name, domain_category, definition, numerator_definition,
                        denominator_definition, data_source, calculation_method, exclusions,
                        baseline_target, threshold_target, version, owner_role
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    met_id, met["code"], met["name"], met["domain_category"], met["definition"],
                    met["numerator_definition"], met["denominator_definition"], met["data_source"],
                    met["calculation_method"], met["exclusions"], met["baseline_target"],
                    met["threshold_target"], met["version"], met["owner_role"]
                ))
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # 1. Pilot Evaluation Lifecycle
    # =========================================================================

    def create_evaluation(
        self,
        pilot_program_id: str,
        organization_id: str,
        evaluation_title: str,
        build_commit: str,
        review_period_start: str,
        review_period_end: str,
        facility_id: Optional[str] = None,
        scope_version_id: Optional[str] = None,
        enabled_features: Optional[List[str]] = None,
        disabled_features: Optional[List[str]] = None,
        roles_covered: Optional[List[str]] = None,
        integrations_covered: Optional[List[str]] = None,
        success_criteria: Optional[Dict[str, Any]] = None,
        targets: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new versioned evaluation record with PRE-AGREED targets."""
        conn = self.manager.get_connection()
        eval_id = f"eval-{uuid.uuid4().hex[:12]}"

        # Look up active scope if not specified
        if not scope_version_id:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM pilot_scope_versions
                WHERE pilot_program_id = ? AND status = 'ACTIVE'
                ORDER BY version_number DESC LIMIT 1;
            """, (pilot_program_id,))
            row = cursor.fetchone()
            if row:
                scope_version_id = row["id"]

        try:
            conn.execute("""
                INSERT INTO pilot_evaluations (
                    id, pilot_program_id, scope_version_id, organization_id, facility_id,
                    evaluation_title, build_commit, review_period_start, review_period_end,
                    status, enabled_features_json, disabled_features_json, roles_covered_json,
                    integrations_covered_json, success_criteria_json, targets_json, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'EVIDENCE_COLLECTION', ?, ?, ?, ?, ?, ?, ?);
            """, (
                eval_id, pilot_program_id, scope_version_id, organization_id, facility_id,
                evaluation_title, build_commit, review_period_start, review_period_end,
                json.dumps(enabled_features or ["OPD_CONSULTATION", "PRESCRIPTION_ENGINE", "UNANI_ASSESSMENT"]),
                json.dumps(disabled_features or ["EXTERNAL_LIVE_ABDM", "DIRECT_SMS_GATEWAY"]),
                json.dumps(roles_covered or ["TABIB", "RECEPTIONIST", "DISPENSER", "ORG_ADMIN"]),
                json.dumps(integrations_covered or ["FHIR_R4_HARNESS", "BARCODE_SCANNER"]),
                json.dumps(success_criteria or {"zero_p0_open": True, "zero_safety_bypass": True, "min_training_pass": 90}),
                json.dumps(targets or {"encounter_completion_rate": "90%", "save_success_rate": "99.9%"}),
                created_by
            ))
            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=created_by,
                action_type="PILOT_EVALUATION_CREATED",
                target_entity_type="PILOT_EVALUATION",
                target_entity_id=eval_id,
                organization_id=organization_id,
                details={"title": evaluation_title, "build": build_commit, "period": f"{review_period_start} to {review_period_end}"}
            )
            return self.get_evaluation(eval_id)
        finally:
            conn.close()

    def get_evaluation(self, evaluation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve evaluation master record with parsed JSON fields."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pilot_evaluations WHERE id = ?;", (evaluation_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            for k in ["enabled_features_json", "disabled_features_json", "roles_covered_json",
                      "integrations_covered_json", "success_criteria_json", "targets_json"]:
                if res.get(k):
                    try:
                        res[k.replace("_json", "")] = json.loads(res[k])
                    except Exception:
                        res[k.replace("_json", "")] = res[k]
            return res
        finally:
            conn.close()

    def list_evaluations(self, pilot_program_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List evaluations filtered by program or organization."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM pilot_evaluations WHERE 1=1"
            params = []
            if pilot_program_id:
                query += " AND pilot_program_id = ?"
                params.append(pilot_program_id)
            if organization_id:
                query += " AND organization_id = ?"
                params.append(organization_id)
            query += " ORDER BY created_at DESC;"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                for k in ["enabled_features_json", "disabled_features_json", "roles_covered_json", "integrations_covered_json"]:
                    if item.get(k):
                        try:
                            item[k.replace("_json", "")] = json.loads(item[k])
                        except Exception:
                            item[k.replace("_json", "")] = item[k]
                results.append(item)
            return results
        finally:
            conn.close()

    def update_evaluation_status(
        self,
        evaluation_id: str,
        new_status: str,
        findings_summary: Optional[str] = None,
        limitations_summary: Optional[str] = None,
        primary_recommendation: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update evaluation lifecycle status and summaries."""
        valid_statuses = [
            "NOT_STARTED", "EVIDENCE_COLLECTION", "NOT_YET_ASSESSABLE",
            "ASSESSABLE_WITH_LIMITATIONS", "READY_FOR_DECISION",
            "DECISION_APPROVED", "REMEDIATION_REQUIRED"
        ]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid_statuses}")

        conn = self.manager.get_connection()
        try:
            updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            params = [new_status]

            if findings_summary is not None:
                updates.append("findings_summary = ?")
                params.append(findings_summary)
            if limitations_summary is not None:
                updates.append("limitations_summary = ?")
                params.append(limitations_summary)
            if primary_recommendation is not None:
                updates.append("primary_recommendation = ?")
                params.append(primary_recommendation)

            params.append(evaluation_id)
            conn.execute(f"UPDATE pilot_evaluations SET {', '.join(updates)} WHERE id = ?;", params)
            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=actor_id,
                action_type="PILOT_EVALUATION_STATUS_UPDATED",
                target_entity_type="PILOT_EVALUATION",
                target_entity_id=evaluation_id,
                details={"new_status": new_status, "recommendation": primary_recommendation}
            )
            return self.get_evaluation(evaluation_id)
        finally:
            conn.close()

    # =========================================================================
    # 2. Evidence Inventory
    # =========================================================================

    def register_evidence_item(
        self,
        evaluation_id: str,
        source_reference: str,
        category: str,
        owner: str,
        build_commit: str,
        extraction_method: str,
        completeness: str = "COMPLETE",
        access_restrictions: str = "INTERNAL_RESTRICTED",
        date_range_start: Optional[str] = None,
        date_range_end: Optional[str] = None,
        limitations: Optional[str] = None,
        verification_status: str = "VERIFIED",
        verified_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a verified evidence source item."""
        conn = self.manager.get_connection()
        item_id = f"evi-{uuid.uuid4().hex[:12]}"
        try:
            conn.execute("""
                INSERT INTO evidence_inventory_items (
                    id, evaluation_id, source_reference, category, owner, build_commit,
                    date_range_start, date_range_end, completeness, access_restrictions,
                    extraction_method, limitations, verification_status, verified_by, verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (
                item_id, evaluation_id, source_reference, category, owner, build_commit,
                date_range_start, date_range_end, completeness, access_restrictions,
                extraction_method, limitations, verification_status, verified_by
            ))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM evidence_inventory_items WHERE id = ?;", (item_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def list_evidence_items(self, evaluation_id: str) -> List[Dict[str, Any]]:
        """List all evidence items registered for an evaluation."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM evidence_inventory_items
                WHERE evaluation_id = ?
                ORDER BY created_at ASC;
            """, (evaluation_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # =========================================================================
    # 3. Metric Definitions & Scorecard Calculation
    # =========================================================================

    def list_metric_definitions(self, domain_category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List pre-agreed metric definitions."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            if domain_category:
                cursor.execute("SELECT * FROM metric_definitions WHERE domain_category = ? ORDER BY code ASC;", (domain_category,))
            else:
                cursor.execute("SELECT * FROM metric_definitions ORDER BY domain_category, code ASC;")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def record_metric_observation(
        self,
        evaluation_id: str,
        metric_definition_id: str,
        date_range_start: str,
        date_range_end: str,
        numerator_value: Optional[float] = None,
        denominator_value: Optional[float] = None,
        observed_value: Optional[float] = None,
        observed_formatted: Optional[str] = None,
        is_unavailable: bool = False,
        unavailable_reason: Optional[str] = None,
        target_met: Optional[bool] = None,
        limitations: Optional[str] = None,
        review_state: str = "UNREVIEWED",
        reviewer_notes: Optional[str] = None,
        reviewed_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record or update an observed metric result or explicit unavailable status."""
        conn = self.manager.get_connection()
        obs_id = f"obs-{uuid.uuid4().hex[:12]}"
        try:
            conn.execute("""
                INSERT INTO metric_observations (
                    id, evaluation_id, metric_definition_id, date_range_start, date_range_end,
                    numerator_value, denominator_value, observed_value, observed_formatted,
                    is_unavailable, unavailable_reason, target_met, limitations,
                    review_state, reviewer_notes, reviewed_by, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (
                obs_id, evaluation_id, metric_definition_id, date_range_start, date_range_end,
                numerator_value, denominator_value, observed_value, observed_formatted,
                1 if is_unavailable else 0, unavailable_reason,
                1 if target_met else (0 if target_met is False else None), limitations,
                review_state, reviewer_notes, reviewed_by
            ))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM metric_observations WHERE id = ?;", (obs_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def calculate_scorecard(self, evaluation_id: str) -> List[Dict[str, Any]]:
        """
        Derive reproducible metrics from actual persisted pilot data.
        If underlying telemetry or data source is absent, explicitly mark as UNAVAILABLE.
        Never invent metrics or assume 100% success on missing data.
        """
        eval_record = self.get_evaluation(evaluation_id)
        if not eval_record:
            raise ValueError(f"Evaluation '{evaluation_id}' not found")

        pilot_program_id = eval_record["pilot_program_id"]
        start_date = eval_record["review_period_start"]
        end_date = eval_record["review_period_end"]

        conn = self.manager.get_connection()
        scorecard = []

        try:
            definitions = self.list_metric_definitions()
            for mdef in definitions:
                code = mdef["code"]
                num_val = None
                den_val = None
                obs_val = None
                obs_fmt = None
                is_unavail = False
                unavail_reason = None
                target_met = None
                limitation = None

                cursor = conn.cursor()

                if code == "MET-USAB-01":
                    # Encounter Completion Rate
                    cursor.execute("""
                        SELECT count(*) as total,
                               sum(case when status in ('COMPLETED', 'SIGNED') then 1 else 0 end) as completed
                        FROM encounters
                        WHERE date(created_at) >= date(?) AND date(created_at) <= date(?);
                    """, (start_date, end_date))
                    row = cursor.fetchone()
                    total = row["total"] or 0
                    completed = row["completed"] or 0
                    if total > 0:
                        num_val = float(completed)
                        den_val = float(total)
                        obs_val = round((completed / total) * 100, 1)
                        obs_fmt = f"{obs_val}%"
                        target_met = obs_val >= 90.0
                    else:
                        is_unavail = True
                        unavail_reason = "No clinical encounters registered in specified review date range"

                elif code == "MET-REL-02":
                    # Prescription Document Generation
                    cursor.execute("""
                        SELECT count(*) as total,
                               sum(case when signature_hash is not null and length(signature_hash) = 64 then 1 else 0 end) as valid_hashed
                        FROM prescriptions
                        WHERE status = 'SIGNED' AND date(created_at) >= date(?) AND date(created_at) <= date(?);
                    """, (start_date, end_date))
                    row = cursor.fetchone()
                    total = row["total"] or 0
                    valid_cnt = row["valid_hashed"] or 0
                    if total > 0:
                        num_val = float(valid_cnt)
                        den_val = float(total)
                        obs_val = round((valid_cnt / total) * 100, 1)
                        obs_fmt = f"{obs_val}%"
                        target_met = obs_val >= 99.5
                    else:
                        is_unavail = True
                        unavail_reason = "No signed prescriptions created in specified review date range"

                elif code == "MET-CLIN-01":
                    # Authorized Clinician PIN Signing Rate
                    cursor.execute("""
                        SELECT count(*) as total,
                               sum(case when signed_by is not null then 1 else 0 end) as signed
                        FROM prescriptions
                        WHERE status in ('SIGNED', 'COMPLETED') AND date(created_at) >= date(?) AND date(created_at) <= date(?);
                    """, (start_date, end_date))
                    row = cursor.fetchone()
                    total = row["total"] or 0
                    signed = row["signed"] or 0
                    if total > 0:
                        num_val = float(signed)
                        den_val = float(total)
                        obs_val = round((signed / total) * 100, 1)
                        obs_fmt = f"{obs_val}%"
                        target_met = obs_val == 100.0
                    else:
                        is_unavail = True
                        unavail_reason = "No finalized prescriptions available for audit check"

                elif code == "MET-SAFE-02":
                    # Unresolved Safety Findings Count
                    cursor.execute("""
                        SELECT count(*) as pending
                        FROM clinical_safety_incident_queue
                        WHERE pilot_program_id = ? AND status = 'PENDING_REVIEW';
                    """, (pilot_program_id,))
                    row = cursor.fetchone()
                    pending = row["pending"] or 0
                    obs_val = float(pending)
                    obs_fmt = f"{pending} open"
                    target_met = (pending == 0)

                elif code == "MET-ADOPT-01":
                    # Staff Training Curriculum Pass Rate
                    cursor.execute("""
                        SELECT count(*) as total,
                               sum(case when status = 'PASSED' and score >= 80 then 1 else 0 end) as passed
                        FROM staff_training_enrollments
                        WHERE pilot_program_id = ?;
                    """, (pilot_program_id,))
                    row = cursor.fetchone()
                    total = row["total"] or 0
                    passed = row["passed"] or 0
                    if total > 0:
                        num_val = float(passed)
                        den_val = float(total)
                        obs_val = round((passed / total) * 100, 1)
                        obs_fmt = f"{obs_val}%"
                        target_met = obs_val >= 90.0
                    else:
                        is_unavail = True
                        unavail_reason = "No staff training enrollments found for pilot program"

                elif code == "MET-ADOPT-02":
                    # Onboarding Stage Completion Rate
                    cursor.execute("""
                        SELECT count(*) as total,
                               sum(case when status = 'COMPLETED' then 1 else 0 end) as completed
                        FROM facility_onboarding_checklists
                        WHERE pilot_program_id = ?;
                    """, (pilot_program_id,))
                    row = cursor.fetchone()
                    total = row["total"] or 0
                    completed = row["completed"] or 0
                    if total > 0:
                        num_val = float(completed)
                        den_val = float(total)
                        obs_val = round((completed / total) * 100, 1)
                        obs_fmt = f"{obs_val}%"
                        target_met = obs_val >= 92.0
                    else:
                        is_unavail = True
                        unavail_reason = "No facility onboarding checklist initialized"

                elif code == "MET-SUPP-01":
                    # Open P0 / P1 Support Ticket Count
                    cursor.execute("""
                        SELECT count(*) as open_cnt
                        FROM pilot_support_tickets
                        WHERE pilot_program_id = ? AND severity in ('SEV_1_CRITICAL', 'SEV_2_HIGH') AND status != 'CLOSED';
                    """, (pilot_program_id,))
                    row = cursor.fetchone()
                    open_cnt = row["open_cnt"] or 0
                    obs_val = float(open_cnt)
                    obs_fmt = f"{open_cnt} open"
                    target_met = (open_cnt == 0)

                elif code == "MET-OUT-01":
                    # Descriptive Outcomes Completeness
                    # Strictly marked as descriptive monitoring; no causal benefit inferred
                    cursor.execute("""
                        SELECT count(*) as total,
                               sum(case when lower(status) = 'completed' then 1 else 0 end) as completed
                        FROM follow_up_plans
                        WHERE date(created_at) >= date(?) AND date(created_at) <= date(?);
                    """, (start_date, end_date))
                    row = cursor.fetchone()
                    total = row["total"] or 0
                    completed = row["completed"] or 0
                    if total > 0:
                        num_val = float(completed)
                        den_val = float(total)
                        obs_val = round((completed / total) * 100, 1)
                        obs_fmt = f"{obs_val}%"
                        target_met = obs_val >= 60.0
                    else:
                        is_unavail = True
                        unavail_reason = "No follow-up plans created in review window"
                    limitation = "Descriptive outcome observation only; does not infer clinical efficacy or treatment causation."

                else:
                    # Default telemetry check for items requiring external log collectors
                    is_unavail = True
                    unavail_reason = f"Detailed telemetry collector for {code} is external or unconfigured in edge sandbox"

                # Persist or update observation
                obs = self.record_metric_observation(
                    evaluation_id=evaluation_id,
                    metric_definition_id=mdef["id"],
                    date_range_start=start_date,
                    date_range_end=end_date,
                    numerator_value=num_val,
                    denominator_value=den_val,
                    observed_value=obs_val,
                    observed_formatted=obs_fmt,
                    is_unavailable=is_unavail,
                    unavailable_reason=unavail_reason,
                    target_met=target_met,
                    limitations=limitation,
                    review_state="REVIEWED" if not is_unavail else "UNREVIEWED"
                )
                obs["metric_code"] = code
                obs["metric_name"] = mdef["name"]
                obs["domain_category"] = mdef["domain_category"]
                scorecard.append(obs)

            return scorecard
        finally:
            conn.close()

    def list_metric_observations(self, evaluation_id: str) -> List[Dict[str, Any]]:
        """List observed metrics joined with definition names."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.*, d.code as metric_code, d.name as metric_name, d.domain_category,
                       d.threshold_target, d.baseline_target, d.owner_role
                FROM metric_observations o
                JOIN metric_definitions d ON o.metric_definition_id = d.id
                WHERE o.evaluation_id = ?
                ORDER BY d.domain_category, d.code ASC;
            """, (evaluation_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # =========================================================================
    # 4. User Feedback Triage Review
    # =========================================================================

    def review_feedback_theme(
        self,
        evaluation_id: str,
        theme_title: str,
        classification: str,
        affected_role: str,
        affected_workflow: str,
        redacted_evidence_quote: str,
        severity_impact: str,
        root_cause_hypothesis: str,
        owner_role: str,
        verified_count: int = 1,
        disposition: str = "ACCEPTED_ACTION",
        proposed_fix_rationale: Optional[str] = None,
        retest_requirement: Optional[str] = None,
        is_governance_reviewed: bool = False
    ) -> Dict[str, Any]:
        """
        Record a structured feedback theme with redacted evidence and root-cause hypothesis.
        Patient-identifying information must never be included.
        """
        valid_classes = [
            "USABILITY_FRICTION", "MISSING_WORKFLOW", "RELIABILITY_PERFORMANCE",
            "CLINICAL_CONTENT_QUESTION", "SAFETY_CONCERN", "INTEGRATION_ISSUE",
            "TRAINING_GAP", "ACCESSIBILITY_LANGUAGE", "FEATURE_REQUEST"
        ]
        if classification not in valid_classes:
            raise ValueError(f"Invalid classification '{classification}'. Must be one of {valid_classes}")

        # Basic sanitization check to ensure no raw phone/email/MRN leaked
        if re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", redacted_evidence_quote):
            raise ValueError("Redacted quote contains email address. Patient/User identifiers must be sanitized.")
        if re.search(r"\b\d{10}\b", redacted_evidence_quote):
            raise ValueError("Redacted quote contains 10-digit phone number. Patient identifiers must be sanitized.")

        conn = self.manager.get_connection()
        theme_id = f"fdb-thm-{uuid.uuid4().hex[:12]}"

        try:
            conn.execute("""
                INSERT INTO feedback_theme_reviews (
                    id, evaluation_id, theme_title, classification, affected_role, affected_workflow,
                    verified_count, redacted_evidence_quote, severity_impact, root_cause_hypothesis,
                    disposition, owner_role, proposed_fix_rationale, retest_requirement, is_governance_reviewed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                theme_id, evaluation_id, theme_title, classification, affected_role, affected_workflow,
                verified_count, redacted_evidence_quote, severity_impact, root_cause_hypothesis,
                disposition, owner_role, proposed_fix_rationale, retest_requirement,
                1 if is_governance_reviewed else 0
            ))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM feedback_theme_reviews WHERE id = ?;", (theme_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def list_feedback_themes(self, evaluation_id: str) -> List[Dict[str, Any]]:
        """List feedback theme reviews for an evaluation."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM feedback_theme_reviews
                WHERE evaluation_id = ?
                ORDER BY severity_impact, created_at DESC;
            """, (evaluation_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # =========================================================================
    # 5. Incident & Risk Review
    # =========================================================================

    def record_incident_risk_review(
        self,
        evaluation_id: str,
        issue_ref: str,
        issue_type: str,
        severity: str,
        verified_facts: str,
        containment_status: str,
        corrective_action: str,
        uncertainties: Optional[str] = None,
        confirmed_root_cause: Optional[str] = None,
        suspected_root_cause: Optional[str] = None,
        retest_evidence_ref: Optional[str] = None,
        approving_owner_id: Optional[str] = None,
        status: str = "OPEN"
    ) -> Dict[str, Any]:
        """
        Record a comprehensive pre-expansion risk review.
        Rule: Safety concerns cannot be downgraded purely because no harm was reported.
        """
        conn = self.manager.get_connection()
        risk_id = f"inc-risk-{uuid.uuid4().hex[:12]}"

        try:
            conn.execute("""
                INSERT INTO incident_risk_reviews (
                    id, evaluation_id, issue_ref, issue_type, severity, verified_facts,
                    uncertainties, containment_status, confirmed_root_cause, suspected_root_cause,
                    corrective_action, retest_evidence_ref, is_safety_downgraded, approving_owner_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?);
            """, (
                risk_id, evaluation_id, issue_ref, issue_type, severity, verified_facts,
                uncertainties, containment_status, confirmed_root_cause, suspected_root_cause,
                corrective_action, retest_evidence_ref, approving_owner_id, status
            ))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incident_risk_reviews WHERE id = ?;", (risk_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def list_incident_risk_reviews(self, evaluation_id: str) -> List[Dict[str, Any]]:
        """List incident and risk reviews for an evaluation."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM incident_risk_reviews
                WHERE evaluation_id = ?
                ORDER BY severity, created_at DESC;
            """, (evaluation_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # =========================================================================
    # 6. Expansion Gates & Independent Evaluation
    # =========================================================================

    def create_expansion_proposal(
        self,
        evaluation_id: str,
        proposal_type: str,
        target_scope_details: Dict[str, Any],
        justification: str,
        prerequisite_dependencies: List[str]
    ) -> Dict[str, Any]:
        """Create an independent expansion proposal for gate evaluation."""
        valid_proposals = [
            "MORE_USERS_SAME_FACILITY", "ANOTHER_BRANCH_FACILITY",
            "PHARMACY_INVENTORY_ENABLEMENT", "EXTERNAL_COMMUNICATIONS",
            "HOSPITAL_IPD_LAB_REFERRAL", "FHIR_ABDM_EXCHANGE",
            "LARGER_DATA_VOLUME", "BROADER_PRODUCTION_AVAILABILITY"
        ]
        if proposal_type not in valid_proposals:
            raise ValueError(f"Invalid proposal type '{proposal_type}'. Must be one of {valid_proposals}")

        conn = self.manager.get_connection()
        prop_id = f"exp-prop-{uuid.uuid4().hex[:12]}"

        try:
            conn.execute("""
                INSERT INTO expansion_proposals (
                    id, evaluation_id, proposal_type, target_scope_details_json,
                    justification, prerequisite_dependencies_json, overall_gate_status
                ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING');
            """, (
                prop_id, evaluation_id, proposal_type, json.dumps(target_scope_details),
                justification, json.dumps(prerequisite_dependencies)
            ))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expansion_proposals WHERE id = ?;", (prop_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def evaluate_expansion_gate(
        self,
        proposal_id: str,
        gate_name: str,
        gate_status: str,
        evidence_notes: str,
        blocker_details: Optional[str] = None,
        checked_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record the evaluation result for a specific expansion gate."""
        valid_gates = [
            "DEPENDENCY_CHECK", "SCOPE_ACCESS_TESTS", "TRAINING_ONBOARDING_CAPACITY",
            "END_TO_END_TESTS", "CLINICAL_CONTENT_APPROVAL", "BACKUP_RESTORE_DRILL",
            "INCIDENT_RESPONSE_READY", "INTEGRATION_READINESS", "MONITORING_SUPPORT_CAPACITY",
            "ABSENCE_OF_STOP_CONDITIONS", "MANDATORY_SAFETY_GATE"
        ]
        if gate_name not in valid_gates:
            raise ValueError(f"Invalid gate name '{gate_name}'. Must be one of {valid_gates}")

        valid_statuses = ["PASS", "FAIL", "BLOCKED", "WAIVED"]
        if gate_status not in valid_statuses:
            raise ValueError(f"Invalid status '{gate_status}'. Must be one of {valid_statuses}")

        conn = self.manager.get_connection()
        gate_id = f"exp-gate-{uuid.uuid4().hex[:12]}"

        try:
            conn.execute("""
                INSERT OR REPLACE INTO expansion_gate_results (
                    id, proposal_id, gate_name, gate_status, evidence_notes,
                    blocker_details, checked_by, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (gate_id, proposal_id, gate_name, gate_status, evidence_notes, blocker_details, checked_by))

            # Recompute overall gate status for the proposal
            cursor = conn.cursor()
            cursor.execute("SELECT gate_status FROM expansion_gate_results WHERE proposal_id = ?;", (proposal_id,))
            statuses = [r["gate_status"] for r in cursor.fetchall()]

            if any(s in ("FAIL", "BLOCKED") for s in statuses):
                overall = "BLOCKED"
            elif all(s in ("PASS", "WAIVED") for s in statuses) and len(statuses) >= 3:
                overall = "PASSED"
            else:
                overall = "PENDING"

            conn.execute("UPDATE expansion_proposals SET overall_gate_status = ? WHERE id = ?;", (overall, proposal_id))
            conn.commit()

            cursor.execute("SELECT * FROM expansion_gate_results WHERE id = ?;", (gate_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def list_expansion_proposals(self, evaluation_id: str) -> List[Dict[str, Any]]:
        """List proposals and their nested gate results."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM expansion_proposals WHERE evaluation_id = ? ORDER BY created_at ASC;", (evaluation_id,))
            props = [dict(r) for r in cursor.fetchall()]
            for p in props:
                try:
                    p["target_scope_details"] = json.loads(p["target_scope_details_json"])
                    p["prerequisite_dependencies"] = json.loads(p["prerequisite_dependencies_json"])
                except Exception:
                    pass
                cursor.execute("SELECT * FROM expansion_gate_results WHERE proposal_id = ? ORDER BY gate_name ASC;", (p["id"],))
                p["gates"] = [dict(g) for g in cursor.fetchall()]
            return props
        finally:
            conn.close()

    # =========================================================================
    # 7. Decision Framework & Multi-Role Approvals
    # =========================================================================

    def record_decision(
        self,
        evaluation_id: str,
        decision: str,
        rationale: str,
        allowed_scope_summary: str,
        disabled_features_summary: str,
        recorded_by: str,
        accepted_residual_risks: Optional[str] = None,
        next_review_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record a formal post-pilot evaluation decision.
        Enforces Stop/Containment invariants:
        - Any unresolved P0 or active stop condition forbids EXPAND_* or ENABLE_*
        """
        valid_decisions = [
            "CONTINUE_CURRENT_PILOT", "EXPAND_WITHIN_APPROVED_SCOPE",
            "EXPAND_TO_ADDITIONAL_FACILITY", "ENABLE_SPECIFIC_MODULE",
            "PAUSE_FOR_REMEDIATION", "STOP_OR_ROLLBACK", "NOT_YET_ASSESSABLE"
        ]
        if decision not in valid_decisions:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of {valid_decisions}")

        conn = self.manager.get_connection()
        dec_id = f"dec-rec-{uuid.uuid4().hex[:12]}"

        try:
            eval_record = self.get_evaluation(evaluation_id)
            if not eval_record:
                raise ValueError("Evaluation record not found")

            # Check for active stop conditions or unresolved P0s
            cursor = conn.cursor()
            cursor.execute("""
                SELECT count(*) as active_stops
                FROM pilot_stop_events
                WHERE pilot_program_id = ? AND is_active = 1;
            """, (eval_record["pilot_program_id"],))
            active_stops = cursor.fetchone()["active_stops"] or 0

            cursor.execute("""
                SELECT count(*) as open_p0
                FROM incident_risk_reviews
                WHERE evaluation_id = ? AND severity = 'P0_CRITICAL' AND status != 'RESOLVED';
            """, (evaluation_id,))
            open_p0 = cursor.fetchone()["open_p0"] or 0

            if (active_stops > 0 or open_p0 > 0) and decision in ("EXPAND_WITHIN_APPROVED_SCOPE", "EXPAND_TO_ADDITIONAL_FACILITY", "ENABLE_SPECIFIC_MODULE"):
                blockers = []
                if active_stops > 0:
                    blockers.append(f"{active_stops} active stop condition(s) present")
                if open_p0 > 0:
                    blockers.append(f"{open_p0} unresolved P0 critical incident(s) open")
                raise ExpansionGateBlockedError(blockers)

            conn.execute("""
                INSERT INTO evaluation_decision_records (
                    id, evaluation_id, decision, rationale, allowed_scope_summary,
                    disabled_features_summary, accepted_residual_risks, next_review_date, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                dec_id, evaluation_id, decision, rationale, allowed_scope_summary,
                disabled_features_summary, accepted_residual_risks, next_review_date, recorded_by
            ))

            # Set evaluation primary recommendation and status to READY_FOR_DECISION
            new_eval_status = "REMEDIATION_REQUIRED" if decision in ("PAUSE_FOR_REMEDIATION", "STOP_OR_ROLLBACK") else "READY_FOR_DECISION"
            conn.execute("""
                UPDATE pilot_evaluations
                SET status = ?,
                    primary_recommendation = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_eval_status, decision, evaluation_id))

            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=recorded_by,
                action_type="PILOT_DECISION_RECORDED",
                target_entity_type="DECISION_RECORD",
                target_entity_id=dec_id,
                details={"decision": decision, "rationale": rationale}
            )

            cursor.execute("SELECT * FROM evaluation_decision_records WHERE id = ?;", (dec_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def approve_decision(
        self,
        decision_record_id: str,
        required_role: str,
        approver_user_id: str,
        approval_status: str = "APPROVED",
        conditions_or_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record a required stakeholder approval signature.
        Roles: CLINICAL_GOVERNANCE, PRODUCT_OPERATIONS, SECURITY_PRIVACY.
        Transitions evaluation status to DECISION_APPROVED when all 3 roles approve.
        """
        valid_roles = ["CLINICAL_GOVERNANCE", "PRODUCT_OPERATIONS", "SECURITY_PRIVACY"]
        if required_role not in valid_roles:
            raise ValueError(f"Invalid required role '{required_role}'. Must be one of {valid_roles}")

        conn = self.manager.get_connection()
        app_id = f"dec-app-{uuid.uuid4().hex[:12]}"

        try:
            conn.execute("""
                INSERT OR REPLACE INTO decision_approvals (
                    id, decision_record_id, required_role, approver_user_id,
                    approval_status, conditions_or_notes, signed_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (app_id, decision_record_id, required_role, approver_user_id, approval_status, conditions_or_notes))

            # Check if all 3 required roles are APPROVED
            cursor = conn.cursor()
            cursor.execute("""
                SELECT required_role, approval_status
                FROM decision_approvals
                WHERE decision_record_id = ?;
            """, (decision_record_id,))
            approvals = {r["required_role"]: r["approval_status"] for r in cursor.fetchall()}

            cursor.execute("SELECT evaluation_id FROM evaluation_decision_records WHERE id = ?;", (decision_record_id,))
            dec_row = cursor.fetchone()
            eval_id = dec_row["evaluation_id"] if dec_row else None

            all_approved = (
                approvals.get("CLINICAL_GOVERNANCE") == "APPROVED" and
                approvals.get("PRODUCT_OPERATIONS") == "APPROVED" and
                approvals.get("SECURITY_PRIVACY") == "APPROVED"
            )

            if all_approved and eval_id:
                conn.execute("""
                    UPDATE pilot_evaluations
                    SET status = 'DECISION_APPROVED',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (eval_id,))

            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=approver_user_id,
                action_type="PILOT_DECISION_APPROVED",
                target_entity_type="DECISION_APPROVAL",
                target_entity_id=app_id,
                details={"role": required_role, "status": approval_status, "all_approved": all_approved}
            )

            cursor.execute("SELECT * FROM decision_approvals WHERE id = ?;", (app_id,))
            res = dict(cursor.fetchone())
            res["all_approved"] = all_approved
            return res
        finally:
            conn.close()

    def get_decision_with_approvals(self, evaluation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve latest decision record and all associated sign-off approvals."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM evaluation_decision_records
                WHERE evaluation_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (evaluation_id,))
            dec_row = cursor.fetchone()
            if not dec_row:
                return None
            decision = dict(dec_row)

            cursor.execute("""
                SELECT * FROM decision_approvals
                WHERE decision_record_id = ?
                ORDER BY signed_at ASC;
            """, (decision["id"],))
            decision["approvals"] = [dict(a) for a in cursor.fetchall()]
            return decision
        finally:
            conn.close()

    # =========================================================================
    # 8. Remediation Actions
    # =========================================================================

    def add_remediation_action(
        self,
        evaluation_id: str,
        title: str,
        description: str,
        category: str,
        priority: str,
        owner_role: str,
        retest_requirement: str,
        owner_user_id: Optional[str] = None,
        due_date: Optional[str] = None,
        retest_evidence_ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a trackable remediation action."""
        conn = self.manager.get_connection()
        act_id = f"act-{uuid.uuid4().hex[:12]}"
        try:
            conn.execute("""
                INSERT INTO remediation_actions (
                    id, evaluation_id, title, description, category, priority,
                    owner_role, owner_user_id, due_date, retest_requirement, retest_evidence_ref, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN');
            """, (
                act_id, evaluation_id, title, description, category, priority,
                owner_role, owner_user_id, due_date, retest_requirement, retest_evidence_ref
            ))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM remediation_actions WHERE id = ?;", (act_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def close_remediation_action(
        self,
        action_id: str,
        closed_by_user_id: str,
        retest_evidence_ref: str
    ) -> Dict[str, Any]:
        """
        Close an action item upon verified retest evidence.
        Invariant: Action CANNOT close without valid retest evidence!
        """
        if not retest_evidence_ref or len(retest_evidence_ref.strip()) < 5:
            raise RetestEvidenceMissingError("Cannot close remediation action without verified retest evidence reference.")

        conn = self.manager.get_connection()
        try:
            conn.execute("""
                UPDATE remediation_actions
                SET status = 'VERIFIED_CLOSED',
                    retest_evidence_ref = ?,
                    closed_by = ?,
                    closed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (retest_evidence_ref, closed_by_user_id, action_id))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM remediation_actions WHERE id = ?;", (action_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def list_remediation_actions(self, evaluation_id: str) -> List[Dict[str, Any]]:
        """List remediation actions for an evaluation."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM remediation_actions
                WHERE evaluation_id = ?
                ORDER BY priority, created_at ASC;
            """, (evaluation_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # =========================================================================
    # 9. Comprehensive Evaluation Report Generator
    # =========================================================================

    def generate_evaluation_report(self, evaluation_id: str, generated_by: str) -> Dict[str, Any]:
        """
        Generate a comprehensive, reproducible Markdown review package and JSON manifest.
        Strictly preserves provenance, unavailable telemetry status, and gate boundaries.
        """
        eval_record = self.get_evaluation(evaluation_id)
        if not eval_record:
            raise ValueError("Evaluation record not found")

        evidence_items = self.list_evidence_items(evaluation_id)
        scorecard = self.list_metric_observations(evaluation_id)
        feedback_themes = self.list_feedback_themes(evaluation_id)
        incident_risks = self.list_incident_risk_reviews(evaluation_id)
        proposals = self.list_expansion_proposals(evaluation_id)
        decision = self.get_decision_with_approvals(evaluation_id)
        actions = self.list_remediation_actions(evaluation_id)

        # Markdown Report Assembly
        lines = [
            f"# ZAYVORA MATAB OS — Post-Pilot Evaluation & Scale Decision",
            f"",
            f"## Executive Overview",
            f"- **Evaluation ID:** `{eval_record['id']}`",
            f"- **Pilot Program ID:** `{eval_record['pilot_program_id']}`",
            f"- **Build / Release Commit:** `{eval_record['build_commit']}`",
            f"- **Review Date Range:** `{eval_record['review_period_start']}` to `{eval_record['review_period_end']}`",
            f"- **Evaluation Status:** **{eval_record['status']}**",
            f"- **Primary Recommendation:** **{eval_record.get('primary_recommendation') or 'PENDING_REVIEW'}**",
            f"",
            f"---",
            f"",
            f"## 1. Verified Evidence Inventory",
            f"| Ref | Category | Source / Method | Owner | Completeness | Status |",
            f"| :--- | :--- | :--- | :--- | :---: | :---: |",
        ]
        for e in evidence_items:
            lines.append(f"| `{e['source_reference']}` | {e['category']} | {e['extraction_method']} | {e['owner']} | {e['completeness']} | {e['verification_status']} |")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 2. Adoption & Reliability Metric Scorecard",
            f"| Code | Domain | Metric Name | Target | Observed / Status | Result |",
            f"| :--- | :--- | :--- | :--- | :--- | :---: |",
        ])
        for m in scorecard:
            res_str = m.get("observed_formatted") or (f"UNAVAILABLE ({m.get('unavailable_reason')})" if m.get("is_unavailable") else "N/A")
            target_str = "PASS" if m.get("target_met") else ("FAIL" if m.get("target_met") is False else "UNAVAILABLE")
            lines.append(f"| `{m['metric_code']}` | {m['domain_category']} | {m['metric_name']} | {m.get('threshold_target') or '-'} | {res_str} | **{target_str}** |")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 3. Feedback Theme Reviews (Redacted Quotes)",
            f"| Theme | Classification | Role | Quote (Sanitized) | Hypothesis | Disposition |",
            f"| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for f in feedback_themes:
            lines.append(f"| {f['theme_title']} | {f['classification']} | {f['affected_role']} | *\"{f['redacted_evidence_quote']}\"* | {f['root_cause_hypothesis']} | {f['disposition']} |")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 4. Pre-Expansion Incident & Risk Review",
            f"| Issue Ref | Type | Severity | Verified Facts | Containment | Corrective Action |",
            f"| :--- | :--- | :---: | :--- | :---: | :--- |",
        ])
        for r in incident_risks:
            lines.append(f"| `{r['issue_ref']}` | {r['issue_type']} | {r['severity']} | {r['verified_facts']} | {r['containment_status']} | {r['corrective_action']} |")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 5. Independent Expansion Gates Matrix",
        ])
        for p in proposals:
            lines.append(f"### Proposal: `{p['proposal_type']}` — Overall Status: **{p['overall_gate_status']}**")
            lines.append(f"- **Justification:** {p['justification']}")
            lines.append(f"| Gate Name | Status | Evidence Notes | Blockers |")
            lines.append(f"| :--- | :---: | :--- | :--- |")
            for g in p.get("gates", []):
                lines.append(f"| {g['gate_name']} | **{g['gate_status']}** | {g.get('evidence_notes') or '-'} | {g.get('blocker_details') or '-'} |")
            lines.append("")

        lines.extend([
            f"---",
            f"",
            f"## 6. Decision & Multi-Role Governance Sign-off",
        ])
        if decision:
            lines.append(f"- **Formal Decision:** **{decision['decision']}**")
            lines.append(f"- **Rationale:** {decision['rationale']}")
            lines.append(f"- **Allowed Scope:** {decision['allowed_scope_summary']}")
            lines.append(f"- **Disabled Features:** {decision['disabled_features_summary']}")
            lines.append(f"- **Next Review Date:** `{decision.get('next_review_date') or 'TBD'}`")
            lines.append(f"")
            lines.append(f"### Approvals Ledger:")
            lines.append(f"| Required Stakeholder Role | Status | Approver User ID | Signed At |")
            lines.append(f"| :--- | :---: | :--- | :--- |")
            for a in decision.get("approvals", []):
                lines.append(f"| **{a['required_role']}** | {a['approval_status']} | `{a['approver_user_id']}` | {a['signed_at']} |")
        else:
            lines.append(f"*Decision record pending submission.*")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 7. Post-Pilot Remediation Actions",
            f"| Title | Category | Priority | Retest Requirement | Status |",
            f"| :--- | :--- | :---: | :--- | :---: |",
        ])
        for a in actions:
            lines.append(f"| {a['title']} | {a['category']} | {a['priority']} | {a['retest_requirement']} | **{a['status']}** |")

        report_markdown = "\n".join(lines)

        manifest = {
            "evaluation_id": eval_record["id"],
            "pilot_program_id": eval_record["pilot_program_id"],
            "build_commit": eval_record["build_commit"],
            "review_period": f"{eval_record['review_period_start']} to {eval_record['review_period_end']}",
            "status": eval_record["status"],
            "recommendation": eval_record.get("primary_recommendation"),
            "evidence_item_count": len(evidence_items),
            "scorecard_metrics_count": len(scorecard),
            "feedback_themes_count": len(feedback_themes),
            "incident_risks_count": len(incident_risks),
            "expansion_proposals_count": len(proposals),
            "remediation_actions_count": len(actions),
            "decision_signed_off": bool(decision and all(a["approval_status"] == "APPROVED" for a in decision.get("approvals", [])))
        }

        # Persist versioned report snapshot
        conn = self.manager.get_connection()
        rep_id = f"rep-ver-{uuid.uuid4().hex[:12]}"
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT coalesce(max(version_number), 0) + 1 FROM evaluation_report_versions WHERE evaluation_id = ?;", (evaluation_id,))
            ver_num = cursor.fetchone()[0]

            conn.execute("""
                INSERT INTO evaluation_report_versions (
                    id, evaluation_id, version_number, report_title, report_markdown,
                    manifest_json, generated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                rep_id, evaluation_id, ver_num, f"Evaluation Report v{ver_num}",
                report_markdown, json.dumps(manifest), generated_by
            ))
            conn.commit()

            return {
                "report_id": rep_id,
                "version_number": ver_num,
                "report_markdown": report_markdown,
                "manifest": manifest
            }
        finally:
            conn.close()
