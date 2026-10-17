"""Unit tests for Enterprise Workflow Intelligence, SLA Governance & Exception Resolution Engine.

Phase 36 for ZAYVORA MATAB OS.
Tests:
1. Operational SLA Policy Draft Creation & Threshold Validation.
2. SLA Policy Lifecycle State Machine & Immutable Version Snapshots.
3. Operational Exception Ingestion, Auto-matching & Deduplication.
4. Deterministic SLA Timer Calculation, Projections & UNMEASURABLE State.
5. Pause Ledger Accounting, Resume Recalculations & Reason Code Enforcement.
6. Multi-Stage Escalation Matrix Execution (Zero-PHI Safe Messages).
7. Resolution Code Enforcement & Separation of Duties Verification Gate.
8. Exception Dismissal & Reopen Cycle.
9. Operational Monitor Aggregate Pulse & Governance Caveats.
"""

import os
import json
import uuid
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.sla_governance import SlaGovernanceEngine, VALID_PAUSE_REASONS
from apps.api.core.errors import ValidationError, ConflictError, NotFoundError, ForbiddenError


class TestSlaGovernanceEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_sla_governance.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = SlaGovernanceEngine(db_path=cls.db_path)

        conn = cls.engine._get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin_row = cur.fetchone()
        cls.admin_id = admin_row["id"]
        cls.org_id = admin_row["organization_id"]

        # Secondary user for separation of duties tests
        cur.execute("SELECT id FROM users WHERE username != 'admin' LIMIT 1;")
        second_row = cur.fetchone()
        if second_row:
            cls.verifier_id = second_row["id"]
        else:
            cls.verifier_id = f"usr-verif-{uuid.uuid4().hex[:6]}"
            cur.execute(
                """
                INSERT INTO users (id, organization_id, username, email, full_name, role, status)
                VALUES (?, ?, 'verifier1', 'verifier1@matab.local', 'Clinical Verifier', 'CLINICIAN', 'ACTIVE');
                """,
                (cls.verifier_id, cls.org_id)
            )

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        fac_row = cur.fetchone()
        cls.fac_id = fac_row["id"] if fac_row else "fac-central-opd"

        conn.commit()
        conn.close()

        cls.admin_ctx = {
            "id": cls.admin_id,
            "user_id": cls.admin_id,
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
            "role": "SYSTEM_ADMIN"
        }

        cls.verifier_ctx = {
            "id": cls.verifier_id,
            "user_id": cls.verifier_id,
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
            "role": "CLINICIAN"
        }

    # --------------------------------------------------------------------------
    # 1. Operational SLA Policy Registry & Validation
    # --------------------------------------------------------------------------

    def test_01_create_policy_draft_success_and_validation(self):
        """Test valid SLA policy draft creation and threshold validations."""
        data = {
            "name": "High Priority Lab Review SLA",
            "category": "clinical_review",
            "target_entity_type": "care_continuity_tasks",
            "owner_role": "CLINICAL_SUPPORT",
            "warning_threshold_mins": 30,
            "breach_threshold_mins": 60,
            "verification_required": True,
            "allowed_resolution_codes": ["RESULT_COMMUNICATED", "ALTERNATIVE_OBTAINED"],
            "escalation_matrix": [
                {"stage": 1, "trigger_delay_mins": 0, "escalate_to_role": "SUPERVISOR", "channel": "in_app"}
            ]
        }
        policy = self.engine.create_policy_draft(data, self.admin_ctx)
        self.assertEqual(policy["status"], "DRAFT")
        self.assertEqual(policy["warning_threshold_mins"], 30)
        self.assertEqual(policy["breach_threshold_mins"], 60)
        self.assertEqual(policy["verification_required"], 1)

        # Invalid: warning > breach
        invalid_data = dict(data)
        invalid_data["name"] = "Invalid Thresholds Policy"
        invalid_data["warning_threshold_mins"] = 90
        invalid_data["breach_threshold_mins"] = 45
        with self.assertRaises(ValidationError):
            self.engine.create_policy_draft(invalid_data, self.admin_ctx)

        # Invalid category
        invalid_cat_data = dict(data)
        invalid_cat_data["category"] = "unsupported_category"
        with self.assertRaises(ValidationError):
            self.engine.create_policy_draft(invalid_cat_data, self.admin_ctx)

    def test_02_policy_lifecycle_state_machine_and_versioning(self):
        """Test policy status transitions: DRAFT -> IN_REVIEW -> APPROVED -> ACTIVE -> RETIRED."""
        data = {
            "name": "Discharge Handover SLA",
            "category": "administrative",
            "warning_threshold_mins": 20,
            "breach_threshold_mins": 40
        }
        draft = self.engine.create_policy_draft(data, self.admin_ctx)
        pid = draft["id"]

        # Advance to IN_REVIEW
        in_review = self.engine.advance_policy_status(pid, "submit_for_review", self.admin_ctx)
        self.assertEqual(in_review["status"], "IN_REVIEW")

        # Approve policy (creates version snapshot in sla_policy_versions)
        approved = self.engine.advance_policy_status(pid, "approve", self.admin_ctx, reason="Clinical governance signoff")
        self.assertEqual(approved["status"], "APPROVED")
        self.assertEqual(approved["approved_by"], self.admin_id)

        # Verify snapshot exists
        conn = self.engine._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM sla_policy_versions WHERE policy_id = ?;", (pid,))
        snap = cur.fetchone()
        conn.close()
        self.assertIsNotNone(snap)
        self.assertEqual(snap["change_reason"], "Clinical governance signoff")

        # Activate policy
        active = self.engine.advance_policy_status(pid, "activate", self.admin_ctx)
        self.assertEqual(active["status"], "ACTIVE")

        # Updates directly to active policy should be blocked
        with self.assertRaises(ConflictError):
            self.engine.update_policy_draft(pid, {"name": "Should Fail"}, self.admin_ctx)

        # Retire policy
        retired = self.engine.advance_policy_status(pid, "retire", self.admin_ctx)
        self.assertEqual(retired["status"], "RETIRED")

    # --------------------------------------------------------------------------
    # 2. Operational Exception Detection, Ingestion & Deduplication
    # --------------------------------------------------------------------------

    def test_03_detect_and_ingest_exception_with_deduplication(self):
        """Test deterministic exception ingestion and idempotency deduplication."""
        source_id = f"token-{uuid.uuid4().hex[:6]}"
        data = {
            "category": "administrative",
            "source_entity": "queue_tokens",
            "source_entity_id": source_id,
            "priority": "HIGH",
            "title": f"Patient Wait Time Delay for {source_id}"
        }

        # First ingestion
        exc1 = self.engine.detect_and_ingest_exception(data, self.admin_ctx)
        self.assertEqual(exc1["status"], "OPEN")
        self.assertEqual(exc1["source_entity_id"], source_id)
        self.assertEqual(exc1["category"], "administrative")

        # Second ingestion with identical parameters (Idempotent: returns existing without error)
        exc2 = self.engine.detect_and_ingest_exception(data, self.admin_ctx)
        self.assertEqual(exc1["id"], exc2["id"])

    # --------------------------------------------------------------------------
    # 3. Deterministic SLA Timers & Projections
    # --------------------------------------------------------------------------

    def test_04_timer_projection_states_and_unmeasurable(self):
        """Test timer states: ON_TRACK, AT_RISK, BREACHED, and UNMEASURABLE."""
        now = datetime.now(timezone.utc)

        # 1. On Track: started 10 mins ago (warning=30, breach=45)
        exc_on_track = {
            "status": "OPEN",
            "started_at": (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
            "warning_threshold_mins": 30,
            "breach_threshold_mins": 45,
            "total_paused_duration_mins": 0
        }
        res_ot = self.engine.calculate_timer_projection(exc_on_track, now)
        self.assertEqual(res_ot["timer_state"], "ON_TRACK")
        self.assertFalse(res_ot["is_breached"])

        # 2. At Risk: started 35 mins ago (exceeds warning=30, under breach=45)
        exc_at_risk = {
            "status": "OPEN",
            "started_at": (now - timedelta(minutes=35)).strftime("%Y-%m-%d %H:%M:%S"),
            "warning_threshold_mins": 30,
            "breach_threshold_mins": 45,
            "total_paused_duration_mins": 0
        }
        res_ar = self.engine.calculate_timer_projection(exc_at_risk, now)
        self.assertEqual(res_ar["timer_state"], "AT_RISK")
        self.assertFalse(res_ar["is_breached"])

        # 3. Breached: started 50 mins ago (exceeds breach=45)
        exc_breached = {
            "status": "OPEN",
            "started_at": (now - timedelta(minutes=50)).strftime("%Y-%m-%d %H:%M:%S"),
            "warning_threshold_mins": 30,
            "breach_threshold_mins": 45,
            "total_paused_duration_mins": 0
        }
        res_br = self.engine.calculate_timer_projection(exc_breached, now)
        self.assertEqual(res_br["timer_state"], "BREACHED")
        self.assertTrue(res_br["is_breached"])

        # 4. Unmeasurable: missing or malformed timestamp
        exc_unmeas = {
            "status": "OPEN",
            "started_at": None,
            "warning_threshold_mins": 30,
            "breach_threshold_mins": 45
        }
        res_un = self.engine.calculate_timer_projection(exc_unmeas, now)
        self.assertEqual(res_un["timer_state"], "UNMEASURABLE")

    # --------------------------------------------------------------------------
    # 4. Exception Lifecycle: Acknowledge, Start, Pause & Resume
    # --------------------------------------------------------------------------

    def test_05_pause_resume_accounting_and_reason_validation(self):
        """Test pause ledger, reason code enforcement, and due_at extension upon resume."""
        source_id = f"cont-{uuid.uuid4().hex[:6]}"
        exc = self.engine.detect_and_ingest_exception({
            "category": "follow_up",
            "source_entity": "care_continuity_tasks",
            "source_entity_id": source_id
        }, self.admin_ctx)

        eid = exc["id"]

        # Acknowledge
        ack = self.engine.acknowledge_exception(eid, self.admin_ctx)
        self.assertEqual(ack["status"], "ACKNOWLEDGED")

        # Start work
        in_prog = self.engine.start_work_on_exception(eid, self.admin_ctx)
        self.assertEqual(in_prog["status"], "IN_PROGRESS")

        # Attempt to pause with invalid reason code
        with self.assertRaises(ValidationError):
            self.engine.pause_exception(eid, "UNAUTHORIZED_VACATION", self.admin_ctx)

        # Pause with valid reason code: WAITING_PATIENT_RESPONSE
        paused = self.engine.pause_exception(eid, "WAITING_PATIENT_RESPONSE", self.admin_ctx, notes="Patient stepped out for prayer")
        self.assertEqual(paused["status"], "WAITING")
        self.assertEqual(paused["sla_state"], "PAUSED")
        self.assertEqual(len(paused["pause_intervals"]), 1)

        # Resume exception
        resumed = self.engine.resume_exception(eid, self.admin_ctx)
        self.assertEqual(resumed["status"], "IN_PROGRESS")
        self.assertGreaterEqual(resumed["total_paused_duration_mins"], 1)

    # --------------------------------------------------------------------------
    # 5. Multi-Stage Escalations
    # --------------------------------------------------------------------------

    def test_06_multi_stage_escalation_execution(self):
        """Test escalation matrix dispatch for breached exceptions with zero PHI."""
        # Create an exception that is already breached (started 2 hours ago for administrative SLA which has 45m breach)
        source_id = f"tok-esc-{uuid.uuid4().hex[:6]}"
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=150)).strftime("%Y-%m-%d %H:%M:%S")

        exc = self.engine.detect_and_ingest_exception({
            "category": "administrative",
            "source_entity": "queue_tokens",
            "source_entity_id": source_id,
            "started_at": past_time
        }, self.admin_ctx)

        eid = exc["id"]
        self.assertEqual(exc["sla_state"], "BREACHED")

        # Process escalations
        escalations = self.engine.process_escalations(eid, self.admin_ctx)
        self.assertGreaterEqual(len(escalations), 1)

        # Verify safe notification message (No PHI)
        first_esc = escalations[0]
        self.assertIn("[SLA BREACH ALERT]", first_esc["message"])
        self.assertIn(eid, first_esc["message"])

        # Running again should be idempotent (no duplicate stage dispatch)
        subsequent_esc = self.engine.process_escalations(eid, self.admin_ctx)
        self.assertEqual(len(subsequent_esc), 0)

    # --------------------------------------------------------------------------
    # 6. Resolution & Separation of Duties
    # --------------------------------------------------------------------------

    def test_07_resolution_and_separation_of_duties_verification(self):
        """Test resolution code check, and ensure resolver cannot verify their own work."""
        source_id = f"batch-verif-{uuid.uuid4().hex[:6]}"
        # Inventory policy (sla-pol-004) requires verification (verification_required = 1)
        exc = self.engine.detect_and_ingest_exception({
            "category": "inventory",
            "source_entity": "inventory_batches",
            "source_entity_id": source_id
        }, self.admin_ctx)

        eid = exc["id"]
        self.engine.acknowledge_exception(eid, self.admin_ctx)
        self.engine.start_work_on_exception(eid, self.admin_ctx)

        # Invalid resolution code rejected
        with self.assertRaises(ValidationError):
            self.engine.resolve_exception(eid, "MAGICALLY_SOLVED", "Notes", self.admin_ctx)

        # Resolve with allowed code by admin
        resolved = self.engine.resolve_exception(eid, "STOCK_RESTOCKED", "Emergency restock order received", self.admin_ctx)
        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertEqual(resolved["resolved_by"], self.admin_id)

        # SEPARATION OF DUTIES: Admin attempts to verify their own resolution -> FORBIDDEN
        with self.assertRaises(ForbiddenError):
            self.engine.verify_exception(eid, "Self verification attempt", self.admin_ctx)

        # Independent verification by secondary user -> SUCCESS
        verified = self.engine.verify_exception(eid, "Independent verification complete", self.verifier_ctx)
        self.assertEqual(verified["status"], "VERIFIED")
        self.assertEqual(verified["verified_by"], self.verifier_id)

    # --------------------------------------------------------------------------
    # 7. Dismissal & Reopening
    # --------------------------------------------------------------------------

    def test_08_dismissal_and_reopening_cycle(self):
        """Test dismissing an exception and reopening it."""
        source_id = f"dup-{uuid.uuid4().hex[:6]}"
        exc = self.engine.detect_and_ingest_exception({
            "category": "administrative",
            "source_entity": "queue_tokens",
            "source_entity_id": source_id
        }, self.admin_ctx)

        eid = exc["id"]

        # Dismiss exception
        dismissed = self.engine.dismiss_exception(eid, "Duplicate token created in error", self.admin_ctx)
        self.assertEqual(dismissed["status"], "DISMISSED")
        self.assertEqual(dismissed["sla_state"], "DISMISSED")

        # Reopen exception
        reopened = self.engine.reopen_exception(eid, "Token confirmed valid by front desk manager", self.admin_ctx)
        self.assertEqual(reopened["status"], "OPEN")
        self.assertEqual(reopened["reopened_by"], self.admin_id)

    # --------------------------------------------------------------------------
    # 8. Operational Monitor Summary Pulse
    # --------------------------------------------------------------------------

    def test_09_operational_monitor_summary_pulse(self):
        """Test SLA monitor summary aggregation and governance caveats."""
        summary = self.engine.get_sla_monitor_summary({}, self.admin_ctx)
        self.assertIn("active_policies_count", summary)
        self.assertIn("total_open_exceptions", summary)
        self.assertIn("on_track_count", summary)
        self.assertIn("breached_count", summary)
        self.assertIn("status_breakdown", summary)
        self.assertIn("caveats", summary)
        self.assertTrue(any("clinical" in c.lower() for c in summary["caveats"]))


if __name__ == "__main__":
    unittest.main()
