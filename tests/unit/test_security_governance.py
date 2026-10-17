"""Unit tests for Enterprise Security, Privacy, Consent & Identity Access Governance Engine.

Phase 30 validation for ZAYVORA MATAB OS.
Enforces non-negotiables:
1. Never invent identity, credentials, or consent.
2. Authentication is not authorization; enforce RBAC and resource scoping.
3. Fail-closed for sensitive clinical actions when clinician credentials are unverified/suspended.
4. Purpose-specific patient consent with audited withdrawal.
5. Delegated temporary access with expiration.
6. Emergency break-glass access with time-limits and mandatory post-review.
7. Periodic role recertification review campaigns.
8. Cryptographic audit emission into Prompt 29's tamper-evident ledger.
"""

import os
import json
import uuid
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.security_governance import SecurityGovernanceEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, AuthenticationError
from apps.api.core.security import hash_password


class TestSecurityGovernanceEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_security_gov.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = SecurityGovernanceEngine(cls.db_path)

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

        # Create practitioner test user with known password
        cls.practitioner_id = f"usr-prac-{uuid.uuid4().hex[:8]}"
        pwd_hash = hash_password("practitioner123")
        cur.execute(
            """
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, ?, ?, ?, ?, 'Dr. Hakeem Aslam', 1);
            """,
            (cls.practitioner_id, cls.org_id, f"hakeem_{uuid.uuid4().hex[:4]}", "aslam@matab.local", pwd_hash),
        )
        conn.commit()
        conn.close()

        cls.admin_user = {
            "user_id": cls.admin_id,
            "roles": ["ORG_ADMIN"],
            "permissions": ["security:admin", "security:read", "security:credentials", "security:consent", "security:break_glass", "security:review", "security:policy"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

        cls.practitioner_user = {
            "user_id": cls.practitioner_id,
            "roles": ["PHYSICIAN_HAKEEM"],
            "permissions": ["security:read", "security:break_glass", "security:consent"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

    # --------------------------------------------------------------------------
    # Test 1: User Session Listing & Remote Revocation
    # --------------------------------------------------------------------------
    def test_user_session_listing_and_remote_revocation(self):
        token = f"tok-{uuid.uuid4().hex}"
        now = datetime.utcnow()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO user_sessions (
                id, token, user_id, organization_id, active_facility_id, ip_address,
                user_agent, device_fingerprint, expires_at, idle_timeout_at, is_revoked
            ) VALUES (?, ?, ?, ?, ?, '192.168.1.50', 'TestBrowser/1.0', 'fp-device-1', ?, ?, 0);
            """,
            (f"sess-{uuid.uuid4().hex[:8]}", token, self.practitioner_id, self.org_id, self.fac_id, (now + timedelta(hours=8)).isoformat(), (now + timedelta(minutes=30)).isoformat()),
        )
        conn.commit()
        conn.close()

        # List active sessions
        sessions = self.engine.list_user_sessions(self.practitioner_id, self.admin_user)
        self.assertTrue(len(sessions) >= 1)
        sess_id = sessions[0]["id"]
        self.assertEqual(sessions[0]["is_revoked"], 0)

        # Remote revocation
        rev_res = self.engine.revoke_session(sess_id, "Device suspected compromised", self.admin_user)
        self.assertEqual(rev_res["status"], "REVOKED")

        # Refetch: session should no longer be listed as active
        active = self.engine.list_user_sessions(self.practitioner_id, self.admin_user)
        matching = [s for s in active if s["id"] == sess_id]
        self.assertEqual(len(matching), 0)

    # --------------------------------------------------------------------------
    # Test 2: Step-Up Authentication Elevation & Failure
    # --------------------------------------------------------------------------
    def test_step_up_authentication_elevation_and_failure(self):
        token = f"tok-stepup-{uuid.uuid4().hex}"
        now = datetime.utcnow()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO user_sessions (
                id, token, user_id, organization_id, expires_at, idle_timeout_at, is_revoked
            ) VALUES (?, ?, ?, ?, ?, ?, 0);
            """,
            (f"sess-{uuid.uuid4().hex[:8]}", token, self.practitioner_id, self.org_id, (now + timedelta(hours=8)).isoformat(), (now + timedelta(minutes=30)).isoformat()),
        )
        conn.commit()
        conn.close()

        # Failed step-up with bad password
        with self.assertRaises(AuthenticationError):
            self.engine.verify_step_up(token, "wrong_password_xyz", "CLINICAL_SIGNING", self.practitioner_user)

        # Successful step-up with correct password
        elevated = self.engine.verify_step_up(token, "practitioner123", "CLINICAL_SIGNING", self.practitioner_user)
        self.assertTrue(elevated["step_up_verified"])
        self.assertEqual(elevated["scope"], "CLINICAL_SIGNING")
        self.assertIsNotNone(elevated["valid_until"])

    # --------------------------------------------------------------------------
    # Test 3: Clinician Credential Registry, Verification & Suspension
    # --------------------------------------------------------------------------
    def test_clinician_credential_lifecycle_and_fail_closed_gate(self):
        # 1. Register pending credential
        cred = self.engine.register_credential({
            "practitioner_user_id": self.practitioner_id,
            "credential_type": "BUMS",
            "registration_number": "UP-UNANI-2026-9041",
            "issuing_council": "Board of Ayurvedic and Unani Systems of Medicine, UP",
            "jurisdiction": "INDIA",
            "effective_date": "2020-01-01",
            "expiry_date": "2030-12-31",
            "approved_scope": "FULL_CLINICAL_UNANI"
        }, self.admin_user)

        self.assertEqual(cred["verification_status"], "pending")

        # Gatekeeper blocks unverified practitioner
        with self.assertRaises(ForbiddenError):
            self.engine.assert_practitioner_credential_valid(self.practitioner_id)

        # 2. Formally verify credential
        verified = self.engine.verify_credential(cred["id"], {
            "verification_source": "STATE_COUNCIL_PORTAL",
            "evidence_reference": "DOC-VERIF-AUDIT-2026-01"
        }, self.admin_user)

        self.assertEqual(verified["verification_status"], "verified")
        # Now gatekeeper passes
        self.engine.assert_practitioner_credential_valid(self.practitioner_id)

        # 3. Suspend credential -> Fails closed immediately
        suspended = self.engine.suspend_credential(cred["id"], "Disciplinary inquiry ongoing", self.admin_user)
        self.assertEqual(suspended["verification_status"], "suspended")

        with self.assertRaises(ForbiddenError):
            self.engine.assert_practitioner_credential_valid(self.practitioner_id)

    # --------------------------------------------------------------------------
    # Test 4: Purpose-Specific Patient Consent & Governed Withdrawal
    # --------------------------------------------------------------------------
    def test_purpose_specific_patient_consent_and_withdrawal(self):
        # 1. Record granted consent
        cns = self.engine.record_consent_event({
            "patient_id": self.patient_id,
            "consent_type": "DATA_SHARING_REFERRAL",
            "purpose_code": "EXTERNAL_SPECIALIST_CONSULTATION",
            "granting_party_type": "PATIENT_DIRECT",
            "data_categories": ["demographics", "clinical_notes", "prescriptions"],
            "recipient_scope": "DISTRICT_AYUSH_HOSPITAL"
        }, self.admin_user)

        self.assertEqual(cns["status"], "granted")
        self.assertTrue(self.engine.check_consent_allowance(self.patient_id, "DATA_SHARING_REFERRAL", "EXTERNAL_SPECIALIST_CONSULTATION"))

        # Checking unconsented purpose returns False
        self.assertFalse(self.engine.check_consent_allowance(self.patient_id, "RESEARCH_OBSERVATIONAL", "PUBLIC_HEALTH_STUDY"))

        # 2. Withdraw consent
        withdrawn = self.engine.withdraw_consent(cns["id"], {
            "reason": "Patient decided to manage referral privately"
        }, self.admin_user)

        self.assertEqual(withdrawn["status"], "withdrawn")
        self.assertIsNotNone(withdrawn["withdrawn_at"])

        # Allowance is now False
        self.assertFalse(self.engine.check_consent_allowance(self.patient_id, "DATA_SHARING_REFERRAL", "EXTERNAL_SPECIALIST_CONSULTATION"))

    # --------------------------------------------------------------------------
    # Test 5: Delegated Temporary Access Lifecycle
    # --------------------------------------------------------------------------
    def test_delegated_temporary_access_lifecycle(self):
        now = datetime.utcnow()
        grant = self.engine.grant_delegated_access({
            "delegatee_user_id": self.practitioner_id,
            "target_resource_type": "PATIENT",
            "target_resource_id": self.patient_id,
            "allowed_actions": ["read", "create_draft"],
            "purpose": "Covering cross-consultation while primary Hakeem is on leave",
            "expires_at": (now + timedelta(days=2)).isoformat()
        }, self.admin_user)

        self.assertEqual(grant["status"], "ACTIVE")

        # Revoke grant early
        rev = self.engine.revoke_delegated_access(grant["id"], "Primary Hakeem resumed duty early", self.admin_user)
        self.assertEqual(rev["status"], "REVOKED")
        self.assertIsNotNone(rev["revoked_at"])

    # --------------------------------------------------------------------------
    # Test 6: Emergency Break-Glass Access & Mandatory Post-Review
    # --------------------------------------------------------------------------
    def test_emergency_break_glass_access_and_mandatory_post_review(self):
        bg = self.engine.request_break_glass({
            "patient_id": self.patient_id,
            "reason_code": "ACUTE_LIFE_THREATENING_EMERGENCY",
            "rationale": "Patient presented unresponsive with suspected severe allergic reaction, consent unobtainable",
            "duration_minutes": 45
        }, self.practitioner_user)

        self.assertEqual(bg["status"], "ACTIVE")
        self.assertEqual(bg["patient_id"], self.patient_id)

        # Log access to resource
        self.engine.record_break_glass_access(bg["id"], f"rx-{self.patient_id}", "READ_PRESCRIPTION_HISTORY")
        fetched = self.engine.get_break_glass_event(bg["id"], self.admin_user)
        self.assertEqual(fetched["access_count"], 1)
        self.assertEqual(len(fetched["accessed_resources"]), 1)

        # Mandatory Post-Access Review
        reviewed = self.engine.review_break_glass(bg["id"], {
            "decision": "REVIEWED_JUSTIFIED",
            "notes": "Emergency access verified with ICU admission documentation"
        }, self.admin_user)

        self.assertEqual(reviewed["status"], "REVIEWED_JUSTIFIED")
        self.assertEqual(reviewed["post_review_decision"], "REVIEWED_JUSTIFIED")

    # --------------------------------------------------------------------------
    # Test 7: Access Review Campaigns & Decisions (Periodic Recertification)
    # --------------------------------------------------------------------------
    def test_access_review_campaign_and_recertification(self):
        camp = self.engine.create_review_campaign({
            "campaign_code": f"RECERT-Q4-{uuid.uuid4().hex[:6].upper()}",
            "title": "Q4 Privileged Access Recertification",
            "scope_type": "PRIVILEGED_ADMINS",
            "due_date": "2026-11-30"
        }, self.admin_user)

        self.assertEqual(camp["status"], "ACTIVE")

        # Record review decision
        dec = self.engine.record_review_decision(camp["id"], {
            "subject_user_id": self.practitioner_id,
            "role_or_permission": "PHYSICIAN_HAKEEM",
            "decision": "RETAIN",
            "rationale": "Active verified physician license, clinical duties confirmed"
        }, self.admin_user)

        self.assertEqual(dec["decision"], "RETAIN")
        self.assertEqual(dec["remediation_status"], "PENDING")

    # --------------------------------------------------------------------------
    # Test 8: Versioned Security Policy Registry & Deny Precedence
    # --------------------------------------------------------------------------
    def test_versioned_security_policy_registry_evaluation(self):
        pol = self.engine.create_security_policy({
            "policy_code": f"POL-DENY-EXPORT-{uuid.uuid4().hex[:6].upper()}",
            "title": "Block Unapproved Bulk Export of Patient Records",
            "resource_type": "patient_records",
            "action": "BULK_EXPORT",
            "effect": "DENY",
            "priority": 10,
            "reason_code": "BULK_EXPORT_DISALLOWED_OUTSIDE_COMPLIANCE_OFFICE"
        }, self.admin_user)

        self.assertEqual(pol["effect"], "DENY")

        allowed, reason = self.engine.evaluate_security_policy("patient_records", "BULK_EXPORT", {})
        self.assertFalse(allowed)
        self.assertEqual(reason, "BULK_EXPORT_DISALLOWED_OUTSIDE_COMPLIANCE_OFFICE")

    # --------------------------------------------------------------------------
    # Test 9: Cryptographic Audit Ledger Integration (Prompt 29 Chaining)
    # --------------------------------------------------------------------------
    def test_audit_ledger_cryptographic_integration(self):
        # Trigger an action in security governance
        cns = self.engine.record_consent_event({
            "patient_id": self.patient_id,
            "consent_type": "TELECONSULTATION",
            "purpose_code": "VIDEO_CALL_CLINICAL_ASSESSMENT",
            "granting_party_type": "PATIENT_DIRECT"
        }, self.admin_user)

        # Query Prompt 29 ledger
        events = self.engine.audit_engine.query_ledger({
            "event_family": "consent_governance",
            "target_entity_id": cns["id"]
        }, self.admin_user)

        self.assertTrue(len(events) >= 1)
        evt = events[0]
        self.assertEqual(evt["event_code"], "CONSENT_RECORDED")
        self.assertIsNotNone(evt["event_hash"])
        self.assertTrue(evt["ledger_sequence"] >= 1)


if __name__ == "__main__":
    unittest.main()
