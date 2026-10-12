"""Organ-Axis Mapping REST API Routes: Concepts, Contextual Associations, and Acknowledgment."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.domains.organ_axis import OrganAxisService

def handle_organ_axis_concepts_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List master Organ-Axis concepts (Meda, Kabid, Qalb, Dimagh, etc.)."""
    user = req["user"]
    require_permission(user, "organ_axis:read", request_id=req.get("request_id"))
    concepts = OrganAxisService.list_concepts(conn)
    return 200, {"concepts": concepts, "total": len(concepts)}

def handle_organ_axis_mappings_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List contextual Organ-Axis mappings with honest evidence and citation status."""
    user = req["user"]
    require_permission(user, "organ_axis:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    concept_code = params.get("concept")
    status = params.get("status", "APPROVED")

    mappings = OrganAxisService.get_mappings(conn, concept_code=concept_code, status=status)
    return 200, {"mappings": mappings, "total": len(mappings)}

def handle_organ_axis_mapping_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Get mapping details by ID."""
    user = req["user"]
    require_permission(user, "organ_axis:read", request_id=req.get("request_id"))
    mapping_id = req["path_params"]["id"]
    mapping = OrganAxisService.get_mapping_by_id(conn, mapping_id)
    return 200, {"mapping": mapping}

def handle_organ_axis_mapping_acknowledge(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Clinician acknowledgment of an Organ-Axis association during an assessment."""
    user = req["user"]
    require_permission(user, "organ_axis:read", request_id=req.get("request_id"))
    mapping_id = req["path_params"]["id"]
    body = req.get("body", {})

    res = OrganAxisService.record_mapping_acknowledgement(
        conn=conn,
        user_ctx=user,
        assessment_id=body.get("assessment_id"),
        mapping_id=mapping_id,
        notes=body.get("notes")
    )
    return 200, res
