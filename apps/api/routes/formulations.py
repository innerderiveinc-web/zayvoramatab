"""Formulations REST API Routes: Search, Details, Ingredients, Sources, and Authoring Lifecycle."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError
from apps.api.domains.formulations import FormulationService

def handle_clinical_sources_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List statutory and pharmacopoeial knowledge sources."""
    user = req["user"]
    require_permission(user, "formulary:read", request_id=req.get("request_id"))
    sources = FormulationService.list_clinical_sources(conn, user["organization_id"])
    return 200, {"sources": sources, "total": len(sources)}

def handle_ingredients_search(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Search master ingredient catalog with Mudabbar and Schedule E(1) flags."""
    user = req["user"]
    require_permission(user, "formulary:read", request_id=req.get("request_id"))
    query = req.get("query_params", {}).get("q", "")
    limit = int(req.get("query_params", {}).get("limit", 20))
    ingredients = FormulationService.search_ingredients(conn, query=query, limit=limit)
    return 200, {"ingredients": ingredients, "total": len(ingredients)}

def handle_formulations_search(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Search master formulations catalog with multi-script matching and dosage forms."""
    user = req["user"]
    require_permission(user, "formulary:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    query = params.get("q", "")
    dosage_form = params.get("dosage_form")
    status = params.get("status", "APPROVED")
    limit = int(params.get("limit", 20))
    offset = int(params.get("offset", 0))

    formulations, total = FormulationService.search_formulations(
        conn=conn,
        organization_id=user["organization_id"],
        q=query,
        dosage_form=dosage_form,
        status=status,
        limit=limit,
        offset=offset
    )
    return 200, {"formulations": formulations, "total": total, "limit": limit, "offset": offset}

def handle_formulation_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Fetch complete formulation aggregate with versions and composition."""
    user = req["user"]
    require_permission(user, "formulary:read", request_id=req.get("request_id"))
    formulation_id = req["path_params"]["id"]
    version_str = req.get("query_params", {}).get("version")
    version_num = int(version_str) if version_str else None

    formulation = FormulationService.get_formulation_by_id(
        conn=conn,
        organization_id=user["organization_id"],
        formulation_id=formulation_id,
        version_number=version_num
    )
    return 200, {"formulation": formulation}

def handle_formulation_create_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Author a new formulation draft."""
    user = req["user"]
    require_permission(user, "formulary:draft_create", request_id=req.get("request_id"))
    body = req.get("body", {})

    formulation = FormulationService.create_formulation_draft(
        conn=conn,
        organization_id=user["organization_id"],
        author_id=user["user_id"],
        code=body.get("code", ""),
        name=body.get("name", ""),
        transliteration=body.get("transliteration"),
        dosage_form=body.get("dosage_form", "SAFOOF"),
        preparation_method=body.get("preparation_method"),
        standard_indication=body.get("standard_indication"),
        standard_adult_dose=body.get("standard_adult_dose"),
        classical_source_id=body.get("classical_source_id"),
        source_locator=body.get("source_locator"),
        ingredients=body.get("ingredients", []),
        synonyms=body.get("synonyms", [])
    )
    return 201, {"formulation": formulation}

def handle_formulation_submit_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Submit draft formulation version for clinical review."""
    user = req["user"]
    require_permission(user, "formulary:submit_review", request_id=req.get("request_id"))
    version_id = req["path_params"]["version_id"]
    body = req.get("body", {})
    notes = body.get("notes")

    res = FormulationService.submit_formulation_review(
        conn=conn,
        organization_id=user["organization_id"],
        formulation_version_id=version_id,
        user_id=user["user_id"],
        notes=notes
    )
    return 200, {"formulation": res}

def handle_formulation_approve(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Approve or reject formulation version (Clinical Governance)."""
    user = req["user"]
    require_permission(user, "formulary:approve", request_id=req.get("request_id"))
    version_id = req["path_params"]["version_id"]
    body = req.get("body", {})
    decision = body.get("decision", "APPROVED")
    notes = body.get("notes")

    res = FormulationService.approve_formulation_version(
        conn=conn,
        organization_id=user["organization_id"],
        formulation_version_id=version_id,
        reviewer_id=user["user_id"],
        notes=notes
    )
    return 200, {"formulation": res}
