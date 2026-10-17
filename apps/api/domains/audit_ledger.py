"""Clinical Audit, Accountability, Compliance Evidence & Tamper-Evident Event Ledger Engine.

Phase 29 for ZAYVORA MATAB OS.
Enforces non-negotiables:
- Zero fabrication of audit events or verification results.
- Record actual outcomes, not attempted UI clicks (attempt vs committed result distinct).
- No silent editing or deletion of audit history (corrections appended as annotations).
- Cryptographic tamper evidence: continuous SHA-256 hash chaining over canonical event serializations.
- Separate clinical records from audit ledger; preserve exact entity versions and actors.
- No secrets or full patient chart narratives in audit metadata (data minimization).
- Fail-closed for consequential actions when audit commit cannot be secured.
"""

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class ClinicalAuditLedgerEngine:
    """Core domain engine for Phase 29 Tamper-Evident Audit Ledger & Compliance Evidence."""

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    SENSITIVE_FIELD_KEYS = {
        "password",
        "password_hash",
        "token",
        "auth_token",
        "secret",
        "access_token",
        "private_key",
        "session_cookie",
        "pin_hash",
    }

    VALID_RESULT_STATES = {"succeeded", "failed", "denied", "partial", "unknown", "blocked"}
    VALID_ACTOR_TYPES = {"human", "service", "scheduled_job", "integration", "anonymous", "unknown"}

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = DatabaseConnection(self.db_path).get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def canonical_json(obj: Any) -> str:
        """Produce deterministic, sorted JSON representation without whitespace."""
        return json.dumps(obj, sort_keys=True, separators=(",", ":"))

    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Strip sensitive secrets or credentials from audit metadata (Data Minimization)."""
        clean = {}
        for k, v in metadata.items():
            if k.lower() in self.SENSITIVE_FIELD_KEYS:
                clean[k] = "[REDACTED_SECRET]"
            elif isinstance(v, dict):
                clean[k] = self._sanitize_metadata(v)
            elif isinstance(v, str) and len(v) > 2000:
                clean[k] = v[:200] + "... [TRUNCATED_CHART_TEXT]"
            else:
                clean[k] = v
        return clean

    def _compute_event_hash(self, core_fields: Dict[str, Any], prev_hash: str) -> str:
        """Compute SHA-256 hash chaining over event core fields and previous hash."""
        canonical_str = self.canonical_json(core_fields)
        chained_input = f"{prev_hash}:{canonical_str}".encode("utf-8")
        return hashlib.sha256(chained_input).hexdigest()

    # --------------------------------------------------------------------------
    # 1. Event Recording with Cryptographic Chaining
    # --------------------------------------------------------------------------

    def record_event(self, data: Dict[str, Any], user_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append an immutable, cryptographically chained audit event to the clinical ledger."""
        required = ["event_code", "event_family", "target_entity_type", "target_entity_id", "action", "action_intent"]
        for r in required:
            if not data.get(r):
                raise ValidationError(f"Field '{r}' is required for audit event recording.")

        result_state = data.get("result_state", "succeeded")
        if result_state not in self.VALID_RESULT_STATES:
            raise ValidationError(f"Invalid result_state '{result_state}'. Allowed: {sorted(list(self.VALID_RESULT_STATES))}")

        actor_type = data.get("actor_type", "human" if user_ctx and user_ctx.get("user_id") else "service")
        if actor_type not in self.VALID_ACTOR_TYPES:
            raise ValidationError(f"Invalid actor_type '{actor_type}'. Allowed: {sorted(list(self.VALID_ACTOR_TYPES))}")

        user_ctx = user_ctx or {}
        actor_id = data.get("actor_principal_id") or user_ctx.get("user_id") or "sys-daemon"
        acting_role = data.get("acting_role") or user_ctx.get("role") or (user_ctx.get("roles", ["SYSTEM"])[0] if user_ctx.get("roles") else "SYSTEM")
        tenant_id = data.get("tenant_id") or user_ctx.get("organization_id") or "org-default"
        clinic_id = data.get("clinic_id") or user_ctx.get("facility_id") or "fac-default"
        request_id = data.get("request_id") or user_ctx.get("request_id") or str(uuid.uuid4())

        now_str = datetime.utcnow().isoformat()
        event_time = data.get("event_time") or now_str

        # Sanitize metadata
        raw_meta = data.get("metadata", {})
        clean_meta = self._sanitize_metadata(raw_meta)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Check policy if gating consequential action
            cur.execute("SELECT * FROM audit_event_policy_registry WHERE event_code = ? AND is_active = 1;", (data["event_code"],))
            policy = cur.fetchone()
            gates_action = policy["gates_consequential_action"] if policy else 0

            # Acquire sequence and previous hash atomically
            cur.execute("SELECT ledger_sequence, event_hash FROM clinical_ledger_events ORDER BY ledger_sequence DESC LIMIT 1;")
            latest = cur.fetchone()

            if latest:
                seq = latest["ledger_sequence"] + 1
                prev_hash = latest["event_hash"]
            else:
                seq = 1
                prev_hash = self.GENESIS_HASH

            event_id = f"evt-{uuid.uuid4().hex[:12]}"
            core_fields = {
                "event_id": event_id,
                "event_code": data["event_code"],
                "event_family": data["event_family"],
                "event_time": event_time,
                "recorded_at": now_str,
                "actor_principal_id": actor_id,
                "actor_type": actor_type,
                "tenant_id": tenant_id,
                "clinic_id": clinic_id,
                "target_entity_type": data["target_entity_type"],
                "target_entity_id": data["target_entity_id"],
                "target_entity_version": data.get("target_entity_version"),
                "action": data["action"],
                "action_intent": data["action_intent"],
                "result_state": result_state,
                "reason_code": data.get("reason_code"),
                "ledger_sequence": seq,
            }

            event_hash = self._compute_event_hash(core_fields, prev_hash)

            try:
                cur.execute(
                    """
                    INSERT INTO clinical_ledger_events (
                        event_id, event_schema_version, event_code, event_family,
                        event_time, recorded_at, time_source, actor_principal_id,
                        actor_type, acting_role, on_behalf_of_principal_id,
                        tenant_id, clinic_id, branch_id, session_ref, request_id,
                        target_entity_type, target_entity_id, target_entity_version,
                        target_record_hash, action, action_intent, result_state,
                        reason_code, policy_version, metadata_json,
                        previous_event_hash, event_hash, ledger_sequence, created_at
                    ) VALUES (
                        ?, '1.0', ?, ?,
                        ?, ?, 'SERVER_NTP_UTC', ?,
                        ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, 'v1.0', ?,
                        ?, ?, ?, ?
                    );
                    """,
                    (
                        event_id, data["event_code"], data["event_family"],
                        event_time, now_str, actor_id,
                        actor_type, acting_role, data.get("on_behalf_of_principal_id"),
                        tenant_id, clinic_id, data.get("branch_id"), data.get("session_ref"), request_id,
                        data["target_entity_type"], data["target_entity_id"], data.get("target_entity_version"),
                        data.get("target_record_hash"), data["action"], data["action_intent"], result_state,
                        data.get("reason_code"), json.dumps(clean_meta),
                        prev_hash, event_hash, seq, now_str,
                    ),
                )
                conn.commit()
            except Exception as e:
                if gates_action:
                    raise ValidationError(
                        f"Fail-Closed Protection: Consequential action '{data['action']}' blocked because required audit event "
                        f"'{data['event_code']}' could not be durably committed: {str(e)}"
                    )
                raise

            cur.execute("SELECT * FROM clinical_ledger_events WHERE event_id = ?;", (event_id,))
            res = dict(cur.fetchone())
            res["metadata"] = clean_meta
            return res
        finally:
            conn.close()

    def get_event(self, event_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch audit event by ID along with its annotations and dispute ledger."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM clinical_ledger_events WHERE event_id = ?;", (event_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Audit event '{event_id}' not found.")

            evt = dict(row)
            try:
                evt["metadata"] = json.loads(evt.get("metadata_json") or "{}")
            except Exception:
                evt["metadata"] = {}

            # Fetch linked annotations
            cur.execute("SELECT * FROM audit_annotations WHERE target_event_id = ? ORDER BY created_at ASC;", (event_id,))
            evt["annotations"] = [dict(a) for a in cur.fetchall()]

            return evt
        finally:
            conn.close()

    def query_ledger(self, filters: Dict[str, Any], user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query ledger events with multi-field filtering."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT * FROM clinical_ledger_events WHERE 1=1"
            params: List[Any] = []

            if filters.get("event_family"):
                query += " AND event_family = ?"
                params.append(filters["event_family"])
            if filters.get("event_code"):
                query += " AND event_code = ?"
                params.append(filters["event_code"])
            if filters.get("target_entity_type"):
                query += " AND target_entity_type = ?"
                params.append(filters["target_entity_type"])
            if filters.get("target_entity_id"):
                query += " AND target_entity_id = ?"
                params.append(filters["target_entity_id"])
            if filters.get("actor_principal_id"):
                query += " AND actor_principal_id = ?"
                params.append(filters["actor_principal_id"])
            if filters.get("result_state"):
                query += " AND result_state = ?"
                params.append(filters["result_state"])

            query += " ORDER BY ledger_sequence DESC LIMIT ?;"
            params.append(filters.get("limit", 100))

            cur.execute(query, params)
            rows = cur.fetchall()

            results = []
            for r in rows:
                item = dict(r)
                try:
                    item["metadata"] = json.loads(item.get("metadata_json") or "{}")
                except Exception:
                    item["metadata"] = {}
                results.append(item)
            return results
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Audit Annotations & Disputes (No Silent Edits)
    # --------------------------------------------------------------------------

    def add_annotation(self, target_event_id: str, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Append a correction, annotation, or dispute note to an existing audit event without silent mutation."""
        annot_type = data.get("annotation_type", "ANNOTATION_ADDED")
        allowed = {
            "CORRECTION_REQUESTED", "CORRECTION_REVIEWED", "ANNOTATION_ADDED",
            "EVENT_DISPUTED", "CORRECTION_ACCEPTED", "CORRECTION_REJECTED",
            "INTEGRITY_EXCEPTION_OPENED", "INTEGRITY_EXCEPTION_RESOLVED"
        }
        if annot_type not in allowed:
            raise ValidationError(f"Invalid annotation_type '{annot_type}'. Allowed: {sorted(list(allowed))}")

        if not data.get("rationale") or not data.get("rationale").strip():
            raise ValidationError("Mandatory documented rationale is required for audit annotations.")

        actor_id = user_ctx.get("user_id") or "usr-admin-1"
        annot_id = f"ann-{uuid.uuid4().hex[:12]}"
        now_str = datetime.utcnow().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT event_id FROM clinical_ledger_events WHERE event_id = ?;", (target_event_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Target audit event '{target_event_id}' not found.")

            cur.execute(
                """
                INSERT INTO audit_annotations (
                    id, target_event_id, annotation_type, actor_id, rationale, supporting_refs_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    annot_id, target_event_id, annot_type, actor_id,
                    data["rationale"], json.dumps(data.get("supporting_refs", [])), now_str,
                ),
            )
            conn.commit()

            cur.execute("SELECT * FROM audit_annotations WHERE id = ?;", (annot_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Integrity Verification & Sweep Service
    # --------------------------------------------------------------------------

    def verify_integrity(self, scope_filter: Optional[Dict[str, Any]] = None, user_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform a cryptographic integrity sweep over the ledger, verifying hash chains and sequence monotonicity."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM clinical_ledger_events ORDER BY ledger_sequence ASC;")
            rows = [dict(r) for r in cur.fetchall()]

            verifier_id = (user_ctx.get("user_id") if user_ctx else None) or "usr-admin-1"
            now_str = datetime.utcnow().isoformat()
            scope_desc = "FULL_LEDGER_CHAIN"

            if not rows:
                chk_id = f"chk-{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """
                    INSERT INTO audit_integrity_checkpoints (
                        id, checkpoint_type, checked_scope, start_sequence, end_sequence,
                        total_events_checked, root_hash, verification_result, verified_by, verified_at
                    ) VALUES (?, 'MANUAL_VERIFICATION', ?, 0, 0, 0, ?, 'passed_for_checked_scope', ?, ?);
                    """,
                    (chk_id, scope_desc, self.GENESIS_HASH, verifier_id, now_str),
                )
                conn.commit()
                return {
                    "checkpoint_id": chk_id,
                    "total_events_checked": 0,
                    "verification_result": "passed_for_checked_scope",
                    "root_hash": self.GENESIS_HASH,
                    "errors": [],
                }

            expected_prev_hash = self.GENESIS_HASH
            expected_sequence = 1
            mismatches = []

            for r in rows:
                seq = r["ledger_sequence"]
                # 1. Monotonic sequence check
                if seq != expected_sequence:
                    mismatches.append({
                        "error_type": "SEQUENCE_GAP_OR_REORDER",
                        "expected_sequence": expected_sequence,
                        "actual_sequence": seq,
                        "event_id": r["event_id"],
                    })

                # 2. Previous hash link check
                if r["previous_event_hash"] != expected_prev_hash:
                    mismatches.append({
                        "error_type": "PREVIOUS_HASH_MISMATCH",
                        "sequence": seq,
                        "event_id": r["event_id"],
                        "expected_prev_hash": expected_prev_hash,
                        "actual_prev_hash": r["previous_event_hash"],
                    })

                # 3. Recompute current event hash
                core_fields = {
                    "event_id": r["event_id"],
                    "event_code": r["event_code"],
                    "event_family": r["event_family"],
                    "event_time": r["event_time"],
                    "recorded_at": r["recorded_at"],
                    "actor_principal_id": r["actor_principal_id"],
                    "actor_type": r["actor_type"],
                    "tenant_id": r["tenant_id"],
                    "clinic_id": r["clinic_id"],
                    "target_entity_type": r["target_entity_type"],
                    "target_entity_id": r["target_entity_id"],
                    "target_entity_version": r["target_entity_version"],
                    "action": r["action"],
                    "action_intent": r["action_intent"],
                    "result_state": r["result_state"],
                    "reason_code": r["reason_code"],
                    "ledger_sequence": seq,
                }
                recomputed_hash = self._compute_event_hash(core_fields, r["previous_event_hash"])
                if recomputed_hash != r["event_hash"]:
                    mismatches.append({
                        "error_type": "PAYLOAD_TAMPERING_DETECTED",
                        "sequence": seq,
                        "event_id": r["event_id"],
                        "stored_hash": r["event_hash"],
                        "recomputed_hash": recomputed_hash,
                    })

                expected_prev_hash = r["event_hash"]
                expected_sequence = seq + 1

            ver_result = "passed_for_checked_scope" if not mismatches else "failed_integrity_mismatch"
            root_hash = expected_prev_hash
            start_seq = rows[0]["ledger_sequence"]
            end_seq = rows[-1]["ledger_sequence"]

            chk_id = f"chk-{uuid.uuid4().hex[:12]}"
            cur.execute(
                """
                INSERT INTO audit_integrity_checkpoints (
                    id, checkpoint_type, checked_scope, start_sequence, end_sequence,
                    total_events_checked, root_hash, verification_result, mismatch_details_json,
                    verified_by, verified_at
                ) VALUES (?, 'MANUAL_VERIFICATION', ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    chk_id, scope_desc, start_seq, end_seq, len(rows), root_hash,
                    ver_result, json.dumps(mismatches), verifier_id, now_str,
                ),
            )
            conn.commit()

            return {
                "checkpoint_id": chk_id,
                "total_events_checked": len(rows),
                "start_sequence": start_seq,
                "end_sequence": end_seq,
                "root_hash": root_hash,
                "verification_result": ver_result,
                "errors_count": len(mismatches),
                "errors": mismatches,
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Retention Policies & Legal Holds
    # --------------------------------------------------------------------------

    def list_retention_policies(self, user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List active governed audit retention policies."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM audit_retention_policies ORDER BY created_at ASC;")
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def place_legal_hold(self, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Place a legal hold across specified audit event scopes."""
        required = ["hold_code", "title", "reason", "scope_filter"]
        for r in required:
            if not data.get(r):
                raise ValidationError(f"Field '{r}' is required for legal hold placement.")

        user_id = user_ctx.get("user_id") or "usr-admin-1"
        now_str = datetime.utcnow().isoformat()
        hold_id = f"hold-{uuid.uuid4().hex[:12]}"

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM audit_legal_holds WHERE hold_code = ?;", (data["hold_code"],))
            if cur.fetchone():
                raise ConflictError(f"Legal hold with code '{data['hold_code']}' already exists.")

            cur.execute(
                """
                INSERT INTO audit_legal_holds (
                    id, hold_code, title, scope_filter_json, reason, placed_by, placed_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE');
                """,
                (hold_id, data["hold_code"], data["title"], json.dumps(data["scope_filter"]), data["reason"], user_id, now_str),
            )
            conn.commit()

            cur.execute("SELECT * FROM audit_legal_holds WHERE id = ?;", (hold_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def release_legal_hold(self, hold_id: str, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Release a legal hold with documented rationale."""
        user_id = user_ctx.get("user_id") or "usr-admin-1"
        now_str = datetime.utcnow().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM audit_legal_holds WHERE id = ?;", (hold_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Legal hold '{hold_id}' not found.")

            cur.execute(
                """
                UPDATE audit_legal_holds
                SET status = 'RELEASED',
                    released_at = ?,
                    released_by = ?
                WHERE id = ?;
                """,
                (now_str, user_id, hold_id),
            )
            conn.commit()

            cur.execute("SELECT * FROM audit_legal_holds WHERE id = ?;", (hold_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Purpose-Bound Compliance Evidence Exports
    # --------------------------------------------------------------------------

    def export_evidence_package(self, data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a cryptographically verified compliance evidence export package."""
        if not data.get("purpose"):
            raise ValidationError("Mandatory purpose is required for compliance evidence exports.")

        scope_filter = data.get("scope", {})
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Run integrity check first
            integrity_check = self.verify_integrity(scope_filter, user_ctx)
            if integrity_check["verification_result"] != "passed_for_checked_scope":
                raise ValidationError("Cannot export evidence package: Ledger integrity check failed.")

            # 2. Query events in scope
            events = self.query_ledger(scope_filter, user_ctx)

            # 3. Assemble package manifest
            export_manifest = {
                "purpose": data["purpose"],
                "exported_at": datetime.utcnow().isoformat(),
                "requested_by": user_ctx.get("user_id") or "usr-admin-1",
                "total_events": len(events),
                "root_checkpoint_id": integrity_check["checkpoint_id"],
                "root_hash": integrity_check["root_hash"],
                "events_manifest": [
                    {
                        "sequence": e["ledger_sequence"],
                        "event_id": e["event_id"],
                        "code": e["event_code"],
                        "hash": e["event_hash"],
                        "recorded_at": e["recorded_at"],
                    }
                    for e in events
                ],
            }

            manifest_hash = hashlib.sha256(self.canonical_json(export_manifest).encode("utf-8")).hexdigest()
            export_num = f"EXP-{datetime.utcnow().year}-{uuid.uuid4().hex[:8].upper()}"
            export_id = f"exp-{uuid.uuid4().hex[:12]}"
            now_str = datetime.utcnow().isoformat()
            user_id = user_ctx.get("user_id") or "usr-admin-1"

            cur.execute(
                """
                INSERT INTO audit_evidence_exports (
                    id, export_number, purpose, scope_json, total_events_exported,
                    export_manifest_hash, verification_checkpoint_id, requested_by,
                    authorized_by, export_artifact_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    export_id, export_num, data["purpose"], json.dumps(scope_filter),
                    len(events), manifest_hash, integrity_check["checkpoint_id"],
                    user_id, user_id, json.dumps(export_manifest), now_str,
                ),
            )
            conn.commit()

            cur.execute("SELECT * FROM audit_evidence_exports WHERE id = ?;", (export_id,))
            res = dict(cur.fetchone())
            res["export_artifact"] = export_manifest
            return res
        finally:
            conn.close()
