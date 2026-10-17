"""Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Domain Engine.

Phase 43 for ZAYVORA MATAB OS.
Enforces non-negotiable principles:
- "Impact unknown" is a real result, never "no impact": uninstrumented dynamic or external
  consumers are flagged as unknown and block automated releases (BLOCKED_BY_UNKNOWNS).
- Zero autonomous clinical alterations: finalized clinical notes, prescriptions, and dosage
  safety gates are immutable and require qualified human review.
- Zero fabrication: dependencies and contract definitions are based on verified evidence;
  never infer missing clinical facts or fake dependencies.
- Separation of duties: the creator of a change request cannot approve their own release gate.
- Graph reproducibility & zero PHI: lineage graphs reference schema structures and metadata,
  never storing protected health information (PHI).
"""

import os
import re
import json
import sqlite3
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set, Union

from apps.api.config import config
from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError
)
from apps.api.core.permissions import require_permission


class EnterpriseDataLineageEngine:
    """Core domain engine for Phase 43 Enterprise Data Lineage, Schema Evolution & Change Impact Analysis."""

    VALID_CONTRACT_TYPES = {"database", "api", "event", "import", "export", "terminology", "metric", "configuration"}
    VALID_COMPATIBILITY_POLICIES = {"BACKWARD", "FORWARD", "FULL", "STRICT_BREAKING"}
    VALID_SENSITIVITIES = {"PUBLIC", "INTERNAL", "RESTRICTED_PHI", "FINANCIAL"}
    VALID_CONTRACT_STATUSES = {"draft", "review", "approved", "retired"}
    VALID_NODE_TYPES = {
        "domain_entity", "db_table", "db_column", "api_endpoint",
        "event_topic", "workflow_rule", "terminology_concept",
        "analytics_metric", "external_integration"
    }
    VALID_RELATIONSHIP_TYPES = {
        "produces", "reads", "writes", "transforms", "validates",
        "publishes", "subscribes_to", "maps_to", "aggregates_into",
        "indexes_into", "exports_to", "authorizes", "audits", "depends_on"
    }
    VALID_EVIDENCE_TYPES = {"code_reference", "schema_fk", "test_assertion", "config", "manual_audit"}
    VALID_VERIFICATION_STATUSES = {"verified", "inferred", "unknown", "stale", "not_applicable"}
    VALID_CHANGE_TYPES = {"additive", "breaking", "semantically_breaking", "config_change"}
    VALID_CR_STATUSES = {
        "draft", "analysis_pending", "review_required", "blocked_by_unknowns",
        "approved_for_test", "testing", "approved_for_release",
        "deployed_pending_verification", "verified", "rejected", "rolled_back", "closed"
    }
    VALID_COMPATIBILITY_CLASSIFICATIONS = {
        "additive_compatible", "conditionally_compatible", "breaking",
        "semantically_breaking", "unassessed"
    }
    VALID_RELEASE_GATES = {"PROCEED", "MANUAL_REVIEW_REQUIRED", "BLOCKED_BY_UNKNOWNS"}
    VALID_REVIEW_ROLES = {"CLINICAL_DIRECTOR", "DATA_ARCHITECT", "LEGAL_COUNSEL", "CISO"}
    VALID_REVIEW_DECISIONS = {"approved", "rejected", "revision_requested"}

    def __init__(self, db_or_conn: Optional[Any] = None):
        if isinstance(db_or_conn, sqlite3.Connection):
            self.conn = db_or_conn
            self.db_path = None
        else:
            self.db_path = db_or_conn or config.db_path
            self._manager = DatabaseConnection(self.db_path)
            self.conn = self._manager.get_connection()
            self.conn.row_factory = sqlite3.Row

    # -------------------------------------------------------------------------
    # 1. Governed Data & API Contracts Registry
    # -------------------------------------------------------------------------
    def create_contract(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new machine-readable schema or API contract."""
        require_permission(user_ctx, "lineage:contract_manage")
        org_id = user_ctx["organization_id"]

        contract_key = (payload.get("contract_key") or "").strip()
        contract_type = (payload.get("contract_type") or "").strip()
        version = (payload.get("version") or "1.0.0").strip()
        owner = (payload.get("owner") or "Core Platform").strip()
        schema_def = payload.get("schema_definition_json") or {}
        policy = payload.get("compatibility_policy") or "BACKWARD"
        sensitivity = payload.get("sensitivity") or "INTERNAL"
        status = payload.get("status") or "approved"
        limitations = payload.get("limitations_json") or []

        if not contract_key or len(contract_key) < 3:
            raise ValidationError("contract_key must be at least 3 characters.")
        if contract_type not in self.VALID_CONTRACT_TYPES:
            raise ValidationError(f"Invalid contract_type '{contract_type}'. Valid: {sorted(self.VALID_CONTRACT_TYPES)}")
        if policy not in self.VALID_COMPATIBILITY_POLICIES:
            raise ValidationError(f"Invalid compatibility_policy '{policy}'. Valid: {sorted(self.VALID_COMPATIBILITY_POLICIES)}")
        if sensitivity not in self.VALID_SENSITIVITIES:
            raise ValidationError(f"Invalid sensitivity '{sensitivity}'. Valid: {sorted(self.VALID_SENSITIVITIES)}")
        if status not in self.VALID_CONTRACT_STATUSES:
            raise ValidationError(f"Invalid status '{status}'. Valid: {sorted(self.VALID_CONTRACT_STATUSES)}")

        schema_json = json.dumps(schema_def) if isinstance(schema_def, (dict, list)) else str(schema_def)
        limitations_json = json.dumps(limitations) if isinstance(limitations, list) else str(limitations)

        contract_id = f"cnt_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO lineage_contracts_registry (
                    id, organization_id, contract_key, contract_type, version,
                    owner, schema_definition_json, compatibility_policy,
                    sensitivity, status, limitations_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    contract_id, org_id, contract_key, contract_type, version,
                    owner, schema_json, policy, sensitivity, status,
                    limitations_json, now, now
                )
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(f"Contract '{contract_key}' version '{version}' already exists for this organization: {e}")

        return self.get_contract(user_ctx, contract_id)

    def get_contracts(
        self,
        user_ctx: Dict[str, Any],
        contract_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List registered contracts."""
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = "SELECT * FROM lineage_contracts_registry WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if contract_type:
            query += " AND contract_type = ?"
            params.append(contract_type)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY contract_key ASC, version DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "organization_id": r["organization_id"],
                "contract_key": r["contract_key"],
                "contract_type": r["contract_type"],
                "version": r["version"],
                "owner": r["owner"],
                "schema_definition": json.loads(r["schema_definition_json"]),
                "compatibility_policy": r["compatibility_policy"],
                "sensitivity": r["sensitivity"],
                "status": r["status"],
                "limitations": json.loads(r["limitations_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            })
        return results

    def get_contract(self, user_ctx: Dict[str, Any], contract_id: str) -> Dict[str, Any]:
        """Fetch a single contract by ID."""
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM lineage_contracts_registry WHERE id = ? AND organization_id = ?",
            (contract_id, org_id)
        )
        row = cur.fetchone()
        if not row:
            raise NotFoundError(f"Contract '{contract_id}' not found.")

        return {
            "id": row["id"],
            "organization_id": row["organization_id"],
            "contract_key": row["contract_key"],
            "contract_type": row["contract_type"],
            "version": row["version"],
            "owner": row["owner"],
            "schema_definition": json.loads(row["schema_definition_json"]),
            "compatibility_policy": row["compatibility_policy"],
            "sensitivity": row["sensitivity"],
            "status": row["status"],
            "limitations": json.loads(row["limitations_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    # -------------------------------------------------------------------------
    # 2. Lineage Graph Nodes
    # -------------------------------------------------------------------------
    def register_node(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Register or update a lineage graph node."""
        require_permission(user_ctx, "lineage:contract_manage")
        org_id = user_ctx["organization_id"]

        node_key = (payload.get("node_key") or "").strip()
        node_type = (payload.get("node_type") or "").strip()
        name = (payload.get("name") or "").strip()
        description = payload.get("description") or ""
        contract_id = payload.get("contract_id")
        owner = payload.get("owner") or "Core Platform"
        sensitivity = payload.get("sensitivity") or "INTERNAL"
        metadata = payload.get("metadata_json") or {}

        if not node_key or len(node_key) < 2:
            raise ValidationError("node_key must be at least 2 characters.")
        if node_type not in self.VALID_NODE_TYPES:
            raise ValidationError(f"Invalid node_type '{node_type}'. Valid: {sorted(self.VALID_NODE_TYPES)}")
        if not name:
            raise ValidationError("name is required.")
        if sensitivity not in self.VALID_SENSITIVITIES:
            raise ValidationError(f"Invalid sensitivity '{sensitivity}'. Valid: {sorted(self.VALID_SENSITIVITIES)}")

        meta_json = json.dumps(metadata) if isinstance(metadata, (dict, list)) else str(metadata)
        node_id = f"nod_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO lineage_nodes (
                    id, organization_id, node_key, node_type, name, description,
                    contract_id, owner, sensitivity, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    node_id, org_id, node_key, node_type, name, description,
                    contract_id, owner, sensitivity, meta_json, now, now
                )
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(f"Node '{node_key}' already exists in this organization: {e}")

        return self.get_node(user_ctx, node_id)

    def get_nodes(
        self,
        user_ctx: Dict[str, Any],
        node_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List lineage nodes."""
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = "SELECT * FROM lineage_nodes WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if node_type:
            query += " AND node_type = ?"
            params.append(node_type)
        if search:
            query += " AND (node_key LIKE ? OR name LIKE ? OR description LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])

        query += " ORDER BY node_key ASC"
        cur.execute(query, params)
        rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "organization_id": r["organization_id"],
                "node_key": r["node_key"],
                "node_type": r["node_type"],
                "name": r["name"],
                "description": r["description"],
                "contract_id": r["contract_id"],
                "owner": r["owner"],
                "sensitivity": r["sensitivity"],
                "metadata": json.loads(r["metadata_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            })
        return results

    def get_node(self, user_ctx: Dict[str, Any], node_id_or_key: str) -> Dict[str, Any]:
        """Fetch node details with its immediate upstream and downstream edges."""
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM lineage_nodes
            WHERE (id = ? OR node_key = ?) AND organization_id = ?
            """,
            (node_id_or_key, node_id_or_key, org_id)
        )
        row = cur.fetchone()
        if not row:
            raise NotFoundError(f"Lineage node '{node_id_or_key}' not found.")

        node_id = row["id"]
        # Fetch immediate upstream edges (target == this node)
        cur.execute(
            """
            SELECT e.*, sn.node_key as source_key, sn.name as source_name, sn.node_type as source_type
            FROM lineage_edges e
            JOIN lineage_nodes sn ON e.source_node_id = sn.id
            WHERE e.target_node_id = ? AND e.organization_id = ?
            """,
            (node_id, org_id)
        )
        upstream = [
            {
                "edge_id": u["id"],
                "source_node_id": u["source_node_id"],
                "source_key": u["source_key"],
                "source_name": u["source_name"],
                "source_type": u["source_type"],
                "relationship_type": u["relationship_type"],
                "evidence_type": u["evidence_type"],
                "verification_status": u["verification_status"],
                "evidence_details": json.loads(u["evidence_details_json"])
            }
            for u in cur.fetchall()
        ]

        # Fetch immediate downstream edges (source == this node)
        cur.execute(
            """
            SELECT e.*, tn.node_key as target_key, tn.name as target_name, tn.node_type as target_type
            FROM lineage_edges e
            JOIN lineage_nodes tn ON e.target_node_id = tn.id
            WHERE e.source_node_id = ? AND e.organization_id = ?
            """,
            (node_id, org_id)
        )
        downstream = [
            {
                "edge_id": d["id"],
                "target_node_id": d["target_node_id"],
                "target_key": d["target_key"],
                "target_name": d["target_name"],
                "target_type": d["target_type"],
                "relationship_type": d["relationship_type"],
                "evidence_type": d["evidence_type"],
                "verification_status": d["verification_status"],
                "evidence_details": json.loads(d["evidence_details_json"])
            }
            for d in cur.fetchall()
        ]

        return {
            "id": row["id"],
            "organization_id": row["organization_id"],
            "node_key": row["node_key"],
            "node_type": row["node_type"],
            "name": row["name"],
            "description": row["description"],
            "contract_id": row["contract_id"],
            "owner": row["owner"],
            "sensitivity": row["sensitivity"],
            "metadata": json.loads(row["metadata_json"]),
            "upstream_edges": upstream,
            "downstream_edges": downstream,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    # -------------------------------------------------------------------------
    # 3. Directed Lineage Dependencies & Evidence Edges
    # -------------------------------------------------------------------------
    def create_edge(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a directed evidence-backed edge between two nodes."""
        require_permission(user_ctx, "lineage:contract_manage")
        org_id = user_ctx["organization_id"]

        source_id = payload.get("source_node_id")
        target_id = payload.get("target_node_id")
        rel_type = payload.get("relationship_type")
        evidence_type = payload.get("evidence_type") or "code_reference"
        verification_status = payload.get("verification_status") or "verified"
        evidence_details = payload.get("evidence_details_json") or {}

        if not source_id or not target_id:
            raise ValidationError("source_node_id and target_node_id are required.")
        if source_id == target_id:
            raise ValidationError("Self-referencing edges are not allowed in data lineage graph.")
        if rel_type not in self.VALID_RELATIONSHIP_TYPES:
            raise ValidationError(f"Invalid relationship_type '{rel_type}'. Valid: {sorted(self.VALID_RELATIONSHIP_TYPES)}")
        if evidence_type not in self.VALID_EVIDENCE_TYPES:
            raise ValidationError(f"Invalid evidence_type '{evidence_type}'. Valid: {sorted(self.VALID_EVIDENCE_TYPES)}")
        if verification_status not in self.VALID_VERIFICATION_STATUSES:
            raise ValidationError(f"Invalid verification_status '{verification_status}'. Valid: {sorted(self.VALID_VERIFICATION_STATUSES)}")

        # Verify nodes exist
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM lineage_nodes WHERE id = ? AND organization_id = ?", (source_id, org_id))
        if not cur.fetchone():
            raise NotFoundError(f"Source node '{source_id}' does not exist.")
        cur.execute("SELECT id FROM lineage_nodes WHERE id = ? AND organization_id = ?", (target_id, org_id))
        if not cur.fetchone():
            raise NotFoundError(f"Target node '{target_id}' does not exist.")

        edge_id = f"edg_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        ev_json = json.dumps(evidence_details) if isinstance(evidence_details, (dict, list)) else str(evidence_details)

        try:
            cur.execute(
                """
                INSERT INTO lineage_edges (
                    id, organization_id, source_node_id, target_node_id,
                    relationship_type, evidence_type, verification_status,
                    evidence_details_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    edge_id, org_id, source_id, target_id,
                    rel_type, evidence_type, verification_status,
                    ev_json, now, now
                )
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(f"Dependency edge between '{source_id}' and '{target_id}' with type '{rel_type}' already exists: {e}")

        cur.execute("SELECT * FROM lineage_edges WHERE id = ?", (edge_id,))
        r = cur.fetchone()
        return {
            "id": r["id"],
            "organization_id": r["organization_id"],
            "source_node_id": r["source_node_id"],
            "target_node_id": r["target_node_id"],
            "relationship_type": r["relationship_type"],
            "evidence_type": r["evidence_type"],
            "verification_status": r["verification_status"],
            "evidence_details": json.loads(r["evidence_details_json"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        }

    def get_edges(
        self,
        user_ctx: Dict[str, Any],
        source_node_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
        verification_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List lineage dependency edges."""
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = "SELECT * FROM lineage_edges WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if source_node_id:
            query += " AND source_node_id = ?"
            params.append(source_node_id)
        if target_node_id:
            query += " AND target_node_id = ?"
            params.append(target_node_id)
        if verification_status:
            query += " AND verification_status = ?"
            params.append(verification_status)

        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "organization_id": r["organization_id"],
                "source_node_id": r["source_node_id"],
                "target_node_id": r["target_node_id"],
                "relationship_type": r["relationship_type"],
                "evidence_type": r["evidence_type"],
                "verification_status": r["verification_status"],
                "evidence_details": json.loads(r["evidence_details_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            })
        return results

    def delete_edge(self, user_ctx: Dict[str, Any], edge_id: str) -> Dict[str, Any]:
        """Delete a lineage edge."""
        require_permission(user_ctx, "lineage:contract_manage")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        cur.execute("SELECT id FROM lineage_edges WHERE id = ? AND organization_id = ?", (edge_id, org_id))
        if not cur.fetchone():
            raise NotFoundError(f"Edge '{edge_id}' not found.")

        cur.execute("DELETE FROM lineage_edges WHERE id = ? AND organization_id = ?", (edge_id, org_id))
        self.conn.commit()
        return {"status": "deleted", "edge_id": edge_id}

    # -------------------------------------------------------------------------
    # 4. Cycle-Safe Graph Traversal (Upstream Provenance & Downstream Blast Radius)
    # -------------------------------------------------------------------------
    def trace_lineage(
        self,
        user_ctx: Dict[str, Any],
        node_id_or_key: str,
        direction: str = "downstream",
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        Perform cycle-safe, depth-bounded traversal across the lineage graph.
        direction: 'downstream' (blast radius / consumers) or 'upstream' (provenance / producers).
        """
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]

        if direction not in ("downstream", "upstream"):
            raise ValidationError("direction must be 'downstream' or 'upstream'.")
        if max_depth < 1 or max_depth > 20:
            raise ValidationError("max_depth must be between 1 and 20.")

        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM lineage_nodes WHERE (id = ? OR node_key = ?) AND organization_id = ?",
            (node_id_or_key, node_id_or_key, org_id)
        )
        root_row = cur.fetchone()
        if not root_row:
            raise NotFoundError(f"Root node '{node_id_or_key}' not found.")

        root_id = root_row["id"]
        visited_nodes: Set[str] = set()
        traversal_nodes: Dict[str, Dict[str, Any]] = {}
        traversal_edges: List[Dict[str, Any]] = []
        unknown_nodes: List[Dict[str, Any]] = []
        has_cycles = False
        deepest_depth = 0

        # Queue items: (current_node_id, current_depth, path_set)
        queue: List[Tuple[str, int, Set[str]]] = [(root_id, 0, {root_id})]

        # Pre-cache root node info
        traversal_nodes[root_id] = {
            "id": root_row["id"],
            "node_key": root_row["node_key"],
            "node_type": root_row["node_type"],
            "name": root_row["name"],
            "depth": 0,
            "sensitivity": root_row["sensitivity"]
        }

        while queue:
            curr_id, curr_depth, path = queue.pop(0)
            if curr_depth > deepest_depth:
                deepest_depth = curr_depth

            if curr_depth >= max_depth:
                continue

            # Query edges in direction
            if direction == "downstream":
                cur.execute(
                    """
                    SELECT e.*, n.id as next_id, n.node_key as next_key, n.node_type as next_type,
                           n.name as next_name, n.sensitivity as next_sensitivity
                    FROM lineage_edges e
                    JOIN lineage_nodes n ON e.target_node_id = n.id
                    WHERE e.source_node_id = ? AND e.organization_id = ?
                    """,
                    (curr_id, org_id)
                )
            else:  # upstream
                cur.execute(
                    """
                    SELECT e.*, n.id as next_id, n.node_key as next_key, n.node_type as next_type,
                           n.name as next_name, n.sensitivity as next_sensitivity
                    FROM lineage_edges e
                    JOIN lineage_nodes n ON e.source_node_id = n.id
                    WHERE e.target_node_id = ? AND e.organization_id = ?
                    """,
                    (curr_id, org_id)
                )

            edges = cur.fetchall()
            for edge in edges:
                next_id = edge["next_id"]
                edge_dict = {
                    "edge_id": edge["id"],
                    "source_node_id": edge["source_node_id"],
                    "target_node_id": edge["target_node_id"],
                    "relationship_type": edge["relationship_type"],
                    "evidence_type": edge["evidence_type"],
                    "verification_status": edge["verification_status"]
                }
                traversal_edges.append(edge_dict)

                if edge["verification_status"] == "unknown":
                    unknown_nodes.append({
                        "node_id": next_id,
                        "node_key": edge["next_key"],
                        "name": edge["next_name"],
                        "reason": f"Edge {edge['id']} has verification_status 'unknown'"
                    })

                if next_id in path:
                    # Cycle detected in current path
                    has_cycles = True
                    continue

                if next_id not in traversal_nodes:
                    traversal_nodes[next_id] = {
                        "id": edge["next_id"],
                        "node_key": edge["next_key"],
                        "node_type": edge["next_type"],
                        "name": edge["next_name"],
                        "depth": curr_depth + 1,
                        "sensitivity": edge["next_sensitivity"]
                    }

                new_path = set(path)
                new_path.add(next_id)
                queue.append((next_id, curr_depth + 1, new_path))

        return {
            "root_node": {
                "id": root_row["id"],
                "node_key": root_row["node_key"],
                "node_type": root_row["node_type"],
                "name": root_row["name"]
            },
            "direction": direction,
            "max_depth_evaluated": deepest_depth,
            "has_cycles": has_cycles,
            "nodes": list(traversal_nodes.values()),
            "edges": traversal_edges,
            "unknown_nodes": unknown_nodes,
            "total_nodes_reachable": len(traversal_nodes)
        }

    # -------------------------------------------------------------------------
    # 5. Schema Evolution & Lineage Change Requests
    # -------------------------------------------------------------------------
    def create_change_request(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a new schema, API, or contract change proposal."""
        require_permission(user_ctx, "lineage:change_request")
        org_id = user_ctx["organization_id"]
        requester_id = user_ctx.get("user_id") or "usr_unknown"

        title = (payload.get("title") or "").strip()
        contract_id = payload.get("contract_id")
        source_node_id = payload.get("source_node_id")
        target_version = (payload.get("target_version") or "").strip()
        change_type = payload.get("change_type") or "additive"
        diff_payload = payload.get("diff_payload_json") or {}
        migration_plan = payload.get("migration_plan_json") or {}

        if not title or len(title) < 4:
            raise ValidationError("title must be at least 4 characters.")
        if not contract_id:
            raise ValidationError("contract_id is required.")
        if not target_version:
            raise ValidationError("target_version is required.")
        if change_type not in self.VALID_CHANGE_TYPES:
            raise ValidationError(f"Invalid change_type '{change_type}'. Valid: {sorted(self.VALID_CHANGE_TYPES)}")

        # Verify contract exists
        cur = self.conn.cursor()
        cur.execute("SELECT id, contract_key FROM lineage_contracts_registry WHERE id = ? AND organization_id = ?", (contract_id, org_id))
        contract_row = cur.fetchone()
        if not contract_row:
            raise NotFoundError(f"Contract '{contract_id}' not found.")

        # If source_node_id not provided, try to find a node associated with this contract
        if not source_node_id:
            cur.execute("SELECT id FROM lineage_nodes WHERE contract_id = ? AND organization_id = ? LIMIT 1", (contract_id, org_id))
            nr = cur.fetchone()
            if nr:
                source_node_id = nr["id"]

        cr_id = f"lcr_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        diff_json = json.dumps(diff_payload) if isinstance(diff_payload, (dict, list)) else str(diff_payload)
        plan_json = json.dumps(migration_plan) if isinstance(migration_plan, (dict, list)) else str(migration_plan)

        cur.execute(
            """
            INSERT INTO lineage_change_requests (
                id, organization_id, title, requester_id, contract_id,
                source_node_id, target_version, change_type, diff_payload_json,
                migration_plan_json, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?);
            """,
            (
                cr_id, org_id, title, requester_id, contract_id,
                source_node_id, target_version, change_type, diff_json,
                plan_json, now, now
            )
        )
        self.conn.commit()
        return self.get_change_request(user_ctx, cr_id)

    def list_change_requests(
        self,
        user_ctx: Dict[str, Any],
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List change requests."""
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = """
            SELECT cr.*, c.contract_key, c.contract_type
            FROM lineage_change_requests cr
            JOIN lineage_contracts_registry c ON cr.contract_id = c.id
            WHERE cr.organization_id = ?
        """
        params: List[Any] = [org_id]
        if status:
            query += " AND cr.status = ?"
            params.append(status)

        query += " ORDER BY cr.created_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "organization_id": r["organization_id"],
                "title": r["title"],
                "requester_id": r["requester_id"],
                "contract_id": r["contract_id"],
                "contract_key": r["contract_key"],
                "contract_type": r["contract_type"],
                "source_node_id": r["source_node_id"],
                "target_version": r["target_version"],
                "change_type": r["change_type"],
                "status": r["status"],
                "diff_payload": json.loads(r["diff_payload_json"]),
                "migration_plan": json.loads(r["migration_plan_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            })
        return results

    def get_change_request(self, user_ctx: Dict[str, Any], change_request_id: str) -> Dict[str, Any]:
        """Fetch change request, latest impact analysis report, and reviews."""
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT cr.*, c.contract_key, c.contract_type, c.schema_definition_json, c.limitations_json
            FROM lineage_change_requests cr
            JOIN lineage_contracts_registry c ON cr.contract_id = c.id
            WHERE cr.id = ? AND cr.organization_id = ?
            """,
            (change_request_id, org_id)
        )
        row = cur.fetchone()
        if not row:
            raise NotFoundError(f"Change request '{change_request_id}' not found.")

        # Latest impact report
        cur.execute(
            """
            SELECT * FROM lineage_impact_reports
            WHERE change_request_id = ? AND organization_id = ?
            ORDER BY evaluated_at DESC LIMIT 1
            """,
            (change_request_id, org_id)
        )
        ir_row = cur.fetchone()
        impact_report = None
        if ir_row:
            impact_report = {
                "id": ir_row["id"],
                "direct_consumers": json.loads(ir_row["direct_consumers_json"]),
                "transitive_consumers": json.loads(ir_row["transitive_consumers_json"]),
                "affected_apis": json.loads(ir_row["affected_apis_json"]),
                "affected_metrics": json.loads(ir_row["affected_metrics_json"]),
                "compatibility_classification": ir_row["compatibility_classification"],
                "clinical_safety_impact_flag": bool(ir_row["clinical_safety_impact_flag"]),
                "financial_impact_flag": bool(ir_row["financial_impact_flag"]),
                "privacy_impact_flag": bool(ir_row["privacy_impact_flag"]),
                "recommended_release_gate": ir_row["recommended_release_gate"],
                "known_unknowns": json.loads(ir_row["known_unknowns_json"]),
                "evaluated_at": ir_row["evaluated_at"]
            }

        # Reviews
        cur.execute(
            """
            SELECT * FROM lineage_change_reviews
            WHERE change_request_id = ? AND organization_id = ?
            ORDER BY reviewed_at ASC
            """,
            (change_request_id, org_id)
        )
        reviews = [
            {
                "id": rev["id"],
                "reviewer_id": rev["reviewer_id"],
                "review_role": rev["review_role"],
                "decision": rev["decision"],
                "rationale": rev["rationale"],
                "reviewed_at": rev["reviewed_at"]
            }
            for rev in cur.fetchall()
        ]

        return {
            "id": row["id"],
            "organization_id": row["organization_id"],
            "title": row["title"],
            "requester_id": row["requester_id"],
            "contract_id": row["contract_id"],
            "contract_key": row["contract_key"],
            "contract_type": row["contract_type"],
            "source_node_id": row["source_node_id"],
            "target_version": row["target_version"],
            "change_type": row["change_type"],
            "status": row["status"],
            "diff_payload": json.loads(row["diff_payload_json"]),
            "migration_plan": json.loads(row["migration_plan_json"]),
            "impact_report": impact_report,
            "reviews": reviews,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }

    # -------------------------------------------------------------------------
    # 6. Change Impact Analysis Engine
    # -------------------------------------------------------------------------
    def analyze_impact(self, user_ctx: Dict[str, Any], change_request_id: str) -> Dict[str, Any]:
        """
        Execute deterministic impact analysis for a change request.
        Non-negotiable rule: "Impact unknown" is a real result, never "no impact".
        """
        require_permission(user_ctx, "lineage:analyze")
        org_id = user_ctx["organization_id"]

        cr = self.get_change_request(user_ctx, change_request_id)
        source_node_id = cr["source_node_id"]
        change_type = cr["change_type"]
        contract_key = cr["contract_key"]
        diff_payload = cr["diff_payload"]

        cur = self.conn.cursor()

        # If source_node_id not attached to CR, lookup by contract
        if not source_node_id:
            cur.execute("SELECT id FROM lineage_nodes WHERE contract_id = ? AND organization_id = ? LIMIT 1", (cr["contract_id"], org_id))
            nr = cur.fetchone()
            if nr:
                source_node_id = nr["id"]

        known_unknowns: List[Dict[str, Any]] = []
        direct_consumers: List[Dict[str, Any]] = []
        transitive_consumers: List[Dict[str, Any]] = []
        affected_apis: List[str] = []
        affected_metrics: List[str] = []
        clinical_safety_flag = 0
        financial_flag = 0
        privacy_flag = 0

        # Check contract limitations
        cur.execute("SELECT limitations_json, sensitivity FROM lineage_contracts_registry WHERE id = ?", (cr["contract_id"],))
        crow = cur.fetchone()
        if crow:
            contract_limits = json.loads(crow["limitations_json"])
            if crow["sensitivity"] == "RESTRICTED_PHI":
                privacy_flag = 1
            for lim in contract_limits:
                known_unknowns.append({
                    "category": "contract_limitation",
                    "description": lim if isinstance(lim, str) else lim.get("description", str(lim))
                })

        # Check if change itself mutates clinical dosage / rules or financial pricing
        diff_str = json.dumps(diff_payload).lower()
        if any(term in diff_str for term in ["dosage", "mizaj", "contraindication", "nuskha", "prescription", "potency"]):
            clinical_safety_flag = 1
        if any(term in diff_str for term in ["price", "billing", "amount", "currency", "invoice", "fee"]):
            financial_flag = 1

        if source_node_id:
            # Run cycle-safe downstream trace
            trace_result = self.trace_lineage(user_ctx, source_node_id, direction="downstream", max_depth=10)
            all_downstream = trace_result["nodes"]

            for n in all_downstream:
                if n["id"] == source_node_id:
                    continue
                node_summary = {
                    "id": n["id"],
                    "node_key": n["node_key"],
                    "node_type": n["node_type"],
                    "name": n["name"],
                    "depth": n["depth"]
                }
                if n["depth"] == 1:
                    direct_consumers.append(node_summary)
                transitive_consumers.append(node_summary)

                if n["node_type"] == "api_endpoint":
                    affected_apis.append(n["node_key"])
                elif n["node_type"] == "analytics_metric":
                    affected_metrics.append(n["node_key"])

                # Check clinical safety, financial, privacy impacts
                if n["node_type"] in ("workflow_rule", "terminology_concept") or "safety" in n["node_key"] or "nuskha" in n["node_key"]:
                    clinical_safety_flag = 1
                if "billing" in n["node_key"] or "invoice" in n["node_key"] or "pricing" in n["node_key"]:
                    financial_flag = 1
                if n.get("sensitivity") == "RESTRICTED_PHI":
                    privacy_flag = 1

            for unk in trace_result["unknown_nodes"]:
                known_unknowns.append({
                    "category": "unverified_lineage_dependency",
                    "node_key": unk["node_key"],
                    "description": unk["reason"]
                })
        else:
            # Without a source node, impact cannot be fully proven
            known_unknowns.append({
                "category": "unattached_source_node",
                "description": f"Contract '{contract_key}' does not have a mapped lineage graph node; blast radius cannot be traversed."
            })

        # Compatibility classification
        if change_type == "breaking":
            compat = "breaking"
        elif change_type == "semantically_breaking":
            compat = "semantically_breaking"
        elif change_type == "additive":
            compat = "additive_compatible"
        else:
            compat = "conditionally_compatible"

        # Determine release gate recommendation
        if known_unknowns:
            release_gate = "BLOCKED_BY_UNKNOWNS"
            next_status = "blocked_by_unknowns"
        elif clinical_safety_flag == 1 or compat in ("breaking", "semantically_breaking"):
            release_gate = "MANUAL_REVIEW_REQUIRED"
            next_status = "review_required"
        else:
            release_gate = "PROCEED"
            next_status = "approved_for_test"

        report_id = f"lir_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()

        cur.execute(
            """
            INSERT INTO lineage_impact_reports (
                id, organization_id, change_request_id, direct_consumers_json,
                transitive_consumers_json, affected_apis_json, affected_metrics_json,
                compatibility_classification, clinical_safety_impact_flag,
                financial_impact_flag, privacy_impact_flag, recommended_release_gate,
                known_unknowns_json, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                report_id, org_id, change_request_id,
                json.dumps(direct_consumers), json.dumps(transitive_consumers),
                json.dumps(affected_apis), json.dumps(affected_metrics),
                compat, clinical_safety_flag, financial_flag, privacy_flag,
                release_gate, json.dumps(known_unknowns), now
            )
        )

        # Update change request status
        cur.execute(
            """
            UPDATE lineage_change_requests
            SET status = ?, updated_at = ?
            WHERE id = ? AND organization_id = ?
            """,
            (next_status, now, change_request_id, org_id)
        )
        self.conn.commit()

        return self.get_change_request(user_ctx, change_request_id)

    # -------------------------------------------------------------------------
    # 7. Multi-Stakeholder Change Review & Release Governance
    # -------------------------------------------------------------------------
    def submit_review(self, user_ctx: Dict[str, Any], change_request_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record a review on a change request with strict Separation of Duties.
        Author/requester cannot approve their own release gate.
        """
        require_permission(user_ctx, "lineage:approve")
        org_id = user_ctx["organization_id"]
        reviewer_id = user_ctx.get("user_id") or "usr_reviewer"

        review_role = payload.get("review_role")
        decision = payload.get("decision")
        rationale = (payload.get("rationale") or "").strip()

        if review_role not in self.VALID_REVIEW_ROLES:
            raise ValidationError(f"Invalid review_role '{review_role}'. Valid: {sorted(self.VALID_REVIEW_ROLES)}")
        if decision not in self.VALID_REVIEW_DECISIONS:
            raise ValidationError(f"Invalid decision '{decision}'. Valid: {sorted(self.VALID_REVIEW_DECISIONS)}")
        if not rationale or len(rationale) < 8:
            raise ValidationError("rationale must be at least 8 characters explaining the review decision.")

        cr = self.get_change_request(user_ctx, change_request_id)

        # Non-negotiable Separation of Duties invariant
        if cr["requester_id"] == reviewer_id and decision == "approved":
            raise ForbiddenError("Separation of duties violation: Change request author cannot self-approve release gates.")

        # If blocked by unknowns, approval is rejected unless explicitly resolved
        if cr["status"] == "blocked_by_unknowns" and decision == "approved":
            raise ConflictError("Cannot approve a change request while blocked by unknown dependencies. Resolve unknowns first.")

        # Clinical safety invariant: If clinical safety is impacted, CLINICAL_DIRECTOR approval is mandatory
        report = cr.get("impact_report")
        if report and report.get("clinical_safety_impact_flag") and decision == "approved" and review_role != "CLINICAL_DIRECTOR":
            # Check if clinical director already approved
            has_cd = any(r["review_role"] == "CLINICAL_DIRECTOR" and r["decision"] == "approved" for r in cr["reviews"])
            if not has_cd:
                raise ForbiddenError("Clinical safety flag active: Clinical Director approval is mandatory prior to technical approval.")

        review_id = f"lrv_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO lineage_change_reviews (
                id, organization_id, change_request_id, reviewer_id,
                review_role, decision, rationale, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (review_id, org_id, change_request_id, reviewer_id, review_role, decision, rationale, now)
        )

        # Update change request status based on decision
        if decision == "rejected":
            new_status = "rejected"
        elif decision == "revision_requested":
            new_status = "draft"
        else:  # approved
            new_status = "approved_for_release" if cr["status"] == "testing" else "approved_for_test"

        cur.execute(
            """
            UPDATE lineage_change_requests
            SET status = ?, updated_at = ?
            WHERE id = ? AND organization_id = ?
            """,
            (new_status, now, change_request_id, org_id)
        )
        self.conn.commit()

        return self.get_change_request(user_ctx, change_request_id)

    def transition_status(
        self,
        user_ctx: Dict[str, Any],
        change_request_id: str,
        target_status: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Advance change request lifecycle status along the governed release workflow."""
        require_permission(user_ctx, "lineage:approve")
        org_id = user_ctx["organization_id"]

        if target_status not in self.VALID_CR_STATUSES:
            raise ValidationError(f"Invalid target_status '{target_status}'. Valid: {sorted(self.VALID_CR_STATUSES)}")

        cr = self.get_change_request(user_ctx, change_request_id)
        current_status = cr["status"]

        # Valid transitions
        allowed_transitions = {
            "draft": {"analysis_pending"},
            "analysis_pending": {"review_required", "blocked_by_unknowns", "approved_for_test"},
            "blocked_by_unknowns": {"analysis_pending", "rejected"},
            "review_required": {"approved_for_test", "rejected", "draft"},
            "approved_for_test": {"testing", "rejected"},
            "testing": {"approved_for_release", "rejected", "draft"},
            "approved_for_release": {"deployed_pending_verification", "rejected"},
            "deployed_pending_verification": {"verified", "rolled_back"},
            "verified": {"closed"},
            "rolled_back": {"closed"},
            "rejected": {"closed", "draft"},
            "closed": set()
        }

        if target_status not in allowed_transitions.get(current_status, set()):
            raise ConflictError(f"Cannot transition change request from '{current_status}' to '{target_status}'. Allowed: {sorted(allowed_transitions.get(current_status, set()))}")

        now = datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE lineage_change_requests
            SET status = ?, updated_at = ?
            WHERE id = ? AND organization_id = ?
            """,
            (target_status, now, change_request_id, org_id)
        )
        self.conn.commit()
        return self.get_change_request(user_ctx, change_request_id)

    # -------------------------------------------------------------------------
    # 8. Lineage & Schema Evolution Summary
    # -------------------------------------------------------------------------
    def get_lineage_summary(self, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate statistical and governance health summary for the data lineage estate."""
        require_permission(user_ctx, "lineage:read")
        org_id = user_ctx["organization_id"]
        cur = self.conn.cursor()

        cur.execute("SELECT COUNT(*) as cnt FROM lineage_contracts_registry WHERE organization_id = ?", (org_id,))
        total_contracts = cur.fetchone()["cnt"]

        cur.execute("SELECT node_type, COUNT(*) as cnt FROM lineage_nodes WHERE organization_id = ? GROUP BY node_type", (org_id,))
        nodes_by_type = {r["node_type"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT verification_status, COUNT(*) as cnt FROM lineage_edges WHERE organization_id = ? GROUP BY verification_status", (org_id,))
        edges_by_verification = {r["verification_status"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT relationship_type, COUNT(*) as cnt FROM lineage_edges WHERE organization_id = ? GROUP BY relationship_type", (org_id,))
        edges_by_relationship = {r["relationship_type"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT status, COUNT(*) as cnt FROM lineage_change_requests WHERE organization_id = ? GROUP BY status", (org_id,))
        cr_by_status = {r["status"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT COUNT(*) as cnt FROM lineage_impact_reports WHERE organization_id = ? AND recommended_release_gate = 'BLOCKED_BY_UNKNOWNS'", (org_id,))
        blocked_by_unknowns_count = cur.fetchone()["cnt"]

        return {
            "organization_id": org_id,
            "total_contracts": total_contracts,
            "total_nodes": sum(nodes_by_type.values()),
            "nodes_by_type": nodes_by_type,
            "total_edges": sum(edges_by_verification.values()),
            "edges_by_verification": edges_by_verification,
            "edges_by_relationship": edges_by_relationship,
            "change_requests_by_status": cr_by_status,
            "blocked_by_unknowns_count": blocked_by_unknowns_count,
            "governance_health": "WARNING" if blocked_by_unknowns_count > 0 or edges_by_verification.get("unknown", 0) > 0 else "HEALTHY"
        }
