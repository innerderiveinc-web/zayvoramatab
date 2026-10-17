"""API Route Handlers for API & Integration Certification, Contract Testing & Developer Governance.

Phase 52 of ZAYVORA MATAB OS.
Mounted under `/api/v1/api-governance/`.
"""

import json
import secrets
import sqlite3
from typing import Dict, Any, Tuple


from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, ForbiddenError, NotFoundError
from apps.api.domains.api_integration_certification_engine import ApiIntegrationCertificationEngine


def _get_engine(conn: sqlite3.Connection) -> ApiIntegrationCertificationEngine:
    return ApiIntegrationCertificationEngine(conn)


# -------------------------------------------------------------------------
# 1. Integrations Catalog
# -------------------------------------------------------------------------

def handle_list_integrations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/api-governance/integrations"""
    user = req.get("user", {})
    require_permission(user, "api_governance:read", request_id=req.get("request_id"))

    tenant_id = user.get("tenant_id", "T-SYSTEM")
    query_params = req.get("query_params", {})
    category = query_params.get("category")
    cert_level = query_params.get("certification_level")

    engine = _get_engine(conn)
    integrations = engine.list_integrations(tenant_id, category=category, certification_level=cert_level)
    return 200, {
        "success": True,
        "count": len(integrations),
        "integrations": integrations,
    }


def handle_get_integration(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/api-governance/integrations/{id}"""
    user = req.get("user", {})
    require_permission(user, "api_governance:read", request_id=req.get("request_id"))

    integration_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    integration = engine.get_integration(integration_id)
    return 200, {"success": True, "integration": integration}


