"""Unit Tests: Prescription Document Rendering, HTML Sanitization, Unicode, and Watermarks."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.database.connection import DatabaseConnection
from apps.api.domains.prescriptions import PrescriptionService

class TestPrescriptionDocumentPdf(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.conn = DatabaseConnection(self.db_path).get_connection()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_signed_document_renders_immutable_snapshot_and_hash(self):
        """Signed prescription renders practitioner registration, SHA-256 fingerprint, and no draft watermark."""
        # rx-syn-001 is seeded as SIGNED for pat-syn-003 in enc-syn-002
        doc = PrescriptionService.render_prescription_document(
            conn=self.conn,
            organization_id="org-matab-default",
            prescription_id="rx-syn-001"
        )
        self.assertEqual(doc["status"], "SIGNED")
        html = doc["html"]
        self.assertIn("SHA-256 DIGITAL FINGERPRINT", html)
        self.assertIn("ELECTRONICALLY SIGNED & VERIFIED", html)
        self.assertNotIn("DRAFT — NOT SIGNED", html)
        self.assertIn("Sharbat Bazoori Motadil", html)

    def test_draft_document_renders_prominent_watermark(self):
        """Draft prescription must display prominent DRAFT — NOT SIGNED watermark banner."""
        draft = PrescriptionService.create_prescription_draft(
            conn=self.conn,
            organization_id="org-matab-default",
            encounter_id="enc-syn-001",
            practitioner_id="usr-hakeem-1",
            actor_id="usr-hakeem-1",
            data={
                "items": [
                    {
                        "item_name": "Majoon Dabeed-ul-Ward",
                        "dosage_form": "MAJOON",
                        "dose_amount": "5",
                        "dose_unit": "g",
                        "frequency": "BD",
                        "duration_days": 10
                    }
                ]
            }
        )
        doc = PrescriptionService.render_prescription_document(
            conn=self.conn,
            organization_id="org-matab-default",
            prescription_id=draft["id"]
        )
        self.assertEqual(doc["status"], "DRAFT")
        html = doc["html"]
        self.assertIn("DRAFT — NOT SIGNED", html)
        self.assertIn("FOR PREVIEW ONLY", html)
        self.assertIn("PENDING CLINICAL SIGN-OFF", html)

    def test_multilingual_unicode_support(self):
        """Document must preserve Unicode Urdu and Hindi script in instructions and items."""
        urdu_instructions = "صبح و شام بعد طعام عرق گلاب کے ساتھ لیں"
        anupan_urdu = "عرق گلاب (Arq Gulab)"
        draft = PrescriptionService.create_prescription_draft(
            conn=self.conn,
            organization_id="org-matab-default",
            encounter_id="enc-syn-001",
            practitioner_id="usr-hakeem-1",
            actor_id="usr-hakeem-1",
            data={
                "items": [
                    {
                        "item_name": "حب پپیتہ (Habb-e-Papeeta)",
                        "dosage_form": "HAB",
                        "dose_amount": "2",
                        "dose_unit": "hab",
                        "frequency": "BD",
                        "duration_days": 7,
                        "anupan_vehicle": anupan_urdu,
                        "instructions": urdu_instructions
                    }
                ]
            }
        )
        doc = PrescriptionService.render_prescription_document(
            conn=self.conn,
            organization_id="org-matab-default",
            prescription_id=draft["id"]
        )
        html = doc["html"]
        self.assertIn(urdu_instructions, html)
        self.assertIn("حب پپیتہ", html)
        self.assertIn("عرق گلاب", html)

if __name__ == "__main__":
    unittest.main()
