"""Modern Clinical Assessment REST API Route Handlers.
Endpoints for structured clinical history, observations/vitals, red flags,
differential candidates, problems, investigations, referrals, signing, and amendments.
"""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError
from apps.api.domains.modern_assessment import ModernAssessmentService


def handle_modern_assessment_create_for_encounter(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Create or return draft modern clinical assessment for active encounter."""
    user = req["user"]
    require_permission(user, "modern_assessment:create_draft", request_id=req.get("request_id"))
    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})

    assessment = ModernAssessmentService.create_assessment_draft(
        conn=conn,
        user_ctx=user,
        encounter_id=encounter_id,
        payload=body
    )
    return 201, {"assessment": assessment}


def handle_modern_assessment_get_for_encounter(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Get active or signed modern assessment for encounter."""
    user = req["user"]
    require_permission(user, "modern_assessment:read", request_id=req.get("request_id"))
    encounter_id = req["path_params"]["id"]

    assessment = ModernAssessmentService.get_assessment_by_encounter(
        conn=conn,
        user_ctx=user,
        encounter_id=encounter_id
    )
    return 200, {"assessment": assessment}


def handle_modern_assessment_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Fetch complete modern assessment aggregate with observations, red flags, differentials, problems, and referrals."""
    user = req["user"]
    require_permission(user, "modern_assessment:read", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]

    assessment = ModernAssessmentService.get_assessment_by_id(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id
    )
    return 200, {"assessment": assessment}


def handle_modern_assessment_update_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Update editable fields of draft assessment with optimistic concurrency checking."""
    user = req["user"]
    require_permission(user, "modern_assessment:update_draft", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    assessment = ModernAssessmentService.update_assessment_draft(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 200, {"assessment": assessment}


def handle_modern_assessment_observations_add(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Record or update typed observations and vitals for assessment."""
    user = req["user"]
    require_permission(user, "modern_assessment:update_draft", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    observations = body.get("observations", [])
    if not isinstance(observations, list) or len(observations) == 0:
        raise ValidationError("Request body must contain a non-empty 'observations' array.")

    assessment = ModernAssessmentService.get_assessment_by_id(conn, user, assessment_id)
    ModernAssessmentService._persist_observations(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        patient_id=assessment["patient_id"],
        encounter_id=assessment["encounter_id"],
        observations_list=observations
    )

    updated = ModernAssessmentService.get_assessment_by_id(conn, user, assessment_id)
    return 200, {"observations": updated["observations"]}


def handle_modern_assessment_run_safety_checks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Evaluate deterministic red-flag safety rules against current assessment context."""
    user = req["user"]
    require_permission(user, "modern_assessment:read", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]

    result = ModernAssessmentService.run_safety_checks(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id
    )
    return 200, result


def handle_modern_assessment_acknowledge_red_flag(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Acknowledge or override a triggered red flag with documented clinical action."""
    user = req["user"]
    require_permission(user, "modern_assessment:update_draft", request_id=req.get("request_id"))
    alert_id = req["path_params"]["alert_id"]
    body = req.get("body", {})

    result = ModernAssessmentService.acknowledge_red_flag(
        conn=conn,
        user_ctx=user,
        alert_id=alert_id,
        payload=body
    )
    return 200, result


def handle_modern_assessment_run_differential(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Run explainable differential diagnosis heuristic evaluation."""
    user = req["user"]
    require_permission(user, "modern_assessment:read", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]

    result = ModernAssessmentService.run_differential_support(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id
    )
    return 200, result


def handle_modern_assessment_decide_differential(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Clinician reviews a differential consideration: ACCEPT, REJECT, DEFER, or CONFIRM_AS_PROBLEM."""
    user = req["user"]
    require_permission(user, "modern_assessment:update_draft", request_id=req.get("request_id"))
    candidate_id = req["path_params"]["candidate_id"]
    body = req.get("body", {})

    result = ModernAssessmentService.decide_differential_candidate(
        conn=conn,
        user_ctx=user,
        candidate_id=candidate_id,
        payload=body
    )
    return 200, result


def handle_modern_assessment_problem_add(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Add a clinical problem or confirmed diagnosis to the assessment problem list."""
    user = req["user"]
    require_permission(user, "modern_assessment:update_draft", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    problem = ModernAssessmentService.add_clinical_problem(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 201, {"problem": problem}


def handle_modern_assessment_decide_investigation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Record clinician decision on an investigation consideration."""
    user = req["user"]
    require_permission(user, "modern_assessment:update_draft", request_id=req.get("request_id"))
    inv_id = req["path_params"]["inv_id"]
    body = req.get("body", {})

    result = ModernAssessmentService.decide_investigation_consideration(
        conn=conn,
        user_ctx=user,
        consideration_id=inv_id,
        payload=body
    )
    return 200, result


def handle_modern_assessment_referral_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Document clinical referral / escalation plan."""
    user = req["user"]
    require_permission(user, "modern_assessment:update_draft", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    referral = ModernAssessmentService.create_referral_record(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 201, {"referral": referral}


def handle_modern_assessment_sign(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Sign and lock modern clinical assessment with clinician PIN authentication."""
    user = req["user"]
    require_permission(user, "modern_assessment:sign", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    assessment = ModernAssessmentService.sign_assessment(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 200, {"assessment": assessment}


def handle_modern_assessment_amend(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Create versioned amendment of signed assessment without rewriting historical record."""
    user = req["user"]
    require_permission(user, "modern_assessment:amend", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    assessment = ModernAssessmentService.amend_assessment(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 200, {"assessment": assessment}


def handle_modern_assessment_cancel(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Cancel assessment draft with clinical rationale."""
    user = req["user"]
    require_permission(user, "modern_assessment:cancel", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    result = ModernAssessmentService.cancel_assessment(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 200, result


def handle_patient_modern_assessments_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List modern clinical assessments for patient across encounters."""
    user = req["user"]
    require_permission(user, "modern_assessment:read", request_id=req.get("request_id"))
    patient_id = req["path_params"]["id"]
    org_id = user["organization_id"]

    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.status, a.assessment_date, a.chief_complaint, a.working_assessment,
               a.uncertainty_level, a.version_number, a.signed_at, a.created_at,
               a.encounter_id, u.full_name as author_name
        FROM modern_clinical_assessments a
        JOIN users u ON a.author_id = u.id
        WHERE a.patient_id = ? AND a.organization_id = ?
        ORDER BY a.created_at DESC;
    """, (patient_id, org_id))
    assessments = [dict(r) for r in cursor.fetchall()]

    return 200, {"assessments": assessments, "total": len(assessments)}
