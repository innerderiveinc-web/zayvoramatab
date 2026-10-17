"""HTTP Route Handlers for Enterprise Data Lineage, Schema Evolution & Change Impact Analysis."""

from typing import Dict, Any, Tuple
import sqlite3

from apps.api.domains.data_lineage import EnterpriseDataLineageEngine
from apps.api.core.errors import ValidationError


def handle_get_contracts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/contracts - List registered contracts."""
    engine = EnterpriseDataLineageEngine(conn)
    qp = req.get("query_params", {})
    contracts = engine.get_contracts(
        req["user"],
        contract_type=qp.get("contract_type"),
        status=qp.get("status")
    )
    return 200, {"success": True, "contracts": contracts}


def handle_create_contract(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lineage/contracts - Register a new machine-readable schema or API contract."""
    engine = EnterpriseDataLineageEngine(conn)
    contract = engine.create_contract(req["user"], req.get("body", {}))
    return 201, {"success": True, "contract": contract}


def handle_get_contract(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/contracts/{id} - Get single contract by ID."""
    engine = EnterpriseDataLineageEngine(conn)
    contract_id = req["path_params"]["id"]
    contract = engine.get_contract(req["user"], contract_id)
    return 200, {"success": True, "contract": contract}


def handle_get_nodes(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/nodes - List lineage graph nodes."""
    engine = EnterpriseDataLineageEngine(conn)
    qp = req.get("query_params", {})
    nodes = engine.get_nodes(
        req["user"],
        node_type=qp.get("node_type"),
        search=qp.get("search")
    )
    return 200, {"success": True, "nodes": nodes}


def handle_register_node(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lineage/nodes - Register or update a lineage node."""
    engine = EnterpriseDataLineageEngine(conn)
    node = engine.register_node(req["user"], req.get("body", {}))
    return 201, {"success": True, "node": node}


def handle_get_node(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/nodes/{id} - Get node details with direct upstream/downstream edges."""
    engine = EnterpriseDataLineageEngine(conn)
    node_id = req["path_params"]["id"]
    node = engine.get_node(req["user"], node_id)
    return 200, {"success": True, "node": node}


def handle_get_edges(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/edges - List lineage dependency edges."""
    engine = EnterpriseDataLineageEngine(conn)
    qp = req.get("query_params", {})
    edges = engine.get_edges(
        req["user"],
        source_node_id=qp.get("source_node_id"),
        target_node_id=qp.get("target_node_id"),
        verification_status=qp.get("verification_status")
    )
    return 200, {"success": True, "edges": edges}


def handle_create_edge(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lineage/edges - Create a directed evidence-backed edge."""
    engine = EnterpriseDataLineageEngine(conn)
    edge = engine.create_edge(req["user"], req.get("body", {}))
    return 201, {"success": True, "edge": edge}


def handle_delete_edge(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """DELETE /api/v1/lineage/edges/{id} - Delete a lineage edge."""
    engine = EnterpriseDataLineageEngine(conn)
    edge_id = req["path_params"]["id"]
    res = engine.delete_edge(req["user"], edge_id)
    return 200, {"success": True, "result": res}


def handle_trace_lineage(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/trace/{id} - Cycle-safe graph traversal in downstream or upstream direction."""
    engine = EnterpriseDataLineageEngine(conn)
    node_id = req["path_params"]["id"]
    qp = req.get("query_params", {})
    direction = qp.get("direction", "downstream")
    max_depth = int(qp.get("max_depth", 10))
    trace = engine.trace_lineage(req["user"], node_id, direction=direction, max_depth=max_depth)
    return 200, {"success": True, "trace": trace}


def handle_list_change_requests(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/change-requests - List change requests."""
    engine = EnterpriseDataLineageEngine(conn)
    qp = req.get("query_params", {})
    requests = engine.list_change_requests(req["user"], status=qp.get("status"))
    return 200, {"success": True, "change_requests": requests}


def handle_create_change_request(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lineage/change-requests - Submit a change proposal."""
    engine = EnterpriseDataLineageEngine(conn)
    cr = engine.create_change_request(req["user"], req.get("body", {}))
    return 201, {"success": True, "change_request": cr}


def handle_get_change_request(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/change-requests/{id} - Get change request with impact report and reviews."""
    engine = EnterpriseDataLineageEngine(conn)
    cr_id = req["path_params"]["id"]
    cr = engine.get_change_request(req["user"], cr_id)
    return 200, {"success": True, "change_request": cr}


def handle_analyze_impact(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lineage/change-requests/{id}/analyze - Run deterministic impact analysis."""
    engine = EnterpriseDataLineageEngine(conn)
    cr_id = req["path_params"]["id"]
    cr = engine.analyze_impact(req["user"], cr_id)
    return 200, {"success": True, "change_request": cr}


def handle_submit_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lineage/change-requests/{id}/reviews - Submit change review with separation-of-duties check."""
    engine = EnterpriseDataLineageEngine(conn)
    cr_id = req["path_params"]["id"]
    cr = engine.submit_review(req["user"], cr_id, req.get("body", {}))
    return 200, {"success": True, "change_request": cr}


def handle_transition_change_request(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lineage/change-requests/{id}/transition - Advance change request release state."""
    engine = EnterpriseDataLineageEngine(conn)
    cr_id = req["path_params"]["id"]
    body = req.get("body", {})
    target_status = body.get("target_status")
    notes = body.get("notes", "")
    cr = engine.transition_status(req["user"], cr_id, target_status, notes=notes)
    return 200, {"success": True, "change_request": cr}


def handle_get_lineage_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lineage/summary - Get summary stats and health of data lineage estate."""
    engine = EnterpriseDataLineageEngine(conn)
    summary = engine.get_lineage_summary(req["user"])
    return 200, {"success": True, "summary": summary}
