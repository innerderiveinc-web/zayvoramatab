"""Unit Tests for Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine.

Phase 43 for ZAYVORA MATAB OS.
Tests core domain logic:
1. Contracts Registry (create, list, get, duplicate validation, invalid schema policy).
2. Lineage Nodes (register, list, get with direct edges).
3. Evidence Edges (create, list, delete, self-reference prevention).
4. Cycle-Safe Graph Traversal (downstream blast radius, upstream provenance, cycle detection, depth limits).
5. Change Proposal & Deterministic Impact Analysis (additive, breaking, semantically breaking).
6. "Impact Unknown" Non-Negotiable Invariant (unverified dependencies flag BLOCKED_BY_UNKNOWNS).
7. Separation of Duties Non-Negotiable Invariant (author cannot self-approve release gate).
8. Clinical Safety Invariant (clinical safety impact requires Clinical Director approval).
9. Change Request Governed State Machine Transitions.
10. Lineage Summary & Health metrics.
"""

import os
import json
import sqlite3
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.data_lineage import EnterpriseDataLineageEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestEnterpriseDataLineageEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_lineage.db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = EnterpriseDataLineageEngine(self.db_path)

        # Contexts
        self.admin_ctx = {
            "id": "usr-admin-1",
            "user_id": "usr-admin-1",
            "username": "admin",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["ORG_ADMIN", "DATA_ARCHITECT"],
            "org_roles": ["ORG_ADMIN", "DATA_ARCHITECT"],
            "permissions": [
                "lineage:read", "lineage:contract_manage", "lineage:analyze",
                "lineage:change_request", "lineage:approve"
            ]
        }

        self.clinical_director_ctx = {
            "id": "usr-director-1",
            "user_id": "usr-director-1",
            "username": "clinical_director",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["CLINICAL_DIRECTOR"],
            "org_roles": ["CLINICAL_DIRECTOR"],
            "permissions": [
                "lineage:read", "lineage:analyze", "lineage:approve"
            ]
        }

        self.developer_ctx = {
            "id": "usr-dev-1",
            "user_id": "usr-dev-1",
            "username": "backend_dev",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["DEVELOPER"],
            "org_roles": ["DEVELOPER"],
            "permissions": [
                "lineage:read", "lineage:change_request", "lineage:contract_manage"
            ]
        }

        self.viewer_ctx = {
            "id": "usr-viewer-1",
            "user_id": "usr-viewer-1",
            "username": "auditor",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["AUDITOR"],
            "org_roles": ["AUDITOR"],
            "permissions": [
                "lineage:read"
            ]
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_seed_contracts_and_nodes_loaded(self):
        """Verify baseline contracts, nodes, and edges seeded correctly."""
        contracts = self.engine.get_contracts(self.admin_ctx)
        self.assertGreaterEqual(len(contracts), 5)
        keys = [c["contract_key"] for c in contracts]
        self.assertIn("db:patients", keys)
        self.assertIn("db:encounters", keys)

        nodes = self.engine.get_nodes(self.admin_ctx)
        self.assertGreaterEqual(len(nodes), 8)
        node_keys = [n["node_key"] for n in nodes]
        self.assertIn("table:patients", node_keys)
        self.assertIn("rule:nuskha_dosage_safety", node_keys)

        edges = self.engine.get_edges(self.admin_ctx)
        self.assertGreaterEqual(len(edges), 5)

    def test_contract_management(self):
        """Test registering a new contract and handling invalid inputs."""
        payload = {
            "contract_key": "event:order_created",
            "contract_type": "event",
            "version": "1.0.0",
            "owner": "Dispensing Operations",
            "schema_definition_json": {"order_id": "string", "amount": "number"},
            "compatibility_policy": "BACKWARD",
            "sensitivity": "FINANCIAL",
            "limitations_json": ["External pharmacy adapter not monitored"]
        }
        res = self.engine.create_contract(self.admin_ctx, payload)
        self.assertEqual(res["contract_key"], "event:order_created")
        self.assertEqual(res["sensitivity"], "FINANCIAL")

        # Duplicate contract key + version should raise ConflictError
        with self.assertRaises(ConflictError):
            self.engine.create_contract(self.admin_ctx, payload)

        # Invalid contract type should raise ValidationError
        with self.assertRaises(ValidationError):
            self.engine.create_contract(self.admin_ctx, {
                "contract_key": "bad:type",
                "contract_type": "invalid_type"
            })

    def test_node_registration_and_retrieval(self):
        """Test node registration and upstream/downstream edge resolution."""
        payload = {
            "node_key": "service:billing_worker",
            "node_type": "domain_entity",
            "name": "Billing Background Worker",
            "owner": "Finance Team",
            "sensitivity": "FINANCIAL"
        }
        node = self.engine.register_node(self.admin_ctx, payload)
        self.assertEqual(node["node_key"], "service:billing_worker")

        # Fetch node with edges
        details = self.engine.get_node(self.admin_ctx, "table:encounters")
        self.assertIn("upstream_edges", details)
        self.assertIn("downstream_edges", details)
        self.assertGreaterEqual(len(details["downstream_edges"]), 1)

    def test_edge_creation_and_self_reference_prevention(self):
        """Test directed edge creation and rejection of self-referencing loops."""
        nodes = self.engine.get_nodes(self.admin_ctx)
        src = nodes[0]["id"]
        tgt = nodes[1]["id"]

        # Self-referencing should fail
        with self.assertRaises(ValidationError):
            self.engine.create_edge(self.admin_ctx, {
                "source_node_id": src,
                "target_node_id": src,
                "relationship_type": "reads"
            })

        # Valid edge creation
        edge = self.engine.create_edge(self.admin_ctx, {
            "source_node_id": src,
            "target_node_id": tgt,
            "relationship_type": "depends_on",
            "evidence_type": "test_assertion",
            "verification_status": "verified"
        })
        self.assertEqual(edge["relationship_type"], "depends_on")

        # Deletion
        del_res = self.engine.delete_edge(self.admin_ctx, edge["id"])
        self.assertEqual(del_res["status"], "deleted")

    def test_cycle_safe_graph_traversal(self):
        """Test downstream and upstream graph traversal with cycle safety."""
        # 1. Downstream from table:patients
        downstream = self.engine.trace_lineage(self.admin_ctx, "table:patients", direction="downstream", max_depth=5)
        self.assertEqual(downstream["direction"], "downstream")
        self.assertGreaterEqual(downstream["total_nodes_reachable"], 3)
        visited_keys = [n["node_key"] for n in downstream["nodes"]]
        self.assertIn("table:encounters", visited_keys)
        self.assertIn("table:prescriptions", visited_keys)

        # 2. Upstream from rule:nuskha_dosage_safety
        upstream = self.engine.trace_lineage(self.admin_ctx, "rule:nuskha_dosage_safety", direction="upstream", max_depth=5)
        self.assertEqual(upstream["direction"], "upstream")
        up_keys = [n["node_key"] for n in upstream["nodes"]]
        self.assertIn("table:prescriptions", up_keys)

        # 3. Cycle handling: introduce an edge creating a loop and verify it terminates safely
        nodes_map = {n["node_key"]: n["id"] for n in self.engine.get_nodes(self.admin_ctx)}
        self.engine.create_edge(self.admin_ctx, {
            "source_node_id": nodes_map["nod-table-prescriptions"] if "nod-table-prescriptions" in nodes_map else nodes_map["table:prescriptions"],
            "target_node_id": nodes_map["nod-table-patients"] if "nod-table-patients" in nodes_map else nodes_map["table:patients"],
            "relationship_type": "reads",
            "evidence_type": "code_reference",
            "verification_status": "verified"
        })

        # Traversal should detect cycle and complete without infinite recursion
        cycle_trace = self.engine.trace_lineage(self.admin_ctx, "table:patients", direction="downstream", max_depth=5)
        self.assertTrue(cycle_trace["has_cycles"])
        self.assertGreater(cycle_trace["total_nodes_reachable"], 0)

    def test_change_request_and_impact_analysis(self):
        """Test change proposal creation and deterministic impact report generation."""
        contracts = self.engine.get_contracts(self.admin_ctx)
        cnt = next(c for c in contracts if c["contract_key"] == "db:encounters")

        cr = self.engine.create_change_request(self.developer_ctx, {
            "title": "Add Clinical Severity Score to Encounters",
            "contract_id": cnt["id"],
            "target_version": "1.1.0",
            "change_type": "additive",
            "diff_payload_json": {"add_field": "clinical_severity_score", "type": "INTEGER"}
        })
        self.assertEqual(cr["status"], "draft")

        # Run impact analysis
        analyzed = self.engine.analyze_impact(self.admin_ctx, cr["id"])
        report = analyzed["impact_report"]
        self.assertIsNotNone(report)
        self.assertEqual(report["compatibility_classification"], "additive_compatible")
        # Direct consumers of encounters should include prescriptions and metrics
        direct_keys = [d["node_key"] for d in report["direct_consumers"]]
        self.assertIn("table:prescriptions", direct_keys)
        # Because prescriptions validates via dosage safety gate, clinical safety flag should be 1
        self.assertTrue(report["clinical_safety_impact_flag"])
        self.assertEqual(report["recommended_release_gate"], "MANUAL_REVIEW_REQUIRED")
        self.assertEqual(analyzed["status"], "review_required")

    def test_unknown_dependency_blocks_release(self):
        """
        Non-negotiable invariant test:
        'Impact unknown' is a real result, never 'no impact'.
        Uninstrumented or unknown dependencies must result in BLOCKED_BY_UNKNOWNS.
        """
        # Register a contract that has known limitations (unknown dynamic callers)
        c = self.engine.create_contract(self.admin_ctx, {
            "contract_key": "api:v1:legacy_export",
            "contract_type": "api",
            "version": "1.0.0",
            "owner": "Legacy Systems",
            "limitations_json": ["Contains unmonitored external cron consumers with unspecified schemas"]
        })

        cr = self.engine.create_change_request(self.developer_ctx, {
            "title": "Modify Legacy Export API Response",
            "contract_id": c["id"],
            "target_version": "2.0.0",
            "change_type": "breaking"
        })

        analyzed = self.engine.analyze_impact(self.admin_ctx, cr["id"])
        report = analyzed["impact_report"]
        self.assertGreater(len(report["known_unknowns"]), 0)
        self.assertEqual(report["recommended_release_gate"], "BLOCKED_BY_UNKNOWNS")
        self.assertEqual(analyzed["status"], "blocked_by_unknowns")

        # Attempting to approve while blocked by unknowns must fail
        with self.assertRaises(ConflictError):
            self.engine.submit_review(self.clinical_director_ctx, cr["id"], {
                "review_role": "CLINICAL_DIRECTOR",
                "decision": "approved",
                "rationale": "Premature attempt to approve unknown impact"
            })

    def test_separation_of_duties_enforcement(self):
        """
        Non-negotiable invariant test:
        The author of a change request cannot approve their own release gate.
        """
        contracts = self.engine.get_contracts(self.admin_ctx)
        cnt = contracts[0]

        # Developer creates CR
        cr = self.engine.create_change_request(self.developer_ctx, {
            "title": "Developer Schema Modification",
            "contract_id": cnt["id"],
            "target_version": "1.2.0",
            "change_type": "additive"
        })
        self.engine.analyze_impact(self.admin_ctx, cr["id"])

        # Developer attempts to self-approve with approve permission
        dev_as_approver = dict(self.developer_ctx)
        dev_as_approver["permissions"] = ["lineage:read", "lineage:approve"]

        with self.assertRaises(ForbiddenError):
            self.engine.submit_review(dev_as_approver, cr["id"], {
                "review_role": "DATA_ARCHITECT",
                "decision": "approved",
                "rationale": "I wrote this and I approve it myself."
            })

    def test_clinical_safety_review_role_requirement(self):
        """
        Clinical safety invariant test:
        If clinical safety flag is active, Clinical Director approval is required.
        """
        contracts = self.engine.get_contracts(self.admin_ctx)
        cnt = next(c for c in contracts if c["contract_key"] == "db:encounters")

        cr = self.engine.create_change_request(self.developer_ctx, {
            "title": "Clinical Rule Revision",
            "contract_id": cnt["id"],
            "target_version": "2.0.0",
            "change_type": "semantically_breaking",
            "diff_payload_json": {"rule": "altering dosage formula for nuskha"}
        })
        self.engine.analyze_impact(self.admin_ctx, cr["id"])

        # Technical Architect attempts to approve without Clinical Director approval first
        with self.assertRaises(ForbiddenError):
            self.engine.submit_review(self.admin_ctx, cr["id"], {
                "review_role": "DATA_ARCHITECT",
                "decision": "approved",
                "rationale": "Technical verification looks sound."
            })

        # Clinical Director approves
        cd_res = self.engine.submit_review(self.clinical_director_ctx, cr["id"], {
            "review_role": "CLINICAL_DIRECTOR",
            "decision": "approved",
            "rationale": "Clinical evaluation confirmed safe humor balance threshold."
        })
        self.assertEqual(cd_res["status"], "approved_for_test")

    def test_state_machine_governed_transitions(self):
        """Test sequential progression through release states and invalid jumps."""
        contracts = self.engine.get_contracts(self.admin_ctx)
        cnt = contracts[0]
        cr = self.engine.create_change_request(self.developer_ctx, {
            "title": "Workflow Lifecycle Test CR",
            "contract_id": cnt["id"],
            "target_version": "1.0.1",
            "change_type": "additive"
        })

        # Invalid jump from draft directly to deployed_pending_verification
        with self.assertRaises(ConflictError):
            self.engine.transition_status(self.admin_ctx, cr["id"], "deployed_pending_verification")

        # Valid transition: draft -> analysis_pending
        step1 = self.engine.transition_status(self.admin_ctx, cr["id"], "analysis_pending")
        self.assertEqual(step1["status"], "analysis_pending")

    def test_lineage_summary_metrics(self):
        """Test aggregate summary reporting."""
        summary = self.engine.get_lineage_summary(self.admin_ctx)
        self.assertEqual(summary["organization_id"], "org-matab-default")
        self.assertGreaterEqual(summary["total_contracts"], 5)
        self.assertGreaterEqual(summary["total_nodes"], 8)
        self.assertGreaterEqual(summary["total_edges"], 5)
        self.assertIn("db_table", summary["nodes_by_type"])
        self.assertIn(summary["governance_health"], ["HEALTHY", "WARNING"])
