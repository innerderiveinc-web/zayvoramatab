"""Clinical Content & Governed Rules REST Route Handlers.
Returns safe metadata about active clinical content sources and rules catalog.
"""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.domains.clinical_rules import ClinicalRulesEngine


def handle_clinical_content_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Return status of active clinical sources, governance state, and health."""
    user = req["user"]
    require_permission(user, "clinical_rules:read", request_id=req.get("request_id"))

    status_data = ClinicalRulesEngine.get_content_status(conn)
    return 200, status_data


def handle_clinical_rules_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Browse catalog of governed clinical rules and heuristics."""
    user = req["user"]
    require_permission(user, "clinical_rules:read", request_id=req.get("request_id"))

    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, r.rule_id, r.rule_version, r.rule_type, r.title, r.scope,
               r.severity, r.plain_language_rationale, r.recommended_action,
               r.governance_status, r.clinical_owner, r.reviewer_name,
               s.title as source_title, s.authority as source_authority
        FROM clinical_rule_definitions r
        LEFT JOIN clinical_content_sources s ON r.source_id = s.id
        ORDER BY r.rule_type, r.severity;
    """)
    rules = [dict(r) for r in cursor.fetchall()]
    return 200, {"rules": rules, "total": len(rules)}
