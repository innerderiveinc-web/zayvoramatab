"""REST API Route Handlers for Clinical Workflow Intelligence & Data Quality Engine.

Phase 24 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- data_quality:read
- data_quality:evaluate
- data_quality:reconcile
- data_quality:manage
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.data_quality import DataQualityEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> DataQualityEngine:
    db_path = req.get("db_path")
    return DataQualityEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Rule Registry & Freshness Policies
# --------------------------------------------------------------------------

def handle_list_rules(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/data-quality/rules"""
    user = req["user"]
    require_permission(user, "data_quality:read", request_id=req.get("request_id"))
    active_only = req.get("query_params", {}).get("active_only", "true").lower() == "true"
    scope_type = req.get("query_params", {}).get("scope_type")

    engine = _get_engine(req)
    rules = engine.list_rules(active_only=active_only, scope_type=scope_type)
    return 200, {"rules": rules, "total": len(rules)}


def handle_get_rule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/data-quality/rules/{rule_code}"""
    user = req["user"]
    require_permission(user, "data_quality:read", request_id=req.get("request_id"))
    rule_code = _param(req, "rule_code")

    engine = _get_engine(req)
    rule = engine.get_rule(rule_code)
    return 200, {"rule": rule}


def handle_list_freshness_policies(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/data-quality/freshness-policies"""
    user = req["user"]
    require_permission(user, "data_quality:read", request_id=req.get("request_id"))
    active_only = req.get("query_params", {}).get("active_only", "true").lower() == "true"

    engine = _get_engine(req)
    policies = engine.list_freshness_policies(active_only=active_only)
    return 200, {"freshness_policies": policies, "total": len(policies)}


# --------------------------------------------------------------------------
# 2. Data Quality Evaluation Execution
# --------------------------------------------------------------------------

def handle_evaluate_data_quality(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/data-quality/evaluations"""
    user = req["user"]
    require_permission(user, "data_quality:evaluate", request_id=req.get("request_id"))
    body = req.get("body", {})

    patient_id = body.get("patient_id")
    if not patient_id:
        raise ValidationError("patient_id is required for data quality evaluation.")

    encounter_id = body.get("encounter_id")
    scope_type = body.get("scope_type", "ENCOUNTER" if encounter_id else "PATIENT")
    trigger = body.get("evaluation_trigger", "MANUAL")

    engine = _get_engine(req)
    result = engine.evaluate_data_quality(
        patient_id=patient_id,
        encounter_id=encounter_id,
        scope_type=scope_type,
        trigger=trigger,
        user_ctx=user
    )
    return 201, result


# --------------------------------------------------------------------------
# 3. Findings & Remediation Resolution
# --------------------------------------------------------------------------

def handle_list_findings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/data-quality/findings"""
    user = req["user"]
    require_permission(user, "data_quality:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})

    encounter_id = qp.get("encounter_id")
    patient_id = qp.get("patient_id")
    remediation_status = qp.get("remediation_status")
    remediation_role = qp.get("remediation_role")

    engine = _get_engine(req)
    findings = engine.list_findings(
        encounter_id=encounter_id,
        patient_id=patient_id,
        remediation_status=remediation_status,
        remediation_role=remediation_role
    )
    return 200, {"findings": findings, "total": len(findings)}


def handle_get_finding(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/data-quality/findings/{id}"""
    user = req["user"]
    require_permission(user, "data_quality:read", request_id=req.get("request_id"))
    finding_id = _param(req, "id")

    engine = _get_engine(req)
    finding = engine.get_finding(finding_id)
    return 200, {"finding": finding}


def handle_resolve_finding(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/data-quality/findings/{id}/resolve"""
    user = req["user"]
    require_permission(user, "data_quality:reconcile", request_id=req.get("request_id"))
    finding_id = _param(req, "id")
    body = req.get("body", {})

    action = body.get("action")
    if not action:
        raise ValidationError("Remediation action is required.")

    reason = body.get("reason")
    details = body.get("resolution_details")

    engine = _get_engine(req)
    res = engine.resolve_finding(
        finding_id=finding_id,
        action=action,
        user_ctx=user,
        reason=reason,
        resolution_details=details
    )
    return 200, res


# --------------------------------------------------------------------------
# 4. Conflict Reconciliation
# --------------------------------------------------------------------------

def handle_reconcile_conflict(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/data-quality/reconcile"""
    user = req["user"]
    require_permission(user, "data_quality:reconcile", request_id=req.get("request_id"))
    body = req.get("body", {})

    patient_id = body.get("patient_id")
    field_name = body.get("field_name")
    conflict_summary = body.get("conflict_summary")
    options_evaluated = body.get("options_evaluated", [])
    selected_value = body.get("selected_value")
    clinician_rationale = body.get("clinician_rationale")
    encounter_id = body.get("encounter_id")

    if not patient_id or not field_name or not conflict_summary:
        raise ValidationError("patient_id, field_name, and conflict_summary are required.")

    engine = _get_engine(req)
    res = engine.reconcile_conflict(
        patient_id=patient_id,
        field_name=field_name,
        conflict_summary=conflict_summary,
        options_evaluated=options_evaluated,
        selected_value=selected_value,
        clinician_rationale=clinician_rationale,
        user_ctx=user,
        encounter_id=encounter_id
    )
    return 201, res


# --------------------------------------------------------------------------
# 5. Field Provenance
# --------------------------------------------------------------------------

def handle_record_provenance(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/data-quality/provenance"""
    user = req["user"]
    require_permission(user, "data_quality:evaluate", request_id=req.get("request_id"))
    body = req.get("body", {})

    org_id = user.get("organization_id", "org-matab-default")
    entity_type = body.get("entity_type")
    entity_id = body.get("entity_id")
    field_name = body.get("field_name")
    field_value = body.get("field_value")
    source_stream = body.get("source_stream")
    unit = body.get("unit")
    policy_code = body.get("freshness_policy_code")
    encounter_id = body.get("source_encounter_id")

    if not entity_type or not entity_id or not field_name or not source_stream:
        raise ValidationError("entity_type, entity_id, field_name, and source_stream are required.")

    engine = _get_engine(req)
    res = engine.record_field_provenance(
        organization_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
        field_value=field_value,
        recorded_by=user.get("user_id", "system"),
        source_stream=source_stream,
        unit=unit,
        freshness_policy_code=policy_code,
        source_encounter_id=encounter_id
    )
    return 201, res


def handle_get_provenance(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/data-quality/provenance"""
    user = req["user"]
    require_permission(user, "data_quality:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})

    entity_type = qp.get("entity_type")
    entity_id = qp.get("entity_id")
    field_name = qp.get("field_name")

    if not entity_type or not entity_id:
        raise ValidationError("entity_type and entity_id query parameters are required.")

    engine = _get_engine(req)
    history = engine.get_field_provenance(entity_type=entity_type, entity_id=entity_id, field_name=field_name)
    return 200, {"provenance_records": history, "total": len(history)}


# --------------------------------------------------------------------------
# 6. Encounter Data Quality Readiness
# --------------------------------------------------------------------------

def handle_check_dq_readiness(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/encounters/{encounter_id}/data-quality-readiness"""
    user = req["user"]
    require_permission(user, "data_quality:read", request_id=req.get("request_id"))
    encounter_id = _param(req, "encounter_id")

    engine = _get_engine(req)
    readiness = engine.check_dq_readiness(encounter_id, user_ctx=user)
    return 200, readiness
