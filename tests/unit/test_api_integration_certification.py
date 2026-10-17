"""Unit Tests for API & Integration Certification, Contract Testing & Developer Governance Engine.

Phase 52 Verification Suite for ZAYVORA MATAB OS.
"""

import hashlib
import hmac
import json
import sqlite3
import time
import unittest
from datetime import datetime, timezone

from apps.api.domains.api_integration_certification_engine import ApiIntegrationCertificationEngine
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
    AuthenticationError,
)


class TestApiIntegrationCertificationEngine(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self._apply_migrations()
        self.engine = ApiIntegrationCertificationEngine(self.conn)

    def tearDown(self):
        self.conn.close()

    def _apply_migrations(self):
        cursor = self.conn.cursor()
        # Minimal tables for migration 050
        with open("apps/api/database/migrations/050_enterprise_api_integration_certification_developer_governance_schema.sql") as f:
            cursor.executescript(f.read())
        self.conn.commit()

    def test_integrations_catalog_listing_and_registration(self):
        """Test listing seeded integrations and registering a new provider."""
        integrations = self.engine.list_integrations("T-001")
        self.assertGreaterEqual(len(integrations), 7)
        ids = {i["integration_id"] for i in integrations}
        self.assertIn("INT-CORE-CLINICAL", ids)
        self.assertIn("INT-ABDM-GW", ids)

        # Register custom laboratory integration
        new_int = self.engine.register_integration(
            tenant_id="T-001",
            data={
                "integration_id": "INT-LAB-EXTERNAL",
                "title": "Central Pathology Laboratory LIS",
                "category": "INTERNAL_SERVICE",
                "direction": "BIDIRECTIONAL",
                "provider_name": "PathCare Systems",
                "auth_type": "MUTUAL_TLS",
                "data_classification": "RESTRICTED_PHI",
                "rate_limit_rpm": 100,
                "timeout_ms": 6000,
            },
            actor_id="USER-ARCH-1",
        )
        self.assertEqual(new_int["integration_id"], "INT-LAB-EXTERNAL")
        self.assertEqual(new_int["certification_level"], "CONTRACT_DEFINED")

    def test_contract_definition_and_drift_detection(self):
        """Test registering endpoint contract definitions and detecting route drift."""
        contract = self.engine.register_contract(
            data={
                "contract_id": "CTR-PATIENTS-GET",
                "integration_id": "INT-CORE-CLINICAL",
                "endpoint_path": "/api/v1/patients",
                "http_method": "GET",
                "summary": "List patients with filter",
                "required_scopes": ["patients:read"],
                "is_idempotent": True,
            },
            actor_id="USER-ARCH-1",
        )
        self.assertEqual(contract["contract_id"], "CTR-PATIENTS-GET")

        # Mock runtime routes to test drift detector
        runtime_routes = [
            ("GET", r"^/api/v1/patients$", None, True),
            ("POST", r"^/api/v1/encounters$", None, True),
            ("GET", r"^/api/v1/undocumented-route$", None, True),
        ]
        drift_report = self.engine.detect_contract_drift(runtime_routes)
        self.assertEqual(drift_report["total_runtime_routes"], 3)
        self.assertGreaterEqual(drift_report["documented_contracts"], 1)
        self.assertTrue(drift_report["drift_detected"])

    def test_developer_api_key_lifecycle(self):
        """Test API Key generation, hashing, authentication, and revocation."""
        key_res = self.engine.generate_api_key(
            tenant_id="T-001",
            client_name="Mobile EHR Client",
            environment="SANDBOX",
            allowed_scopes=["encounters:read", "prescriptions:read"],
            rate_limit_rpm=60,
            allowed_ips=["192.0.2.1"],
            created_by="ADMIN-1",
        )
        raw_key = key_res["raw_key"]
        self.assertTrue(raw_key.startswith("ak_test_"))
        key_id = key_res["key_id"]

        # Authenticate with valid key and valid IP
        auth_ctx = self.engine.authenticate_api_key(raw_key, client_ip="192.0.2.1")
        self.assertEqual(auth_ctx["key_id"], key_id)
        self.assertEqual(auth_ctx["tenant_id"], "T-001")
        self.assertIn("encounters:read", auth_ctx["allowed_scopes"])

        # Authenticate with unpermitted IP -> ForbiddenError
        with self.assertRaises(ForbiddenError):
            self.engine.authenticate_api_key(raw_key, client_ip="203.0.113.99")

        # Revoke key
        rev_res = self.engine.revoke_api_key(key_id, actor_id="ADMIN-1", reason="Security rotation")
        self.assertEqual(rev_res["status"], "REVOKED")

        # Authenticate with revoked key -> AuthenticationError
        with self.assertRaises(AuthenticationError):
            self.engine.authenticate_api_key(raw_key, client_ip="192.0.2.1")

    def test_idempotency_engine(self):
        """Test strict idempotency caching and conflict detection on modified payload."""
        payload_1 = {"patient_id": "P-100", "encounter_type": "OPD"}
        endpoint = "/api/v1/encounters"
        key = "idem-req-999"

        # First call: cache miss
        miss = self.engine.check_or_set_idempotency("T-001", key, endpoint, payload_1)
        self.assertFalse(miss["cached"])

        # Store response
        self.engine.store_idempotency_result(
            tenant_id="T-001",
            idempotency_key=key,
            endpoint_path=endpoint,
            request_payload=payload_1,
            status_code=201,
            response_body={"encounter_id": "ENC-001", "status": "ACTIVE"},
        )

        # Second call with identical payload: cache hit
        hit = self.engine.check_or_set_idempotency("T-001", key, endpoint, payload_1)
        self.assertTrue(hit["cached"])
        self.assertEqual(hit["status_code"], 201)
        self.assertEqual(hit["response_body"]["encounter_id"], "ENC-001")

        # Third call with DIFFERENT payload using same key -> ConflictError
        payload_2 = {"patient_id": "P-100", "encounter_type": "TELEMEDICINE"}
        with self.assertRaises(ConflictError):
            self.engine.check_or_set_idempotency("T-001", key, endpoint, payload_2)

    def test_inbound_webhook_verification_and_replay_protection(self):
        """Test HMAC verification, replay deduplication, and timestamp expiration."""
        secret = "secret_payment_webhook_token"
        raw_body = b'{"event": "payment.captured", "amount": 5000}'
        sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        event_id = "evt_pay_1001"

        # 1. Valid signature and current timestamp
        now_ts = str(int(time.time()))
        res1 = self.engine.verify_inbound_webhook(
            tenant_id="T-001",
            provider="RAZORPAY",
            raw_payload_bytes=raw_body,
            signature_header=sig,
            timestamp_header=now_ts,
            secret_token=secret,
            event_id=event_id,
        )
        self.assertTrue(res1["verified"])
        self.assertEqual(res1["status"], "VERIFIED")

        # 2. Replay of same event_id -> REPLAY_DUPLICATE
        res_replay = self.engine.verify_inbound_webhook(
            tenant_id="T-001",
            provider="RAZORPAY",
            raw_payload_bytes=raw_body,
            signature_header=sig,
            timestamp_header=now_ts,
            secret_token=secret,
            event_id=event_id,
        )
        self.assertFalse(res_replay["verified"])
        self.assertEqual(res_replay["status"], "REPLAY_DUPLICATE")

        # 3. Expired timestamp (> 300s skew)
        old_ts = str(int(time.time()) - 400)
        res_expired = self.engine.verify_inbound_webhook(
            tenant_id="T-001",
            provider="RAZORPAY",
            raw_payload_bytes=raw_body,
            signature_header=sig,
            timestamp_header=old_ts,
            secret_token=secret,
            event_id="evt_pay_1002",
        )
        self.assertFalse(res_expired["verified"])
        self.assertEqual(res_expired["status"], "EXPIRED_TIMESTAMP")

    def test_outbound_webhook_ssrf_shield(self):
        """Test SSRF protection blocking loopback and private RFC 1918 destination IP addresses."""
        # 1. Loopback blocked
        with self.assertRaises(ValidationError):
            self.engine.validate_target_url_ssrf("http://127.0.0.1:8080/webhook")

        # 2. Link-local cloud metadata blocked
        with self.assertRaises(ValidationError):
            self.engine.validate_target_url_ssrf("http://169.254.169.254/latest/meta-data")

        # 3. Insecure HTTP rejected in production mode
        with self.assertRaises(ValidationError):
            self.engine.validate_target_url_ssrf("http://example.com/webhook", allow_test_local=False)

        # 4. Valid HTTPS passes SSRF validation
        self.engine.validate_target_url_ssrf("https://api.external-clinic.org/events", allow_test_local=True)

        # Create subscription and test dispatch
        sub = self.engine.create_webhook_subscription(
            tenant_id="T-001",
            target_url="https://api.external-clinic.org/events",
            event_types=["encounter.finalized"],
            secret_token="sub_secret_token",
            actor_id="USER-ADMIN",
            allow_test_local=True,
        )
        self.assertEqual(sub["target_url"], "https://api.external-clinic.org/events")

        deliv = self.engine.dispatch_outbound_webhook(
            subscription_id=sub["subscription_id"],
            event_id="EVT-101",
            event_type="encounter.finalized",
            payload={"patient_id": "P-01"},
            signing_secret="sub_secret_token",
            allow_test_local=True,
        )
        self.assertEqual(deliv["status"], "DELIVERED")

    def test_integration_certification_role_gating(self):
        """Test certification of an integration requiring authorized clinical/architect role."""
        # Unprivileged role (NURSE) rejected -> ForbiddenError
        with self.assertRaises(ForbiddenError):
            self.engine.certify_integration(
                integration_id="INT-CORE-CLINICAL",
                certification_level="CONTRACT_TESTED",
                evidence_summary="Verified in unit and API integration suites",
                certified_by="USER-NURSE",
                certified_by_role="NURSE",
            )

        # Authorized role (CLINICAL_SAFETY_OFFICER) succeeds
        cert = self.engine.certify_integration(
            integration_id="INT-CORE-CLINICAL",
            certification_level="CONTRACT_TESTED",
            evidence_summary="Verified against OpenAPI schema and negative auth tests",
            certified_by="USER-CSO-1",
            certified_by_role="CLINICAL_SAFETY_OFFICER",
            valid_days=365,
        )
        self.assertEqual(cert["certification_level"], "CONTRACT_TESTED")
        self.assertEqual(cert["status"], "ACTIVE")

        # Verify catalog updated
        int_obj = self.engine.get_integration("INT-CORE-CLINICAL")
        self.assertEqual(int_obj["certification_level"], "CONTRACT_TESTED")

    def test_sha256_audit_ledger_integrity(self):
        """Test cryptographic hash chain verification and tamper detection."""
        # 1. Clean verification
        report = self.engine.verify_audit_ledger_integrity()
        self.assertTrue(report["verified"])
        self.assertEqual(report["status"], "CHAIN_INTEGRITY_VERIFIED")

        # 2. Tamper injection
        cursor = self.conn.cursor()
        cursor.execute("UPDATE api_developer_governance_ledger SET payload_json = '{\"tampered\": true}' WHERE sequence_number = 1")
        self.conn.commit()

        tamper_report = self.engine.verify_audit_ledger_integrity()
        # Genesis block or chain will detect mismatch
        self.assertTrue(tamper_report.get("tamper_detected") or not tamper_report["verified"])


if __name__ == "__main__":
    unittest.main()
