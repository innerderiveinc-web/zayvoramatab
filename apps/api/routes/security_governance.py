"""REST API Route Handlers for Enterprise Security, Privacy, Consent & Access Governance.

Phase 30 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- security:read
- security:admin
- security:credentials
- security:consent
- security:break_glass
- security:review
- security:policy
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.security_governance import SecurityGovernanceEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> SecurityGovernanceEngine:
    db_path = req.get("db_path")
    return SecurityGovernanceEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Identity, Session Control & Step-Up Authentication
# --------------------------------------------------------------------------

def handle_security_me(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security/me"""
    user = req["user"]
    return 200, {
        "principal_id": user.get("user_id"),
        "roles": user.get("roles", []),
        "permissions": user.get("permissions", []),
        "organization_id": user.get("organization_id"),
        "facility_id": user.get("facility_id"),
        "session_active": True,
    }


def handle_list_sessions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security/sessions"""
    user = req["user"]
    require_permission(user, "security:read", request_id=req.get("request_id"))
    target_id = req.get("query_params", {}).get("user_id") or user.get("user_id")
    engine = _get_engine(req)
    sessions = engine.list_user_sessions(target_id, user)
    return 200, {"total_sessions": len(sessions), "sessions": sessions}


def handle_revoke_session(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/sessions/revoke"""
    user = req["user"]
    require_permission(user, "security:admin", request_id=req.get("request_id"))
    data = req.get("body") or {}
    session_id = data.get("session_id")
    target_user_id = data.get("user_id")
    reason = data.get("reason", "Administrative session revocation")

    engine = _get_engine(req)
    if session_id:
        res = engine.revoke_session(session_id, reason, user)
        return 200, res
    elif target_user_id:
        count = engine.revoke_all_user_sessions(target_user_id, reason, user)
        return 200, {"revoked_count": count, "user_id": target_user_id, "status": "ALL_REVOKED"}
    else:
        raise ValidationError("Either 'session_id' or 'user_id' must be provided.")


