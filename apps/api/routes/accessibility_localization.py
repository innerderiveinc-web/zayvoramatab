"""
REST API Route Handlers for Accessibility, Localization, RTL & Clinical Human-Factors (Prompt 51).
"""

from typing import Dict, Any, Tuple
from apps.api.domains.accessibility_localization_engine import AccessibilityLocalizationEngine


def handle_list_locales(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    locales = AccessibilityLocalizationEngine.list_locales(conn)
    return 200, {"locales": locales, "total": len(locales)}


def handle_register_locale(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    actor_id = user.get("id", "sys-admin")
    actor_role = user.get("roles", ["ADMIN"])[0] if user.get("roles") else "ADMIN"
    data = req.get("body", {})

    try:
        result = AccessibilityLocalizationEngine.register_locale(conn, tenant_id, data, actor_id, actor_role)
        return 201, result
    except ValueError as e:
        return 400, {"error": True, "message": str(e)}


def handle_list_catalogs(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    query_params = req.get("query_params", {})
    locale_code = query_params.get("locale", "en")
    namespace = query_params.get("namespace")

    entries = AccessibilityLocalizationEngine.list_catalogs(conn, locale_code, namespace)
    return 200, {"entries": entries, "total": len(entries), "locale": locale_code}


def handle_upsert_catalog_entry(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    actor_id = user.get("id", "sys-admin")
    actor_role = user.get("roles", ["ADMIN"])[0] if user.get("roles") else "ADMIN"
    data = req.get("body", {})

    try:
        result = AccessibilityLocalizationEngine.upsert_catalog_entry(conn, tenant_id, data, actor_id, actor_role)
        return 201, result
    except ValueError as e:
        return 400, {"error": True, "message": str(e)}


def handle_review_catalog_entry(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    actor_id = user.get("id", "sys-admin")
    actor_role = user.get("roles", ["ADMIN"])[0] if user.get("roles") else "ADMIN"
    path_params = req.get("path_params", {})
    catalog_id = path_params.get("id", "")
    body = req.get("body", {})
    status = body.get("status", "approved")

    try:
        result = AccessibilityLocalizationEngine.review_catalog_entry(conn, tenant_id, catalog_id, status, actor_id, actor_role)
        return 200, result
    except LookupError as e:
        return 404, {"error": True, "message": str(e)}
    except PermissionError as e:
        return 403, {"error": True, "message": str(e)}
    except ValueError as e:
        return 400, {"error": True, "message": str(e)}


def handle_list_glossary(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    query_params = req.get("query_params", {})
    search = query_params.get("q")
    terms = AccessibilityLocalizationEngine.list_glossary(conn, search)
    return 200, {"terms": terms, "total": len(terms)}


def handle_upsert_glossary_term(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    actor_id = user.get("id", "sys-admin")
    actor_role = user.get("roles", ["ADMIN"])[0] if user.get("roles") else "ADMIN"
    data = req.get("body", {})

    try:
        result = AccessibilityLocalizationEngine.upsert_glossary_term(conn, tenant_id, data, actor_id, actor_role)
        return 201, result
    except ValueError as e:
        return 400, {"error": True, "message": str(e)}


def handle_get_user_preferences(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    path_params = req.get("path_params", {})
    user_id = path_params.get("user_id", "")
    prefs = AccessibilityLocalizationEngine.get_user_preferences(conn, user_id)
    return 200, prefs


def handle_update_user_preferences(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    path_params = req.get("path_params", {})
    user_id = path_params.get("user_id", "")
    data = req.get("body", {})

    prefs = AccessibilityLocalizationEngine.update_user_preferences(conn, tenant_id, user_id, data)
    return 200, prefs


def handle_list_a11y_audits(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    audits = AccessibilityLocalizationEngine.list_a11y_audits(conn, tenant_id)
    return 200, {"audits": audits, "total": len(audits)}


def handle_record_a11y_audit(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    actor_id = user.get("id", "sys-admin")
    actor_role = user.get("roles", ["ADMIN"])[0] if user.get("roles") else "ADMIN"
    data = req.get("body", {})

    result = AccessibilityLocalizationEngine.record_a11y_audit(conn, tenant_id, data, actor_id, actor_role)
    return 201, result


def handle_list_human_factors_scenarios(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    scenarios = AccessibilityLocalizationEngine.list_human_factors_scenarios(conn, tenant_id)
    return 200, {"scenarios": scenarios, "total": len(scenarios)}


def handle_record_human_factors_scenario(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    actor_id = user.get("id", "sys-admin")
    actor_role = user.get("roles", ["ADMIN"])[0] if user.get("roles") else "ADMIN"
    data = req.get("body", {})

    result = AccessibilityLocalizationEngine.record_human_factors_scenario(conn, tenant_id, data, actor_id, actor_role)
    return 201, result


def handle_get_audit_ledger(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    records = AccessibilityLocalizationEngine.get_audit_ledger(conn, tenant_id)
    return 200, {"records": records, "total": len(records)}


def handle_verify_audit_integrity(conn, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user", {})
    tenant_id = user.get("tenant_id", "T-001")
    verification = AccessibilityLocalizationEngine.verify_audit_ledger_integrity(conn, tenant_id)
    return 200, verification
