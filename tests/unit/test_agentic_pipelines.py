"""Unit tests for ZAYVORA MATAB OS — Autonomous Agentic Systems Pipelines.
Verifies:
1. KAVSIngestionAgent: Document ingestion, Unani ontology extraction, Schedule E(1) verification.
2. PharmacovigilanceWatchdogAgent: Symptom scanning, batch correlation, WHO-UMC causality, cluster signal.
3. FEFORestockAgent: Inventory audit, seasonal consumption projection, purchase order draft staging.
4. ClinicalEvidencePackAgent: Dual-corpus citation binding, 3-phase cascade, Merkle pack hash.
5. AgenticOrchestrator: Full multi-pipeline execution cycle and status reporting.
"""

import os
import sys
import unittest
import tempfile
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.agentic.kavs_agent import KAVSIngestionAgent
from apps.api.agentic.pharmacovigilance_agent import PharmacovigilanceWatchdogAgent
from apps.api.agentic.inventory_agent import FEFORestockAgent
from apps.api.agentic.evidence_agent import ClinicalEvidencePackAgent
from apps.api.agentic.orchestrator import AgenticOrchestrator


class TestAgenticPipelines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_agentic.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

    def test_01_kavs_ingestion_pipeline(self):
        agent = KAVSIngestionAgent(db_path=self.db_path)
        pages = [
            {
                "page_number": 55,
                "text": "Mufrad: Suranjan (Colchicum autumnale)\nMizaj: Har dar Darja Saum, Yabis dar Darja Saum\nAf'aal: Muhallil-e-Warm\nMudabbar: With Roghan Zard\nBadal: Zafran (1/4 wazn)"
            }
        ]
        res = agent.run_pipeline(
            book_title="Test Kitab al-Mufradat",
            author="Classical Hakeem",
            raw_text_pages=pages,
            user_id="usr-admin-1"
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["pages_processed"], 1)
        self.assertGreaterEqual(res["total_monographs_extracted"], 1)
        mono = res["sample_monographs"][0]
        self.assertEqual(mono["name"], "Suranjan")
        self.assertTrue(mono["is_schedule_e1"])
        self.assertEqual(mono["canonical_musleh"], "Zafran / Kateera")
        self.assertTrue(mono["mudabbar_specified"])

    def test_02_pharmacovigilance_watchdog_pipeline(self):
        agent = PharmacovigilanceWatchdogAgent(db_path=self.db_path)
        res = agent.run_surveillance_pipeline(lookback_days=30, cluster_threshold=2)
        self.assertTrue(res["success"])
        self.assertIn("cluster_signals_generated", res)
        self.assertIn("signals", res)
        self.assertGreaterEqual(len(res["signals"]), 1)
        sig = res["signals"][0]
        self.assertIn(sig["who_umc_causality"], ["PROBABLE", "CERTAIN"])
        self.assertIn(sig["risk_level"], ["HIGH", "CRITICAL"])
        self.assertIn("Quarantine", sig["recommended_action"])

    def test_03_fefo_restock_pipeline(self):
        agent = FEFORestockAgent(db_path=self.db_path)
        res = agent.run_restock_pipeline(facility_id="fac-central-opd", season="WINTER")
        self.assertTrue(res["success"])
        self.assertEqual(res["season_applied"], "WINTER")
        self.assertIn("purchase_order_draft", res)
        po = res["purchase_order_draft"]
        self.assertEqual(po["status"], "DRAFT_PENDING_APPROVAL")
        self.assertGreater(po["total_estimated_cost_inr"], 0)
        self.assertGreaterEqual(len(po["items"]), 1)

    def test_04_clinical_evidence_pack_pipeline(self):
        agent = ClinicalEvidencePackAgent(db_path=self.db_path)
        res = agent.generate_evidence_pack(clinical_condition="Waja-ul-Mafasil Joint Arthritis", patient_mizaj="BALGHAMI")
        self.assertTrue(res["success"])
        pack = res["evidence_pack"]
        self.assertIn("deterministic_sha256", pack)
        self.assertEqual(pack["organ_axis"], "MUSCULOSKELETAL")
        self.assertGreaterEqual(len(pack["classical_compendia_citations"]), 1)
        self.assertGreaterEqual(len(pack["modern_pharmacopoeial_citations"]), 1)
        self.assertIn("phase1", pack["usul_e_ilaj_cascade"])
        self.assertIn("phase2", pack["usul_e_ilaj_cascade"])
        self.assertIn("phase3", pack["usul_e_ilaj_cascade"])

    def test_05_master_agentic_orchestrator(self):
        orchestrator = AgenticOrchestrator(db_path=self.db_path)
        status = orchestrator.get_system_status()
        self.assertEqual(status["status"], "OPERATIONAL")
        self.assertIn("kavs_ingestion", status["pipelines"])
        self.assertIn("pharmacovigilance", status["pipelines"])
        self.assertIn("fefo_inventory", status["pipelines"])
        self.assertIn("clinical_evidence", status["pipelines"])

        res = orchestrator.run_all(facility_id="fac-central-opd", user_id="usr-admin-1")
        self.assertEqual(res["status"], "ALL_PIPELINES_EXECUTED_SUCCESSFULLY")
        self.assertTrue(res["pipeline_results"]["kavs_ingestion"]["success"])
        self.assertTrue(res["pipeline_results"]["pharmacovigilance"]["success"])
        self.assertTrue(res["pipeline_results"]["fefo_inventory"]["success"])
        self.assertTrue(res["pipeline_results"]["clinical_evidence"]["success"])

    def test_06_extended_canonical_conditions_evidence_packs(self):
        agent = ClinicalEvidencePackAgent(db_path=self.db_path)
        for cond, expected_axis in [
            ("Ziabetus Shakari Diabetes", "RENAL / METABOLIC"),
            ("Zaght-ud-Dam Hypertension", "CARDIOVASCULAR / VASCULAR"),
            ("Falij wa Laqwa Stroke", "NEUROLOGICAL / NEUROMOTOR")
        ]:
            res = agent.generate_evidence_pack(clinical_condition=cond, user_id="usr-hakeem-1")
            self.assertTrue(res["success"])
            pack = res["evidence_pack"]
            self.assertEqual(pack["organ_axis"], expected_axis)
            self.assertGreaterEqual(len(pack["classical_compendia_citations"]), 2)
            self.assertGreaterEqual(len(pack["modern_pharmacopoeial_citations"]), 2)
            self.assertIn("phase1", pack["usul_e_ilaj_cascade"])
            self.assertIn("phase2", pack["usul_e_ilaj_cascade"])
            self.assertIn("phase3", pack["usul_e_ilaj_cascade"])
            self.assertGreaterEqual(len(pack["governed_formulations"]), 2)
            self.assertTrue(pack["deterministic_sha256"])


if __name__ == "__main__":
    unittest.main()
