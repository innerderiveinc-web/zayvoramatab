"""
REST Route Handlers for Phase 15: Post-Pilot Evaluation, Adoption Scorecard & Scale Decision
ZAYVORA MATAB OS — Independent Standalone Product
"""

import sqlite3
from typing import Any, Dict, Tuple, Optional

from apps.api.core.permissions import require_permission
from apps.api.domains.post_pilot_evaluation import (
    PostPilotEvaluationEngine,
    EvaluationStateError,
    ExpansionGateBlockedError,
    RetestEvidenceMissingError
)


def _engine(req: Dict[str, Any] = None) -> PostPilotEvaluationEngine:
    db_path = req.get("db_path") if req else None
    return PostPilotEvaluationEngine(db_path=db_path)


def _ctx(req: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str, str, str]:
    user = req["user"]
    org_id = user["organization_id"]
    fac_id = user.get("active_facility_id") or "fac-central-opd"
    actor_id = user["user_id"]
    request_id = req.get("request_id")
    return user, org_id, fac_id, actor_id, request_id


# =============================================================================
# 1. Pilot Evaluation Master Lifecycle
# =============================================================================

def handle_list_evaluations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    program_id = req.get("query_params", {}).get("pilot_program_id")
    evaluations = _engine(req).list_evaluations(pilot_program_id=program_id, organization_id=org_id)
    return 200, {"evaluations": evaluations, "request_id": request_id}


def handle_create_evaluation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    body = req.get("body", {})

    program_id = body.get("pilot_program_id")
    title = body.get("evaluation_title")
    build_commit = body.get("build_commit")
    start_date = body.get("review_period_start")
    end_date = body.get("review_period_end")

    if not all([program_id, title, build_commit, start_date, end_date]):
        return 400, {
            "error": True,
            "message": "Missing mandatory fields: 'pilot_program_id', 'evaluation_title', 'build_commit', 'review_period_start', 'review_period_end'.",
            "request_id": request_id
        }

    evaluation = _engine(req).create_evaluation(
        pilot_program_id=program_id,
        organization_id=org_id,
        evaluation_title=title,
        build_commit=build_commit,
        review_period_start=start_date,
        review_period_end=end_date,
        facility_id=body.get("facility_id") or fac_id,
        scope_version_id=body.get("scope_version_id"),
        enabled_features=body.get("enabled_features"),
        disabled_features=body.get("disabled_features"),
        roles_covered=body.get("roles_covered"),
        integrations_covered=body.get("integrations_covered"),
        success_criteria=body.get("success_criteria"),
        targets=body.get("targets"),
        created_by=actor_id
    )
    return 201, {"evaluation": evaluation, "request_id": request_id}


def handle_get_evaluation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    eval_id = req["path_params"]["id"]
    evaluation = _engine(req).get_evaluation(eval_id)
    if not evaluation:
        return 404, {"error": True, "message": f"Evaluation '{eval_id}' not found.", "request_id": request_id}
    return 200, {"evaluation": evaluation, "request_id": request_id}


def handle_update_evaluation_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    eval_id = req["path_params"]["id"]
    body = req.get("body", {})

    status = body.get("status")
    if not status:
        return 400, {"error": True, "message": "Missing 'status' field.", "request_id": request_id}

    try:
        evaluation = _engine(req).update_evaluation_status(
            evaluation_id=eval_id,
            new_status=status,
            findings_summary=body.get("findings_summary"),
            limitations_summary=body.get("limitations_summary"),
            primary_recommendation=body.get("primary_recommendation"),
            actor_id=actor_id
        )
        return 200, {"evaluation": evaluation, "request_id": request_id}
    except ValueError as e:
        return 400, {"error": True, "message": str(e), "request_id": request_id}


# =============================================================================
# 2. Evidence Inventory
# =============================================================================

