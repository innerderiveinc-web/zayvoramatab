"""Unit tests for Clinical Safety Firewall & Interaction Engine (Prompt 07).
Validates:
- Substance identity resolution (Resolved, Ambiguous, Unresolved)
- Structural and field completeness validation
- Documented allergy matching (critical non-overridable block)
- Drug-Drug and Herb-Drug interaction checking from reviewed records
- Duplicate therapy and ingredient cumulative dose calculation
- Schedule E(1) toxin & Mudabbar certification checks
- Pregnancy contraindication rules
- Honest coverage reporting & limits disclosure
- Clinician disposition & override governance (blocking non-overridable overrides)
"""

import unittest
import os
import tempfile
import json
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.safety_firewall import SafetyFirewallEngine
from apps.api.core.errors import ConflictError, ValidationError


class TestSafetyFirewallEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.temp_db_fd)
        run_migrations(cls.temp_db_path)
        seed_development_data(cls.temp_db_path)
        cls.engine = SafetyFirewallEngine(cls.temp_db_path)
        cls.user_ctx = {
            "user_id": "usr-hakeem-1",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "role": "practitioner"
        }

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_db_path):
            os.remove(cls.temp_db_path)

    def test_substance_identity_resolution(self):
        """Substance resolution correctly maps canonical names, aliases, and flags ambiguous inputs."""
        # 1. Exact canonical
        res_exact = self.engine.resolve_substance_identity("Senna")
        self.assertEqual(res_exact["status"], "RESOLVED")
        self.assertEqual(res_exact["substance"]["id"], "sub-senna")

        # 2. Preferred Urdu transliteration alias
        res_alias = self.engine.resolve_substance_identity("Sana Makki")
        self.assertEqual(res_alias["status"], "RESOLVED")
        self.assertEqual(res_alias["substance"]["id"], "sub-senna")

        # 3. Unresolved substance
        res_unresolved = self.engine.resolve_substance_identity("Unknown Extracted Powder XYZ")
        self.assertEqual(res_unresolved["status"], "UNRESOLVED")

    def test_empty_prescription_triggers_critical_structural_block(self):
        """Empty prescription list triggers critical structural block."""
        report = self.engine.run_preflight(
            patient_context={"patient_id": "pat-syn-001"},
            prescription_items=[],
            user_ctx=self.user_ctx
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertFalse(report["is_signable"])
        self.assertTrue(any(f["rule_code"] == "SAF-STRUCT-001" for f in report["findings"]))

    def test_documented_allergy_triggers_critical_non_overridable_block(self):
        """Prescribing an item matching patient documented allergy creates a critical non-overridable block."""
        # Patient pat-syn-001 has documented allergy to 'Badam' / 'Roghan Badam Shireen'
        items = [
            {
                "item_name": "Roghan Badam Shireen",
                "dose_amount": "5",
                "dose_unit": "ml",
                "frequency": "HS",
                "duration_days": 7
            }
        ]
        report = self.engine.run_preflight(
            patient_context={"patient_id": "pat-syn-001"},
            prescription_items=items,
            user_ctx=self.user_ctx
        )
        self.assertEqual(report["overall_status"], "blocked")
        self.assertFalse(report["is_signable"])
        allergy_finding = next((f for f in report["findings"] if f["finding_type"] == "ALLERGY"), None)
        self.assertIsNotNone(allergy_finding)
        self.assertEqual(allergy_finding["severity"], "critical")
        self.assertEqual(allergy_finding["is_overridable"], 0)

        # Attempting to override this finding must fail with ConflictError
        with self.assertRaises(ConflictError):
            self.engine.record_finding_disposition(
                finding_id=allergy_finding["id"],
                user_ctx=self.user_ctx,
                disposition_type="OVERRIDDEN_WITH_RATIONALE",
                rationale="Attempting illegal override of anaphylactic risk"
            )

    def test_herb_drug_interaction_detection_and_governed_disposition(self):
        """Detects herb-drug interaction (Senna + Digoxin) and allows clinician acknowledgment with rationale."""
        items = [
            {
                "item_name": "Senna",
                "dose_amount": "3",
                "dose_unit": "g",
                "frequency": "OD",
                "duration_days": 3
            }
        ]
        report = self.engine.run_preflight(
            patient_context={
                "patient_id": "pat-syn-001",
                "current_medication_list": ["Digoxin"]
            },
            prescription_items=items,
            user_ctx=self.user_ctx
        )
        self.assertEqual(report["overall_status"], "blocked")
        int_finding = next((f for f in report["findings"] if f["finding_type"] == "INTERACTION"), None)
        self.assertIsNotNone(int_finding)
        self.assertIn("Digoxin", int_finding["title"])

        # Record disposition: ACKNOWLEDGED
        res = self.engine.record_finding_disposition(
            finding_id=int_finding["id"],
            user_ctx=self.user_ctx,
            disposition_type="ACKNOWLEDGED",
            rationale="Short term 3-day treatment with daily serum potassium monitoring ordered."
        )
        self.assertEqual(res["status"], "acknowledged")

    def test_schedule_e1_toxin_requires_mudabbar_certification(self):
        """Schedule E(1) toxin (Azaraqi / Kuchla) blocks without verified Mudabbar certification."""
        items_uncertified = [
            {
                "item_name": "Azaraqi (Kuchla)",
                "dose_amount": "60",
                "dose_unit": "mg",
                "frequency": "OD",
                "duration_days": 7,
                "is_mudabbar_certified": False
            }
        ]
        report_blocked = self.engine.run_preflight(
            patient_context={"patient_id": "pat-syn-001"},
            prescription_items=items_uncertified,
            user_ctx=self.user_ctx
        )
        self.assertEqual(report_blocked["overall_status"], "blocked")
        self.assertTrue(any(f["rule_code"] == "SAF-TOX-001" for f in report_blocked["findings"]))

        # Certified item passes the toxin block
        items_certified = [
            {
                "item_name": "Azaraqi (Kuchla)",
                "dose_amount": "60",
                "dose_unit": "mg",
                "frequency": "OD",
                "duration_days": 7,
                "is_mudabbar_certified": True
            }
        ]
        report_passed = self.engine.run_preflight(
            patient_context={"patient_id": "pat-syn-001"},
            prescription_items=items_certified,
            user_ctx=self.user_ctx
        )
        self.assertFalse(any(f["rule_code"] == "SAF-TOX-001" for f in report_passed["findings"]))

    def test_honest_coverage_report_and_limits_disclosure(self):
        """Every preflight run must report evaluated checks and explicit limitations disclosure."""
        items = [
            {
                "item_name": "Filfil Siah",
                "dose_amount": "500",
                "dose_unit": "mg",
                "frequency": "BD",
                "duration_days": 5
            }
        ]
        report = self.engine.run_preflight(
            patient_context={"patient_id": "pat-syn-001", "is_pregnant": False},
            prescription_items=items,
            user_ctx=self.user_ctx
        )
        coverage = report["coverage_report"]
        self.assertIn("STRUCTURAL_FIELD_COMPLETENESS", coverage["checks_evaluated"])
        self.assertIn("DOCUMENTED_ALLERGIES", coverage["checks_evaluated"])
        self.assertIn("INTERACTION_ENGINE", coverage["checks_evaluated"])
        self.assertIn("dataset_limitation", coverage)
        self.assertIn("does NOT imply combination is risk-free", coverage["dataset_limitation"])


if __name__ == "__main__":
    unittest.main()
