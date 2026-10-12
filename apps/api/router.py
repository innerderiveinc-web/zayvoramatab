"""HTTP Request Router with Request ID Correlation and Middleware Dispatch."""

import re
import json
import uuid
import sqlite3
from typing import Dict, Any, Tuple, Optional
from apps.api.core.errors import AppError, NotFoundError, AuthenticationError
from apps.api.core.security import validate_session
from apps.api.database.connection import get_db
from apps.api.routes import health, auth, tenancy, admin, audit, capabilities, patients, encounters

ROUTES = [
    # Observability & Liveness
    ("GET", r"^/api/v1/health/live$", health.handle_health_live, False),
    ("GET", r"^/api/v1/health/ready$", health.handle_health_ready, False),
    
    # Authentication & Session
    ("POST", r"^/api/v1/auth/login$", auth.handle_auth_login, False),
    ("POST", r"^/api/v1/auth/logout$", auth.handle_auth_logout, True),
    ("GET", r"^/api/v1/auth/me$", auth.handle_auth_me, True),
    ("POST", r"^/api/v1/auth/password-reset$", auth.handle_password_reset_request, False),
    
    # Tenancy & Facilities
    ("GET", r"^/api/v1/organizations$", tenancy.handle_organizations_list, True),
    ("GET", r"^/api/v1/facilities$", tenancy.handle_facilities_list, True),
    ("POST", r"^/api/v1/facilities$", tenancy.handle_facilities_create, True),
    ("GET", r"^/api/v1/facilities/(?P<id>[^/]+)$", tenancy.handle_facility_get, True),
    
    # Administration (Users, Roles, Permissions)
    ("GET", r"^/api/v1/users$", admin.handle_users_list, True),
    ("POST", r"^/api/v1/users$", admin.handle_users_create, True),
    ("GET", r"^/api/v1/roles$", admin.handle_roles_list, True),
    ("GET", r"^/api/v1/permissions$", admin.handle_permissions_list, True),
    
    # Audit & Governance
    ("GET", r"^/api/v1/audit$", audit.handle_audit_list, True),
    ("GET", r"^/api/v1/system/capabilities$", capabilities.handle_capabilities_list, True),

    # Patients Domain (Master Patient Index, Identifiers, Consents, Duplicates, Timeline)
    ("POST", r"^/api/v1/patients$", patients.handle_patients_create, True),
    ("GET", r"^/api/v1/patients$", patients.handle_patients_search, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)$", patients.handle_patient_get_360, True),
    ("PATCH", r"^/api/v1/patients/(?P<id>[^/]+)$", patients.handle_patient_update_demographics, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/identifiers$", patients.handle_patient_identifiers_list, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/identifiers$", patients.handle_patient_identifier_add, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/identifiers/(?P<identifier_id>[^/]+)/retire$", patients.handle_patient_identifier_retire, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/consents$", patients.handle_patient_consents_list, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/consents$", patients.handle_patient_consent_record, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/consents/(?P<consent_id>[^/]+)/withdraw$", patients.handle_patient_consent_withdraw, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/duplicate-candidates$", patients.handle_patient_duplicate_candidates_get, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/duplicate-resolutions/(?P<candidate_id>[^/]+)$", patients.handle_patient_duplicate_resolution, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/timeline$", patients.handle_patient_timeline, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/encounters$", encounters.handle_encounter_create_for_patient, True),

    # Encounters Domain (Lifecycle, Transitions)
    ("GET", r"^/api/v1/encounters/(?P<id>[^/]+)$", encounters.handle_encounter_get, True),
    ("PATCH", r"^/api/v1/encounters/(?P<id>[^/]+)$", encounters.handle_encounter_update_draft, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/transition$", encounters.handle_encounter_transition, True),
]

class ApiRouter:
    @staticmethod
    def dispatch(method: str, path: str, headers: Dict[str, str], query_params: Dict[str, str],
                  body_bytes: bytes, client_ip: str, db_path: Optional[str] = None) -> Tuple[int, Dict[str, str], bytes]:
        """Dispatch incoming request through middleware, authentication, and route handlers."""
        # Correlation / Request ID tracking
        request_id = headers.get("x-request-id") or str(uuid.uuid4())

        # Parse JSON payload
        body = {}
        if body_bytes:
            try:
                body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                err_resp = {
                    "error": True,
                    "code": "MALFORMED_JSON",
                    "message": "Malformed JSON payload in request body",
                    "request_id": request_id,
                    "details": {}
                }
                return 400, {"Content-Type": "application/json", "X-Request-Id": request_id}, json.dumps(err_resp).encode("utf-8")

        # Resolve auth token (Bearer header or cookie)
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
            "request_id": request_id,
            "path_params": {}
        }

        with get_db(db_path) as conn:
            for route_method, pattern, handler_fn, requires_auth in ROUTES:
                if route_method == method:
                    match = re.match(pattern, path)
                    if match:
                        req["path_params"] = match.groupdict()

                        # Enforce Session Authentication
                        if requires_auth:
                            try:
                                req["user"] = validate_session(conn, token)
                            except AuthenticationError as e:
                                e.request_id = request_id
                                return e.status_code, {"Content-Type": "application/json", "X-Request-Id": request_id}, json.dumps(e.to_dict()).encode("utf-8")

                        try:
                            status_code, response_data = handler_fn(conn, req)
                            resp_bytes = json.dumps(response_data, indent=2, default=str).encode("utf-8")
                            return status_code, {"Content-Type": "application/json", "X-Request-Id": request_id}, resp_bytes
                        except AppError as e:
                            e.request_id = request_id
                            resp_bytes = json.dumps(e.to_dict()).encode("utf-8")
                            return e.status_code, {"Content-Type": "application/json", "X-Request-Id": request_id}, resp_bytes
                        except Exception as e:
                            err_resp = {
                                "error": True,
                                "code": "INTERNAL_SERVER_ERROR",
                                "message": "An internal server error occurred.",
                                "request_id": request_id,
                                "details": {}
                            }
                            resp_bytes = json.dumps(err_resp).encode("utf-8")
                            return 500, {"Content-Type": "application/json", "X-Request-Id": request_id}, resp_bytes

            # Route not matched
            err_resp = {
                "error": True,
                "code": "NOT_FOUND",
                "message": f"Endpoint '{method} {path}' not found.",
                "request_id": request_id,
                "details": {}
            }
            return 404, {"Content-Type": "application/json", "X-Request-Id": request_id}, json.dumps(err_resp).encode("utf-8")
