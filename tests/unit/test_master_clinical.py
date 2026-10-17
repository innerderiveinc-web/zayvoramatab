"""Unit tests for Master Clinical System (12 Axes, 21 Protocols, 21 Kits, Safety)."""

import unittest
import sqlite3
from apps.api.domains.master_clinical import MasterClinicalService


class TestMasterClinicalService(unittest.TestCase):
    def setUp(self):
        self.svc = MasterClinicalService("matab.db")

    def test_get_organ_axes(self):
        axes = self.svc.get_organ_axes()
        self.assertGreaterEqual(len(axes), 11)
        axis_ids = [a["id"] for a in axes]
        self.assertIn("Qalb-Uroq", axis_ids)
        self.assertIn("Jigar-Banas", axis_ids)
        self.assertIn("Dimagh-Qalb", axis_ids)

    def test_axis_scoring_and_protocol_recommendation(self):
        scores = {
            "Jigar-Banas": 5,
            "Dimagh-Qalb": 3,
            "Meda-Amaa": 2
        }
        res = self.svc.score_axes(scores)
        self.assertEqual(res["primary_axis"], "Jigar-Banas")
        self.assertEqual(res["primary_score"], 5)
        self.assertEqual(res["secondary_axis"], "Dimagh-Qalb")
        self.assertEqual(res["secondary_score"], 3)
        self.assertGreaterEqual(len(res["recommended_protocols"]), 1)

    def test_get_kits_and_parhez(self):
        kits = self.svc.get_protocol_kits()
        self.assertEqual(len(kits), 21)
        k1 = next(k for k in kits if k["kit_code"] == "K-01")
        self.assertEqual(k1["name"], "DIABETES CONTROL KIT")

        parhez = self.svc.get_parhez_protocols()
        self.assertGreaterEqual(len(parhez), 8)
        p_mf = self.svc.get_parhez_by_code("MF-01")
        self.assertIn("Male Fertility", p_mf["name"])

    def test_herb_drug_safety_screening(self):
        alerts = self.svc.check_herb_drug_safety(
            herbs=["Asgandh", "Guggul"],
            prescription_drugs=["Warfarin", "Levothyroxine"]
        )
        self.assertGreaterEqual(len(alerts), 2)
        alert_herbs = [a["herb"] for a in alerts]
        self.assertTrue(any("Asgandh" in h for h in alert_herbs))
        self.assertTrue(any("Guggul" in h for h in alert_herbs))


if __name__ == "__main__":
    unittest.main()
