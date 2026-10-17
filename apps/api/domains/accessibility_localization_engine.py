"""
Accessibility, Localization, RTL & Clinical Human-Factors Validation Engine (Prompt 51).

Provides centralized translation catalogs, governed clinical glossary management,
WCAG 2.1 AA accessibility auditing, clinical human-factors scenario tracking,
and tamper-evident SHA-256 audit chaining.
"""

import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


class AccessibilityLocalizationEngine:

    @staticmethod
    def _compute_hash(previous_hash: str, payload_str: str) -> str:
        h = hashlib.sha256()
        h.update((previous_hash + payload_str).encode("utf-8"))
        return h.hexdigest()

    @staticmethod
    def _record_audit_event(conn, tenant_id: str, event_type: str, actor_id: str, actor_role: str, payload: Dict[str, Any]) -> str:
        cur = conn.cursor()
        cur.execute(
            "SELECT record_hash FROM a11y_human_factors_audit_ledger WHERE tenant_id = ? ORDER BY timestamp DESC, rowid DESC LIMIT 1",
            (tenant_id,)
        )
        row = cur.fetchone()
        previous_hash = row[0] if row else "0" * 64

        record_id = f"a11y-rec-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.utcnow().isoformat() + "Z"
        payload_str = json.dumps(payload, sort_keys=True)
        record_hash = AccessibilityLocalizationEngine._compute_hash(previous_hash, payload_str)

        cur.execute(
            """
            INSERT INTO a11y_human_factors_audit_ledger
            (record_id, tenant_id, event_type, actor_id, actor_role, payload_json, timestamp, previous_hash, record_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (record_id, tenant_id, event_type, actor_id, actor_role, payload_str, now_iso, previous_hash, record_hash)
        )
        return record_id

    # ---------------------------------------------------------
    # 1. Locales Management
    # ---------------------------------------------------------

    @staticmethod
    def list_locales(conn) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        cur.execute("SELECT locale_code, name, native_name, direction, script, is_default, is_active, completion_percent, reviewed_by, reviewed_at FROM i18n_locales ORDER BY is_default DESC, locale_code ASC")
        rows = cur.fetchall()
        return [
            {
                "locale_code": r[0],
                "name": r[1],
                "native_name": r[2],
                "direction": r[3],
                "script": r[4],
                "is_default": bool(r[5]),
                "is_active": bool(r[6]),
                "completion_percent": r[7],
                "reviewed_by": r[8],
                "reviewed_at": r[9]
            }
            for r in rows
        ]

    @staticmethod
    def register_locale(conn, tenant_id: str, data: Dict[str, Any], actor_id: str, actor_role: str) -> Dict[str, Any]:
        locale_code = data.get("locale_code", "").strip().lower()
        if not locale_code or len(locale_code) > 10:
            raise ValueError("Valid locale_code is required (e.g., 'en', 'ur', 'hi')")

        name = data.get("name", "").strip()
        native_name = data.get("native_name", "").strip() or name
        direction = data.get("direction", "ltr").strip().lower()
        if direction not in ("ltr", "rtl"):
            raise ValueError("direction must be 'ltr' or 'rtl'")

        script = data.get("script", "Latn").strip()
        if script not in ("Latn", "Arab", "Deva"):
            raise ValueError("script must be 'Latn', 'Arab', or 'Deva'")

        now_iso = datetime.utcnow().isoformat() + "Z"
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO i18n_locales (locale_code, name, native_name, direction, script, is_default, is_active, completion_percent, reviewed_by, reviewed_at, created_at)
            VALUES (?, ?, ?, ?, ?, 0, 1, 100.0, ?, ?, ?)
            ON CONFLICT(locale_code) DO UPDATE SET
                name=excluded.name,
                native_name=excluded.native_name,
                direction=excluded.direction,
                script=excluded.script,
                reviewed_by=excluded.reviewed_by,
                reviewed_at=excluded.reviewed_at
            """,
            (locale_code, name, native_name, direction, script, actor_id, now_iso, now_iso)
        )

        AccessibilityLocalizationEngine._record_audit_event(
            conn, tenant_id, "LOCALE_REGISTERED", actor_id, actor_role,
            {"locale_code": locale_code, "direction": direction, "script": script}
        )

        return {"locale_code": locale_code, "name": name, "direction": direction, "script": script}

    # ---------------------------------------------------------
    # 2. Translation Catalogs
    # ---------------------------------------------------------

    @staticmethod
    def list_catalogs(conn, locale_code: str, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        query = "SELECT catalog_id, locale_code, namespace, string_key, source_en_text, localized_text, status, is_safety_critical, context_notes, reviewed_by, reviewed_at FROM i18n_translation_catalogs WHERE locale_code = ?"
        params = [locale_code]
        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)
        query += " ORDER BY namespace ASC, string_key ASC"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [
            {
                "catalog_id": r[0],
                "locale_code": r[1],
                "namespace": r[2],
                "string_key": r[3],
                "source_en_text": r[4],
                "localized_text": r[5],
                "status": r[6],
                "is_safety_critical": bool(r[7]),
                "context_notes": r[8],
                "reviewed_by": r[9],
                "reviewed_at": r[10]
            }
            for r in rows
        ]

    @staticmethod
    def upsert_catalog_entry(conn, tenant_id: str, data: Dict[str, Any], actor_id: str, actor_role: str) -> Dict[str, Any]:
        locale_code = data.get("locale_code", "").strip().lower()
        namespace = data.get("namespace", "common").strip()
        string_key = data.get("string_key", "").strip()
        source_en = data.get("source_en_text", "").strip()
        localized = data.get("localized_text", "").strip()
        is_safety = int(bool(data.get("is_safety_critical", False)))
        context = data.get("context_notes", "")

        if not locale_code or not string_key or not source_en or not localized:
            raise ValueError("locale_code, string_key, source_en_text, and localized_text are mandatory")

        # Safety non-negotiable: default to 'draft' status if not reviewed by Tabib/Safety Officer
        initial_status = "draft"
        if actor_role in ("PRACTITIONER", "CLINICAL_SAFETY_OFFICER", "ORG_ADMIN"):
            initial_status = "approved"

        catalog_id = f"cat-{locale_code}-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.utcnow().isoformat() + "Z"

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO i18n_translation_catalogs
            (catalog_id, locale_code, namespace, string_key, source_en_text, localized_text, status, is_safety_critical, context_notes, reviewed_by, reviewed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(locale_code, namespace, string_key) DO UPDATE SET
                source_en_text = excluded.source_en_text,
                localized_text = excluded.localized_text,
                status = excluded.status,
                is_safety_critical = excluded.is_safety_critical,
                context_notes = excluded.context_notes,
                reviewed_by = excluded.reviewed_by,
                reviewed_at = excluded.reviewed_at
            """,
            (catalog_id, locale_code, namespace, string_key, source_en, localized, initial_status, is_safety, context, actor_id, now_iso, now_iso)
        )

        AccessibilityLocalizationEngine._record_audit_event(
            conn, tenant_id, "CATALOG_ENTRY_UPSERTED", actor_id, actor_role,
            {"locale_code": locale_code, "namespace": namespace, "string_key": string_key, "is_safety": is_safety, "status": initial_status}
        )

        return {
            "catalog_id": catalog_id,
            "locale_code": locale_code,
            "namespace": namespace,
            "string_key": string_key,
            "status": initial_status,
            "is_safety_critical": bool(is_safety)
        }

    @staticmethod
    def review_catalog_entry(conn, tenant_id: str, catalog_id: str, status: str, reviewer_id: str, reviewer_role: str) -> Dict[str, Any]:
        if status not in ("draft", "reviewed", "approved", "retired"):
            raise ValueError("Invalid review status")

        cur = conn.cursor()
        cur.execute("SELECT is_safety_critical, string_key FROM i18n_translation_catalogs WHERE catalog_id = ?", (catalog_id,))
        row = cur.fetchone()
        if not row:
            raise LookupError(f"Catalog entry '{catalog_id}' not found")

        is_safety = bool(row[0])
        # Clinician/Safety Officer check for safety critical
        if is_safety and status == "approved" and reviewer_role not in ("PRACTITIONER", "CLINICAL_SAFETY_OFFICER", "ORG_ADMIN"):
            raise PermissionError("Only licensed Tabib or Clinical Safety Officer can approve safety-critical translations")

        now_iso = datetime.utcnow().isoformat() + "Z"
        cur.execute(
            "UPDATE i18n_translation_catalogs SET status = ?, reviewed_by = ?, reviewed_at = ? WHERE catalog_id = ?",
            (status, reviewer_id, now_iso, catalog_id)
        )

        AccessibilityLocalizationEngine._record_audit_event(
            conn, tenant_id, "CATALOG_ENTRY_REVIEWED", reviewer_id, reviewer_role,
            {"catalog_id": catalog_id, "status": status, "is_safety": is_safety}
        )

        return {"catalog_id": catalog_id, "status": status, "reviewed_by": reviewer_id, "reviewed_at": now_iso}

    # ---------------------------------------------------------
    # 3. Governed Clinical Glossary
    # ---------------------------------------------------------

    @staticmethod
    def list_glossary(conn, search: Optional[str] = None) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        query = "SELECT term_id, canonical_code, classical_arabic_urdu, roman_transliteration, hindi_devanagari, english_biomedical_equivalent, clinical_definition, epistemological_boundary_warning, is_approved_by_tabib, tabib_reviewer_id, reviewed_at FROM i18n_clinical_glossary"
        params = []
        if search:
            query += " WHERE canonical_code LIKE ? OR classical_arabic_urdu LIKE ? OR roman_transliteration LIKE ? OR hindi_devanagari LIKE ? OR english_biomedical_equivalent LIKE ?"
            s = f"%{search}%"
            params = [s, s, s, s, s]
        query += " ORDER BY canonical_code ASC"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [
            {
                "term_id": r[0],
                "canonical_code": r[1],
                "classical_arabic_urdu": r[2],
                "roman_transliteration": r[3],
                "hindi_devanagari": r[4],
                "english_biomedical_equivalent": r[5],
                "clinical_definition": r[6],
                "epistemological_boundary_warning": r[7],
                "is_approved_by_tabib": bool(r[8]),
                "tabib_reviewer_id": r[9],
                "reviewed_at": r[10]
            }
            for r in rows
        ]

    @staticmethod
    def upsert_glossary_term(conn, tenant_id: str, data: Dict[str, Any], actor_id: str, actor_role: str) -> Dict[str, Any]:
        canonical_code = data.get("canonical_code", "").strip().upper()
        classical = data.get("classical_arabic_urdu", "").strip()
        transliteration = data.get("roman_transliteration", "").strip()
        hindi = data.get("hindi_devanagari", "").strip()
        biomedical = data.get("english_biomedical_equivalent", "").strip()
        definition = data.get("clinical_definition", "").strip()
        warning = data.get("epistemological_boundary_warning", "")

        if not canonical_code or not classical or not transliteration or not biomedical:
            raise ValueError("canonical_code, classical_arabic_urdu, roman_transliteration, and english_biomedical_equivalent are required")

        is_tabib = 1 if actor_role in ("PRACTITIONER", "CLINICAL_SAFETY_OFFICER") else 0
        term_id = f"gloss-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.utcnow().isoformat() + "Z"

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO i18n_clinical_glossary
            (term_id, canonical_code, classical_arabic_urdu, roman_transliteration, hindi_devanagari, english_biomedical_equivalent, clinical_definition, epistemological_boundary_warning, is_approved_by_tabib, tabib_reviewer_id, reviewed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_code) DO UPDATE SET
                classical_arabic_urdu = excluded.classical_arabic_urdu,
                roman_transliteration = excluded.roman_transliteration,
                hindi_devanagari = excluded.hindi_devanagari,
                english_biomedical_equivalent = excluded.english_biomedical_equivalent,
                clinical_definition = excluded.clinical_definition,
                epistemological_boundary_warning = excluded.epistemological_boundary_warning,
                is_approved_by_tabib = excluded.is_approved_by_tabib,
                tabib_reviewer_id = excluded.tabib_reviewer_id,
                reviewed_at = excluded.reviewed_at
            """,
            (term_id, canonical_code, classical, transliteration, hindi, biomedical, definition, warning, is_tabib, actor_id if is_tabib else None, now_iso if is_tabib else None, now_iso)
        )

        AccessibilityLocalizationEngine._record_audit_event(
            conn, tenant_id, "GLOSSARY_TERM_UPSERTED", actor_id, actor_role,
            {"canonical_code": canonical_code, "is_tabib_approved": is_tabib}
        )

        return {"term_id": term_id, "canonical_code": canonical_code, "is_approved_by_tabib": bool(is_tabib)}

    # ---------------------------------------------------------
    # 4. Accessibility Preferences & Auditing
    # ---------------------------------------------------------

    @staticmethod
    def get_user_preferences(conn, user_id: str) -> Dict[str, Any]:
        cur = conn.cursor()
        cur.execute(
            "SELECT preferred_locale, font_size_scale, high_contrast_enabled, reduced_motion_enabled, screen_reader_optimized, keyboard_navigation_hints FROM user_a11y_preferences WHERE user_id = ?",
            (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return {
                "preferred_locale": "en",
                "font_size_scale": 1.0,
                "high_contrast_enabled": False,
                "reduced_motion_enabled": False,
                "screen_reader_optimized": False,
                "keyboard_navigation_hints": True
            }
        return {
            "preferred_locale": row[0],
            "font_size_scale": row[1],
            "high_contrast_enabled": bool(row[2]),
            "reduced_motion_enabled": bool(row[3]),
            "screen_reader_optimized": bool(row[4]),
            "keyboard_navigation_hints": bool(row[5])
        }

    @staticmethod
    def update_user_preferences(conn, tenant_id: str, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        preferred_locale = data.get("preferred_locale", "en").strip().lower()
        scale = float(data.get("font_size_scale", 1.0))
        high_contrast = int(bool(data.get("high_contrast_enabled", False)))
        reduced_motion = int(bool(data.get("reduced_motion_enabled", False)))
        sr_opt = int(bool(data.get("screen_reader_optimized", False)))
        kb_hints = int(bool(data.get("keyboard_navigation_hints", True)))

        pref_id = f"pref-{user_id}"
        now_iso = datetime.utcnow().isoformat() + "Z"

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_a11y_preferences
            (preference_id, user_id, tenant_id, preferred_locale, font_size_scale, high_contrast_enabled, reduced_motion_enabled, screen_reader_optimized, keyboard_navigation_hints, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferred_locale = excluded.preferred_locale,
                font_size_scale = excluded.font_size_scale,
                high_contrast_enabled = excluded.high_contrast_enabled,
                reduced_motion_enabled = excluded.reduced_motion_enabled,
                screen_reader_optimized = excluded.screen_reader_optimized,
                keyboard_navigation_hints = excluded.keyboard_navigation_hints,
                updated_at = excluded.updated_at
            """,
            (pref_id, user_id, tenant_id, preferred_locale, scale, high_contrast, reduced_motion, sr_opt, kb_hints, now_iso)
        )

        return {
            "user_id": user_id,
            "preferred_locale": preferred_locale,
            "font_size_scale": scale,
            "high_contrast_enabled": bool(high_contrast),
            "reduced_motion_enabled": bool(reduced_motion),
            "screen_reader_optimized": bool(sr_opt),
            "keyboard_navigation_hints": bool(kb_hints)
        }

    @staticmethod
    def record_a11y_audit(conn, tenant_id: str, data: Dict[str, Any], auditor_id: str, auditor_role: str) -> Dict[str, Any]:
        standard = data.get("standard", "WCAG_2_1_AA")
        target_route = data.get("target_route", "/consultation")
        viewport = data.get("viewport_profile", "DESKTOP_1440")
        contrast_pass = int(bool(data.get("color_contrast_pass", True)))
        keyboard_pass = int(bool(data.get("keyboard_operable_pass", True)))
        aria_pass = int(bool(data.get("aria_landmarks_pass", True)))
        labels_pass = int(bool(data.get("labels_and_errors_pass", True)))
        focus_pass = int(bool(data.get("focus_management_pass", True)))
        violations = json.dumps(data.get("violations", []))
        notes = data.get("remediation_notes", "")

        audit_id = f"a11y-aud-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.utcnow().isoformat() + "Z"

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO a11y_accessibility_audits
            (audit_id, tenant_id, standard, target_route, viewport_profile, color_contrast_pass, keyboard_operable_pass, aria_landmarks_pass, labels_and_errors_pass, focus_management_pass, violations_json, remediation_notes, auditor_actor_id, audit_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (audit_id, tenant_id, standard, target_route, viewport, contrast_pass, keyboard_pass, aria_pass, labels_pass, focus_pass, violations, notes, auditor_id, now_iso)
        )

        overall_pass = bool(contrast_pass and keyboard_pass and aria_pass and labels_pass and focus_pass)
        AccessibilityLocalizationEngine._record_audit_event(
            conn, tenant_id, "A11Y_AUDIT_RECORDED", auditor_id, auditor_role,
            {"audit_id": audit_id, "target_route": target_route, "overall_pass": overall_pass}
        )

        return {
            "audit_id": audit_id,
            "target_route": target_route,
            "standard": standard,
            "overall_pass": overall_pass,
            "audit_timestamp": now_iso
        }

    @staticmethod
    def list_a11y_audits(conn, tenant_id: str) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT audit_id, standard, target_route, viewport_profile, color_contrast_pass, keyboard_operable_pass,
                   aria_landmarks_pass, labels_and_errors_pass, focus_management_pass, violations_json, remediation_notes,
                   auditor_actor_id, audit_timestamp
            FROM a11y_accessibility_audits
            WHERE tenant_id = ?
            ORDER BY audit_timestamp DESC
            """,
            (tenant_id,)
        )
        rows = cur.fetchall()
        return [
            {
                "audit_id": r[0],
                "standard": r[1],
                "target_route": r[2],
                "viewport_profile": r[3],
                "color_contrast_pass": bool(r[4]),
                "keyboard_operable_pass": bool(r[5]),
                "aria_landmarks_pass": bool(r[6]),
                "labels_and_errors_pass": bool(r[7]),
                "focus_management_pass": bool(r[8]),
                "violations": json.loads(r[9]),
                "remediation_notes": r[10],
                "auditor_actor_id": r[11],
                "audit_timestamp": r[12]
            }
            for r in rows
        ]

    # ---------------------------------------------------------
    # 5. Clinical Human Factors Scenarios
    # ---------------------------------------------------------

    @staticmethod
    def record_human_factors_scenario(conn, tenant_id: str, data: Dict[str, Any], actor_id: str, actor_role: str) -> Dict[str, Any]:
        scenario_code = data.get("scenario_code", "HF-SC-01")
        workflow_name = data.get("workflow_name", "")
        target_role = data.get("target_role", "PRACTITIONER")
        locale_tested = data.get("locale_tested", "en")
        task_desc = data.get("task_description", "")
        completed = int(bool(data.get("task_completed", True)))
        time_seconds = float(data.get("time_to_complete_seconds", 120.0))
        errors = int(data.get("clinical_error_count", 0))
        alert_fatigue = float(data.get("alert_fatigue_score", 2.0))
        workload = float(data.get("cognitive_workload_score", 25.0))
        confusion = data.get("confusion_observations", "")
        notes = data.get("evaluator_notes", "")

        scenario_id = f"hf-sc-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.utcnow().isoformat() + "Z"

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO human_factors_validation_scenarios
            (scenario_id, tenant_id, scenario_code, workflow_name, target_role, locale_tested, task_description, task_completed, time_to_complete_seconds, clinical_error_count, alert_fatigue_score, cognitive_workload_score, confusion_observations, evaluator_notes, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (scenario_id, tenant_id, scenario_code, workflow_name, target_role, locale_tested, task_desc, completed, time_seconds, errors, alert_fatigue, workload, confusion, notes, now_iso)
        )

        AccessibilityLocalizationEngine._record_audit_event(
            conn, tenant_id, "HUMAN_FACTORS_SCENARIO_RECORDED", actor_id, actor_role,
            {"scenario_id": scenario_id, "scenario_code": scenario_code, "cognitive_workload": workload}
        )

        return {
            "scenario_id": scenario_id,
            "scenario_code": scenario_code,
            "task_completed": bool(completed),
            "cognitive_workload_score": workload,
            "evaluated_at": now_iso
        }

    @staticmethod
    def list_human_factors_scenarios(conn, tenant_id: str) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT scenario_id, scenario_code, workflow_name, target_role, locale_tested, task_description, task_completed,
                   time_to_complete_seconds, clinical_error_count, alert_fatigue_score, cognitive_workload_score,
                   confusion_observations, evaluator_notes, evaluated_at
            FROM human_factors_validation_scenarios
            WHERE tenant_id = ?
            ORDER BY evaluated_at DESC
            """,
            (tenant_id,)
        )
        rows = cur.fetchall()
        return [
            {
                "scenario_id": r[0],
                "scenario_code": r[1],
                "workflow_name": r[2],
                "target_role": r[3],
                "locale_tested": r[4],
                "task_description": r[5],
                "task_completed": bool(r[6]),
                "time_to_complete_seconds": r[7],
                "clinical_error_count": r[8],
                "alert_fatigue_score": r[9],
                "cognitive_workload_score": r[10],
                "confusion_observations": r[11],
                "evaluator_notes": r[12],
                "evaluated_at": r[13]
            }
            for r in rows
        ]

    # ---------------------------------------------------------
    # 6. Audit Ledger Verification
    # ---------------------------------------------------------

    @staticmethod
    def get_audit_ledger(conn, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT record_id, tenant_id, event_type, actor_id, actor_role, payload_json, timestamp, previous_hash, record_hash
            FROM a11y_human_factors_audit_ledger
            WHERE tenant_id = ?
            ORDER BY timestamp DESC, rowid DESC
            LIMIT ?
            """,
            (tenant_id, limit)
        )
        rows = cur.fetchall()
        return [
            {
                "record_id": r[0],
                "tenant_id": r[1],
                "event_type": r[2],
                "actor_id": r[3],
                "actor_role": r[4],
                "payload": json.loads(r[5]),
                "timestamp": r[6],
                "previous_hash": r[7],
                "record_hash": r[8]
            }
            for r in rows
        ]

    @staticmethod
    def verify_audit_ledger_integrity(conn, tenant_id: str) -> Dict[str, Any]:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT record_id, payload_json, previous_hash, record_hash
            FROM a11y_human_factors_audit_ledger
            WHERE tenant_id = ?
            ORDER BY timestamp ASC, rowid ASC
            """,
            (tenant_id,)
        )
        rows = cur.fetchall()
        if not rows:
            return {"verified": True, "records_checked": 0, "status": "EMPTY"}

        expected_prev = rows[0][3]
        for i, r in enumerate(rows):
            rec_id, payload_json, declared_prev, declared_hash = r
            if i == 0:
                continue
            if declared_prev != expected_prev:
                return {
                    "verified": False,
                    "records_checked": len(rows),
                    "tampered_record_id": rec_id,
                    "status": "PREVIOUS_HASH_MISMATCH"
                }
            computed_hash = AccessibilityLocalizationEngine._compute_hash(declared_prev, payload_json)
            if computed_hash != declared_hash:
                return {
                    "verified": False,
                    "records_checked": len(rows),
                    "tampered_record_id": rec_id,
                    "status": "HASH_MISMATCH"
                }
            expected_prev = declared_hash

        return {"verified": True, "records_checked": len(rows), "status": "VERIFIED"}
