"""Integration tests for Enterprise Interoperability, FHIR APIs & ABDM Integration REST APIs.

Phase 31 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Specification registry APIs (GET/POST /api/v1/interop/specifications)
2. Unani terminology safe mappings (GET/POST /api/v1/interop/terminology)
3. FHIR R4 DocumentBundle export (POST /api/v1/interop/fhir/export-encounter)
4. ABDM M1 Identity verification & linking (POST /api/v1/interop/abdm/verify-identity, link-patient)
5. ABDM M2 HIP Care context discovery & notification (GET/POST /api/v1/interop/abdm/care-contexts)
6. ABDM M3 HIU Consent request, callback, scope gate & revocation (POST /api/v1/interop/abdm/consent-requests)
7. ABDM M4 Registries verification (POST /api/v1/interop/abdm/verify-hfr, verify-hpr)
8. Inbound record staging & clinician reconciliation queue (POST /api/v1/interop/inbound/stage, GET queue, POST reconcile)
9. Durable integration outbox & dispatch (POST/GET /api/v1/interop/outbox/*)
10. Inbound webhook verification & replay protection (POST /api/v1/interop/webhooks/verify)
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
from apps.api.router import ApiRouter


class TestEnterpriseInteroperabilityApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_interop_api.db")
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
        cls.auth_token = json.loads(body)["token"]

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin_row = cur.fetchone()
        cls.admin_id = admin_row["id"]
        cls.org_id = admin_row["organization_id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        fac_row = cur.fetchone()
        cls.fac_id = fac_row["id"] if fac_row else "fac-default"

        cur.execute("SELECT id FROM patients WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        pat_row = cur.fetchone()
        cls.patient_id = pat_row["id"]

        # Ensure encounter exists
        cur.execute("SELECT id FROM encounters WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        enc_row = cur.fetchone()
        if enc_row:
            cls.encounter_id = enc_row["id"]
        else:
            cls.encounter_id = f"enc-{uuid.uuid4().hex[:8]}"
            cur.execute(
                """
                INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, encounter_type)
                VALUES (?, ?, ?, ?, ?, 'SIGNED', 'OPD');
                """,
                (cls.encounter_id, cls.org_id, cls.fac_id, cls.patient_id, cls.admin_id),
            )
            conn.commit()

        # Add clinical problem
        cur.execute("SELECT id FROM modern_clinical_assessments WHERE encounter_id = ? LIMIT 1;", (cls.encounter_id,))
        assess_row = cur.fetchone()
        if assess_row:
            assess_id = assess_row["id"]
        else:
            assess_id = f"mca-{uuid.uuid4().hex[:8]}"
            cur.execute(
                """
                INSERT INTO modern_clinical_assessments (id, organization_id, facility_id, patient_id, encounter_id, author_id, status, assessment_date)
                VALUES (?, ?, ?, ?, ?, ?, 'SIGNED', CURRENT_TIMESTAMP);
                """,
                (assess_id, cls.org_id, cls.fac_id, cls.patient_id, cls.encounter_id, cls.admin_id),
            )

        cur.execute(
            """
            INSERT INTO clinical_problems (
                id, organization_id, patient_id, encounter_id, assessment_id,
                problem_title, code_system, code_value, coding_status, status, is_primary, recorded_by
            ) VALUES (?, ?, ?, ?, ?, 'Su-e-Mizaj Har Maddi', 'SNOMED-CT', '386661006', 'CONFIRMED_CODED', 'CONFIRMED', 1, ?);
            """,
            (f"prob-{uuid.uuid4().hex[:8]}", cls.org_id, cls.patient_id, cls.encounter_id, assess_id, cls.admin_id),
        )
        conn.commit()
        conn.close()

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "x-facility-id": self.fac_id,
        }

    def _call(self, method: str, path: str, body: dict = None, query: dict = None):
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        status, headers, resp_bytes = ApiRouter.dispatch(
            method, path, self._headers(), query or {}, body_bytes, "127.0.0.1", self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8"))

    def test_01_specifications_api(self):
        """GET & POST /api/v1/interop/specifications"""
        status, data = self._call("GET", "/api/v1/interop/specifications")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total"], 6)

        # Register new specification
        spec_payload = {
            "spec_code": "REFERRAL_FHIR_PROFILE",
            "spec_name": "Inter-Hospital Referral FHIR Profile",
            "canonical_url": "https://zayvora.internal/profiles/referral",
            "package_id": "zayvora.interop.referral",
            "pinned_version": "1.0.0",
        }
        s2, d2 = self._call("POST", "/api/v1/interop/specifications", body=spec_payload)
        self.assertEqual(s2, 201)
        self.assertEqual(d2["status"], "active")

        # Deprecate specification
        s3, d3 = self._call(
            "POST",
            "/api/v1/interop/specifications/deprecate",
            body={"spec_code": "REFERRAL_FHIR_PROFILE", "pinned_version": "1.0.0"},
        )
        self.assertEqual(s3, 200)
        self.assertEqual(d3["status"], "deprecated")

    def test_02_terminology_api(self):
        """GET & POST /api/v1/interop/terminology"""
        map_payload = {
            "concept_domain": "UNANI_AKHLAT",
            "internal_code": "KHLIT_SAFRA",
            "internal_display": "Yellow Bile (Safra)",
            "target_system_uri": "http://snomed.info/sct",
            "mapping_state": "no_safe_mapping",
            "clinical_rationale": "Classical humor has no standard SNOMED CT clinical equivalent.",
        }
        status, data = self._call("POST", "/api/v1/interop/terminology", body=map_payload)
        self.assertEqual(status, 200)
        self.assertEqual(data["mapping_state"], "no_safe_mapping")

        s2, d2 = self._call("GET", "/api/v1/interop/terminology")
        self.assertEqual(s2, 200)
        self.assertGreaterEqual(d2["total"], 1)

    def test_03_fhir_export_encounter_bundle_api(self):
        """POST /api/v1/interop/fhir/export-encounter"""
        status, data = self._call(
            "POST",
            "/api/v1/interop/fhir/export-encounter",
            body={"encounter_id": self.encounter_id},
        )
        self.assertEqual(status, 200)
        self.assertIn("bundle_id", data)
        self.assertIn("fhir_bundle", data)
        bundle = data["fhir_bundle"]
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "document")
        self.assertEqual(bundle["entry"][0]["resource"]["resourceType"], "Composition")

    def test_04_abdm_m1_identity_api(self):
        """POST /api/v1/interop/abdm/verify-identity & link-patient"""
        # Verify identity
        status, data = self._call(
            "POST",
            "/api/v1/interop/abdm/verify-identity",
            body={"abha_address": "hakeem.specialist@abdm", "abha_number": "91123456789012"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["verified"])

        # Link to patient
        s2, d2 = self._call(
            "POST",
            "/api/v1/interop/abdm/link-patient",
            body={
                "patient_id": self.patient_id,
                "abha_address": "hakeem.specialist@abdm",
                "abha_number": "91123456789012",
            },
        )
        self.assertEqual(s2, 200)
        self.assertEqual(d2["status"], "LINKED")

    def test_05_abdm_m2_care_contexts_api(self):
        """GET /api/v1/interop/abdm/care-contexts & POST notify-context-link"""
        status, data = self._call(
            "GET",
            "/api/v1/interop/abdm/care-contexts",
            query={"patient_id": self.patient_id, "abha_address": "hakeem.specialist@abdm"},
        )
        self.assertEqual(status, 200)
        self.assertIn("care_contexts", data)

        # Notify care context link
        s2, d2 = self._call(
            "POST",
            "/api/v1/interop/abdm/notify-context-link",
            body={"patient_id": self.patient_id, "encounter_id": self.encounter_id},
        )
        self.assertEqual(s2, 200)
        self.assertEqual(d2["status"], "NOTIFIED")

    def test_06_abdm_m3_consent_lifecycle_api(self):
        """M3 HIU Consent flow: create request, callback, validate scope, revoke"""
        # 1. Create consent request
        status, data = self._call(
            "POST",
            "/api/v1/interop/abdm/consent-requests",
            body={
                "patient_id": self.patient_id,
                "abha_address": "patient.demo@abdm",
                "purpose_code": "CAREMGT",
                "hi_types": ["OPConsultation", "Prescription", "DiagnosticReport"],
            },
        )
        self.assertEqual(status, 201)
        gw_id = data["gateway_request_id"]

        # 2. Status callback
        now = datetime.now(timezone.utc)
        artefact_id = f"art-{uuid.uuid4().hex[:10]}"
        s2, d2 = self._call(
            "POST",
            "/api/v1/interop/abdm/consent-status-callback",
            body={
                "gateway_request_id": gw_id,
                "status": "GRANTED",
                "consent_artefact": {
                    "artefact_id": artefact_id,
                    "hi_types": ["OPConsultation", "Prescription"],
                    "valid_from": (now - timedelta(days=1)).isoformat(),
                    "valid_to": (now + timedelta(days=15)).isoformat(),
                },
            },
        )
        self.assertEqual(s2, 200)
        self.assertEqual(d2["status"], "GRANTED")

        # 3. Validate scope
        s3, d3 = self._call(
            "POST",
            "/api/v1/interop/abdm/validate-consent-scope",
            body={"artefact_id": artefact_id, "hi_type": "OPConsultation"},
        )
        self.assertEqual(s3, 200)
        self.assertTrue(d3["is_authorized"])

        # 4. Revoke consent
        s4, d4 = self._call(
            "POST",
            "/api/v1/interop/abdm/revoke-consent",
            body={"artefact_id": artefact_id, "reason": "Patient requested withdrawal"},
        )
        self.assertEqual(s4, 200)
        self.assertEqual(d4["status"], "REVOKED")

    def test_07_abdm_m4_registries_api(self):
        """POST /api/v1/interop/abdm/verify-hfr & verify-hpr"""
        s1, d1 = self._call(
            "POST",
            "/api/v1/interop/abdm/verify-hfr",
            body={"facility_id": self.fac_id, "hfr_id": "IN-FAC-78210"},
        )
        self.assertEqual(s1, 200)
        self.assertEqual(d1["registry_status"], "ACTIVE_VERIFIED")

        s2, d2 = self._call(
            "POST",
            "/api/v1/interop/abdm/verify-hpr",
            body={"practitioner_id": self.admin_id, "hpr_id": "HPR-HAKEEM-099"},
        )
        self.assertEqual(s2, 200)
        self.assertEqual(d2["registry_status"], "ACTIVE_VERIFIED")

    def test_08_inbound_reconciliation_queue_api(self):
        """Inbound staging and reconciliation queue actions"""
        # 1. Stage inbound record
        status, data = self._call(
            "POST",
            "/api/v1/interop/inbound/stage",
            body={
                "patient_id": self.patient_id,
                "source_system": "EXTERNAL_LIS",
                "resource_type": "DiagnosticReport",
                "raw_payload": {"test_name": "Complete Blood Count", "result": "Normal"},
                "summary_text": "External LIS CBC Report",
            },
        )
        self.assertEqual(status, 201)
        rec_id = data["reconciliation_id"]

        # 2. List queue
        s2, d2 = self._call("GET", "/api/v1/interop/inbound/queue", query={"patient_id": self.patient_id})
        self.assertEqual(s2, 200)
        self.assertTrue(any(r["id"] == rec_id for r in d2["records"]))

        # 3. Clinician reconciliation
        s3, d3 = self._call(
            "POST",
            "/api/v1/interop/inbound/reconcile",
            body={
                "record_id": rec_id,
                "decision": "ATTACHED_AS_DOCUMENT",
                "decision_notes": "Filed as historical reference document",
            },
        )
        self.assertEqual(s3, 200)
        self.assertEqual(d3["decision"], "ATTACHED_AS_DOCUMENT")

    def test_09_outbox_and_webhook_api(self):
        """Outbox enqueue/dispatch and webhook verification"""
        idem_key = f"outbox-api-{uuid.uuid4().hex[:8]}"

        # 1. Enqueue outbox job
        status, data = self._call(
            "POST",
            "/api/v1/interop/outbox/enqueue",
            body={
                "job_type": "ABDM_DATA_PUSH",
                "destination_endpoint": "https://dev.abdm.gov.in/gateway/v0.5/data/push",
                "payload": {"encrypted_data": "sample_ciphertext"},
                "idempotency_key": idem_key,
            },
        )
        self.assertEqual(status, 201)
        job_id = data["job_id"]

        # 2. List outbox jobs
        s2, d2 = self._call("GET", "/api/v1/interop/outbox/jobs")
        self.assertEqual(s2, 200)
        self.assertGreaterEqual(d2["total"], 1)

        # 3. Dispatch job
        s3, d3 = self._call("POST", "/api/v1/interop/outbox/dispatch", body={"job_id": job_id})
        self.assertEqual(s3, 200)
        self.assertEqual(d3["status"], "DELIVERED")

        # 4. Webhook verification
        req_id = f"wh-api-{uuid.uuid4().hex[:10]}"
        now_ts = datetime.now(timezone.utc).isoformat()
        s4, d4 = self._call(
            "POST",
            "/api/v1/interop/webhooks/verify",
            body={
                "request_id": req_id,
                "timestamp_header": now_ts,
                "payload_body": '{"status": "CONFIRMED"}',
            },
        )
        self.assertEqual(s4, 200)
        self.assertTrue(d4["is_valid"])


if __name__ == "__main__":
    unittest.main()
