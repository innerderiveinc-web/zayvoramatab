"""
REST API Route Handlers for Enterprise Test Automation, Regression & Release Qualification
ZAYVORA MATAB OS — Phase 49
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.test_automation import EnterpriseTestAutomationReleaseQualificationEngine


def handle_get_test_qualification_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/summary - Executive test automation and qualification KPIs."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    summary = engine.get_test_qualification_summary()
    return 200, {"success": True, "summary": summary}


# -------------------------------------------------------------------------
# Test Suites Catalog
# -------------------------------------------------------------------------
def handle_list_test_suites(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/suites - List registered test suites."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    params = req.get("query_params", {})
    suites = engine.list_test_suites(
        test_layer=params.get("test_layer"),
        target_subsystem=params.get("target_subsystem"),
        status=params.get("status"),
    )
    return 200, {"success": True, "suites": suites, "count": len(suites)}


def handle_get_test_suite(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/suites/{id} - Get test suite details."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    suite_id = req["path_params"]["id"]
    suite = engine.get_test_suite(suite_id)
    return 200, {"success": True, "suite": suite}


def handle_register_test_suite(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/suites - Register a new test suite."""
    require_permission(req["user"], "test_qualification:manage", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    suite = engine.register_test_suite(
        actor_id=actor_id,
        suite_code=body.get("suite_code", ""),
        name=body.get("name", ""),
        test_layer=body.get("test_layer", "UNIT"),
        target_subsystem=body.get("target_subsystem", "CLINICAL"),
        test_file_path=body.get("test_file_path", ""),
        command_template=body.get("command_template", ""),
        execution_environment=body.get("execution_environment", "ISOLATED_SYNTHETIC"),
        is_mandatory_for_release=body.get("is_mandatory_for_release", 1),
        timeout_seconds=body.get("timeout_seconds", 60),
    )
    return 201, {"success": True, "suite": suite}


def handle_update_test_suite(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PUT /api/v1/test-qualification/suites/{id} - Update test suite metadata or status."""
    require_permission(req["user"], "test_qualification:manage", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    suite_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    suite = engine.update_test_suite(actor_id=actor_id, suite_id=suite_id, update_fields=body)
    return 200, {"success": True, "suite": suite}


# -------------------------------------------------------------------------
# Test Execution Runs Evidence Ledger
# -------------------------------------------------------------------------
def handle_list_execution_runs(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/runs - List test execution runs."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    params = req.get("query_params", {})
    limit = int(params.get("limit", 100))
    runs = engine.list_execution_runs(
        suite_id=params.get("suite_id"),
        target_release_version=params.get("target_release_version"),
        status=params.get("status"),
        limit=limit,
    )
    return 200, {"success": True, "runs": runs, "count": len(runs)}


def handle_get_execution_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/runs/{id} - Get execution run detail."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    run_id = req["path_params"]["id"]
    run = engine.get_execution_run(run_id)
    return 200, {"success": True, "run": run}


def handle_record_execution_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/runs - Record a verified test execution run."""
    require_permission(req["user"], "test_qualification:execute", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    run = engine.record_execution_run(
        actor_id=actor_id,
        suite_id=body.get("suite_id", ""),
        target_release_version=body.get("target_release_version", "v1.0.0"),
        environment=body.get("environment", "ISOLATED_SYNTHETIC"),
        commit_hash=body.get("commit_hash", "HEAD"),
        trigger_source=body.get("trigger_source", "CI_PIPELINE"),
        status=body.get("status", "PASSED"),
        total_tests=int(body.get("total_tests", 0)),
        passed_tests=int(body.get("passed_tests", 0)),
        failed_tests=int(body.get("failed_tests", 0)),
        skipped_tests=int(body.get("skipped_tests", 0)),
        execution_duration_ms=int(body.get("execution_duration_ms", 0)),
        evidence_summary=body.get("evidence_summary"),
    )
    return 201, {"success": True, "run": run}


# -------------------------------------------------------------------------
# Test Flakiness & Quarantine Register
# -------------------------------------------------------------------------
def handle_list_quarantined_tests(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/quarantines - List quarantined tests."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    params = req.get("query_params", {})
    quarantines = engine.list_quarantined_tests(
        status=params.get("status"),
        suite_id=params.get("suite_id"),
    )
    return 200, {"success": True, "quarantines": quarantines, "count": len(quarantines)}


def handle_get_quarantined_test(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/quarantines/{id} - Get quarantined test details."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    quarantine_id = req["path_params"]["id"]
    quarantine = engine.get_quarantined_test(quarantine_id)
    return 200, {"success": True, "quarantine": quarantine}


def handle_quarantine_test(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/quarantines - Quarantine an unstable/flaky test."""
    require_permission(req["user"], "test_qualification:quarantine", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    quarantine = engine.quarantine_test(
        actor_id=actor_id,
        suite_id=body.get("suite_id", ""),
        test_name=body.get("test_name", ""),
        reason=body.get("reason", ""),
        root_cause_category=body.get("root_cause_category", "UNKNOWN"),
        assigned_owner=body.get("assigned_owner", ""),
        target_resolution_days=int(body.get("target_resolution_days", 14)),
    )
    return 201, {"success": True, "quarantine": quarantine}


def handle_resolve_quarantine(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/quarantines/{id}/resolve - Resolve or re-enable a quarantined test."""
    require_permission(req["user"], "test_qualification:quarantine", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    quarantine_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    quarantine = engine.resolve_quarantine(
        actor_id=actor_id,
        quarantine_id=quarantine_id,
        status=body.get("status", "RESOLVED"),
        notes=body.get("notes"),
    )
    return 200, {"success": True, "quarantine": quarantine}


# -------------------------------------------------------------------------
# Release Qualification Profiles
# -------------------------------------------------------------------------
def handle_list_qualification_profiles(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/profiles - List qualification profiles."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    params = req.get("query_params", {})
    profiles = engine.list_qualification_profiles(target_tier=params.get("target_tier"))
    return 200, {"success": True, "profiles": profiles, "count": len(profiles)}


def handle_get_qualification_profile(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/profiles/{id} - Get profile details."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    profile_id = req["path_params"]["id"]
    profile = engine.get_qualification_profile(profile_id)
    return 200, {"success": True, "profile": profile}


def handle_create_qualification_profile(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/profiles - Create qualification profile."""
    require_permission(req["user"], "test_qualification:manage", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    profile = engine.create_qualification_profile(
        actor_id=actor_id,
        profile_code=body.get("profile_code", ""),
        name=body.get("name", ""),
        target_tier=body.get("target_tier", "DEVELOPMENT"),
        required_test_layers=body.get("required_test_layers", []),
        required_suites=body.get("required_suites", []),
        min_pass_rate_bp=int(body.get("min_pass_rate_bp", 10000)),
        allow_quarantined_tests=int(body.get("allow_quarantined_tests", 0)),
        max_critical_defects=int(body.get("max_critical_defects", 0)),
    )
    return 201, {"success": True, "profile": profile}


# -------------------------------------------------------------------------
# Release Candidate Qualifications (Gate Decisions)
# -------------------------------------------------------------------------
def handle_list_candidate_qualifications(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/candidates - List release qualification verdicts."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    params = req.get("query_params", {})
    candidates = engine.list_candidate_qualifications(
        target_release_version=params.get("target_release_version"),
        overall_verdict=params.get("overall_verdict"),
    )
    return 200, {"success": True, "candidates": candidates, "count": len(candidates)}


def handle_get_candidate_qualification(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/candidates/{id} - Get qualification decision detail."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    candidate_id = req["path_params"]["id"]
    candidate = engine.get_candidate_qualification(candidate_id)
    return 200, {"success": True, "candidate": candidate}


def handle_evaluate_release_candidate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/candidates/evaluate - Run fail-closed release gate evaluation."""
    require_permission(req["user"], "test_qualification:qualify_release", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    candidate = engine.evaluate_release_candidate(
        actor_id=actor_id,
        target_release_version=body.get("target_release_version", "v1.0.0"),
        profile_id=body.get("profile_id", ""),
        commit_hash=body.get("commit_hash", "HEAD"),
        repository_revision=body.get("repository_revision", "HEAD"),
    )
    status_code = 200 if candidate["overall_verdict"] == "QUALIFIED" else 422
    return status_code, {"success": candidate["overall_verdict"] == "QUALIFIED", "candidate": candidate}


# -------------------------------------------------------------------------
# Test Automation Defect Register
# -------------------------------------------------------------------------
def handle_list_defects(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/defects - List defects."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    params = req.get("query_params", {})
    defects = engine.list_defects(
        severity=params.get("severity"),
        status=params.get("status"),
        linked_hazard_id=params.get("linked_hazard_id"),
    )
    return 200, {"success": True, "defects": defects, "count": len(defects)}


def handle_get_defect(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/defects/{id} - Get defect detail."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    defect_id = req["path_params"]["id"]
    defect = engine.get_defect(defect_id)
    return 200, {"success": True, "defect": defect}


def handle_log_defect(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/defects - Log a new defect with hazard linkage."""
    require_permission(req["user"], "test_qualification:manage", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    defect = engine.log_defect(
        actor_id=actor_id,
        title=body.get("title", ""),
        test_name=body.get("test_name", ""),
        severity=body.get("severity", "MAJOR"),
        failure_classification=body.get("failure_classification", "PRODUCT_DEFECT"),
        sanitized_stack_trace=body.get("sanitized_stack_trace", ""),
        reproduction_steps=body.get("reproduction_steps", ""),
        assigned_owner=body.get("assigned_owner", ""),
        test_run_id=body.get("test_run_id"),
        linked_hazard_id=body.get("linked_hazard_id"),
    )
    return 201, {"success": True, "defect": defect}


def handle_update_defect_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/defects/{id}/status - Update defect status."""
    require_permission(req["user"], "test_qualification:manage", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    defect_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    defect = engine.update_defect_status(
        actor_id=actor_id,
        defect_id=defect_id,
        new_status=body.get("new_status", "INVESTIGATING"),
        notes=body.get("notes"),
    )
    return 200, {"success": True, "defect": defect}


# -------------------------------------------------------------------------
# Tamper-Evident Audit Ledger & Verification
# -------------------------------------------------------------------------
def handle_get_audit_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/test-qualification/audit - View SHA-256 audit ledger."""
    require_permission(req["user"], "test_qualification:read", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    params = req.get("query_params", {})
    limit = int(params.get("limit", 100))
    audit_events = engine.get_audit_ledger(
        limit=limit,
        actor_id=params.get("actor_id"),
        event_type=params.get("event_type"),
    )
    return 200, {"success": True, "audit_events": audit_events, "count": len(audit_events)}


def handle_verify_audit_integrity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/test-qualification/audit/verify - Verify cryptographic hash chain integrity."""
    require_permission(req["user"], "test_qualification:manage", request_id=req.get("request_id"))
    engine = EnterpriseTestAutomationReleaseQualificationEngine(conn)
    verification = engine.verify_audit_integrity()
    return 200, {"success": True, "verification": verification}
