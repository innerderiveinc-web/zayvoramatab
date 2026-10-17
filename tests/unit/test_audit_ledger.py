"""Unit tests for Clinical Audit, Accountability, Compliance Evidence & Tamper-Evident Event Ledger.

Phase 29 validation for ZAYVORA MATAB OS.
Enforces non-negotiables:
1. Never fabricate audit events or verification results.
2. Record actual outcomes, not attempted UI clicks.
3. No silent editing or deletion of audit history (corrections appended as annotations).
4. Cryptographic tamper evidence: continuous SHA-256 hash chaining over canonical event serializations.
5. Separate clinical records from audit ledger; preserve exact entity versions and actors.
6. No secrets or full patient chart narratives in audit metadata (data minimization).
7. Fail-closed for consequential actions when audit commit cannot be secured.
"""

import os
import unittest
import tempfile
import sqlite3
import uuid
import json
from datetime import datetime

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.audit_ledger import ClinicalAuditLedgerEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestClinicalAuditLedgerEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_audit_ledger.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = ClinicalAuditLedgerEngine(cls.db_path)

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin = cur.fetchone()
        cls.admin_id = admin["id"]
        cls.org_id = admin["organization_id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        cls.fac_id = cur.fetchone()["id"]

        cur.execute("SELECT id FROM patients WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        cls.patient_id = cur.fetchone()["id"]

        conn.close()

        cls.admin_user = {
            "user_id": cls.admin_id,
            "roles": ["ORG_ADMIN"],
            "permissions": ["audit:read", "audit:record", "audit:verify", "audit:annotate", "audit:export", "audit:manage"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

        cls.hakeem_user = {
            "user_id": "usr-hakeem-1",
            "roles": ["PHYSICIAN_HAKEEM"],
            "permissions": ["audit:read", "audit:record", "audit:annotate"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

    # --------------------------------------------------------------------------
    # Test 1: Event Recording with Continuous Cryptographic Hash Chaining
    # --------------------------------------------------------------------------
    def test_record_event_cryptographic_hash_chaining(self):
        # 1. First event chains from GENESIS_HASH
        evt1 = self.engine.record_event({
            "event_code": "PRESCRIPTION_SIGN",
            "event_family": "prescription_lifecycle",
            "target_entity_type": "prescription",
            "target_entity_id": "rx-2026-001",
            "target_entity_version": "v1.0",
            "action": "SIGN_PRESCRIPTION_ELECTRONICALLY",
            "action_intent": "Formal clinical prescription signing",
            "result_state": "succeeded",
            "metadata": {"items_count": 3, "preflight_result": "PASS"}
        }, self.hakeem_user)

        self.assertTrue(evt1["ledger_sequence"] >= 1)
        self.assertIsNotNone(evt1["previous_event_hash"])
        self.assertIsNotNone(evt1["event_hash"])

        # Check genesis hash contract on sequence 1
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT previous_event_hash FROM clinical_ledger_events WHERE ledger_sequence = 1;")
        first_row = cur.fetchone()
        conn.close()
        if first_row:
            self.assertEqual(first_row[0], ClinicalAuditLedgerEngine.GENESIS_HASH)

        # 2. Second event chains from evt1.event_hash
        evt2 = self.engine.record_event({
            "event_code": "SAFETY_OVERRIDE",
            "event_family": "safety_override",
            "target_entity_type": "clinical_rule",
            "target_entity_id": "crule-allergy-001",
            "action": "OVERRIDE_SAFETY_WARNING",
            "action_intent": "Documented mild allergy override",
            "result_state": "succeeded",
            "metadata": {"override_rationale": "Patient previously tolerated processing without reaction"}
        }, self.hakeem_user)

        self.assertEqual(evt2["ledger_sequence"], evt1["ledger_sequence"] + 1)
        self.assertEqual(evt2["previous_event_hash"], evt1["event_hash"])
        self.assertIsNotNone(evt2["event_hash"])
        self.assertNotEqual(evt2["event_hash"], evt1["event_hash"])

    # --------------------------------------------------------------------------
    # Test 2: Data Minimization Sanitizes Secrets and Truncates Long Notes
    # --------------------------------------------------------------------------
    def test_data_minimization_sanitizes_secrets_and_long_chart_notes(self):
        massive_note = "A" * 3000
        evt = self.engine.record_event({
            "event_code": "CONSULTATION_NOTE_UPDATE",
            "event_family": "clinical_record_change",
            "target_entity_type": "encounter",
            "target_entity_id": "enc-test-001",
            "action": "UPDATE_CLINICAL_NOTE",
            "action_intent": "Consultation note edit",
            "result_state": "succeeded",
            "metadata": {
                "auth_token": "secret_bearer_token_xyz_123",
                "password": "super_secret_password",
                "chart_narrative": massive_note,
                "diagnoses_count": 2
            }
        }, self.hakeem_user)

        meta = evt["metadata"]
        self.assertEqual(meta["auth_token"], "[REDACTED_SECRET]")
        self.assertEqual(meta["password"], "[REDACTED_SECRET]")
        self.assertTrue(meta["chart_narrative"].endswith("... [TRUNCATED_CHART_TEXT]"))
        self.assertEqual(meta["diagnoses_count"], 2)

    # --------------------------------------------------------------------------
    # Test 3: Fail-Closed Protection for Gated Consequential Actions
    # --------------------------------------------------------------------------
    def test_fail_closed_blocks_consequential_action_when_audit_fails(self):
        # We simulate a broken DB constraint or invalid payload for a gated action
        with self.assertRaises(ValidationError):
            self.engine.record_event({
                "event_code": "PRESCRIPTION_SIGN",  # Gated action
                "event_family": "prescription_lifecycle",
                "target_entity_type": "prescription",
                "target_entity_id": "rx-fail-closed",
                "action": "SIGN_PRESCRIPTION",
                "action_intent": "Fail-closed test",
                "result_state": "INVALID_RESULT_STATE_XYZ",  # Triggers validation failure
            }, self.hakeem_user)

    # --------------------------------------------------------------------------
    # Test 4: Audit Annotations & Dispute Ledger (No Silent Edits)
    # --------------------------------------------------------------------------
    def test_audit_annotation_never_mutates_original_record(self):
        evt = self.engine.record_event({
            "event_code": "DATA_EXPORT",
            "event_family": "data_export",
            "target_entity_type": "patient",
            "target_entity_id": self.patient_id,
            "action": "EXPORT_PATIENT_RECORDS",
            "action_intent": "Referral record export",
            "result_state": "succeeded",
            "metadata": {"records_count": 5}
        }, self.hakeem_user)

        orig_hash = evt["event_hash"]

        # Append a dispute / correction annotation
        annot = self.engine.add_annotation(evt["event_id"], {
            "annotation_type": "EVENT_DISPUTED",
            "rationale": "Patient clarified export destination was intended for District Hospital, not private clinic.",
            "supporting_refs": ["REF-TICKET-9921"]
        }, self.admin_user)

        self.assertIsNotNone(annot["id"])
        self.assertEqual(annot["annotation_type"], "EVENT_DISPUTED")

        # Re-fetch original event: core record and event_hash must remain 100% UNCHANGED
        refetched = self.engine.get_event(evt["event_id"], self.admin_user)
        self.assertEqual(refetched["event_hash"], orig_hash)
        self.assertEqual(len(refetched["annotations"]), 1)
        self.assertEqual(refetched["annotations"][0]["annotation_type"], "EVENT_DISPUTED")

    # --------------------------------------------------------------------------
    # Test 5: Cryptographic Integrity Sweep Detects Valid Chain
    # --------------------------------------------------------------------------
    def test_integrity_verification_sweep_detects_valid_chain(self):
        report = self.engine.verify_integrity(user_ctx=self.admin_user)
        self.assertIsNotNone(report["checkpoint_id"])
        self.assertEqual(report["verification_result"], "passed_for_checked_scope")
        self.assertEqual(report["errors_count"], 0)
        self.assertIsNotNone(report["root_hash"])

    # --------------------------------------------------------------------------
    # Test 6: Integrity Verification Sweep Detects Payload Tampering
    # --------------------------------------------------------------------------
    def test_integrity_verification_sweep_detects_tampering(self):
        # Record a test event
        tamper_target = self.engine.record_event({
            "event_code": "BREAK_GLASS_ACCESS",
            "event_family": "break_glass_access",
            "target_entity_type": "patient",
            "target_entity_id": self.patient_id,
            "action": "EMERGENCY_ACCESS",
            "action_intent": "Tamper test event",
            "result_state": "succeeded",
            "metadata": {"duration_minutes": 15}
        }, self.admin_user)

        # Maliciously modify the action column in SQLite
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE clinical_ledger_events SET action = 'TAMPERED_ACTION_EDIT' WHERE event_id = ?;",
            (tamper_target["event_id"],)
        )
        conn.commit()
        conn.close()

        # Run integrity sweep -> Must detect payload tampering!
        sweep = self.engine.verify_integrity(user_ctx=self.admin_user)
        self.assertEqual(sweep["verification_result"], "failed_integrity_mismatch")
        self.assertTrue(sweep["errors_count"] > 0)
        tamper_errors = [e for e in sweep["errors"] if e["error_type"] == "PAYLOAD_TAMPERING_DETECTED"]
        self.assertTrue(len(tamper_errors) > 0)
        self.assertEqual(tamper_errors[0]["event_id"], tamper_target["event_id"])

        # Revert change to restore clean state for remaining tests
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE clinical_ledger_events SET action = 'EMERGENCY_ACCESS' WHERE event_id = ?;",
            (tamper_target["event_id"],)
        )
        conn.commit()
        conn.close()

    # --------------------------------------------------------------------------
    # Test 7: Integrity Verification Sweep Detects Sequence Gaps
    # --------------------------------------------------------------------------
    def test_integrity_verification_sweep_detects_sequence_gap(self):
        # Insert event with an artificial sequence jump
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT MAX(ledger_sequence) FROM clinical_ledger_events;")
        row = cur.fetchone()
        max_seq = (row[0] if row and row[0] is not None else 10)

        gap_seq = max_seq + 5  # Skipped 4 sequence numbers
        fake_id = f"evt-gap-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO clinical_ledger_events (
                event_id, event_schema_version, event_code, event_family,
                event_time, recorded_at, time_source, tenant_id, clinic_id,
                request_id, target_entity_type, target_entity_id,
                action, action_intent, result_state, metadata_json,
                previous_event_hash, event_hash, ledger_sequence, created_at, actor_type
            ) VALUES (
                ?, '1.0', 'GAP_TEST', 'test', '2026-10-14T00:00:00', '2026-10-14T00:00:00',
                'SERVER_NTP_UTC', 'org-1', 'fac-1', 'req-gap', 'entity', 'id',
                'GAP_ACTION', 'intent', 'succeeded', '{}', '0000', '1111', ?, '2026-10-14T00:00:00', 'human'
            );
            """,
            (fake_id, gap_seq),
        )
        conn.commit()
        conn.close()

        sweep = self.engine.verify_integrity(user_ctx=self.admin_user)
        self.assertEqual(sweep["verification_result"], "failed_integrity_mismatch")
        gap_errors = [e for e in sweep["errors"] if e["error_type"] == "SEQUENCE_GAP_OR_REORDER"]
        self.assertTrue(len(gap_errors) > 0)

        # Cleanup artificial gap row
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM clinical_ledger_events WHERE event_id = ?;", (fake_id,))
        conn.commit()
        conn.close()

    # --------------------------------------------------------------------------
    # Test 8: Governed Retention Policies & Legal Hold Lifecycle
    # --------------------------------------------------------------------------
    def test_retention_policy_listing_and_legal_hold_lifecycle(self):
        policies = self.engine.list_retention_policies(self.admin_user)
        self.assertTrue(len(policies) >= 3)
        codes = [p["policy_code"] for p in policies]
        self.assertIn("CLINICAL_STANDARD_7YR", codes)

        # Place legal hold
        hold = self.engine.place_legal_hold({
            "hold_code": "HOLD-LEGAL-2026-001",
            "title": "Litigation Hold - Clinical Audit Scope 2026",
            "reason": "Statutory compliance audit notice from state medical authority",
            "scope_filter": {"event_family": "prescription_lifecycle"}
        }, self.admin_user)

        self.assertEqual(hold["hold_code"], "HOLD-LEGAL-2026-001")
        self.assertEqual(hold["status"], "ACTIVE")

        # Release legal hold
        released = self.engine.release_legal_hold(hold["id"], {}, self.admin_user)
        self.assertEqual(released["status"], "RELEASED")
        self.assertIsNotNone(released["released_at"])

    # --------------------------------------------------------------------------
    # Test 9: Compliance Evidence Export Package Assembly
    # --------------------------------------------------------------------------
    def test_evidence_export_package_assembly_with_cryptographic_receipt(self):
        self.engine.record_event({
            "event_code": "PRESCRIPTION_SIGN",
            "event_family": "prescription_lifecycle",
            "target_entity_type": "prescription",
            "target_entity_id": "rx-export-test-01",
            "action": "SIGN_PRESCRIPTION_ELECTRONICALLY",
            "action_intent": "Export package test setup",
            "result_state": "succeeded",
            "metadata": {"items_count": 2}
        }, self.hakeem_user)

        export = self.engine.export_evidence_package({
            "purpose": "Accreditation and Statutory Compliance Review",
            "scope": {"event_family": "prescription_lifecycle"}
        }, self.admin_user)

        self.assertIsNotNone(export["export_number"])
        self.assertTrue(export["export_number"].startswith("EXP-"))
        self.assertIsNotNone(export["export_manifest_hash"])
        self.assertIsNotNone(export["verification_checkpoint_id"])
        self.assertTrue(export["total_events_exported"] >= 1)
        self.assertIsNotNone(export["export_artifact"]["root_hash"])


if __name__ == "__main__":
    unittest.main()