def handle_collect_evidence(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    eval_id = req["path_params"]["id"]
    body = req.get("body", {})

    source_ref = body.get("source_reference")
    category = body.get("category")
    owner = body.get("owner")
    build_commit = body.get("build_commit")
    extraction_method = body.get("extraction_method")

    if not all([source_ref, category, owner, build_commit, extraction_method]):
        return 400, {
            "error": True,
            "message": "Missing mandatory fields: 'source_reference', 'category', 'owner', 'build_commit', 'extraction_method'.",
            "request_id": request_id
        }

    item = _engine(req).register_evidence_item(
        evaluation_id=eval_id,
        source_reference=source_ref,
        category=category,
        owner=owner,
        build_commit=build_commit,
        extraction_method=extraction_method,
        completeness=body.get("completeness", "COMPLETE"),
        access_restrictions=body.get("access_restrictions", "INTERNAL_RESTRICTED"),
        date_range_start=body.get("date_range_start"),
        date_range_end=body.get("date_range_end"),
        limitations=body.get("limitations"),
        verification_status=body.get("verification_status", "VERIFIED"),
        verified_by=actor_id
    )
    return 201, {"evidence_item": item, "request_id": request_id}


def handle_list_evidence(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    eval_id = req["path_params"]["id"]
    evidence = _engine(req).list_evidence_items(eval_id)
    return 200, {"evidence_items": evidence, "request_id": request_id}


# =============================================================================
# 3. Scorecard & Metrics
# =============================================================================

def handle_calculate_scorecard(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    eval_id = req["path_params"]["id"]

    try:
        scorecard = _engine(req).calculate_scorecard(eval_id)
        return 200, {"scorecard": scorecard, "request_id": request_id}
    except ValueError as e:
        return 404, {"error": True, "message": str(e), "request_id": request_id}


def handle_list_scorecard(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    eval_id = req["path_params"]["id"]
    observations = _engine(req).list_metric_observations(eval_id)
    return 200, {"metric_observations": observations, "request_id": request_id}


# =============================================================================
# 4. Feedback Theme Triage Review
# =============================================================================

def handle_review_feedback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    eval_id = req["path_params"]["id"]
    body = req.get("body", {})

    theme_title = body.get("theme_title")
    classification = body.get("classification")
    affected_role = body.get("affected_role")
    affected_workflow = body.get("affected_workflow")
    redacted_quote = body.get("redacted_evidence_quote")
    severity = body.get("severity_impact")
    hypothesis = body.get("root_cause_hypothesis")
    owner_role = body.get("owner_role")

    if not all([theme_title, classification, affected_role, affected_workflow, redacted_quote, severity, hypothesis, owner_role]):
        return 400, {
            "error": True,
            "message": "Missing required feedback theme triage fields.",
            "request_id": request_id
        }

    try:
        theme = _engine(req).review_feedback_theme(
            evaluation_id=eval_id,
            theme_title=theme_title,
            classification=classification,
            affected_role=affected_role,
            affected_workflow=affected_workflow,
            redacted_evidence_quote=redacted_quote,
            severity_impact=severity,
            root_cause_hypothesis=hypothesis,
            owner_role=owner_role,
            verified_count=body.get("verified_count", 1),
            disposition=body.get("disposition", "ACCEPTED_ACTION"),
            proposed_fix_rationale=body.get("proposed_fix_rationale"),
            retest_requirement=body.get("retest_requirement"),
            is_governance_reviewed=body.get("is_governance_reviewed", False)
        )
        return 201, {"feedback_theme": theme, "request_id": request_id}
    except ValueError as e:
        return 400, {"error": True, "message": str(e), "request_id": request_id}


def handle_list_feedback_themes(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    eval_id = req["path_params"]["id"]
    themes = _engine(req).list_feedback_themes(eval_id)
    return 200, {"feedback_themes": themes, "request_id": request_id}


# =============================================================================
# 5. Incident & Risk Reviews
# =============================================================================

def handle_review_risks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    eval_id = req["path_params"]["id"]
    body = req.get("body", {})

    issue_ref = body.get("issue_ref")
    issue_type = body.get("issue_type")
    severity = body.get("severity")
    verified_facts = body.get("verified_facts")
    containment_status = body.get("containment_status")
    corrective_action = body.get("corrective_action")

    if not all([issue_ref, issue_type, severity, verified_facts, containment_status, corrective_action]):
        return 400, {
            "error": True,
            "message": "Missing mandatory risk review fields: 'issue_ref', 'issue_type', 'severity', 'verified_facts', 'containment_status', 'corrective_action'.",
            "request_id": request_id
        }

    risk = _engine(req).record_incident_risk_review(
        evaluation_id=eval_id,
        issue_ref=issue_ref,
        issue_type=issue_type,
        severity=severity,
        verified_facts=verified_facts,
        containment_status=containment_status,
        corrective_action=corrective_action,
        uncertainties=body.get("uncertainties"),
        confirmed_root_cause=body.get("confirmed_root_cause"),
        suspected_root_cause=body.get("suspected_root_cause"),
        retest_evidence_ref=body.get("retest_evidence_ref"),
        approving_owner_id=actor_id,
        status=body.get("status", "OPEN")
    )
    return 201, {"incident_risk_review": risk, "request_id": request_id}


def handle_list_incident_risks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    eval_id = req["path_params"]["id"]
    risks = _engine(req).list_incident_risk_reviews(eval_id)
    return 200, {"incident_risk_reviews": risks, "request_id": request_id}


# =============================================================================
# 6. Expansion Proposals & Gates
# =============================================================================

def handle_create_expansion_proposal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    eval_id = req["path_params"]["id"]
    body = req.get("body", {})

    prop_type = body.get("proposal_type")
    justification = body.get("justification")
    target_scope = body.get("target_scope_details", {})
    deps = body.get("prerequisite_dependencies", [])

    if not prop_type or not justification:
        return 400, {"error": True, "message": "Missing 'proposal_type' or 'justification'.", "request_id": request_id}

    try:
        proposal = _engine(req).create_expansion_proposal(
            evaluation_id=eval_id,
            proposal_type=prop_type,
            target_scope_details=target_scope,
            justification=justification,
            prerequisite_dependencies=deps
        )
        return 201, {"expansion_proposal": proposal, "request_id": request_id}
    except ValueError as e:
        return 400, {"error": True, "message": str(e), "request_id": request_id}


def handle_evaluate_expansion_gate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    prop_id = req["path_params"]["proposal_id"]
    body = req.get("body", {})

    gate_name = body.get("gate_name")
    gate_status = body.get("gate_status")
    notes = body.get("evidence_notes", "")

    if not gate_name or not gate_status:
        return 400, {"error": True, "message": "Missing 'gate_name' or 'gate_status'.", "request_id": request_id}

    try:
        gate_res = _engine(req).evaluate_expansion_gate(
            proposal_id=prop_id,
            gate_name=gate_name,
            gate_status=gate_status,
            evidence_notes=notes,
            blocker_details=body.get("blocker_details"),
            checked_by=actor_id
        )
        return 200, {"gate_result": gate_res, "request_id": request_id}
    except ValueError as e:
        return 400, {"error": True, "message": str(e), "request_id": request_id}


def handle_list_expansion_proposals(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    eval_id = req["path_params"]["id"]
    proposals = _engine(req).list_expansion_proposals(eval_id)
    return 200, {"expansion_proposals": proposals, "request_id": request_id}


# =============================================================================
# 7. Decision Records & Approvals
# =============================================================================

def handle_record_decision(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    eval_id = req["path_params"]["id"]
    body = req.get("body", {})

    decision = body.get("decision")
    rationale = body.get("rationale")
    allowed_scope = body.get("allowed_scope_summary")
    disabled_features = body.get("disabled_features_summary")

    if not all([decision, rationale, allowed_scope, disabled_features]):
        return 400, {
            "error": True,
            "message": "Missing mandatory decision fields: 'decision', 'rationale', 'allowed_scope_summary', 'disabled_features_summary'.",
            "request_id": request_id
        }

    try:
        record = _engine(req).record_decision(
            evaluation_id=eval_id,
            decision=decision,
            rationale=rationale,
            allowed_scope_summary=allowed_scope,
            disabled_features_summary=disabled_features,
            recorded_by=actor_id,
            accepted_residual_risks=body.get("accepted_residual_risks"),
            next_review_date=body.get("next_review_date")
        )
        return 201, {"decision_record": record, "request_id": request_id}
    except ExpansionGateBlockedError as e:
        return 409, {"error": True, "code": "EXPANSION_BLOCKED", "message": str(e), "blockers": e.blockers, "request_id": request_id}
    except ValueError as e:
        return 400, {"error": True, "message": str(e), "request_id": request_id}


def handle_approve_decision(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:approve_decision", request_id=request_id)
    body = req.get("body", {})

    decision_id = body.get("decision_record_id")
    role = body.get("required_role")
    status = body.get("approval_status", "APPROVED")

    if not decision_id or not role:
        return 400, {"error": True, "message": "Missing 'decision_record_id' or 'required_role'.", "request_id": request_id}

    try:
        approval = _engine(req).approve_decision(
            decision_record_id=decision_id,
            required_role=role,
            approver_user_id=actor_id,
            approval_status=status,
            conditions_or_notes=body.get("conditions_or_notes")
        )
        return 200, {"decision_approval": approval, "request_id": request_id}
    except ValueError as e:
        return 400, {"error": True, "message": str(e), "request_id": request_id}


def handle_get_decision(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    eval_id = req["path_params"]["id"]
    decision = _engine(req).get_decision_with_approvals(eval_id)
    return 200, {"decision": decision, "request_id": request_id}


# =============================================================================
# 8. Remediation Actions
# =============================================================================

def handle_create_remediation_action(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:remediation", request_id=request_id)
    eval_id = req["path_params"]["id"]
    body = req.get("body", {})

    title = body.get("title")
    desc = body.get("description")
    cat = body.get("category")
    prio = body.get("priority")
    owner_role = body.get("owner_role")
    retest_req = body.get("retest_requirement")

    if not all([title, desc, cat, prio, owner_role, retest_req]):
        return 400, {
            "error": True,
            "message": "Missing mandatory action fields: 'title', 'description', 'category', 'priority', 'owner_role', 'retest_requirement'.",
            "request_id": request_id
        }

    action = _engine(req).add_remediation_action(
        evaluation_id=eval_id,
        title=title,
        description=desc,
        category=cat,
        priority=prio,
        owner_role=owner_role,
        retest_requirement=retest_req,
        owner_user_id=body.get("owner_user_id"),
        due_date=body.get("due_date"),
        retest_evidence_ref=body.get("retest_evidence_ref")
    )
    return 201, {"remediation_action": action, "request_id": request_id}


def handle_close_remediation_action(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:remediation", request_id=request_id)
    action_id = req["path_params"]["action_id"]
    body = req.get("body", {})

    retest_ref = body.get("retest_evidence_ref")
    if not retest_ref:
        return 400, {"error": True, "message": "Mandatory 'retest_evidence_ref' required to close action.", "request_id": request_id}

    try:
        action = _engine(req).close_remediation_action(
            action_id=action_id,
            closed_by_user_id=actor_id,
            retest_evidence_ref=retest_ref
        )
        return 200, {"remediation_action": action, "request_id": request_id}
    except RetestEvidenceMissingError as e:
        return 400, {"error": True, "message": str(e), "request_id": request_id}


def handle_list_remediation_actions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    eval_id = req["path_params"]["id"]
    actions = _engine(req).list_remediation_actions(eval_id)
    return 200, {"remediation_actions": actions, "request_id": request_id}


# =============================================================================
# 9. Comprehensive Report Generator
# =============================================================================

def handle_generate_report(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "pilot:evaluate", request_id=request_id)
    eval_id = req["path_params"]["id"]

    try:
        report = _engine(req).generate_evaluation_report(evaluation_id=eval_id, generated_by=actor_id)
        return 200, {"report": report, "request_id": request_id}
    except ValueError as e:
        return 404, {"error": True, "message": str(e), "request_id": request_id}
