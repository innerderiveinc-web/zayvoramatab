"""HTTP Route Handlers for Enterprise Master Data Management, Data Governance & Data Quality Stewardship."""

from typing import Dict, Any, Tuple
import sqlite3

from apps.api.domains.data_governance import EnterpriseMasterDataGovernanceEngine
from apps.api.core.errors import ValidationError


def handle_get_master_entities(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/entities - List master entities catalog."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    entities = engine.get_master_entities(req["user"])
    return 200, {"success": True, "entities": entities}


def handle_register_master_entity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/entities - Register master entity with survivorship and normalization rules."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    entity = engine.register_master_entity(req["user"], req.get("body", {}))
    return 201, {"success": True, "entity": entity}


def handle_list_dq_rules(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/rules - List versioned data quality rules across 9 dimensions."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    qp = req.get("query_params", {})
    rules = engine.list_dq_rules(
        req["user"],
        dimension=qp.get("dimension"),
        status=qp.get("status"),
        entity_type=qp.get("entity_type")
    )
    return 200, {"success": True, "rules": rules}


def handle_create_dq_rule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/rules - Create versioned data quality rule."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    rule = engine.create_dq_rule(req["user"], req.get("body", {}))
    return 201, {"success": True, "rule": rule}


def handle_run_dq_scan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/scans/run - Execute data quality evaluation scan."""
    body = req.get("body", {})
    target_entity = body.get("target_entity_type", "patient")
    scope = body.get("scope", "tenant")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    scan_result = engine.run_dq_scan(req["user"], target_entity_type=target_entity, scope=scope)
    return 200, {"success": True, "scan": scan_result}


def handle_list_dq_scans(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/scans - List past scan runs."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    scans = engine.list_dq_scans(req["user"])
    return 200, {"success": True, "scans": scans}


def handle_get_scan_findings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/scans/:id/findings - Fetch granular findings of a scan."""
    scan_id = req["path_params"].get("id")
    if not scan_id:
        raise ValidationError("Missing scan ID parameter.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    findings = engine.get_scan_findings(req["user"], scan_id)
    return 200, {"success": True, "findings": findings}


def handle_detect_duplicate_candidates(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/duplicates/detect - Detect duplicate candidate pairs without auto-merging."""
    body = req.get("body", {})
    entity_type = body.get("entity_type", "patient")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    detected = engine.detect_duplicate_candidates(req["user"], entity_type=entity_type)
    return 200, {"success": True, "detected_candidates": detected}


def handle_list_duplicate_reviews(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/duplicates/reviews - List candidate reviews with explainability features."""
    qp = req.get("query_params", {})
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    reviews = engine.list_duplicate_reviews(req["user"], status=qp.get("status"))
    return 200, {"success": True, "reviews": reviews}


def handle_resolve_duplicate_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/duplicates/reviews/:id/resolve - Human steward decision resolution."""
    review_id = req["path_params"].get("id")
    if not review_id:
        raise ValidationError("Missing review ID parameter.")
    body = req.get("body", {})
    decision = body.get("decision")
    rationale = body.get("rationale")
    create_master_link = body.get("create_master_link", False)
    if not decision or not rationale:
        raise ValidationError("decision and rationale are mandatory.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    res = engine.resolve_duplicate_review(
        req["user"], review_id, decision, rationale, create_master_link=create_master_link
    )
    return 200, {"success": True, "resolution": res}


def handle_list_cross_references(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/cross-references - List patient aliases and cross-references."""
    qp = req.get("query_params", {})
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    xrefs = engine.list_cross_references(req["user"], master_patient_id=qp.get("master_patient_id"))
    return 200, {"success": True, "cross_references": xrefs}


def handle_create_cross_reference(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/cross-references - Establish reversible master cross-reference."""
    body = req.get("body", {})
    master_id = body.get("master_patient_id")
    linked_id = body.get("linked_patient_id")
    link_type = body.get("link_type", "alias")
    notes = body.get("notes")
    if not master_id or not linked_id:
        raise ValidationError("master_patient_id and linked_patient_id are required.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    res = engine.create_cross_reference(req["user"], master_id, linked_id, link_type=link_type, notes=notes)
    return 201, {"success": True, "cross_reference": res}


def handle_unlink_cross_reference(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/cross-references/:id/unlink - Reversibly decouple cross-reference."""
    xref_id = req["path_params"].get("id")
    if not xref_id:
        raise ValidationError("Missing cross-reference ID parameter.")
    body = req.get("body", {})
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    res = engine.unlink_cross_reference(req["user"], xref_id, notes=body.get("notes"))
    return 200, {"success": True, "cross_reference": res}


def handle_list_terminology_mappings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/terminology/mappings - List governed terminology mappings."""
    qp = req.get("query_params", {})
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    mappings = engine.list_terminology_mappings(
        req["user"],
        unani_concept_code=qp.get("unani_concept_code"),
        review_status=qp.get("review_status")
    )
    return 200, {"success": True, "mappings": mappings}


def handle_create_terminology_mapping(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/terminology/mappings - Propose terminology mapping draft."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    mapping = engine.create_terminology_mapping(req["user"], req.get("body", {}))
    return 201, {"success": True, "mapping": mapping}


def handle_review_terminology_mapping(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/terminology/mappings/:id/review - Review and approve terminology mapping."""
    mapping_id = req["path_params"].get("id")
    if not mapping_id:
        raise ValidationError("Missing mapping ID parameter.")
    body = req.get("body", {})
    decision = body.get("decision")
    rationale = body.get("rationale", "")
    if not decision:
        raise ValidationError("decision is required.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    res = engine.review_terminology_mapping(req["user"], mapping_id, decision, rationale)
    return 200, {"success": True, "mapping": res}


def handle_stage_import_batch(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/imports/stage - Stage raw import batch records."""
    body = req.get("body", {})
    batch_name = body.get("batch_name")
    entity_type = body.get("entity_type", "patient")
    raw_records = body.get("raw_records", [])
    source_system = body.get("source_system", "CSV_INGEST")
    idem_key = body.get("idempotency_key")
    if not batch_name:
        raise ValidationError("batch_name is required.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    res = engine.stage_import_batch(
        req["user"], batch_name, entity_type, raw_records,
        source_system=source_system, idempotency_key=idem_key
    )
    return 201, {"success": True, "batch": res}


def handle_evaluate_import_dry_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/imports/:id/dry-run - Side-effect free validation evaluation."""
    batch_id = req["path_params"].get("id")
    if not batch_id:
        raise ValidationError("Missing batch ID parameter.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    res = engine.evaluate_import_dry_run(req["user"], batch_id)
    return 200, {"success": True, "dry_run": res}


def handle_commit_import_batch(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/imports/:id/commit - Idempotent commit of validated records."""
    batch_id = req["path_params"].get("id")
    if not batch_id:
        raise ValidationError("Missing batch ID parameter.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    res = engine.commit_import_batch(req["user"], batch_id)
    return 200, {"success": True, "commit": res}


def handle_list_import_batches(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/imports - List import batches."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    batches = engine.list_import_batches(req["user"])
    return 200, {"success": True, "batches": batches}


def handle_create_stewardship_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/stewardship/cases - Create data quality stewardship issue."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    case = engine.create_stewardship_case(req["user"], req.get("body", {}))
    return 201, {"success": True, "case": case}


def handle_list_stewardship_cases(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/stewardship/cases - List stewardship cases."""
    qp = req.get("query_params", {})
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    cases = engine.list_stewardship_cases(
        req["user"],
        status=qp.get("status"),
        category=qp.get("category")
    )
    return 200, {"success": True, "cases": cases}


def handle_transition_stewardship_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/mdm/stewardship/cases/:id/transition - Transition stewardship case state."""
    case_id = req["path_params"].get("id")
    if not case_id:
        raise ValidationError("Missing case ID parameter.")
    body = req.get("body", {})
    to_status = body.get("to_status")
    comment = body.get("comment")
    if not to_status or not comment:
        raise ValidationError("to_status and comment are required.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    res = engine.transition_stewardship_case(req["user"], case_id, to_status, comment)
    return 200, {"success": True, "case": res}


def handle_get_stewardship_case_events(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/stewardship/cases/:id/events - List event audit trail for case."""
    case_id = req["path_params"].get("id")
    if not case_id:
        raise ValidationError("Missing case ID parameter.")
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    events = engine.get_stewardship_case_events(req["user"], case_id)
    return 200, {"success": True, "events": events}


def handle_get_mdm_pulse(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/mdm/pulse - Master data governance health and metric pulse."""
    engine = EnterpriseMasterDataGovernanceEngine(conn)
    pulse = engine.get_mdm_pulse(req["user"])
    return 200, {"success": True, "pulse": pulse}