def handle_verify_step_up(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/step-up"""
    user = req["user"]
    data = req.get("body") or {}
    token = req.get("auth_token") or data.get("token")
    credential = data.get("credential")  # password or PIN
    scope = data.get("scope", "CLINICAL_SIGNING")

    if not credential:
        raise ValidationError("Field 'credential' is required for step-up verification.")

    engine = _get_engine(req)
    res = engine.verify_step_up(token, credential, scope, user)
    return 200, res


# --------------------------------------------------------------------------
# 2. Clinician Professional Credential Registry
# --------------------------------------------------------------------------

def handle_register_credential(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/credentials"""
    user = req["user"]
    require_permission(user, "security:credentials", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    cred = engine.register_credential(data, user)
    return 201, cred


def handle_verify_credential(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/credentials/{id}/verify"""
    user = req["user"]
    require_permission(user, "security:credentials", request_id=req.get("request_id"))
    cred_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    verified = engine.verify_credential(cred_id, data, user)
    return 200, verified


def handle_suspend_credential(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/credentials/{id}/suspend"""
    user = req["user"]
    require_permission(user, "security:credentials", request_id=req.get("request_id"))
    cred_id = _param(req, "id")
    data = req.get("body") or {}
    reason = data.get("reason", "Suspended by medical council or internal governance")
    engine = _get_engine(req)
    suspended = engine.suspend_credential(cred_id, reason, user)
    return 200, suspended


# --------------------------------------------------------------------------
# 3. Purpose-Specific Patient Consent & Authority
# --------------------------------------------------------------------------

def handle_list_consent_records(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security/consent-records"""
    user = req["user"]
    require_permission(user, "security:read", request_id=req.get("request_id"))
    patient_id = req.get("query_params", {}).get("patient_id")
    if not patient_id:
        raise ValidationError("Query parameter 'patient_id' is required.")
    engine = _get_engine(req)
    records = engine.list_patient_consents(patient_id, user)
    return 200, {"total_records": len(records), "records": records}


def handle_record_consent(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/consent-records"""
    user = req["user"]
    require_permission(user, "security:consent", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    cns = engine.record_consent_event(data, user)
    return 201, cns


def handle_withdraw_consent(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/consent-records/{id}/withdraw"""
    user = req["user"]
    require_permission(user, "security:consent", request_id=req.get("request_id"))
    consent_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    withdrawn = engine.withdraw_consent(consent_id, data, user)
    return 200, withdrawn


# --------------------------------------------------------------------------
# 4. Delegated Temporary Access
# --------------------------------------------------------------------------

def handle_grant_delegation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/delegations"""
    user = req["user"]
    require_permission(user, "security:admin", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    grant = engine.grant_delegated_access(data, user)
    return 201, grant


def handle_revoke_delegation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/delegations/{id}/revoke"""
    user = req["user"]
    require_permission(user, "security:admin", request_id=req.get("request_id"))
    grant_id = _param(req, "id")
    data = req.get("body") or {}
    reason = data.get("reason", "Revocation requested")
    engine = _get_engine(req)
    revoked = engine.revoke_delegated_access(grant_id, reason, user)
    return 200, revoked


# --------------------------------------------------------------------------
# 5. Emergency Break-Glass Access
# --------------------------------------------------------------------------

def handle_request_break_glass(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/break-glass"""
    user = req["user"]
    require_permission(user, "security:break_glass", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    bg = engine.request_break_glass(data, user)
    return 201, bg


def handle_get_break_glass(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security/break-glass/{id}"""
    user = req["user"]
    require_permission(user, "security:read", request_id=req.get("request_id"))
    bg_id = _param(req, "id")
    engine = _get_engine(req)
    bg = engine.get_break_glass_event(bg_id, user)
    return 200, bg


def handle_review_break_glass(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/break-glass/{id}/review"""
    user = req["user"]
    require_permission(user, "security:admin", request_id=req.get("request_id"))
    bg_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    reviewed = engine.review_break_glass(bg_id, data, user)
    return 200, reviewed


# --------------------------------------------------------------------------
# 6. Access Review Campaigns & Decisions (Periodic Recertification)
# --------------------------------------------------------------------------

def handle_create_access_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/access-reviews"""
    user = req["user"]
    require_permission(user, "security:review", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    camp = engine.create_review_campaign(data, user)
    return 201, camp


def handle_record_access_decision(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/access-reviews/{id}/decisions"""
    user = req["user"]
    require_permission(user, "security:review", request_id=req.get("request_id"))
    camp_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    dec = engine.record_review_decision(camp_id, data, user)
    return 201, dec


def handle_list_access_reviews(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security/access-reviews"""
    user = req["user"]
    require_permission(user, "security:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    camps = engine.list_review_campaigns(user)
    return 200, {"total_campaigns": len(camps), "campaigns": camps}


# --------------------------------------------------------------------------
# 7. Versioned Security Policies & Audit Coverage
# --------------------------------------------------------------------------

def handle_create_security_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/policies"""
    user = req["user"]
    require_permission(user, "security:policy", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    pol = engine.create_security_policy(data, user)
    return 201, pol


def handle_evaluate_security_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security/policies/evaluate"""
    user = req["user"]
    require_permission(user, "security:read", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    allowed, reason = engine.evaluate_security_policy(data.get("resource_type", "*"), data.get("action", "*"), data.get("context", {}))
    return 200, {"allowed": allowed, "reason_code": reason}


def handle_get_audit_coverage(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security/audit/coverage"""
    user = req["user"]
    require_permission(user, "security:read", request_id=req.get("request_id"))
    return 200, {
        "status": "OPERATIONAL",
        "hash_chaining": "SHA-256 Monotonic Continuous",
        "genesis_anchored": True,
        "audited_families": [
            "session_security",
            "step_up_auth",
            "credential_lifecycle",
            "consent_governance",
            "delegated_access",
            "break_glass_emergency",
            "access_governance",
            "policy_governance",
        ],
        "non_repudiation_mode": "TAMPER_EVIDENT_APPEND_ONLY",
    }
