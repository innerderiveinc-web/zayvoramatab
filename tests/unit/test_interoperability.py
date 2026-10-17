"""Unit tests for Enterprise Interoperability, FHIR APIs & ABDM Integration Engine.

Phase 31 validation for ZAYVORA MATAB OS.
Enforces non-negotiables:
1. Pinned specifications registry (FHIR R4 4.0.1, NRCeS ndhm.in#6.5.0, LOINC, SNOMED CT, UCUM, ABDM HIE-CM).
2. Unani terminology preservation without lossy coercion (no_safe_mapping defaults).
3. Deterministic NRCeS DocumentBundle generation (Composition as first entry).
4. ABDM Milestones M1 (ABHA Identity), M2 (HIP Privacy), M3 (HIU Consent Gating), M4 (Registries).
5. Inbound record staging with clinician reconciliation (zero silent overwrites).
6. Durable outbox with idempotency and replay-safe webhook verification.
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
from apps.api.domains.interoperability import EnterpriseInteroperabilityEngine
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError


class TestEnterpriseInteroperabilityEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_interop_engine.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = EnterpriseInteroperabilityEngine(cls.db_path)

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

        # Ensure an encounter exists for tests
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

        # Ensure an assessment and clinical problem exists for the encounter
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
            ) VALUES (?, ?, ?, ?, ?, 'Humma-e-Aafan (Infectious Malarial Fever)', 'ICD-10', 'A00.1', 'CONFIRMED_CODED', 'CONFIRMED', 1, ?);
            """,
            (f"prob-{uuid.uuid4().hex[:8]}", cls.org_id, cls.patient_id, cls.encounter_id, assess_id, cls.admin_id),
        )
        conn.commit()
        conn.close()

    def test_01_specifications_registry_seeding_and_management(self):
        """Verify default specification seeding, registration, and deprecation."""
        specs = self.engine.list_specifications(self.org_id)
        self.assertGreaterEqual(len(specs), 6)

        spec_codes = {s["spec_code"] for s in specs}
        self.assertIn("FHIR_R4_CORE", spec_codes)
        self.assertIn("NRCES_ABDM_IG", spec_codes)
        self.assertIn("LOINC_2_76", spec_codes)
        self.assertIn("SNOMED_CT_2024_03", spec_codes)

        # Register a custom connector specification
        custom_spec = self.engine.register_specification(
            self.org_id,
            self.admin_id,
            {
                "spec_code": "LAB_LIS_CUSTOM",
                "spec_name": "Custom Clinic LIS Profile",
                "canonical_url": "https://zayvora.internal/profiles/lis",
                "package_id": "zayvora.interop.lis",
                "pinned_version": "1.0.0",
                "sha256_checksum": "a" * 64,
            },
        )
        self.assertEqual(custom_spec["status"], "active")

        # Deprecate the specification
        deprecated = self.engine.deprecate_specification(
            self.org_id, self.admin_id, "LAB_LIS_CUSTOM", "1.0.0"
        )
        self.assertEqual(deprecated["status"], "deprecated")

    def test_02_unani_terminology_mapping_and_preservation(self):
        """Verify terminology mappings protect Unani concepts without lossy coercion."""
        # 1. Unreviewed coercion missing clinical rationale must fail
        with self.assertRaises(ValidationError):
            self.engine.upsert_terminology_mapping(
                self.org_id,
                self.admin_id,
                {
                    "concept_domain": "UNANI_MIZAJ",
                    "internal_code": "MIZAJ_DAMAWI",
                    "internal_display": "Sanguine Temperament (Damawi)",
                    "target_system_uri": "http://snomed.info/sct",
                    "target_code": "12345678",
                    "mapping_state": "exact_reviewed",  # Missing clinical_rationale
                },
            )

        # 2. Correct mapping with no_safe_mapping preserved
        res_unmapped = self.engine.upsert_terminology_mapping(
            self.org_id,
            self.admin_id,
            {
                "concept_domain": "UNANI_MIZAJ",
                "internal_code": "MIZAJ_DAMAWI",
                "internal_display": "Sanguine Temperament (Damawi)",
                "target_system_uri": "http://snomed.info/sct",
                "mapping_state": "no_safe_mapping",
                "clinical_rationale": "Humoral temperament has no one-to-one biomedical equivalent in SNOMED CT.",
            },
        )
        self.assertEqual(res_unmapped["mapping_state"], "no_safe_mapping")

        # 3. Reviewed exact equivalence
        res_exact = self.engine.upsert_terminology_mapping(
            self.org_id,
            self.admin_id,
            {
                "concept_domain": "UNANI_TASHKHEES",
                "internal_code": "HUMMA_E_AAFAN",
                "internal_display": "Humma-e-Aafan",
                "target_system_uri": "http://snomed.info/sct",
                "target_code": "409702008",
                "target_display": "Infectious fever",
                "mapping_state": "exact_reviewed",
                "clinical_rationale": "Expert consensus on septic/infectious humor etiology mapping.",
            },
        )
        self.assertEqual(res_exact["mapping_state"], "exact_reviewed")

        resolved = self.engine.resolve_terminology_mapping(self.org_id, "HUMMA_E_AAFAN", "http://snomed.info/sct")
        self.assertEqual(resolved["target_code"], "409702008")

    def test_03_generate_encounter_document_bundle(self):
        """Verify NRCeS DocumentBundle generation with Composition as first entry."""
        bundle_res = self.engine.generate_encounter_document_bundle(
            self.org_id, self.encounter_id, self.admin_id
        )
        self.assertIn("bundle_id", bundle_res)
        self.assertIn("bundle_hash", bundle_res)
        self.assertGreaterEqual(bundle_res["entry_count"], 4)

        bundle = bundle_res["fhir_bundle"]
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "document")
        self.assertIn("https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle", bundle["meta"]["profile"])

        # First entry MUST be Composition
        first_entry = bundle["entry"][0]["resource"]
        self.assertEqual(first_entry["resourceType"], "Composition")
        self.assertEqual(first_entry["title"], "Clinical Consultation / OPD Summary")

    def test_04_abdm_m1_identity_management(self):
        """Verify ABHA identity verification and patient record linking."""
        # Invalid address format
        with self.assertRaises(ValidationError):
            self.engine.verify_abha_identity(self.org_id, self.admin_id, "91123456789012", "invalid_address")

        # Invalid 14-digit number length
        with self.assertRaises(ValidationError):
            self.engine.verify_abha_identity(self.org_id, self.admin_id, "123", "valid@abdm")

        # Valid identity verification
        ver = self.engine.verify_abha_identity(
            self.org_id, self.admin_id, "91-1234-5678-9012", "hakeem.test@abdm"
        )
        self.assertTrue(ver["verified"])
        self.assertEqual(ver["abha_address"], "hakeem.test@abdm")

        # Link to patient
        link_res = self.engine.link_abha_to_patient(
            self.org_id, self.admin_id, self.patient_id, "91-1234-5678-9012", "hakeem.test@abdm"
        )
        self.assertEqual(link_res["status"], "LINKED")

    def test_05_abdm_m2_care_context_discovery_privacy(self):
        """Verify care contexts do not leak clinical diagnosis in display strings."""
        contexts = self.engine.discover_care_contexts(self.org_id, self.patient_id, "hakeem.test@abdm")
        self.assertIsInstance(contexts, list)
        self.assertGreaterEqual(len(contexts), 1)

        for ctx in contexts:
            display = ctx["display"]
            # Non-negotiable: Display string must not disclose diagnostic or prescription text
            self.assertNotIn("Humma-e-Aafan", display)
            self.assertNotIn("Fever", display)
            self.assertIn("Consultation", display)

        notify = self.engine.notify_care_context_linked(
            self.org_id, self.admin_id, self.patient_id, self.encounter_id
        )
        self.assertEqual(notify["status"], "NOTIFIED")

    def test_06_abdm_m3_consent_request_and_scope_gating(self):
        """Verify M3 consent request lifecycle, artefact scope validation, and revocation."""
        # 1. Create consent request
        req = self.engine.create_consent_request(
            self.org_id,
            self.admin_id,
            {
                "patient_id": self.patient_id,
                "abha_address": "patient.test@abdm",
                "purpose_code": "CAREMGT",
                "hi_types": ["OPConsultation", "Prescription"],
            },
        )
        self.assertEqual(req["status"], "REQUESTED")
        gw_id = req["gateway_request_id"]

        # 2. Callback granting consent
        now = datetime.now(timezone.utc)
        cb = self.engine.handle_consent_status_callback(
            self.org_id,
            gw_id,
            "GRANTED",
            consent_artefact_payload={
                "artefact_id": f"art-{uuid.uuid4().hex[:12]}",
                "hi_types": ["OPConsultation", "Prescription"],
                "valid_from": (now - timedelta(days=1)).isoformat(),
                "valid_to": (now + timedelta(days=10)).isoformat(),
            },
        )
        self.assertEqual(cb["status"], "GRANTED")
        artefact_id = cb["artefact_id"]
        self.assertIsNotNone(artefact_id)

        # 3. Validate authorized scope
        auth_check = self.engine.validate_consent_artefact_scope(
            self.org_id, artefact_id, "OPConsultation"
        )
        self.assertTrue(auth_check["is_authorized"])

        # 4. Out-of-scope hiType blocked
        disallowed_check = self.engine.validate_consent_artefact_scope(
            self.org_id, artefact_id, "DiagnosticReport"
        )
        self.assertFalse(disallowed_check["is_authorized"])
        self.assertIn("not permitted", disallowed_check["reason"])

        # 5. Revocation blocks further access immediately
        rev = self.engine.revoke_consent_artefact(
            self.org_id, self.admin_id, artefact_id, "Patient requested immediate data revocation"
        )
        self.assertEqual(rev["status"], "REVOKED")

        post_rev_check = self.engine.validate_consent_artefact_scope(
            self.org_id, artefact_id, "OPConsultation"
        )
        self.assertFalse(post_rev_check["is_authorized"])
        self.assertIn("REVOKED", post_rev_check["reason"])

    def test_07_abdm_m4_registries_verification(self):
        """Verify HFR and HPR registry validation."""
        hfr = self.engine.verify_hfr_facility(self.org_id, self.fac_id, "IN-FAC-10029")
        self.assertEqual(hfr["registry_status"], "ACTIVE_VERIFIED")

        hpr = self.engine.verify_hpr_practitioner(self.org_id, self.admin_id, "HPR-HAKEEM-091")
        self.assertEqual(hpr["registry_status"], "ACTIVE_VERIFIED")

    def test_08_inbound_record_staging_and_reconciliation_queue(self):
        """Verify inbound external records do not silently overwrite local clinical charts."""
        stage_res = self.engine.stage_inbound_record(
            self.org_id,
            {
                "patient_id": self.patient_id,
                "source_system": "ABDM_HIU_TRANSFER",
                "resource_type": "Condition",
                "raw_payload": {"code": "E11", "display": "Type 2 diabetes mellitus"},
                "summary_text": "External hospital documented Type 2 Diabetes",
            },
        )
        self.assertEqual(stage_res["status"], "PENDING_REVIEW")
        rec_id = stage_res["reconciliation_id"]

        # Listed in queue
        queue = self.engine.list_reconciliation_queue(self.org_id, self.patient_id, status="PENDING_REVIEW")
        self.assertTrue(any(q["id"] == rec_id for q in queue))

        # Clinician reconciles record
        rec_decision = self.engine.reconcile_inbound_record(
            self.org_id,
            rec_id,
            self.admin_id,
            "ACCEPTED",
            "Clinician confirmed external diabetes history with patient.",
        )
        self.assertEqual(rec_decision["decision"], "ACCEPTED")

        # Second reconciliation on decided record must raise ConflictError
        with self.assertRaises(ConflictError):
            self.engine.reconcile_inbound_record(
                self.org_id, rec_id, self.admin_id, "REJECTED", "Attempt duplicate decision"
            )

    def test_09_durable_outbox_and_replay_safe_webhooks(self):
        """Verify durable outbox idempotency and replay protection on inbound webhooks."""
        idem_key = f"outbox-idem-{uuid.uuid4().hex[:8]}"

        # 1. Enqueue outbox job
        job1 = self.engine.enqueue_outbox_job(
            self.org_id,
            "FHIR_DOCUMENT_EXPORT",
            "https://dev.abdm.gov.in/gateway/v0.5/data/transfer",
            {"sample": "payload"},
            idempotency_key=idem_key,
        )
        self.assertFalse(job1["is_duplicate"])

        # 2. Duplicate enqueue returns existing job
        job2 = self.engine.enqueue_outbox_job(
            self.org_id,
            "FHIR_DOCUMENT_EXPORT",
            "https://dev.abdm.gov.in/gateway/v0.5/data/transfer",
            {"sample": "payload"},
            idempotency_key=idem_key,
        )
        self.assertTrue(job2["is_duplicate"])
        self.assertEqual(job1["job_id"], job2["job_id"])

        # 3. Dispatch outbox job
        dispatch = self.engine.dispatch_outbox_job(self.org_id, job1["job_id"])
        self.assertEqual(dispatch["status"], "DELIVERED")

        # 4. Inbound webhook verification
        req_id = f"wh-req-{uuid.uuid4().hex[:12]}"
        now_ts = datetime.now(timezone.utc).isoformat()

        # Valid fresh webhook
        v1 = self.engine.verify_inbound_webhook(self.org_id, req_id, now_ts, '{"event": "test"}')
        self.assertTrue(v1["is_valid"])

        # Duplicate request_id rejected (Replay Protection)
        v_replay = self.engine.verify_inbound_webhook(self.org_id, req_id, now_ts, '{"event": "test"}')
        self.assertFalse(v_replay["is_valid"])
        self.assertEqual(v_replay["error_code"], "REJECTED_DUPLICATE")

        # Stale timestamp (>300 seconds drift) rejected
        stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()
        v_stale = self.engine.verify_inbound_webhook(self.org_id, f"wh-{uuid.uuid4().hex}", stale_ts, "{}")
        self.assertFalse(v_stale["is_valid"])
        self.assertEqual(v_stale["error_code"], "REJECTED_STALE")


if __name__ == "__main__":
    unittest.main()
