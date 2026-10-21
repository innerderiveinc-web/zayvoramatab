"""Regression tests for Unauthenticated Route Rejection and Secure Token Handling."""

import unittest
import json
from apps.api.router import ApiRouter

class TestAuthRoutesSecurity(unittest.TestCase):
    def test_unauthenticated_inventory_dispense_rejected(self):
        code, headers, body = ApiRouter.dispatch(
            method="POST",
            path="/api/v1/inventory/dispense",
            headers={"Content-Type": "application/json"},
            query_params={},
            body_bytes=json.dumps({"batch_number": "BAT-001", "quantity": 1}).encode("utf-8"),
            client_ip="127.0.0.1"
        )
        self.assertEqual(code, 401)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data.get("error"))

    def test_unauthenticated_settings_save_rejected(self):
        code, headers, body = ApiRouter.dispatch(
            method="POST",
            path="/api/v1/settings",
            headers={"Content-Type": "application/json"},
            query_params={},
            body_bytes=json.dumps({"consultation_fee": 500}).encode("utf-8"),
            client_ip="127.0.0.1"
        )
        self.assertEqual(code, 401)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data.get("error"))

    def test_unauthenticated_hakeem_ai_query_rejected(self):
        code, headers, body = ApiRouter.dispatch(
            method="POST",
            path="/api/v1/hakeem-ai/query",
            headers={"Content-Type": "application/json"},
            query_params={},
            body_bytes=json.dumps({"query": "What is the treatment for Suda?"}).encode("utf-8"),
            client_ip="127.0.0.1"
        )
        self.assertEqual(code, 401)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data.get("error"))

    def test_query_string_token_is_rejected(self):
        code, headers, body = ApiRouter.dispatch(
            method="POST",
            path="/api/v1/settings",
            headers={"Content-Type": "application/json"},
            query_params={"token": "insecure-query-token"},
            body_bytes=json.dumps({"consultation_fee": 500}).encode("utf-8"),
            client_ip="127.0.0.1"
        )
        self.assertEqual(code, 401)

if __name__ == "__main__":
    unittest.main()
