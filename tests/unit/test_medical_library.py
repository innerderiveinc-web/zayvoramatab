"""Unit tests for Medical Library & Compendia Domain Engine."""

import unittest
import tempfile
import os
import sqlite3
import json

from apps.api.database.migrator import run_migrations
from apps.api.domains.library import MedicalLibraryService, CATEGORIES


class TestMedicalLibraryService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_migrations(self.db_path)

        # Create dummy books folder
        self.books_dir = tempfile.mkdtemp()
        self.sample_files = [
            "Al_Qanun_Ibn_Sina.pdf",
            "Kitab_al_Hawi_Vol1.pdf",
            "HARRISON_Internal_Medicine_21st.pdf",
            "Qarabadeen_Hamdard_Kamil.pdf",
            "Makhzan_al_Mufradat.pdf"
        ]
        for f in self.sample_files:
            p = os.path.join(self.books_dir, f)
            with open(p, "wb") as fp:
                fp.write(b"SAMPLE_MEDICAL_PDF_CONTENT_" * 100)

        self.svc = MedicalLibraryService(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        for f in self.sample_files:
            p = os.path.join(self.books_dir, f)
            if os.path.exists(p):
                os.unlink(p)
        if os.path.exists(self.books_dir):
            os.rmdir(self.books_dir)

    def test_indexing_and_stats(self):
        res = self.svc.index_downloaded_books(self.books_dir)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["total_files_examined"], len(self.sample_files))
        self.assertEqual(res["newly_indexed_books"], len(self.sample_files))

        stats = self.svc.get_library_stats()
        self.assertEqual(stats["total_books"], len(self.sample_files))
        self.assertIn("CLASSICAL_CANON", stats["by_category"])
        self.assertIn("MODERN_INTERNAL_MEDICINE", stats["by_category"])

    def test_search_and_filter(self):
        self.svc.index_downloaded_books(self.books_dir)

        # Search by author/title
        search_res = self.svc.search_books(query="Avicenna")
        self.assertGreaterEqual(search_res["total"], 1)
        book = search_res["books"][0]
        self.assertIn("Ibn Sina", book["primary_author"])

        # Filter by category
        canon_res = self.svc.search_books(category="CLASSICAL_CANON")
        self.assertGreaterEqual(canon_res["total"], 2)

        # Fetch detail by ID
        detail = self.svc.get_book_by_id(book["id"])
        self.assertEqual(detail["id"], book["id"])
        self.assertEqual(detail["title"], book["title"])


if __name__ == "__main__":
    unittest.main()
