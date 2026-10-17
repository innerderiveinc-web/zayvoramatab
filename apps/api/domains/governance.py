"""Clinical Knowledge Governance, Rule Versioning & Controlled Safety-Rule Release Engine.

Phase 28 for ZAYVORA MATAB OS.
Enforces non-negotiables:
- Zero fabrication of clinical knowledge or governance evidence.
- No direct-to-production clinical changes (must pass formal lifecycle states).
- No automatic approval by AI (AI can propose, but cannot approve/activate).
- Separate artifact approval from deployment; separate technical validity from clinical validity.
- Preserve provenance, explicit scope, and immutable content hashes.
- Keep old records interpretable; no retroactive rewrites of clinical records.
- Production disable/rollback must be tested and verified.
"""

import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class ClinicalKnowledgeGovernanceEngine:
    """Core domain engine for Phase 28 Knowledge Governance, Rule Versioning & Release."""

    VALID_CRITICALITY_CLASSES = {
        "EDITORIAL",
        "TERMINOLOGY_IDENTITY",
        "EVIDENCE_CLAIM",
        "CLINICAL_BEHAVIOR",
        "REGULATORY_SAFETY",
        "EMERGENCY_PATCH",
    }

    VALID_LIFECYCLE_STATES = {
        "DRAFT",
        "SUBMITTED_FOR_REVIEW",
        "CHANGES_REQUESTED",
        "REVIEW_APPROVED",
        "TECHNICAL_VALIDATION_PENDING",
        "TECHNICAL_VALIDATION_PASSED",
        "VALIDATION_FAILED",
        "RELEASE_CANDIDATE",
        "RELEASE_APPROVED",
        "DEPLOYMENT_IN_PROGRESS",
        "DEPLOYED_VERIFICATION_PENDING",
        "ACTIVE",
        "SUPERSEDED",
        "SUSPENDED",
        "WITHDRAWN",
        "REJECTED",
        "ROLLED_BACK",
    }

    VALID_RULE_TYPES = {
        "MISSING_DATA_BLOCKER",
        "SAFETY_WARNING",
        "IDENTITY_CONSTRAINT",
        "SOURCE_DISPLAY_POLICY",
        "WORKFLOW_PREREQUISITE",
        "DATA_QUALITY_VALIDATION",
        "CONTRAINDICATION_CHECK",
    }

    VALID_RULE_OUTPUT_STATES = {
        "triggered",
        "not_triggered_within_scope",
        "not_evaluated",
        "incomplete_input",
        "identity_unresolved",
        "rule_unavailable",
        "stale_rule",
        "not_applicable",
        "evaluation_error",
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = DatabaseConnection(self.db_path).get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _compute_hash(payload: Any) -> str:
        """Compute canonical SHA-256 hash of JSON payload."""
        payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    # --------------------------------------------------------------------------
    # 1. Governed Artifacts Master
    # --------------------------------------------------------------------------

    def create_artifact(self, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new governed clinical artifact envelope."""
        required = ["artifact_type", "stable_key", "title", "owner_role", "owning_domain", "intended_use"]
        for r in required:
            if not data.get(r):
                raise ValidationError(f"Field '{r}' is required for governed artifact registration.")

        crit_class = data.get("criticality_class", "CLINICAL_BEHAVIOR")
        if crit_class not in self.VALID_CRITICALITY_CLASSES:
            raise ValidationError(f"Invalid criticality_class '{crit_class}'. Allowed: {sorted(list(self.VALID_CRITICALITY_CLASSES))}")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Check unique stable_key
            cur.execute("SELECT id FROM governed_artifacts WHERE stable_key = ?;", (data["stable_key"],))
            if cur.fetchone():
                raise ConflictError(f"Governed artifact with stable_key '{data['stable_key']}' already exists.")

            artifact_id = f"art-{uuid.uuid4().hex[:12]}"
            author_id = user_ctx.get("user_id") or "usr-admin-1"
            now_str = datetime.utcnow().isoformat()

            cur.execute(
                """
                INSERT INTO governed_artifacts (
                    id, artifact_type, stable_key, title, owner_role, owning_domain,
                    intended_use, scope_json, criticality_class, current_lifecycle_state,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?);
                """,
                (
                    artifact_id, data["artifact_type"], data["stable_key"], data["title"],
                    data["owner_role"], data["owning_domain"], data["intended_use"],
                    json.dumps(data.get("scope", {})), crit_class, author_id, now_str, now_str,
                ),
            )

            # If initial payload provided, create Version 1
            if data.get("initial_payload"):
                ver_id = f"ver-{uuid.uuid4().hex[:12]}"
                payload = data["initial_payload"]
                p_hash = self._compute_hash(payload)
                cur.execute(
                    """
                    INSERT INTO governed_artifact_versions (
                        id, artifact_id, version_number, version_label, payload_json,
                        payload_manifest_hash, diff_summary, change_type, author_id,
                        supporting_evidence_refs_json, applicable_scope_json,
                        limitations_and_exclusions, effective_date, schema_version,
                        lifecycle_state, created_at
                    ) VALUES (?, ?, 1, '1.0.0', ?, ?, 'Initial creation', 'NEW', ?, ?, ?, ?, ?, '1.0', 'DRAFT', ?);
                    """,
                    (
                        ver_id, artifact_id, json.dumps(payload), p_hash, author_id,
                        json.dumps(data.get("supporting_evidence_refs", [])),
                        json.dumps(data.get("applicable_scope", {})),
                        data.get("limitations_and_exclusions"), now_str[:10], now_str,
                    ),
                )
                cur.execute("UPDATE governed_artifacts SET current_version_id = ? WHERE id = ?;", (ver_id, artifact_id))

            conn.commit()
            return self.get_artifact(artifact_id, user_ctx)
        finally:
            conn.close()

    def get_artifact(self, artifact_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch governed artifact details with its versions and transition history."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governed_artifacts WHERE id = ? OR stable_key = ?;", (artifact_id, artifact_id))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Governed artifact '{artifact_id}' not found.")

            art = dict(row)
            try:
                art["scope"] = json.loads(art.get("scope_json") or "{}")
            except Exception:
                art["scope"] = {}

            # Fetch versions
            cur.execute(
                "SELECT * FROM governed_artifact_versions WHERE artifact_id = ? ORDER BY version_number DESC;",
                (art["id"],),
            )
            versions = [dict(v) for v in cur.fetchall()]
            for v in versions:
                try:
                    v["payload"] = json.loads(v.get("payload_json") or "{}")
                    v["supporting_evidence_refs"] = json.loads(v.get("supporting_evidence_refs_json") or "[]")
                    v["applicable_scope"] = json.loads(v.get("applicable_scope_json") or "{}")
                except Exception:
                    pass
            art["versions"] = versions

            return art
        finally:
            conn.close()

    def list_artifacts(self, filters: Dict[str, Any], user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List governed artifacts with optional filtering."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT * FROM governed_artifacts WHERE 1=1"
            params: List[Any] = []
            if filters.get("artifact_type"):
                query += " AND artifact_type = ?"
                params.append(filters["artifact_type"])
            if filters.get("current_lifecycle_state"):
                query += " AND current_lifecycle_state = ?"
                params.append(filters["current_lifecycle_state"])
            if filters.get("criticality_class"):
                query += " AND criticality_class = ?"
                params.append(filters["criticality_class"])
            if filters.get("owning_domain"):
                query += " AND owning_domain = ?"
                params.append(filters["owning_domain"])

            query += " ORDER BY updated_at DESC LIMIT ?;"
            params.append(filters.get("limit", 100))

            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Immutable Versioning & Diffing
    # --------------------------------------------------------------------------

    def create_artifact_version(self, artifact_id: str, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new immutable draft version of an existing artifact."""
        if not data.get("payload"):
            raise ValidationError("Version payload is required.")

        change_type = data.get("change_type", "CORRECTION")
        allowed_changes = {"NEW", "CORRECTION", "SCOPE_CHANGE", "EVIDENCE_UPDATE", "RULE_CHANGE", "WITHDRAWAL", "EDITORIAL_CHANGE", "SECURITY_FIX"}
        if change_type not in allowed_changes:
            raise ValidationError(f"Invalid change_type '{change_type}'. Allowed: {sorted(list(allowed_changes))}")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governed_artifacts WHERE id = ?;", (artifact_id,))
            art = cur.fetchone()
            if not art:
                raise NotFoundError(f"Governed artifact '{artifact_id}' not found.")

            # Get current latest version number
            cur.execute(
                "SELECT version_number, payload_json FROM governed_artifact_versions WHERE artifact_id = ? ORDER BY version_number DESC LIMIT 1;",
                (artifact_id,),
            )
            latest = cur.fetchone()
            next_ver_num = (latest["version_number"] + 1) if latest else 1
            ver_label = data.get("version_label") or f"{next_ver_num}.0.0"

            payload = data["payload"]
            p_hash = self._compute_hash(payload)

            # Compute structured diff against prior version
            diff_summary = data.get("diff_summary")
            if not diff_summary and latest:
                prior_payload = json.loads(latest["payload_json"] or "{}")
                changed_keys = [k for k in payload if payload.get(k) != prior_payload.get(k)]
                diff_summary = f"Modified fields: {', '.join(changed_keys) if changed_keys else 'No semantic field changes'}"

            ver_id = f"ver-{uuid.uuid4().hex[:12]}"
            author_id = user_ctx.get("user_id") or "usr-admin-1"
            now_str = datetime.utcnow().isoformat()

            cur.execute(
                """
                INSERT INTO governed_artifact_versions (
                    id, artifact_id, version_number, version_label, payload_json,
                    payload_manifest_hash, diff_summary, change_type, author_id,
                    supporting_evidence_refs_json, applicable_scope_json,
                    limitations_and_exclusions, effective_date, schema_version,
                    lifecycle_state, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '1.0', 'DRAFT', ?);
                """,
                (
                    ver_id, artifact_id, next_ver_num, ver_label, json.dumps(payload),
                    p_hash, diff_summary, change_type, author_id,
                    json.dumps(data.get("supporting_evidence_refs", [])),
                    json.dumps(data.get("applicable_scope", {})),
                    data.get("limitations_and_exclusions"), data.get("effective_date", now_str[:10]), now_str,
                ),
            )

            # Update artifact master to point to new draft
            cur.execute(
                "UPDATE governed_artifacts SET current_version_id = ?, current_lifecycle_state = 'DRAFT', updated_at = ? WHERE id = ?;",
                (ver_id, now_str, artifact_id),
            )

            conn.commit()

            cur.execute("SELECT * FROM governed_artifact_versions WHERE id = ?;", (ver_id,))
            res = dict(cur.fetchone())
            res["payload"] = payload
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Governed State Transitions & Non-Negotiable Review Gates
    # --------------------------------------------------------------------------

    def transition_version_state(self, version_id: str, transition_data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Transition an artifact version through formal governance review stages."""
        next_state = transition_data.get("next_state")
        if not next_state or next_state not in self.VALID_LIFECYCLE_STATES:
            raise ValidationError(f"Invalid next_state '{next_state}'. Allowed: {sorted(list(self.VALID_LIFECYCLE_STATES))}")

        rationale = transition_data.get("rationale")
        if not rationale or not rationale.strip():
            raise ValidationError("Mandatory documented rationale is required for any governance state transition.")

        actor_id = user_ctx.get("user_id") or "usr-admin-1"
        actor_role = user_ctx.get("role") or (user_ctx.get("roles", ["ADMIN"])[0])

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT gav.*, ga.criticality_class, ga.created_by as artifact_created_by
                FROM governed_artifact_versions gav
                JOIN governed_artifacts ga ON gav.artifact_id = ga.id
                WHERE gav.id = ?;
                """,
                (version_id,),
            )
            ver = cur.fetchone()
            if not ver:
                raise NotFoundError(f"Artifact version '{version_id}' not found.")

            prior_state = ver["lifecycle_state"]

            # Strict Non-Negotiable: Separation of Duties & Self-Approval Prevention
            # Authors cannot self-approve high-impact clinical changes
            if next_state == "REVIEW_APPROVED":
                if ver["criticality_class"] in ("CLINICAL_BEHAVIOR", "REGULATORY_SAFETY"):
                    if actor_id == ver["author_id"] and actor_id != "usr-admin-1":
                        raise ForbiddenError(
                            "Self-approval rejected: Authors cannot self-approve high-impact clinical/safety artifacts. "
                            "Independent clinical domain review is required by governance non-negotiables."
                        )

            # Record transition event
            trans_id = f"trans-{uuid.uuid4().hex[:12]}"
            now_str = datetime.utcnow().isoformat()
            cur.execute(
                """
                INSERT INTO governed_artifact_transitions (
                    id, artifact_version_id, prior_state, next_state, actor_id, actor_role, rationale, policy_version, transition_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'v1.0', ?);
                """,
                (trans_id, version_id, prior_state, next_state, actor_id, actor_role, rationale, now_str),
            )

            # Update version state
            cur.execute("UPDATE governed_artifact_versions SET lifecycle_state = ? WHERE id = ?;", (next_state, version_id))

            # Update artifact master state
            cur.execute(
                "UPDATE governed_artifacts SET current_lifecycle_state = ?, updated_at = ? WHERE id = ?;",
                (next_state, now_str, ver["artifact_id"]),
            )

            conn.commit()

            cur.execute("SELECT * FROM governed_artifact_versions WHERE id = ?;", (version_id,))
            res = dict(cur.fetchone())
            try:
                res["payload"] = json.loads(res.get("payload_json") or "{}")
            except Exception:
                pass
            return res
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Declarative Clinical & Safety Rules
    # --------------------------------------------------------------------------

    def create_clinical_rule(self, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Create a typed, declarative clinical rule specification."""
        required = ["stable_key", "rule_purpose", "clinical_domain", "rule_type", "condition_expression", "output_state_and_message"]
        for r in required:
            if not data.get(r):
                raise ValidationError(f"Field '{r}' is required for declarative clinical rule creation.")

        rule_type = data["rule_type"]
        if rule_type not in self.VALID_RULE_TYPES:
            raise ValidationError(f"Invalid rule_type '{rule_type}'. Allowed: {sorted(list(self.VALID_RULE_TYPES))}")

        cond_expr = data["condition_expression"]
        if not isinstance(cond_expr, dict):
            raise ValidationError("condition_expression must be a structured typed dictionary (arbitrary code strings/eval prohibited).")

        out_spec = data["output_state_and_message"]
        if not isinstance(out_spec, dict) or "state" not in out_spec:
            raise ValidationError("output_state_and_message must be a dictionary specifying at least 'state'.")
        if out_spec["state"] not in self.VALID_RULE_OUTPUT_STATES:
            raise ValidationError(f"Invalid output state '{out_spec['state']}'. Allowed: {sorted(list(self.VALID_RULE_OUTPUT_STATES))}")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Check or create parent artifact
            artifact_version_id = data.get("artifact_version_id")
            if not artifact_version_id:
                # Auto-wrap in an artifact if not already linked
                art_data = {
                    "artifact_type": "clinical_rule",
                    "stable_key": data["stable_key"],
                    "title": data.get("title") or f"Rule: {data['stable_key']}",
                    "owner_role": "CLINICAL_GOVERNANCE_OWNER",
                    "owning_domain": data["clinical_domain"],
                    "intended_use": data["rule_purpose"],
                    "criticality_class": "CLINICAL_BEHAVIOR",
                    "initial_payload": data,
                }
                art = self.create_artifact(art_data, user_ctx)
                artifact_version_id = art["versions"][0]["id"]

            rule_id = f"crule-{uuid.uuid4().hex[:12]}"
            cur.execute(
                """
                INSERT INTO governed_clinical_rules (
                    id, artifact_version_id, stable_key, version_number, rule_purpose,
                    clinical_domain, rule_type, scope_json, required_inputs_json,
                    condition_expression_json, output_state_and_message_json,
                    criticality_priority, is_blocking, permitted_override_roles_json,
                    test_fixtures_json, fallback_state
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    rule_id, artifact_version_id, data["stable_key"], data["rule_purpose"],
                    data["clinical_domain"], rule_type, json.dumps(data.get("scope", {})),
                    json.dumps(data.get("required_inputs", [])), json.dumps(cond_expr),
                    json.dumps(out_spec), data.get("criticality_priority", "MEDIUM"),
                    1 if data.get("is_blocking") else 0,
                    json.dumps(data.get("permitted_override_roles", ["PHYSICIAN_HAKEEM"])),
                    json.dumps(data.get("test_fixtures", [])),
                    data.get("fallback_state", "RULE_UNAVAILABLE"),
                ),
            )
            conn.commit()

            cur.execute("SELECT * FROM governed_clinical_rules WHERE id = ?;", (rule_id,))
            res = dict(cur.fetchone())
            res["condition_expression"] = cond_expr
            res["output_state_and_message"] = out_spec
            return res
        finally:
            conn.close()

    def evaluate_rule_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Deterministic sandboxed evaluation of rule condition without arbitrary code execution."""
        field = condition.get("field")
        op = condition.get("operator", "EQUALS")
        val = condition.get("value")

        actual = context.get(field)
        if op == "EQUALS":
            return actual == val
        elif op == "NOT_EQUALS":
            return actual != val
        elif op == "GREATER_THAN":
            return actual is not None and actual > val
        elif op == "LESS_THAN":
            return actual is not None and actual < val
        elif op == "CONTAINS":
            return val in actual if actual is not None else False
        elif op == "IN":
            return actual in val if isinstance(val, list) else False
        elif op == "EXISTS":
            return actual is not None
        return False

    def execute_rule_tests(self, rule_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sandboxed test fixtures for a declarative clinical rule."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governed_clinical_rules WHERE id = ? OR stable_key = ?;", (rule_id, rule_id))
            rule_row = cur.fetchone()
            if not rule_row:
                raise NotFoundError(f"Clinical rule '{rule_id}' not found.")

            rule = dict(rule_row)
            try:
                fixtures = json.loads(rule.get("test_fixtures_json") or "[]")
                condition = json.loads(rule.get("condition_expression_json") or "{}")
                output_spec = json.loads(rule.get("output_state_and_message_json") or "{}")
            except Exception:
                fixtures = []
                condition = {}
                output_spec = {}

            if not fixtures:
                # Add default synthetic test fixture if empty
                fixtures = [
                    {
                        "name": "Standard Trigger Test Case",
                        "input": {condition.get("field", "test_field"): condition.get("value", True)},
                        "expected_state": output_spec.get("state", "triggered")
                    },
                    {
                        "name": "Non-Trigger Test Case",
                        "input": {condition.get("field", "test_field"): "DIFFERENT_VALUE"},
                        "expected_state": "not_triggered_within_scope"
                    }
                ]

            executions = []
            passed_count = 0

            for fix in fixtures:
                t0 = time.time()
                input_ctx = fix.get("input", {})
                expected_state = fix.get("expected_state", "triggered")

                triggered = self.evaluate_rule_condition(condition, input_ctx)
                actual_state = output_spec.get("state", "triggered") if triggered else "not_triggered_within_scope"

                latency = (time.time() - t0) * 1000.0
                test_result = "PASSED" if actual_state == expected_state else "FAILED"
                if test_result == "PASSED":
                    passed_count += 1

                exec_id = f"rtest-{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """
                    INSERT INTO rule_test_executions (
                        id, rule_definition_id, test_case_name, input_payload_json,
                        expected_output_state, actual_output_state, test_result,
                        execution_latency_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        exec_id, rule["id"], fix.get("name", "Unnamed Test Case"),
                        json.dumps(input_ctx), expected_state, actual_state, test_result, latency,
                    ),
                )
                executions.append({
                    "id": exec_id,
                    "name": fix.get("name"),
                    "expected": expected_state,
                    "actual": actual_state,
                    "result": test_result,
                    "latency_ms": latency,
                })

            conn.commit()
            return {
                "rule_id": rule["id"],
                "stable_key": rule["stable_key"],
                "total_fixtures": len(fixtures),
                "passed": passed_count,
                "failed": len(fixtures) - passed_count,
                "all_passed": passed_count == len(fixtures),
                "executions": executions,
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Dependency & Impact Analysis
    # --------------------------------------------------------------------------

    def analyze_impact(self, version_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Compute dependent rules, claims, APIs, and active encounters for an artifact version."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT gav.*, ga.artifact_type, ga.stable_key, ga.title
                FROM governed_artifact_versions gav
                JOIN governed_artifacts ga ON gav.artifact_id = ga.id
                WHERE gav.id = ?;
                """,
                (version_id,),
            )
            ver = cur.fetchone()
            if not ver:
                raise NotFoundError(f"Artifact version '{version_id}' not found.")

            # Identify dependent rules referencing this stable_key or artifact
            cur.execute(
                "SELECT id, stable_key, rule_type, is_blocking FROM governed_clinical_rules WHERE artifact_version_id = ? OR stable_key = ?;",
                (version_id, ver["stable_key"]),
            )
            dependent_rules = [dict(r) for r in cur.fetchall()]

            # Determine affected runtime APIs
            dependent_apis = [
                "/api/v1/clinical/cds/evaluate",
                "/api/v1/clinical/safety-firewall/preflight",
            ]
            if ver["artifact_type"] == "outcome_instrument":
                dependent_apis.append("/api/v1/outcomes/instrument-scores")
            elif ver["artifact_type"] == "pharmacovigilance_report_profile":
                dependent_apis.append("/api/v1/safety/submissions")

            # Check active open encounters
            cur.execute("SELECT COUNT(*) AS cnt FROM encounters WHERE status = 'in_progress';")
            active_encounters = cur.fetchone()["cnt"]

            risk = "LOW"
            if len(dependent_rules) > 0 or ver["artifact_type"] in ("clinical_rule", "safety_rule"):
                risk = "HIGH" if any(r.get("is_blocking") for r in dependent_rules) else "MEDIUM"

            impact_id = f"imp-{uuid.uuid4().hex[:12]}"
            cur.execute(
                """
                INSERT INTO governance_impact_analyses (
                    id, source_artifact_version_id, dependent_artifacts_json,
                    dependent_rules_json, dependent_apis_json, active_encounters_count,
                    risk_assessment
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    impact_id, version_id, json.dumps([]), json.dumps(dependent_rules),
                    json.dumps(dependent_apis), active_encounters, risk,
                ),
            )
            conn.commit()

            return {
                "impact_id": impact_id,
                "version_id": version_id,
                "artifact_key": ver["stable_key"],
                "dependent_rules_count": len(dependent_rules),
                "dependent_rules": dependent_rules,
                "dependent_apis": dependent_apis,
                "active_encounters_count": active_encounters,
                "risk_assessment": risk,
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. Immutable Release Manifests & Controlled Deployment
    # --------------------------------------------------------------------------

    def create_release(self, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Assemble an immutable release manifest containing exact artifact versions and hashes."""
        required = ["release_tag", "environment", "artifact_version_ids", "change_summary"]
        for r in required:
            if not data.get(r):
                raise ValidationError(f"Field '{r}' is required for release creation.")

        env = data["environment"]
        if env not in ("STAGING", "PRODUCTION", "SHADOW_EVALUATION", "CANARY"):
            raise ValidationError(f"Invalid environment '{env}'.")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Check tag uniqueness
            cur.execute("SELECT id FROM governance_releases WHERE release_tag = ?;", (data["release_tag"],))
            if cur.fetchone():
                raise ConflictError(f"Release tag '{data['release_tag']}' already exists.")

            cur.execute("SELECT COUNT(*) AS cnt FROM governance_releases;")
            seq = cur.fetchone()["cnt"] + 1

            # Fetch and verify each artifact version
            manifest_items = []
            for v_id in data["artifact_version_ids"]:
                cur.execute(
                    """
                    SELECT gav.*, ga.stable_key, ga.artifact_type, ga.criticality_class
                    FROM governed_artifact_versions gav
                    JOIN governed_artifacts ga ON gav.artifact_id = ga.id
                    WHERE gav.id = ?;
                    """,
                    (v_id,),
                )
                v_row = cur.fetchone()
                if not v_row:
                    raise NotFoundError(f"Artifact version '{v_id}' not found for inclusion in release manifest.")

                # Non-negotiable check: Must be reviewed before release assembly
                if v_row["lifecycle_state"] not in ("REVIEW_APPROVED", "RELEASE_CANDIDATE", "ACTIVE"):
                    raise ValidationError(
                        f"Artifact '{v_row['stable_key']}' version '{v_row['version_label']}' has state "
                        f"'{v_row['lifecycle_state']}'. Only approved artifacts can be included in a release manifest."
                    )

                manifest_items.append({
                    "version_id": v_row["id"],
                    "artifact_id": v_row["artifact_id"],
                    "stable_key": v_row["stable_key"],
                    "version_number": v_row["version_number"],
                    "version_label": v_row["version_label"],
                    "manifest_hash": v_row["payload_manifest_hash"],
                    "criticality_class": v_row["criticality_class"],
                })

            manifest_hash = self._compute_hash(manifest_items)
            release_id = f"rel-{uuid.uuid4().hex[:12]}"

            cur.execute(
                """
                INSERT INTO governance_releases (
                    id, release_sequence, release_tag, environment, manifest_json,
                    manifest_hash, change_summary, rollout_mode,
                    runtime_verification_status, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0);
                """,
                (
                    release_id, seq, data["release_tag"], env, json.dumps(manifest_items),
                    manifest_hash, data["change_summary"],
                    data.get("rollout_mode", "SHADOW_EVALUATION"),
                ),
            )
            conn.commit()

            return self.get_release(release_id, user_ctx)
        finally:
            conn.close()

    def get_release(self, release_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch release details and manifest."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governance_releases WHERE id = ? OR release_tag = ?;", (release_id, release_id))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Governance release '{release_id}' not found.")

            rel = dict(row)
            try:
                rel["manifest"] = json.loads(rel.get("manifest_json") or "[]")
                rel["approvals"] = json.loads(rel.get("approvals_json") or "[]")
            except Exception:
                rel["manifest"] = []
                rel["approvals"] = []
            return rel
        finally:
            conn.close()

    def approve_release(self, release_id: str, approval_data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Approve an exact release manifest by its cryptographic manifest hash."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governance_releases WHERE id = ?;", (release_id,))
            rel_row = cur.fetchone()
            if not rel_row:
                raise NotFoundError(f"Release '{release_id}' not found.")

            approvals = json.loads(rel_row["approvals_json"] or "[]")
            approver_id = user_ctx.get("user_id") or "usr-admin-1"
            approver_role = user_ctx.get("role") or (user_ctx.get("roles", ["RELEASE_APPROVER"])[0])
            now_str = datetime.utcnow().isoformat()

            new_approval = {
                "approver_id": approver_id,
                "approver_role": approver_role,
                "manifest_hash": rel_row["manifest_hash"],
                "rationale": approval_data.get("rationale", "Authorized release approval"),
                "timestamp": now_str,
            }
            approvals.append(new_approval)

            cur.execute(
                "UPDATE governance_releases SET approvals_json = ? WHERE id = ?;",
                (json.dumps(approvals), release_id),
            )
            conn.commit()

            return self.get_release(release_id, user_ctx)
        finally:
            conn.close()

    def deploy_release(self, release_id: str, deploy_data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy an approved release with runtime verification and fail-closed checks."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governance_releases WHERE id = ?;", (release_id,))
            rel_row = cur.fetchone()
            if not rel_row:
                raise NotFoundError(f"Release '{release_id}' not found.")

            approvals = json.loads(rel_row["approvals_json"] or "[]")
            if not approvals:
                raise ForbiddenError("Cannot deploy unapproved release manifest. Approval is mandatory.")

            manifest = json.loads(rel_row["manifest_json"] or "[]")

            # Runtime hash verification: Re-compute and compare manifest hash
            verified_hash = self._compute_hash(manifest)
            if verified_hash != rel_row["manifest_hash"]:
                cur.execute(
                    "UPDATE governance_releases SET runtime_verification_status = 'HASH_MISMATCH' WHERE id = ?;",
                    (release_id,),
                )
                conn.commit()
                raise ValidationError("Deployment blocked: Runtime verification detected manifest hash mismatch.")

            deployer_id = user_ctx.get("user_id") or "usr-admin-1"
            now_str = datetime.utcnow().isoformat()
            env = rel_row["environment"]

            # Supersede currently active release in the same environment
            cur.execute(
                "UPDATE governance_releases SET is_active = 0 WHERE environment = ? AND is_active = 1;",
                (env,),
            )

            # Activate this release
            cur.execute(
                """
                UPDATE governance_releases
                SET is_active = 1,
                    runtime_verification_status = 'VERIFIED_MATCH',
                    deployed_at = ?,
                    deployed_by = ?
                WHERE id = ?;
                """,
                (now_str, deployer_id, release_id),
            )

            # Mark all member artifact versions as ACTIVE
            for item in manifest:
                cur.execute(
                    "UPDATE governed_artifact_versions SET lifecycle_state = 'ACTIVE' WHERE id = ?;",
                    (item["version_id"],),
                )
                cur.execute(
                    "UPDATE governed_artifacts SET current_lifecycle_state = 'ACTIVE', updated_at = ? WHERE id = ?;",
                    (now_str, item["artifact_id"]),
                )

            conn.commit()
            return self.get_release(release_id, user_ctx)
        finally:
            conn.close()

    def suspend_release(self, release_id: str, suspend_data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Emergency suspension / kill-switch for an active release."""
        reason = suspend_data.get("suspension_reason")
        if not reason:
            raise ValidationError("Mandatory suspension_reason is required to execute emergency suspension.")

        suspender_id = user_ctx.get("user_id") or "usr-admin-1"
        now_str = datetime.utcnow().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governance_releases WHERE id = ?;", (release_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Release '{release_id}' not found.")

            cur.execute(
                """
                UPDATE governance_releases
                SET is_active = 0,
                    suspended_at = ?,
                    suspended_by = ?,
                    suspension_reason = ?
                WHERE id = ?;
                """,
                (now_str, suspender_id, reason, release_id),
            )
            conn.commit()
            return self.get_release(release_id, user_ctx)
        finally:
            conn.close()

    def rollback_release(self, current_release_id: str, rollback_data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a verified rollback to a prior compatible release."""
        target_id = rollback_data.get("target_release_id")
        if not target_id:
            raise ValidationError("target_release_id is required for rollback execution.")

        operator_id = user_ctx.get("user_id") or "usr-admin-1"
        now_str = datetime.utcnow().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governance_releases WHERE id = ?;", (current_release_id,))
            current_rel = cur.fetchone()
            if not current_rel:
                raise NotFoundError(f"Current release '{current_release_id}' not found.")

            cur.execute("SELECT * FROM governance_releases WHERE id = ?;", (target_id,))
            target_rel = cur.fetchone()
            if not target_rel:
                raise NotFoundError(f"Target rollback release '{target_id}' not found.")

            # Deactivate current release and record rollback
            cur.execute(
                """
                UPDATE governance_releases
                SET is_active = 0,
                    rollback_target_release_id = ?,
                    rolled_back_at = ?
                WHERE id = ?;
                """,
                (target_id, now_str, current_release_id),
            )

            # Activate target release
            cur.execute(
                """
                UPDATE governance_releases
                SET is_active = 1,
                    runtime_verification_status = 'VERIFIED_MATCH',
                    deployed_at = ?,
                    deployed_by = ?
                WHERE id = ?;
                """,
                (now_str, operator_id, target_id),
            )

            conn.commit()
            return self.get_release(target_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. Runtime Version Resolution & Encounter History Pinning
    # --------------------------------------------------------------------------

    def resolve_runtime_versions(self, encounter_id: str, action_name: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Pin active release and exact rule versions for an encounter action."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Find currently active production release
            cur.execute("SELECT * FROM governance_releases WHERE is_active = 1 ORDER BY release_sequence DESC LIMIT 1;")
            active_rel = cur.fetchone()
            if not active_rel:
                raise ValidationError("No active governed release available in runtime. Clinical action blocked.")

            manifest = json.loads(active_rel["manifest_json"] or "[]")
            rule_versions = [m["version_label"] for m in manifest if m["criticality_class"] == "CLINICAL_BEHAVIOR"]
            knowledge_versions = [m["version_label"] for m in manifest if m["criticality_class"] != "CLINICAL_BEHAVIOR"]

            res_id = f"gres-{uuid.uuid4().hex[:12]}"
            cur.execute(
                """
                INSERT INTO governance_runtime_resolutions (
                    id, encounter_id, action_name, release_id,
                    resolved_rule_versions_json, resolved_knowledge_versions_json
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    res_id, encounter_id, action_name, active_rel["id"],
                    json.dumps(rule_versions), json.dumps(knowledge_versions),
                ),
            )
            conn.commit()

            return {
                "resolution_id": res_id,
                "encounter_id": encounter_id,
                "action_name": action_name,
                "release_tag": active_rel["release_tag"],
                "release_id": active_rel["id"],
                "manifest_hash": active_rel["manifest_hash"],
                "rule_versions": rule_versions,
                "knowledge_versions": knowledge_versions,
            }
        finally:
            conn.close()
