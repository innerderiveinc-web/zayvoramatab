"""
Controlled Pilot Launch, Clinic Onboarding, Training & Operations Domain Engine
ZAYVORA MATAB OS — Independent Standalone Product
"""

import re
import json
import uuid
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from apps.api.database.connection import DatabaseConnection
from apps.api.core.audit import log_audit_event


class ScopeRestrictionError(Exception):
    """Raised when an operation violates active pilot scope restrictions."""
    pass


class EligibilityGateError(Exception):
    """Raised when pilot activation is blocked by eligibility gate verification."""
    def __init__(self, blockers: List[str]):
        self.blockers = blockers
        super().__init__(f"Pilot activation blocked: {'; '.join(blockers)}")


class PilotLaunchEngine:
    """Core domain orchestrator for controlled clinic pilot launch and operations."""

    def __init__(self, db_path: Optional[str] = None):
        self.manager = DatabaseConnection(db_path)

    # =========================================================================
    # 1. Pilot Program & Scope Management
    # =========================================================================

    def create_pilot_program(
        self,
        code: str,
        name: str,
        organization_id: str,
        description: Optional[str] = None,
        target_start_date: Optional[str] = None,
        target_end_date: Optional[str] = None,
        audit_report_ref: str = "AUDIT-PROMPT13-REPORT-2026-10-13",
        audit_verdict: str = "CONDITIONAL_GO_FOR_LIMITED_PILOT",
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new version-controlled pilot program."""
        conn = self.manager.get_connection()
        program_id = f"plt-{uuid.uuid4().hex[:12]}"
        try:
            conn.execute("""
                INSERT INTO pilot_programs (
                    id, code, name, description, status, organization_id,
                    target_start_date, target_end_date, audit_report_ref, audit_verdict, created_by
                ) VALUES (?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, ?);
            """, (
                program_id, code, name, description, organization_id,
                target_start_date, target_end_date, audit_report_ref, audit_verdict, created_by
            ))
            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=created_by or "system",
                action_type="PILOT_PROGRAM_CREATED",
                target_entity_type="PILOT_PROGRAM",
                target_entity_id=program_id,
                organization_id=organization_id,
                details={"info": f"Created pilot program {code}: {name}"}
            )
            return self.get_pilot_program(program_id)
        finally:
            conn.close()

    def get_pilot_program(self, program_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve pilot program details including active scope and status."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pilot_programs WHERE id = ?;", (program_id,))
            row = cursor.fetchone()
            if not row:
                return None
            program = dict(row)
            program["active_scope"] = self.get_active_scope(program_id)
            return program
        finally:
            conn.close()

    def list_pilot_programs(self, organization_id: str) -> List[Dict[str, Any]]:
        """List all pilot programs for an organization."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pilot_programs
                WHERE organization_id = ?
                ORDER BY created_at DESC;
            """, (organization_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def declare_scope_version(
        self,
        program_id: str,
        enabled_modules: List[str],
        disabled_modules: List[str],
        permitted_roles: List[str],
        permitted_facilities: List[str],
        user_id: str,
        supported_languages: Optional[List[str]] = None,
        supported_devices: Optional[List[str]] = None,
        known_limitations: Optional[str] = None,
        support_hours: str = "09:00 - 18:00 IST",
        approved_by_clinical_lead: Optional[str] = None,
        approved_by_security_lead: Optional[str] = None,
        approved_by_product_lead: Optional[str] = None
    ) -> Dict[str, Any]:
        """Declare and activate a versioned pilot scope record."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(version_number) FROM pilot_scope_versions
                WHERE pilot_program_id = ?;
            """, (program_id,))
            max_v = cursor.fetchone()[0] or 0
            new_v = max_v + 1

            # Supersede previous active scopes
            conn.execute("""
                UPDATE pilot_scope_versions
                SET status = 'SUPERSEDED'
                WHERE pilot_program_id = ? AND status = 'ACTIVE';
            """, (program_id,))

            scope_id = f"psc-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO pilot_scope_versions (
                    id, pilot_program_id, version_number, status,
                    enabled_modules_json, disabled_modules_json, permitted_roles_json,
                    permitted_facilities_json, supported_languages_json, supported_devices_json,
                    known_limitations, support_hours,
                    approved_by_clinical_lead, approved_by_security_lead, approved_by_product_lead
                ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                scope_id, program_id, new_v,
                json.dumps(enabled_modules), json.dumps(disabled_modules),
                json.dumps(permitted_roles), json.dumps(permitted_facilities),
                json.dumps(supported_languages or ["en", "ur", "hi"]),
                json.dumps(supported_devices or ["DESKTOP_WEB", "TABLET_WEB"]),
                known_limitations or "Phase 1 controlled clinic pilot scope.",
                support_hours,
                approved_by_clinical_lead, approved_by_security_lead, approved_by_product_lead
            ))
            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=user_id,
                action_type="PILOT_SCOPE_UPDATED",
                target_entity_type="PILOT_SCOPE",
                target_entity_id=scope_id,
                details={"info": f"Scope version {new_v} activated for program {program_id}"}
            )
            return self.get_active_scope(program_id)
        finally:
            conn.close()

    def get_active_scope(self, program_id: str) -> Optional[Dict[str, Any]]:
        """Get the current active scope version for a pilot program."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pilot_scope_versions
                WHERE pilot_program_id = ? AND status = 'ACTIVE'
                ORDER BY version_number DESC LIMIT 1;
            """, (program_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["enabled_modules"] = json.loads(res["enabled_modules_json"])
            res["disabled_modules"] = json.loads(res["disabled_modules_json"])
            res["permitted_roles"] = json.loads(res["permitted_roles_json"])
            res["permitted_facilities"] = json.loads(res["permitted_facilities_json"])
            res["supported_languages"] = json.loads(res["supported_languages_json"] or "[]")
            res["supported_devices"] = json.loads(res["supported_devices_json"] or "[]")
            return res
        finally:
            conn.close()

    def enforce_pilot_scope(
        self,
        program_id: str,
        facility_id: str,
        role_code: str,
        module_code: str
    ) -> bool:
        """
        Enforce pilot scope boundaries on the backend.
        Fails closed with ScopeRestrictionError if unauthorized.
        """
        program = self.get_pilot_program(program_id)
        if not program:
            raise ScopeRestrictionError(f"Pilot program '{program_id}' not found.")

        if program["status"] in ["PAUSED", "STOPPED", "CONCLUDED"]:
            raise ScopeRestrictionError(f"Pilot program '{program['code']}' is currently {program['status']}. Operations halted.")

        # Check for active stop conditions
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT condition_code, action_taken, affected_module FROM pilot_stop_events
                WHERE pilot_program_id = ? AND is_active = 1
                AND (facility_id IS NULL OR facility_id = ?);
            """, (program_id, facility_id))
            active_stops = cursor.fetchall()
            for stop in active_stops:
                if stop["action_taken"] in ["PAUSE_PILOT_ALL", "TERMINATE_PILOT"]:
                    raise ScopeRestrictionError(f"Global stop condition active: {stop['condition_code']}.")
                if stop["action_taken"] == "PAUSE_FACILITY" and (stop["facility_id"] == facility_id):
                    raise ScopeRestrictionError(f"Facility stop condition active: {stop['condition_code']}.")
                if stop["action_taken"] == "DISABLE_MODULE" and stop["affected_module"] == module_code:
                    raise ScopeRestrictionError(f"Module '{module_code}' temporarily disabled by stop condition: {stop['condition_code']}.")
        finally:
            conn.close()

        scope = program.get("active_scope")
        if not scope:
            raise ScopeRestrictionError(f"No active scope defined for pilot program '{program['code']}'.")

        # 1. Facility check
        if facility_id not in scope["permitted_facilities"]:
            raise ScopeRestrictionError(f"Facility '{facility_id}' is not enrolled in pilot scope {scope['version_number']}.")

        # 2. Module check
        if module_code in scope["disabled_modules"]:
            raise ScopeRestrictionError(f"Module '{module_code}' is explicitly disabled for pilot scope.")
        if module_code not in scope["enabled_modules"]:
            raise ScopeRestrictionError(f"Module '{module_code}' is not included in pilot scope enabled modules.")

        # 3. Role check
        if role_code not in scope["permitted_roles"]:
            raise ScopeRestrictionError(f"Role '{role_code}' is not permitted to execute actions in pilot scope.")

        return True

    # =========================================================================
    # 2. Eligibility Gate Engine
    # =========================================================================

    def evaluate_pilot_eligibility(self, program_id: str) -> Dict[str, Any]:
        """
        Recompute pilot eligibility independently on backend.
        Never trusts client-supplied flags.
        """
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pilot_programs WHERE id = ?;", (program_id,))
            prog_row = cursor.fetchone()
            if not prog_row:
                return {"eligible": False, "blockers": [f"Program '{program_id}' not found."]}

            blockers = []
            gates = []

            # Gate 1: Prompt 13 Audit Verdict Check
            verdict = prog_row["audit_verdict"]
            audit_pass = verdict in ["CONDITIONAL_GO_FOR_LIMITED_PILOT", "GO_FOR_DEFINED_SCOPE"]
            gates.append({
                "gate": "PROMPT_13_AUDIT_VERDICT",
                "status": "PASS" if audit_pass else "FAIL",
                "details": f"Audit ref: {prog_row['audit_report_ref']}, Verdict: {verdict}"
            })
            if not audit_pass:
                blockers.append(f"Audit verdict '{verdict}' does not authorize pilot launch.")

            # Gate 2: Database Integrity Check
            cursor.execute("PRAGMA integrity_check;")
            db_int = cursor.fetchone()[0]
            db_pass = (db_int == "ok")
            gates.append({
                "gate": "DATABASE_INTEGRITY",
                "status": "PASS" if db_pass else "FAIL",
                "details": f"PRAGMA integrity_check: {db_int}"
            })
            if not db_pass:
                blockers.append("Database integrity check failed.")

            # Gate 3: Active P0 Stop Events Check
            cursor.execute("""
                SELECT count(*) FROM pilot_stop_events
                WHERE pilot_program_id = ? AND is_active = 1;
            """, (program_id,))
            active_stop_count = cursor.fetchone()[0]
            gates.append({
                "gate": "STOP_CONDITIONS_CLEAR",
                "status": "PASS" if active_stop_count == 0 else "FAIL",
                "details": f"Active stop events: {active_stop_count}"
            })
            if active_stop_count > 0:
                blockers.append(f"{active_stop_count} active stop events must be resolved.")

            # Gate 4: Active Scope Record & Lead Approvals
            scope = self.get_active_scope(program_id)
            scope_pass = (scope is not None)
            approvals_pass = False
            if scope:
                approvals_pass = bool(
                    scope.get("approved_by_clinical_lead") and
                    scope.get("approved_by_security_lead") and
                    scope.get("approved_by_product_lead")
                )
            gates.append({
                "gate": "SCOPE_GOVERNANCE_APPROVALS",
                "status": "PASS" if (scope_pass and approvals_pass) else "FAIL",
                "details": f"Scope active: {scope_pass}, Multi-stakeholder leads approved: {approvals_pass}"
            })
            if not scope_pass:
                blockers.append("No active pilot scope declared.")
            elif not approvals_pass:
                blockers.append("Scope requires sign-off from clinical, security, and product leads.")

            # Gate 5: Facility Onboarding Readiness (at least 1 facility with stages 1-8 completed)
            if scope and scope["permitted_facilities"]:
                target_fac = scope["permitted_facilities"][0]
                cursor.execute("""
                    SELECT count(*) FROM facility_onboarding_checklists
                    WHERE pilot_program_id = ? AND facility_id = ?
                    AND stage_order <= 8 AND status = 'COMPLETED';
                """, (program_id, target_fac))
                completed_prereqs = cursor.fetchone()[0]
                fac_pass = (completed_prereqs >= 8)
                gates.append({
                    "gate": "FACILITY_ONBOARDING_PREREQUISITES",
                    "status": "PASS" if fac_pass else "FAIL",
                    "details": f"Facility {target_fac}: {completed_prereqs}/8 prerequisite onboarding stages completed"
                })
                if not fac_pass:
                    blockers.append(f"Facility onboarding prerequisites incomplete ({completed_prereqs}/8 completed).")
            else:
                gates.append({
                    "gate": "FACILITY_ONBOARDING_PREREQUISITES",
                    "status": "FAIL",
                    "details": "No permitted facilities in scope."
                })
                blockers.append("Scope must contain at least one permitted facility.")

            is_eligible = (len(blockers) == 0)
            return {
                "program_id": program_id,
                "eligible": is_eligible,
                "gates": gates,
                "blockers": blockers,
                "evaluated_at": datetime.utcnow().isoformat()
            }
        finally:
            conn.close()

    def activate_pilot(self, program_id: str, user_id: str) -> Dict[str, Any]:
        """Activate the pilot program after strict eligibility gate validation."""
        eligibility = self.evaluate_pilot_eligibility(program_id)
        if not eligibility["eligible"]:
            raise EligibilityGateError(eligibility["blockers"])

        conn = self.manager.get_connection()
        try:
            conn.execute("""
                UPDATE pilot_programs
                SET status = 'ACTIVATED',
                    actual_start_date = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (program_id,))
            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=user_id,
                action_type="PILOT_PROGRAM_ACTIVATED",
                target_entity_type="PILOT_PROGRAM",
                target_entity_id=program_id,
                details={"info": f"Pilot program {program_id} activated following eligibility verification."}
            )
            return self.get_pilot_program(program_id)
        finally:
            conn.close()

    # =========================================================================
    # 3. Facility Onboarding 13-Stage Checklist
    # =========================================================================

    def initialize_facility_checklist(
        self,
        program_id: str,
        facility_id: str,
        owner_user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Initialize standard 13-stage onboarding checklist for a facility."""
        conn = self.manager.get_connection()
        stages = [
            ("1_ELIGIBILITY_CONFIRMED", "Prompt 13 Audit Eligibility & Pilot Scope Confirmed", 1),
            ("2_FACILITY_DETAILS_VALIDATED", "Organization & Facility Regulatory Details Validated", 2),
            ("3_STAFF_ROLES_CONFIGURED", "Practitioner & Staff Scope-Aware Roles Configured", 3),
            ("4_SCHEDULES_FEES_CONFIGURED", "Consultation Schedules, Rooms & Fee Catalog Configured", 4),
            ("5_TEMPLATES_CHECKED", "Print Templates & Approved Communication Templates Checked", 5),
            ("6_CLINICAL_CONTENT_REVIEWED", "Unani Monographs & Clinical Safety Datasets Reviewed", 6),
            ("7_DEVICES_NETWORK_CHECKED", "Clinic Devices, Barcode Scanners & Local Network Checked", 7),
            ("8_DATA_MIGRATION_DECISION", "Data Migration Decision Approved (Controlled Registration Mode)", 8),
            ("9_ROLE_TRAINING_COMPLETED", "Role-Based Staff Training & Scenario Practice Completed", 9),
            ("10_ACCEPTANCE_TESTS_PASSED", "User Acceptance Testing & Synthetic Scenario Verification Passed", 10),
            ("11_SITE_OWNER_APPROVAL", "Site Medical Director & Facility Owner Approval Recorded", 11),
            ("12_FACILITY_ACTIVATED", "Facility Activated for Controlled Pilot Live Traffic", 12),
            ("13_FIRST_WEEK_REVIEW", "First-Week Operational Review & Quality Check Completed", 13)
        ]
        try:
            for s_code, s_title, s_order in stages:
                chk_id = f"fob-{uuid.uuid4().hex[:12]}"
                conn.execute("""
                    INSERT OR IGNORE INTO facility_onboarding_checklists (
                        id, pilot_program_id, facility_id, stage_code, stage_title, stage_order,
                        status, owner_user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?);
                """, (chk_id, program_id, facility_id, s_code, s_title, s_order, owner_user_id))
            conn.commit()
            return self.get_facility_checklist(program_id, facility_id)
        finally:
            conn.close()

    def get_facility_checklist(self, program_id: str, facility_id: str) -> List[Dict[str, Any]]:
        """Retrieve all 13 checklist stages ordered by stage_order."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM facility_onboarding_checklists
                WHERE pilot_program_id = ? AND facility_id = ?
                ORDER BY stage_order ASC;
            """, (program_id, facility_id))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_checklist_stage(
        self,
        checklist_id: str,
        status: str,
        user_id: str,
        evidence_notes: Optional[str] = None,
        blocker_details: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a specific checklist stage with evidence and audit tracking."""
        conn = self.manager.get_connection()
        try:
            completed_at = datetime.utcnow().isoformat() if status == "COMPLETED" else None
            conn.execute("""
                UPDATE facility_onboarding_checklists
                SET status = ?,
                    evidence_notes = COALESCE(?, evidence_notes),
                    blocker_details = ?,
                    completed_at = COALESCE(?, completed_at),
                    signoff_user_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (status, evidence_notes, blocker_details, completed_at, user_id, checklist_id))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM facility_onboarding_checklists WHERE id = ?;", (checklist_id,))
            updated = dict(cursor.fetchone())

            log_audit_event(
                conn=conn,
                actor_id=user_id,
                action_type="ONBOARDING_STAGE_UPDATED",
                target_entity_type="FACILITY_ONBOARDING",
                target_entity_id=checklist_id,
                details={"info": f"Stage {updated['stage_code']} status set to {status}"}
            )
            return updated
        finally:
            conn.close()

    # =========================================================================
    # 4. Governed Data Migration & Reconciliation Engine
    # =========================================================================

    def run_data_migration(
        self,
        program_id: str,
        facility_id: str,
        source_system: str,
        source_authority_reference: str,
        raw_records: List[Dict[str, Any]],
        user_id: str,
        mode: str = "DRY_RUN"
    ) -> Dict[str, Any]:
        """
        Execute governed data migration.
        In DRY_RUN: computes counts and ambiguities with ZERO database mutation.
        In EXECUTE: imports clean non-duplicate records into patients table.
        """
        conn = self.manager.get_connection()
        migration_id = f"mig-{uuid.uuid4().hex[:12]}"
        total_read = len(raw_records)
        migrated_count = 0
        rejected_count = 0
        ambiguous_count = 0
        reconciliation_items = []
        errors = []

        try:
            cursor = conn.cursor()
            for idx, item in enumerate(raw_records):
                name = (item.get("name") or "").strip()
                phone = (item.get("phone") or "").strip()
                gender = (item.get("gender") or "UNKNOWN").upper()
                dob = item.get("dob")

                if not name or not phone:
                    rejected_count += 1
                    errors.append({"record_index": idx, "error": "Missing mandatory name or phone number."})
                    continue

                norm_phone = re.sub(r"\D", "", phone)
                norm_10 = norm_phone[-10:] if len(norm_phone) >= 10 else norm_phone

                # Check duplicate in patient_contacts
                cursor.execute("""
                    SELECT p.id, p.display_name, c.contact_value
                    FROM patients p
                    JOIN patient_contacts c ON p.id = c.patient_id
                    WHERE c.contact_type = 'PHONE' AND (c.normalized_value = ? OR c.normalized_value = ? OR c.contact_value = ?);
                """, (norm_phone, norm_10, phone))
                existing = cursor.fetchall()

                if existing:
                    ambiguous_count += 1
                    reconciliation_items.append({
                        "record_index": idx,
                        "name": name,
                        "phone": phone,
                        "status": "AMBIGUOUS_DUPLICATE_FLAGGED",
                        "matched_existing_ids": [r["id"] for r in existing]
                    })
                else:
                    reconciliation_items.append({
                        "record_index": idx,
                        "name": name,
                        "phone": phone,
                        "status": "CLEAN_NEW_RECORD"
                    })
                    if mode == "EXECUTE":
                        # Insert new patient
                        new_pid = f"pat-{uuid.uuid4().hex[:12]}"
                        name_parts = name.split(" ", 1)
                        given_name = name_parts[0]
                        family_name = name_parts[1] if len(name_parts) > 1 else ""
                        mrn = f"MRN-MIG-{uuid.uuid4().hex[:6].upper()}"

                        cursor.execute("""
                            INSERT INTO patients (
                                id, organization_id, facility_id, mrn, given_name, family_name, display_name,
                                date_of_birth, sex, created_by
                            ) VALUES (?, (SELECT organization_id FROM facilities WHERE id = ?), ?, ?, ?, ?, ?, ?, ?, ?);
                        """, (
                            new_pid, facility_id, facility_id, mrn, given_name, family_name, name,
                            dob, gender, user_id
                        ))

                        cursor.execute("""
                            INSERT INTO patient_contacts (
                                id, patient_id, organization_id, contact_type, contact_value, normalized_value, is_preferred
                            ) VALUES (?, ?, (SELECT organization_id FROM facilities WHERE id = ?), 'PHONE', ?, ?, 1);
                        """, (
                            f"con-{uuid.uuid4().hex[:12]}", new_pid, facility_id, phone, norm_phone
                        ))
                        migrated_count += 1

            if mode == "DRY_RUN":
                status = "COMPLETED_DRY_RUN"
            else:
                conn.commit()
                status = "COMPLETED_EXECUTE"

            # Record migration run in database
            conn.execute("""
                INSERT INTO pilot_data_migrations (
                    id, pilot_program_id, facility_id, source_system_name,
                    source_authority_reference, mode, status, total_records_read,
                    records_migrated, records_rejected, ambiguous_duplicates_flagged,
                    reconciliation_report_json, error_log_json, executed_by_user_id, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (
                migration_id, program_id, facility_id, source_system,
                source_authority_reference, mode, status, total_read,
                migrated_count, rejected_count, ambiguous_count,
                json.dumps(reconciliation_items), json.dumps(errors), user_id
            ))
            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=user_id,
                action_type=f"DATA_MIGRATION_{mode}",
                target_entity_type="DATA_MIGRATION",
                target_entity_id=migration_id,
                details={"info": f"Executed {mode} for {source_system}: {migrated_count} imported, {ambiguous_count} flagged, {rejected_count} rejected."}
            )

            return {
                "migration_id": migration_id,
                "mode": mode,
                "status": status,
                "total_records_read": total_read,
                "records_migrated": migrated_count,
                "ambiguous_duplicates_flagged": ambiguous_count,
                "records_rejected": rejected_count,
                "errors": errors
            }
        finally:
            conn.close()

    # =========================================================================
    # 5. Role-Based Training & Acceptance Tracker
    # =========================================================================

    def list_training_modules(self, target_role: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available curriculum modules."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            if target_role:
                cursor.execute("SELECT * FROM training_modules WHERE target_role = ? ORDER BY code ASC;", (target_role,))
            else:
                cursor.execute("SELECT * FROM training_modules ORDER BY target_role, code ASC;")
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def enroll_staff_for_training(
        self,
        program_id: str,
        facility_id: str,
        user_id: str,
        training_module_id: str
    ) -> Dict[str, Any]:
        """Enroll a staff member into a training module."""
        conn = self.manager.get_connection()
        enrollment_id = f"trn-{uuid.uuid4().hex[:12]}"
        try:
            conn.execute("""
                INSERT OR IGNORE INTO staff_training_enrollments (
                    id, pilot_program_id, facility_id, user_id, training_module_id, status
                ) VALUES (?, ?, ?, ?, ?, 'ASSIGNED');
            """, (enrollment_id, program_id, facility_id, user_id, training_module_id))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, m.title, m.code, m.target_role, m.min_pass_score
                FROM staff_training_enrollments e
                JOIN training_modules m ON e.training_module_id = m.id
                WHERE e.user_id = ? AND e.training_module_id = ?;
            """, (user_id, training_module_id))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def record_training_completion(
        self,
        enrollment_id: str,
        score: int,
        scenario_acceptance_notes: str,
        certified_by_user_id: str
    ) -> Dict[str, Any]:
        """Record training completion and score evaluation."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.*, m.min_pass_score FROM staff_training_enrollments e
                JOIN training_modules m ON e.training_module_id = m.id
                WHERE e.id = ?;
            """, (enrollment_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Training enrollment '{enrollment_id}' not found.")

            min_score = row["min_pass_score"]
            status = "PASSED" if score >= min_score else "RETRAINING_REQUIRED"
            completed_at = datetime.utcnow().isoformat() if status == "PASSED" else None

            conn.execute("""
                UPDATE staff_training_enrollments
                SET status = ?,
                    score = ?,
                    scenario_acceptance_notes = ?,
                    certified_by_user_id = ?,
                    completed_at = ?
                WHERE id = ?;
            """, (status, score, scenario_acceptance_notes, certified_by_user_id, completed_at, enrollment_id))
            conn.commit()

            cursor.execute("SELECT * FROM staff_training_enrollments WHERE id = ?;", (enrollment_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def get_facility_training_matrix(self, program_id: str, facility_id: str) -> Dict[str, Any]:
        """Calculate aggregate training progress for a facility."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT count(*) as total,
                       sum(case when status = 'PASSED' then 1 else 0 end) as passed,
                       sum(case when status = 'ASSIGNED' then 1 else 0 end) as assigned,
                       sum(case when status = 'RETRAINING_REQUIRED' then 1 else 0 end) as retraining
                FROM staff_training_enrollments
                WHERE pilot_program_id = ? AND facility_id = ?;
            """, (program_id, facility_id))
            stats = dict(cursor.fetchone())
            total = stats["total"] or 0
            passed = stats["passed"] or 0
            completion_rate = round((passed / total * 100), 1) if total > 0 else 0.0
            return {
                "total_enrollments": total,
                "passed": passed,
                "assigned": stats["assigned"] or 0,
                "retraining_required": stats["retraining"] or 0,
                "completion_rate_percentage": completion_rate
            }
        finally:
            conn.close()

    # =========================================================================
    # 6. Support Tickets & Clinical Safety Escalation
    # =========================================================================

    def create_support_ticket(
        self,
        program_id: str,
        facility_id: str,
        reporter_user_id: str,
        category: str,
        severity: str,
        subject: str,
        safe_description: str,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a support ticket.
        If category is CLINICAL_SAFETY_INCIDENT or severity is SEV_1_CRITICAL,
        automatically routes to the dedicated Clinical Safety Governance Queue.
        """
        conn = self.manager.get_connection()
        ticket_id = f"tkt-{uuid.uuid4().hex[:12]}"
        ticket_num = f"SUP-{datetime.utcnow().year}-{uuid.uuid4().hex[:4].upper()}"

        try:
            conn.execute("""
                INSERT INTO pilot_support_tickets (
                    id, ticket_number, pilot_program_id, facility_id, reporter_user_id,
                    category, severity, subject, safe_description, trace_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN');
            """, (
                ticket_id, ticket_num, program_id, facility_id, reporter_user_id,
                category, severity, subject, safe_description, trace_id
            ))

            # Auto-route clinical safety alerts or SEV-1 incidents
            if category == "CLINICAL_SAFETY_INCIDENT" or severity == "SEV_1_CRITICAL":
                inc_id = f"csi-{uuid.uuid4().hex[:12]}"
                inc_num = f"CSI-{datetime.utcnow().year}-{uuid.uuid4().hex[:4].upper()}"
                conn.execute("""
                    INSERT INTO clinical_safety_incident_queue (
                        id, incident_number, pilot_program_id, facility_id, reporter_user_id,
                        ticket_id, issue_type, clinical_description, severity, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 'SAFETY_ALERT_ESCALATED', ?, 'CRITICAL', 'PENDING_REVIEW');
                """, (inc_id, inc_num, program_id, facility_id, reporter_user_id, ticket_id, safe_description))

            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pilot_support_tickets WHERE id = ?;", (ticket_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def list_support_tickets(
        self,
        program_id: str,
        facility_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List support tickets for a program."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM pilot_support_tickets WHERE pilot_program_id = ?"
            params = [program_id]
            if facility_id:
                query += " AND facility_id = ?"
                params.append(facility_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC;"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_clinical_safety_queue(self, program_id: str) -> List[Dict[str, Any]]:
        """Retrieve items in the clinical safety review queue."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM clinical_safety_incident_queue
                WHERE pilot_program_id = ?
                ORDER BY created_at DESC;
            """, (program_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def resolve_clinical_safety_incident(
        self,
        incident_id: str,
        governance_action: str,
        reviewer_user_id: str,
        notes: str
    ) -> Dict[str, Any]:
        """Record formal clinical governance disposition on a safety incident."""
        conn = self.manager.get_connection()
        try:
            conn.execute("""
                UPDATE clinical_safety_incident_queue
                SET status = 'RESOLVED',
                    governance_action = ?,
                    clinical_governance_reviewer_id = ?,
                    resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (governance_action, reviewer_user_id, incident_id))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clinical_safety_incident_queue WHERE id = ?;", (incident_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    # =========================================================================
    # 7. Structured Feedback & Triage
    # =========================================================================

    def submit_feedback(
        self,
        program_id: str,
        facility_id: str,
        user_id: str,
        category: str,
        impact_level: str,
        affected_workflow: str,
        software_version: str,
        description: str,
        reproduction_steps: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit structured pilot user feedback."""
        conn = self.manager.get_connection()
        feedback_id = f"fdb-{uuid.uuid4().hex[:12]}"
        try:
            conn.execute("""
                INSERT INTO pilot_feedback_items (
                    id, pilot_program_id, facility_id, user_id, category, impact_level,
                    affected_workflow, software_version, description, reproduction_steps, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW');
            """, (
                feedback_id, program_id, facility_id, user_id, category, impact_level,
                affected_workflow, software_version, description, reproduction_steps
            ))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pilot_feedback_items WHERE id = ?;", (feedback_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def list_feedback(self, program_id: str) -> List[Dict[str, Any]]:
        """List feedback items for a program."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pilot_feedback_items
                WHERE pilot_program_id = ?
                ORDER BY created_at DESC;
            """, (program_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    # =========================================================================
    # 8. Stop Conditions & Controlled Containment
    # =========================================================================

    def trigger_stop_condition(
        self,
        program_id: str,
        condition_code: str,
        action_taken: str,
        containment_actions: List[str],
        user_id: str,
        affected_module: Optional[str] = None,
        facility_id: Optional[str] = None,
        restart_criteria: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger a formal pause or stop condition.
        Halts operations without corrupting or deleting signed clinical records.
        """
        valid_conditions = [
            "TENANT_EXPOSURE", "UNAUTHORIZED_SIGNING", "DATA_CORRUPTION",
            "SAFETY_GATE_BYPASS", "FALSE_SAFETY_RESULT", "CREDENTIALS_EXPOSED",
            "SAVE_FAILURE_LOOP", "RESTORE_FAILURE"
        ]
        if condition_code not in valid_conditions:
            raise ValueError(f"Invalid condition code '{condition_code}'. Must be one of {valid_conditions}.")

        conn = self.manager.get_connection()
        event_id = f"stp-{uuid.uuid4().hex[:12]}"

        try:
            # 1. Update pilot program status to PAUSED or STOPPED
            new_status = "STOPPED" if action_taken == "TERMINATE_PILOT" else "PAUSED"
            conn.execute("""
                UPDATE pilot_programs
                SET status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_status, program_id))

            # 2. Record stop event
            conn.execute("""
                INSERT INTO pilot_stop_events (
                    id, pilot_program_id, facility_id, triggered_by_user_id,
                    condition_code, action_taken, affected_module,
                    containment_actions_json, restart_criteria, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
            """, (
                event_id, program_id, facility_id, user_id, condition_code,
                action_taken, affected_module, json.dumps(containment_actions), restart_criteria
            ))
            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=user_id,
                action_type="PILOT_STOP_TRIGGERED",
                target_entity_type="PILOT_STOP_EVENT",
                target_entity_id=event_id,
                details={"info": f"CRITICAL: Condition {condition_code} triggered. Action: {action_taken}. Program status set to {new_status}."}
            )

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pilot_stop_events WHERE id = ?;", (event_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    def resolve_stop_condition(
        self,
        event_id: str,
        user_id: str,
        resolution_notes: str
    ) -> Dict[str, Any]:
        """Resolve a stop condition and deactivate its containment lock."""
        conn = self.manager.get_connection()
        try:
            conn.execute("""
                UPDATE pilot_stop_events
                SET is_active = 0,
                    resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (event_id,))
            conn.commit()

            log_audit_event(
                conn=conn,
                actor_id=user_id,
                action_type="PILOT_STOP_RESOLVED",
                target_entity_type="PILOT_STOP_EVENT",
                target_entity_id=event_id,
                details={"info": f"Stop condition resolved by {user_id}: {resolution_notes}"}
            )

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pilot_stop_events WHERE id = ?;", (event_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()

    # =========================================================================
    # 9. Pilot Success Metrics & Review Pack Generation
    # =========================================================================

    def calculate_pilot_metrics(self, program_id: str, facility_id: Optional[str] = None) -> Dict[str, Any]:
        """Compute real operational metrics from persisted application records."""
        conn = self.manager.get_connection()
        try:
            cursor = conn.cursor()

            # 1. Training metrics
            cursor.execute("""
                SELECT count(*) as total,
                       sum(case when status = 'PASSED' then 1 else 0 end) as passed
                FROM staff_training_enrollments
                WHERE pilot_program_id = ?;
            """, (program_id,))
            t_row = cursor.fetchone()
            t_total = t_row["total"] or 0
            t_passed = t_row["passed"] or 0
            training_pct = round((t_passed / t_total * 100), 1) if t_total > 0 else 0.0

            # 2. Onboarding checklist progress
            cursor.execute("""
                SELECT count(*) as total,
                       sum(case when status = 'COMPLETED' then 1 else 0 end) as completed
                FROM facility_onboarding_checklists
                WHERE pilot_program_id = ?;
            """, (program_id,))
            o_row = cursor.fetchone()
            o_total = o_row["total"] or 0
            o_completed = o_row["completed"] or 0

            # 3. Support tickets by severity
            cursor.execute("""
                SELECT severity, count(*) as cnt FROM pilot_support_tickets
                WHERE pilot_program_id = ? AND status != 'CLOSED'
                GROUP BY severity;
            """, (program_id,))
            tickets_by_sev = {r["severity"]: r["cnt"] for r in cursor.fetchall()}

            # 4. Clinical safety incidents
            cursor.execute("""
                SELECT count(*) as total,
                       sum(case when status = 'PENDING_REVIEW' then 1 else 0 end) as pending
                FROM clinical_safety_incident_queue
                WHERE pilot_program_id = ?;
            """, (program_id,))
            csi_row = cursor.fetchone()

            # 5. Active stop events
            cursor.execute("""
                SELECT count(*) FROM pilot_stop_events
                WHERE pilot_program_id = ? AND is_active = 1;
            """, (program_id,))
            active_stops = cursor.fetchone()[0]

            return {
                "program_id": program_id,
                "timestamp": datetime.utcnow().isoformat(),
                "training": {
                    "total_enrolled": t_total,
                    "passed": t_passed,
                    "completion_rate_percentage": training_pct
                },
                "onboarding": {
                    "total_stages": o_total,
                    "completed_stages": o_completed
                },
                "open_support_tickets": tickets_by_sev,
                "clinical_safety_incidents": {
                    "total": csi_row["total"] or 0,
                    "pending_review": csi_row["pending"] or 0
                },
                "active_stop_conditions": active_stops
            }
        finally:
            conn.close()

    def generate_review_pack(
        self,
        program_id: str,
        review_type: str,
        period_start: str,
        period_end: str,
        recommendation: str,
        prepared_by_user_id: str,
        approved_by_clinical_lead: Optional[str] = None,
        approved_by_operations_lead: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate and persist a formal review pack."""
        metrics = self.calculate_pilot_metrics(program_id)
        safety_queue = self.list_clinical_safety_queue(program_id)
        feedback = self.list_feedback(program_id)

        conn = self.manager.get_connection()
        pack_id = f"rp-{uuid.uuid4().hex[:12]}"

        try:
            conn.execute("""
                INSERT INTO pilot_review_packs (
                    id, pilot_program_id, review_type, period_start, period_end,
                    metrics_snapshot_json, incidents_summary_json, feedback_summary_json,
                    recommendation, prepared_by_user_id, approved_by_clinical_lead, approved_by_operations_lead
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                pack_id, program_id, review_type, period_start, period_end,
                json.dumps(metrics), json.dumps(safety_queue), json.dumps(feedback),
                recommendation, prepared_by_user_id, approved_by_clinical_lead, approved_by_operations_lead
            ))
            conn.commit()

            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pilot_review_packs WHERE id = ?;", (pack_id,))
            return dict(cursor.fetchone())
        finally:
            conn.close()
