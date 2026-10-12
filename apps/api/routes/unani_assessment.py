"""Unani Assessment REST API Routes: Templates, Assessment Drafts, Finalisation, Amendments, and Patient History."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError
from apps.api.domains.unani_assessment import UnaniAssessmentService

def handle_unani_templates_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List active Unani assessment templates."""
    user = req["user"]
    require_permission(user, "template:read", request_id=req.get("request_id"))
    templates = UnaniAssessmentService.list_templates(conn)
    return 200, {"templates": templates, "total": len(templates)}

def handle_unani_template_version_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Get full definition and domain fields of a template version."""
    user = req["user"]
    require_permission(user, "template:read", request_id=req.get("request_id"))
    version_id = req["path_params"]["version_id"]
    tmpl = UnaniAssessmentService.get_template_version_definition(conn, version_id)
    return 200, {"template_version": tmpl}

def handle_unani_assessment_create_for_encounter(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Create draft Unani assessment for active encounter."""
    user = req["user"]
    require_permission(user, "assessment:create_draft", request_id=req.get("request_id"))
    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})

    assessment = UnaniAssessmentService.create_assessment_draft(
        conn=conn,
        user_ctx=user,
        encounter_id=encounter_id,
        payload=body
    )
    return 201, {"assessment": assessment}

def handle_unani_assessment_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Fetch complete assessment aggregate with responses, conclusions, and amendments."""
    user = req["user"]
    require_permission(user, "assessment:read", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]

    assessment = UnaniAssessmentService.get_assessment_by_id(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id
    )
    return 200, {"assessment": assessment}

def handle_unani_assessment_update_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Update draft assessment observations, Mizaj conclusion, and clinical reasoning."""
    user = req["user"]
    require_permission(user, "assessment:update_draft", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    assessment = UnaniAssessmentService.update_assessment_draft(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 200, {"assessment": assessment}

def handle_unani_assessment_finalise(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Clinician explicit finalisation with cryptographic snapshot hashing and immutability lock."""
    user = req["user"]
    require_permission(user, "assessment:finalise", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    assessment = UnaniAssessmentService.finalise_assessment(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 200, {"assessment": assessment}

def handle_unani_assessment_amend(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Amending a finalised assessment. Creates a new linked version and supersedes parent."""
    user = req["user"]
    require_permission(user, "assessment:amend", request_id=req.get("request_id"))
    assessment_id = req["path_params"]["id"]
    body = req.get("body", {})

    new_assessment = UnaniAssessmentService.amend_assessment(
        conn=conn,
        user_ctx=user,
        assessment_id=assessment_id,
        payload=body
    )
    return 201, {"assessment": new_assessment}

def handle_patient_unani_assessments_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List historical assessments for patient across encounters."""
    user = req["user"]
    require_permission(user, "assessment:read", request_id=req.get("request_id"))
    patient_id = req["path_params"]["id"]

    assessments = UnaniAssessmentService.list_assessments_for_patient(
        conn=conn,
        user_ctx=user,
        patient_id=patient_id
    )
    return 200, {"assessments": assessments, "total": len(assessments)}
