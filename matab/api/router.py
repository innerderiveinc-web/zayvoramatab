"""HTTP Request Router and Dispatcher for ZAYVORA MATAB OS."""

import re
import json
import sqlite3
from typing import Dict, Any, Tuple, Optional, Callable
from matab.core.errors import AppError, NotFoundError, AuthenticationError
from matab.core.security import validate_session
from matab.database.connection import get_db
from matab.api import handlers

ROUTES = [
    ("GET", r"^/api/v1/system/health$", handlers.handle_system_health, False),
    ("GET", r"^/api/v1/system/capabilities$", handlers.handle_system_capabilities, False),
    ("POST", r"^/api/v1/auth/login$", handlers.handle_auth_login, False),
    ("POST", r"^/api/v1/auth/logout$", handlers.handle_auth_logout, True),
    ("GET", r"^/api/v1/auth/me$", handlers.handle_auth_me, True),
    ("GET", r"^/api/v1/patients$", handlers.handle_patients_search, True),
    ("POST", r"^/api/v1/patients$", handlers.handle_patients_create, True),
    ("POST", r"^/api/v1/patients/duplicate-check$", handlers.handle_patients_duplicate_check, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/360$", handlers.handle_patient_360, True),
    ("GET", r"^/api/v1/encounters/queue$", handlers.handle_encounters_queue, True),
    ("POST", r"^/api/v1/encounters$", handlers.handle_encounters_create, True),
    ("GET", r"^/api/v1/encounters/(?P<id>[^/]+)$", handlers.handle_encounter_get, True),
    ("PUT", r"^/api/v1/encounters/(?P<id>[^/]+)/vitals$", handlers.handle_encounter_vitals_put, True),
    ("PUT", r"^/api/v1/encounters/(?P<id>[^/]+)/notes$", handlers.handle_encounter_notes_put, True),
    ("POST", r"^/api/v1/unani-assessments$", handlers.handle_unani_assessment_post, True),
    ("POST", r"^/api/v1/clinical-support/red-flags$", handlers.handle_clinical_support_red_flags, False),
    ("POST", r"^/api/v1/care-plans$", handlers.handle_care_plans_post, True),
    ("GET", r"^/api/v1/knowledge/ingredients$", handlers.handle_knowledge_ingredients, False),
    ("GET", r"^/api/v1/knowledge/formulations$", handlers.handle_knowledge_formulations, False),
    ("POST", r"^/api/v1/prescriptions$", handlers.handle_prescriptions_draft_post, True),
    ("POST", r"^/api/v1/prescriptions/(?P<id>[^/]+)/safety-check$", handlers.handle_prescription_safety_check, True),
    ("POST", r"^/api/v1/prescriptions/(?P<id>[^/]+)/sign$", handlers.handle_prescription_sign, True),
    ("GET", r"^/api/v1/prescriptions/(?P<id>[^/]+)/print$", handlers.handle_prescription_print, False),
    ("GET", r"^/api/v1/operations/follow-ups$", handlers.handle_operations_followups, True),
    ("GET", r"^/api/v1/operations/inventory$", handlers.handle_operations_inventory, True),
]

class ApiRouter:
    @staticmethod
    def dispatch(method: str, path: str, headers: Dict[str, str], query_params: Dict[str, str],
                  body_bytes: bytes, client_ip: str, db_path: Optional[str] = None) -> Tuple[int, Dict[str, str], bytes]:
        """Dispatch incoming HTTP request to matched route handler."""
        # Parse JSON body if present
        body = {}
        if body_bytes:
            try:
                body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                err_resp = {
                    "error": True,
                    "code": "INVALID_JSON",
                    "message": "Malformed JSON payload in request body",
                    "details": {}
                }
                return 400, {"Content-Type": "application/json"}, json.dumps(err_resp).encode("utf-8")

        # Extract Bearer token
        auth_header = headers.get("authorization") or headers.get("Authorization") or ""
        token = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else headers.get("x-auth-token", "")

        req = {
            "method": method,
            "path": path,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "auth_token": token,
            "client_ip": client_ip,
            "path_params": {}
        }

        with get_db(db_path) as conn:
            for route_method, pattern, handler_fn, requires_auth in ROUTES:
                if route_method == method:
                    match = re.match(pattern, path)
                    if match:
                        req["path_params"] = match.groupdict()
                        
                        # Authenticate session if route requires it
                        if requires_auth:
                            try:
                                req["user"] = validate_session(conn, token)
                            except AuthenticationError as e:
                                return e.status_code, {"Content-Type": "application/json"}, json.dumps(e.to_dict()).encode("utf-8")

                        try:
                            status_code, response_data = handler_fn(conn, req)
                            resp_bytes = json.dumps(response_data, indent=2, default=str).encode("utf-8")
                            return status_code, {"Content-Type": "application/json"}, resp_bytes
                        except AppError as e:
                            resp_bytes = json.dumps(e.to_dict()).encode("utf-8")
                            return e.status_code, {"Content-Type": "application/json"}, resp_bytes
                        except Exception as e:
                            err_resp = {
                                "error": True,
                                "code": "INTERNAL_SERVER_ERROR",
                                "message": str(e),
                                "details": {}
                            }
                            resp_bytes = json.dumps(err_resp).encode("utf-8")
                            return 500, {"Content-Type": "application/json"}, resp_bytes

            # Route not found
            err_resp = {
                "error": True,
                "code": "ENDPOINT_NOT_FOUND",
                "message": f"Route '{method} {path}' not found on MATAB OS API v1",
                "details": {}
            }
            return 404, {"Content-Type": "application/json"}, json.dumps(err_resp).encode("utf-8")
