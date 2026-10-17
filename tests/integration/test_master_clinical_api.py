"""Integration tests for Master Clinical System API handlers."""

import unittest
import sqlite3
import json

from apps.api.database.migrator import run_migrations
from apps.api.routes.master_clinical import (
    handle_get_axes, handle_score_axes, handle_get_protocols,
    handle_get_protocol_detail, handle_get_kits, handle_get_parhez_list,
    handle_get_parhez_detail, handle_check_safety
)


class TestMasterClinicalAPI(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect("matab.db")
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def test_get_axes_handler(self):
        status, res = handle_get_axes(self.conn, {"db_path": "matab.db"})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(res["organ_axes"]), 11)

    def test_score_axes_handler(self):
        req = {
            "db_path": "matab.db",
            "body": {
                "scores": {
                    "Jigar-Banas": 5,
                    "Dimagh-Qalb": 4
                }
            }
        }
        status, res = handle_score_axes(self.conn, req)
        self.assertEqual(status, 200)
        self.assertEqual(res["primary_axis"], "Jigar-Banas")
        self.assertEqual(res["secondary_axis"], "Dimagh-Qalb")
        self.assertGreaterEqual(len(res["recommended_protocols"]), 1)

    def test_get_protocols_and_detail(self):
        status, res = handle_get_protocols(self.conn, {"db_path": "matab.db", "query_params": {}})
        self.assertEqual(status, 200)
        self.assertEqual(len(res["protocols"]), 21)

        req_detail = {"db_path": "matab.db", "params": {"id": "P-01"}}
        status, detail = handle_get_protocol_detail(self.conn, req_detail)
        self.assertEqual(status, 200)
        self.assertEqual(detail["protocol"]["id"], "P-01")

    def test_get_kits_and_parhez(self):
        status, res = handle_get_kits(self.conn, {"db_path": "matab.db"})
        self.assertEqual(status, 200)
        self.assertEqual(len(res["kits"]), 21)

        status, p_res = handle_get_parhez_list(self.conn, {"db_path": "matab.db"})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(p_res["parhez_protocols"]), 8)

        req_p = {"db_path": "matab.db", "params": {"code": "PC-01"}}
        status, p_det = handle_get_parhez_detail(self.conn, req_p)
        self.assertEqual(status, 200)
        self.assertEqual(p_det["parhez"]["code"], "PC-01")

    def test_check_safety_handler(self):
        req = {
            "db_path": "matab.db",
            "body": {
                "herbs": ["Aqarqarha", "Mulethi"],
                "medications": ["Amlodipine", "Losartan"]
            }
        }
        status, res = handle_check_safety(self.conn, req)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(res["alerts_count"], 1)


if __name__ == "__main__":
    unittest.main()