def handle_register_integration(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/integrations"""
    user = req.get("user", {})
    require_permission(user, "api_governance:manage", request_id=req.get("request_id"))

    tenant_id = user.get("tenant_id", "T-SYSTEM")
    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})

    engine = _get_engine(conn)
    integration = engine.register_integration(tenant_id, body, actor_id=actor_id)
    return 201, {"success": True, "integration": integration}


# -------------------------------------------------------------------------
# 2. Contracts & Drift Detection
# -------------------------------------------------------------------------

def handle_list_contracts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/api-governance/contracts"""
    user = req.get("user", {})
    require_permission(user, "api_governance:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    integration_id = query_params.get("integration_id")

    engine = _get_engine(conn)
    contracts = engine.list_contracts(integration_id=integration_id)
    return 200, {"success": True, "count": len(contracts), "contracts": contracts}


def handle_register_contract(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/contracts"""
    user = req.get("user", {})
    require_permission(user, "api_governance:manage", request_id=req.get("request_id"))

    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})

    engine = _get_engine(conn)
    contract = engine.register_contract(body, actor_id=actor_id)
    return 201, {"success": True, "contract": contract}


def handle_contract_drift_check(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/drift-check"""
    user = req.get("user", {})
    require_permission(user, "api_governance:contract_validate", request_id=req.get("request_id"))

    from apps.api.router import ROUTES
    engine = _get_engine(conn)
    drift_report = engine.detect_contract_drift(ROUTES)
    return 200, {"success": True, "drift_report": drift_report}


# -------------------------------------------------------------------------
# 3. Developer API Keys
# -------------------------------------------------------------------------

def handle_list_api_keys(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/api-governance/keys"""
    user = req.get("user", {})
    require_permission(user, "api_governance:key_manage", request_id=req.get("request_id"))

    tenant_id = user.get("tenant_id", "T-SYSTEM")
    engine = _get_engine(conn)
    keys = engine.list_api_keys(tenant_id)
    return 200, {"success": True, "count": len(keys), "keys": keys}


def handle_generate_api_key(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/keys"""
    user = req.get("user", {})
    require_permission(user, "api_governance:key_manage", request_id=req.get("request_id"))

    tenant_id = user.get("tenant_id", "T-SYSTEM")
    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})

    client_name = body.get("client_name", "")
    environment = body.get("environment", "SANDBOX")
    scopes = body.get("allowed_scopes", ["api:read"])
    rpm = int(body.get("rate_limit_rpm", 120))
    allowed_ips = body.get("allowed_ips")
    facility_id = body.get("facility_id")

    engine = _get_engine(conn)
    key_info = engine.generate_api_key(
        tenant_id=tenant_id,
        client_name=client_name,
        environment=environment,
        allowed_scopes=scopes,
        rate_limit_rpm=rpm,
        allowed_ips=allowed_ips,
        created_by=actor_id,
        facility_id=facility_id,
    )
    return 201, {"success": True, "key": key_info}


def handle_revoke_api_key(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/keys/{id}/revoke"""
    user = req.get("user", {})
    require_permission(user, "api_governance:key_manage", request_id=req.get("request_id"))

    key_id = req["path_params"]["id"]
    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})
    reason = body.get("reason", "Revocation requested via API")

    engine = _get_engine(conn)
    result = engine.revoke_api_key(key_id, actor_id=actor_id, reason=reason)
    return 200, {"success": True, "result": result}


# -------------------------------------------------------------------------
# 4. Idempotency Test Seam
# -------------------------------------------------------------------------

def handle_idempotency_check(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/idempotency/check"""
    user = req.get("user", {})
    require_permission(user, "api_governance:read", request_id=req.get("request_id"))

    tenant_id = user.get("tenant_id", "T-SYSTEM")
    body = req.get("body", {})
    idempotency_key = body.get("idempotency_key", "")
    endpoint_path = body.get("endpoint_path", "/api/v1/sample")
    payload = body.get("payload", {})

    engine = _get_engine(conn)
    result = engine.check_or_set_idempotency(
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        endpoint_path=endpoint_path,
        request_payload=payload,
    )
    return 200, {"success": True, "idempotency_status": result}


# -------------------------------------------------------------------------
# 5. Inbound Webhook Verification
# -------------------------------------------------------------------------

def handle_verify_inbound_webhook(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/webhooks/verify-inbound"""
    user = req.get("user", {})
    require_permission(user, "api_governance:webhook_manage", request_id=req.get("request_id"))

    tenant_id = user.get("tenant_id", "T-SYSTEM")
    body = req.get("body", {})
    provider = body.get("provider", "GENERIC_HMAC")
    payload_str = body.get("payload_str", "{}")
    signature = body.get("signature_header", "")
    timestamp_header = body.get("timestamp_header")
    secret_token = body.get("secret_token")
    event_id = body.get("event_id")

    engine = _get_engine(conn)
    result = engine.verify_inbound_webhook(
        tenant_id=tenant_id,
        provider=provider,
        raw_payload_bytes=payload_str.encode("utf-8"),
        signature_header=signature,
        timestamp_header=timestamp_header,
        secret_token=secret_token,
        event_id=event_id,
    )
    return 200, {"success": True, "verification": result}


# -------------------------------------------------------------------------
# 6. Outbound Webhook Subscriptions & Delivery
# -------------------------------------------------------------------------

def handle_create_webhook_subscription(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/webhooks/subscriptions"""
    user = req.get("user", {})
    require_permission(user, "api_governance:webhook_manage", request_id=req.get("request_id"))

    tenant_id = user.get("tenant_id", "T-SYSTEM")
    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})

    target_url = body.get("target_url", "")
    event_types = body.get("event_types", [])
    secret_token = body.get("secret_token", secrets.token_hex(16))
    allow_test_local = bool(body.get("allow_test_local", False))

    engine = _get_engine(conn)
    subscription = engine.create_webhook_subscription(
        tenant_id=tenant_id,
        target_url=target_url,
        event_types=event_types,
        secret_token=secret_token,
        actor_id=actor_id,
        allow_test_local=allow_test_local,
    )
    return 201, {"success": True, "subscription": subscription}


def handle_dispatch_webhook(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/webhooks/subscriptions/{id}/dispatch"""
    user = req.get("user", {})
    require_permission(user, "api_governance:webhook_manage", request_id=req.get("request_id"))

    subscription_id = req["path_params"]["id"]
    body = req.get("body", {})
    event_id = body.get("event_id", f"EVT-{secrets.token_hex(4).upper()}")
    event_type = body.get("event_type", "clinical.event")
    payload = body.get("payload", {})
    allow_test_local = bool(body.get("allow_test_local", False))

    engine = _get_engine(conn)
    result = engine.dispatch_outbound_webhook(
        subscription_id=subscription_id,
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        allow_test_local=allow_test_local,
    )
    return 200, {"success": True, "delivery": result}


# -------------------------------------------------------------------------
# 7. Integration Certification Lifecycle
# -------------------------------------------------------------------------

def handle_certify_integration(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/api-governance/certify"""
    user = req.get("user", {})
    require_permission(user, "api_governance:certify", request_id=req.get("request_id"))

    actor_id = user.get("user_id", "USER-SYSTEM")
    roles = user.get("org_roles", [])
    certified_by_role = "CLINICAL_SAFETY_OFFICER" if "CLINICAL_SAFETY_OFFICER" in roles else (
        "LEAD_ARCHITECT" if "LEAD_ARCHITECT" in roles else ("ORG_ADMIN" if "ORG_ADMIN" in roles else "PRACTITIONER")
    )

    body = req.get("body", {})
    integration_id = body.get("integration_id", "")
    level = body.get("certification_level", "CONTRACT_TESTED")
    evidence = body.get("evidence_summary", "")
    valid_days = int(body.get("valid_days", 365))
    test_run_id = body.get("test_suite_run_id")

    engine = _get_engine(conn)
    cert = engine.certify_integration(
        integration_id=integration_id,
        certification_level=level,
        evidence_summary=evidence,
        certified_by=actor_id,
        certified_by_role=certified_by_role,
        valid_days=valid_days,
        test_suite_run_id=test_run_id,
    )
    return 200, {"success": True, "certification": cert}


def handle_list_certifications(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/api-governance/certifications"""
    user = req.get("user", {})
    require_permission(user, "api_governance:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    integration_id = query_params.get("integration_id")

    engine = _get_engine(conn)
    certs = engine.list_certifications(integration_id=integration_id)
    return 200, {"success": True, "count": len(certs), "certifications": certs}


# -------------------------------------------------------------------------
# 8. Cryptographic Audit Ledger Verification
# -------------------------------------------------------------------------

def handle_verify_ledger_integrity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/api-governance/audit-ledger/verify"""
    user = req.get("user", {})
    require_permission(user, "api_governance:read", request_id=req.get("request_id"))

    engine = _get_engine(conn)
    report = engine.verify_audit_ledger_integrity()
    return 200, {"success": True, "ledger_report": report}
