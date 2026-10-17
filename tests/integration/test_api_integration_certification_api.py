"""Integration Tests for API & Integration Certification, Contract Testing & Developer Governance REST APIs.

Phase 52 Verification Suite for ZAYVORA MATAB OS.
Mounted under `/api/v1/api-governance/`.
"""

import hashlib
import hmac
import json
import os
import shutil
import tempfile
import time
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestApiIntegrationCertificationApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_api_gov.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        assert status == 200, f"Admin login failed: {body}"
        admin_data = json.loads(body.decode("utf-8"))
        cls.admin_token = admin_data["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}",
        }

        # Authenticate Receptionist (unprivileged for developer key / certification management)
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        assert status == 200, f"Reception login failed: {body}"
        nurse_data = json.loads(body.decode("utf-8"))
        cls.nurse_token = nurse_data["token"]
        cls.nurse_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.nurse_token}",
        }


    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_list_integrations_catalog(self):
        """1. GET /api/v1/api-governance/integrations - List registered integrations."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/api-governance/integrations",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 7)

    def test_02_register_integration_and_rbac(self):
        """2. POST /api/v1/api-governance/integrations - Register integration with RBAC check."""
        payload = {
            "integration_id": "INT-TELEMED-ZOOM",
            "title": "HIPAA Video Telemedicine Gateway",
            "category": "INTERNAL_SERVICE",
            "direction": "BIDIRECTIONAL",
            "provider_name": "Zoom Healthcare",
            "auth_type": "BEARER_JWT",
            "data_classification": "RESTRICTED_PHI",
            "rate_limit_rpm": 120,
            "timeout_ms": 5000,
        }

        # Unprivileged nurse cannot register integrations -> 403 Forbidden
        status, _, _ = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/integrations",
            self.nurse_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 403)

        # Admin can register integration -> 201 Created
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/integrations",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["integration"]["integration_id"], "INT-TELEMED-ZOOM")

    def test_03_contract_definitions_and_drift_check(self):
        """3. GET/POST /api/v1/api-governance/contracts and drift-check."""
        # List contracts
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/api-governance/contracts",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(data["count"], 2)

        # Register new contract
        contract_payload = {
            "integration_id": "INT-CORE-CLINICAL",
            "endpoint_path": "/api/v1/patients",
            "http_method": "POST",
            "summary": "Register new clinical patient",
            "required_scopes": ["patients:write"],
            "is_idempotent": True,
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/contracts",
            self.admin_headers,
            {},
            json.dumps(contract_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)

        # Trigger drift check
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/drift-check",
            self.admin_headers,
            {},
            b"{}",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("drift_report", data)
        self.assertGreater(data["drift_report"]["total_runtime_routes"], 50)

    def test_04_developer_api_keys_lifecycle(self):
        """4. POST/GET/DELETE /api/v1/api-governance/keys - API Key generation, listing, and revocation."""
        key_payload = {
            "client_name": "Integration Partner Portal",
            "environment": "SANDBOX",
            "allowed_scopes": ["encounters:read", "prescriptions:read"],
            "rate_limit_rpm": 60,
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/keys",
            self.admin_headers,
            {},
            json.dumps(key_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        key_obj = data["key"]
        self.assertTrue(key_obj["raw_key"].startswith("ak_test_"))
        key_id = key_obj["key_id"]

        # List keys
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/api-governance/keys",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        keys_list = json.loads(body.decode("utf-8"))["keys"]
        self.assertTrue(any(k["key_id"] == key_id for k in keys_list))

        # Revoke key
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/api-governance/keys/{key_id}/revoke",
            self.admin_headers,
            {},
            json.dumps({"reason": "Test lifecycle cleanup"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["result"]["status"], "REVOKED")

    def test_05_idempotency_check_api(self):
        """5. POST /api/v1/api-governance/idempotency/check - Idempotency verification seam."""
        payload = {
            "idempotency_key": "api-idem-test-001",
            "endpoint_path": "/api/v1/encounters",
            "payload": {"patient_id": "P-99", "type": "OPD"},
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/idempotency/check",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertFalse(data["idempotency_status"]["cached"])

    def test_06_inbound_webhook_verification_api(self):
        """6. POST /api/v1/api-governance/webhooks/verify-inbound - Inbound HMAC verification."""
        secret = "gateway_wh_secret"
        payload_str = '{"event": "payment.authorized", "id": "pay_123"}'
        sig = hmac.new(secret.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()

        verify_payload = {
            "provider": "RAZORPAY",
            "payload_str": payload_str,
            "signature_header": sig,
            "secret_token": secret,
            "event_id": "evt_api_test_01",
            "timestamp_header": str(int(time.time())),
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/webhooks/verify-inbound",
            self.admin_headers,
            {},
            json.dumps(verify_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["verification"]["verified"])
        self.assertEqual(data["verification"]["status"], "VERIFIED")

    def test_07_outbound_webhook_and_ssrf_protection_api(self):
        """7. POST /api/v1/api-governance/webhooks/subscriptions - Outbound webhook & SSRF validation."""
        # SSRF Attempt: private loopback destination blocked -> 400 Bad Request
        ssrf_payload = {
            "target_url": "http://127.0.0.1:8000/internal-api",
            "event_types": ["encounter.finalized"],
            "allow_test_local": False,
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/webhooks/subscriptions",
            self.admin_headers,
            {},
            json.dumps(ssrf_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 400)

        # Valid HTTPS Subscription (in test mode) -> 201 Created
        valid_payload = {
            "target_url": "https://api.external-health.org/webhook",
            "event_types": ["encounter.finalized", "prescription.signed"],
            "allow_test_local": True,
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/webhooks/subscriptions",
            self.admin_headers,
            {},
            json.dumps(valid_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        sub_id = json.loads(body.decode("utf-8"))["subscription"]["subscription_id"]

        # Test Dispatch
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/api-governance/webhooks/subscriptions/{sub_id}/dispatch",
            self.admin_headers,
            {},
            json.dumps({"payload": {"test": "data"}, "allow_test_local": True}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["delivery"]["status"], "DELIVERED")

    def test_08_certify_integration_lifecycle_api(self):
        """8. POST /api/v1/api-governance/certify - Certify integration with audit trail."""
        cert_payload = {
            "integration_id": "INT-ABDM-GW",
            "certification_level": "MOCK_TESTED",
            "evidence_summary": "Passed ABDM milestone M1/M2/M3 synthetic sandbox verification tests.",
            "valid_days": 180,
            "test_suite_run_id": "RUN-2026-10-15-01",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/api-governance/certify",
            self.admin_headers,
            {},
            json.dumps(cert_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["certification"]["certification_level"], "MOCK_TESTED")

        # List certifications
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/api-governance/certifications",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        certs = json.loads(body.decode("utf-8"))["certifications"]
        self.assertTrue(any(c["integration_id"] == "INT-ABDM-GW" for c in certs))

    def test_09_verify_audit_ledger_api(self):
        """9. GET /api/v1/api-governance/audit-ledger/verify - Cryptographic SHA-256 chain verification."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/api-governance/audit-ledger/verify",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["ledger_report"]["verified"])
        self.assertEqual(data["ledger_report"]["status"], "CHAIN_INTEGRITY_VERIFIED")


if __name__ == "__main__":
    unittest.main()
