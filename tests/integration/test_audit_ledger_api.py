"""Integration tests for Clinical Audit, Accountability & Tamper-Evident Ledger REST APIs.

Phase 29 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Record audit event with cryptographic hash chaining
2. Query ledger events with filtering
3. Fetch event by ID with metadata and annotations
4. Append audit annotation/dispute note without mutating original event
5. Execute cryptographic integrity sweep checkpoint
6. List governed retention policies
7. Place and release legal hold
8. Generate tamper-evident compliance evidence export package
"""

import os
import json
import unittest
import tempfile
import sqlite3
import uuid

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestClinicalAuditLedgerApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_audit_ledger_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.db_path
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

        conn.close()

    def _api(self, method: str, path: str, payload: dict = None, query_params: dict = None):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-Facility-Id": self.fac_id,
        }
        body_bytes = json.dumps(payload).encode("utf-8") if payload else b""
        status, resp_headers, body = ApiRouter.dispatch(
            method, path, headers, query_params or {}, body_bytes, "127.0.0.1", self.db_path
        )
        return status, json.loads(body)

    def test_end_to_end_audit_ledger_api_lifecycle(self):
        # 1. Record an event
        status, evt = self._api("POST", "/api/v1/audit/ledger/events", {
            "event_code": "PRESCRIPTION_SIGN",
            "event_family": "prescription_lifecycle",
            "target_entity_type": "prescription",
            "target_entity_id": "rx-api-2026-999",
            "target_entity_version": "v1.0",
            "action": "SIGN_PRESCRIPTION_ELECTRONICALLY",
            "action_intent": "Electronic signature for acute prescription",
            "result_state": "succeeded",
            "metadata": {"items_count": 4, "signed_by": "Hakeem Mansoor"}
        })
        self.assertEqual(status, 201)
        event_id = evt["event_id"]
        self.assertIsNotNone(evt["event_hash"])
        self.assertTrue(evt["ledger_sequence"] >= 1)

        # 2. Query ledger events
        status, query_res = self._api("GET", "/api/v1/audit/ledger/events", query_params={"event_family": "prescription_lifecycle"})
        self.assertEqual(status, 200)
        self.assertTrue(query_res["total_events"] >= 1)
        matching = [e for e in query_res["events"] if e["event_id"] == event_id]
        self.assertEqual(len(matching), 1)

        # 3. Get event by ID
        status, fetched = self._api("GET", f"/api/v1/audit/ledger/events/{event_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["event_id"], event_id)
        self.assertEqual(fetched["metadata"]["items_count"], 4)
        orig_hash = fetched["event_hash"]

        # 4. Append audit annotation / dispute note
        status, annot = self._api("POST", f"/api/v1/audit/ledger/events/{event_id}/annotations", {
            "annotation_type": "ANNOTATION_ADDED",
            "rationale": "Verified secondary signature with Chief Hakeem counter-sign.",
            "supporting_refs": ["REF-CLINICAL-NOTE-901"]
        })
        self.assertEqual(status, 201)
        self.assertEqual(annot["annotation_type"], "ANNOTATION_ADDED")

        # Refetch: verify immutable event hash and attached annotation
        status, refetched = self._api("GET", f"/api/v1/audit/ledger/events/{event_id}")
        self.assertEqual(status, 200)
        self.assertEqual(refetched["event_hash"], orig_hash)
        self.assertEqual(len(refetched["annotations"]), 1)

        # 5. Execute cryptographic integrity sweep
        status, sweep = self._api("POST", "/api/v1/audit/ledger/integrity-checks", {})
        self.assertEqual(status, 200)
        self.assertEqual(sweep["verification_result"], "passed_for_checked_scope")
        self.assertEqual(sweep["errors_count"], 0)
        self.assertIsNotNone(sweep["root_hash"])

        # 6. List retention policies
        status, ret_res = self._api("GET", "/api/v1/audit/ledger/retention-policies")
        self.assertEqual(status, 200)
        self.assertTrue(ret_res["total_policies"] >= 3)

        # 7. Place legal hold
        hold_code = f"HOLD-API-{uuid.uuid4().hex[:6].upper()}"
        status, hold = self._api("POST", "/api/v1/audit/ledger/legal-holds", {
            "hold_code": hold_code,
            "title": "Litigation Hold - Drug Safety Audit",
            "reason": "Statutory pharmacovigilance inspection requirement",
            "scope_filter": {"event_family": "prescription_lifecycle"}
        })
        self.assertEqual(status, 201)
        hold_id = hold["id"]
        self.assertEqual(hold["status"], "ACTIVE")

        # Release legal hold
        status, released = self._api("POST", f"/api/v1/audit/ledger/legal-holds/{hold_id}/release", {
            "rationale": "Audit concluded with satisfactory findings"
        })
        self.assertEqual(status, 200)
        self.assertEqual(released["status"], "RELEASED")

        # 8. Export compliance evidence package with cryptographic receipt
        status, export_pkg = self._api("POST", "/api/v1/audit/ledger/exports", {
            "purpose": "State Medical Council Regulatory Inspection 2026",
            "scope": {"event_family": "prescription_lifecycle"}
        })
        self.assertEqual(status, 201)
        self.assertTrue(export_pkg["export_number"].startswith("EXP-"))
        self.assertTrue(export_pkg["total_events_exported"] >= 1)
        self.assertIsNotNone(export_pkg["export_manifest_hash"])
        self.assertIsNotNone(export_pkg["export_artifact"]["root_hash"])


if __name__ == "__main__":
    unittest.main()
