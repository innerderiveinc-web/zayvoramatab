"""Integration tests for Medical Library & Compendia API."""

import unittest
import tempfile
import os
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.domains.library import MedicalLibraryService
from apps.api.routes.library import (
    handle_library_stats, handle_library_books_list,
    handle_library_book_detail, handle_library_reindex
)


class TestMedicalLibraryAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        run_migrations(self.db_path)

        # Create dummy books folder and index it
        self.books_dir = tempfile.mkdtemp()
        self.sample_files = [
            "Al_Qanun_Ibn_Sina.pdf",
            "Kitab_al_Hawi_Vol1.pdf",
            "HARRISON_Internal_Medicine_21st.pdf"
        ]
        for f in self.sample_files:
            p = os.path.join(self.books_dir, f)
            with open(p, "wb") as fp:
                fp.write(b"SAMPLE_PDF_CONTENT_" * 100)

        self.svc = MedicalLibraryService(self.db_path)
        self.svc.index_downloaded_books(self.books_dir)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        for f in self.sample_files:
            p = os.path.join(self.books_dir, f)
            if os.path.exists(p):
                os.unlink(p)
        if os.path.exists(self.books_dir):
            os.rmdir(self.books_dir)

    def test_api_handlers(self):
        req = {
            "db_path": self.db_path,
            "user": {"id": "usr-test", "role": "HAKEEM", "organization_id": "org-test"},
            "query_params": {}
        }
        status, stats = handle_library_stats(self.conn, req)
        self.assertEqual(status, 200)
        self.assertEqual(stats["total_books"], 3)

        status, books_res = handle_library_books_list(self.conn, req)
        self.assertEqual(status, 200)
        self.assertEqual(len(books_res["books"]), 3)
        book_id = books_res["books"][0]["id"]

        req["params"] = {"book_id": book_id}
        status, detail = handle_library_book_detail(self.conn, req)
        self.assertEqual(status, 200)
        self.assertEqual(detail["book"]["id"], book_id)


if __name__ == "__main__":
    unittest.main()
