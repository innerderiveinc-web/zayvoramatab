"""Unit and Integration Tests: Unani Assessment, Mizaj Scoring, and Asbab-e-Sittah."""

import unittest
import os
import tempfile
from matab.database.connection import DatabaseConnection
from matab.database.migrator import run_migrations
from matab.domains.unani import UnaniService

class TestUnaniAssessment(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        self.db_manager = DatabaseConnection(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_mizaj_scoring_pure_safrawi(self):
        answers = [
            {"question_key": "lawn_complexion", "selected_option": "Yellowish/Pale", "score_safra": 3},
            {"question_key": "haiat_build", "selected_option": "Lean and muscular", "score_safra": 2},
            {"question_key": "malmas_touch", "selected_option": "Hot and dry", "score_safra": 3},
            {"question_key": "ghiza_appetite", "selected_option": "Quick digestion, sharp thirst", "score_safra": 2}
        ]
        calc = UnaniService.calculate_mizaj_scores(answers)
        self.assertEqual(calc["dominant_mizaj"], "SAFRAWI")
        self.assertEqual(calc["scores"]["safra"], 10)
        self.assertEqual(calc["percentages"]["safra"], 100.0)

    def test_mizaj_scoring_compound_motadil(self):
        answers = [
            {"question_key": "q1", "selected_option": "Balanced", "score_dam": 2, "score_balgham": 2}
        ]
        calc = UnaniService.calculate_mizaj_scores(answers)
        self.assertEqual(calc["dominant_mizaj"], "MOTADIL")

    def test_saving_complete_unani_assessment(self):
        conn = self.db_manager.get_connection()
        try:
            assessment = UnaniService.save_unani_assessment(
                conn=conn,
                encounter_id="enc-syn-101",
                patient_id="pat-syn-001",
                hakeem_id="prac-hakeem-1",
                assessment_data={
                    "dominant_mizaj": "BALGHAMI",
                    "mizaj_secondary": "SAUDAWI",
                    "su_e_mizaj_type": "MADDI",
                    "nabz_quality": "BATEE",
                    "baul_observations": "Pale, excessive volume, low specific gravity",
                    "baraz_observations": "Soft, whitish tinge, sluggish evacuation",
                    "afaal_summary": "Sluggish gastric motility, slow digestion",
                    "asbab_sittah_assessment": {
                        "makool_o_mashroob": "Excessive intake of cold and moist dairy foods",
                        "harkat_sukoon_badani": "Sedentary routine with minimal physical exercise",
                        "nawm_o_yaqzah": "Excessive daytime sleep"
                    },
                    "clinical_interpretation": "Su-e-Mizaj Balghami Maddi affecting the gastric faculty (Meda)."
                }
            )
            self.assertEqual(assessment["dominant_mizaj"], "BALGHAMI")
            self.assertEqual(assessment["su_e_mizaj_type"], "MADDI")
            self.assertEqual(assessment["nabz_quality"], "BATEE")
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()
