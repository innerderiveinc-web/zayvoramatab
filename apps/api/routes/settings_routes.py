"""Matab OS System Settings and Clinic Preferences Route."""

import json
import sqlite3
from typing import Dict, Any, Tuple
from pathlib import Path
from apps.api.core.errors import AuthenticationError, ForbiddenError, ValidationError

SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "matab_settings.json"

DEFAULT_SETTINGS = {
    "clinic_name": "[Synthetic Facility Placeholder - Setup Required]",
    "clinic_tagline": "Unani Clinical Information & Bedside Decision Support System",
    "head_practitioner": "[Unverified Practitioner Placeholder]",
    "registration_no": "[AYUSH-REG-PENDING-VERIFICATION]",
    "phone": "+91 00000 00000",
    "email": "clinic-admin@example.local",
    "address": "Clinical Practice Location - Pending Administrator Configuration",
    "is_identity_verified": False,
    "consultation_fee": 300,
    "default_followup_days": 7,
    "default_print_format": "a4",
    "thermal_slip_width": "80mm",
    "header_mode": "full",
    "prescription_disclaimer": "Valid for clinical guidance. Please report any adverse symptoms immediately. Follow-up consultation recommended within 7 days.",
    "require_clinician_pin": True,
    "auto_deduct_inventory": True,
    "low_stock_threshold": 10,
    "enable_abdm_qr": True,
    "mizaj_required": False,
    "default_language": "en",
    "operating_hours": "09:30 AM – 08:30 PM (Mon – Sat)"
}


def load_settings() -> Dict[str, Any]:
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_SETTINGS, **data}
    except Exception:
        pass
    return dict(DEFAULT_SETTINGS)


def save_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**load_settings(), **data}
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return merged


def handle_settings_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    if not req.get("user"):
        raise AuthenticationError("Authentication required to view system settings.")
    settings = load_settings()
    return 200, {"ok": True, "settings": settings, "request_id": req.get("request_id")}


def handle_settings_save(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    if not user:
        raise AuthenticationError("Authentication required to update system settings.")
    
    roles = set(user.get("roles") or ([user.get("role")] if user.get("role") else []))
    perms = set(user.get("permissions") or [])
    is_admin = bool(roles.intersection({"ADMIN", "SUPER_ADMIN", "ORG_ADMIN", "DIRECTOR"}) or "settings:write" in perms)
    if not is_admin:
        raise ForbiddenError("Only Clinic Administrators or Medical Directors may modify institutional settings.")

    body = req.get("body", {})
    if not isinstance(body, dict):
        raise ValidationError("Request body must be a valid JSON object.")

    # Sanitize and validate fields
    sanitized: Dict[str, Any] = {}
    for k, v in body.items():
        if k in DEFAULT_SETTINGS:
            if k == "consultation_fee":
                try:
                    val = float(v)
                    if val < 0:
                        raise ValueError()
                    sanitized[k] = val
                except (ValueError, TypeError):
                    raise ValidationError("consultation_fee must be a non-negative number.")
            elif k == "default_followup_days":
                try:
                    val = int(v)
                    if val < 1 or val > 365:
                        raise ValueError()
                    sanitized[k] = val
                except (ValueError, TypeError):
                    raise ValidationError("default_followup_days must be an integer between 1 and 365.")
            elif isinstance(DEFAULT_SETTINGS[k], bool):
                sanitized[k] = bool(v)
            else:
                sanitized[k] = str(v).strip()

    saved = save_settings(sanitized)
    return 200, {"ok": True, "status": "SAVED", "settings": saved, "request_id": req.get("request_id")}
