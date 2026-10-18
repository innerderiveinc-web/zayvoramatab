"""Matab OS System Settings and Clinic Preferences Route."""

import json
import sqlite3
from typing import Dict, Any, Tuple
from pathlib import Path

SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "matab_settings.json"

DEFAULT_SETTINGS = {
    "clinic_name": "ZAYVORA Matab & Hospital",
    "clinic_tagline": "Center for Classical Unani Medicine & Bedside Decision Support",
    "head_practitioner": "Hakim Tariq Mahmud (Senior Consulting Tabib)",
    "registration_no": "AYUSH-UNANI-98241",
    "phone": "+91 98765 43210",
    "email": "matab@zayvora.com",
    "address": "42 Shifa Marg, Civil Lines, New Delhi, India",
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
    settings = load_settings()
    return 200, {"ok": True, "settings": settings, "request_id": req.get("request_id")}


def handle_settings_save(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    body = req.get("body", {})
    saved = save_settings(body)
    return 200, {"ok": True, "status": "SAVED", "settings": saved, "request_id": req.get("request_id")}
