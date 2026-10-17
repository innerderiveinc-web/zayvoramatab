"""ZAYVORA MATAB OS — Patient-Reported Outcome Measures (PROMs) & Adherence Service.

Tracks longitudinal patient recovery, VAS symptom scores, quality of life, and treatment adherence.
"""

import sqlite3
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

class OutcomesPromService:
    """Core domain service for PROMs and Medication Adherence."""

    @classmethod
    def record_prom_response(cls, conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        cur = conn.cursor()
        prom_id = f"PROM-{uuid.uuid4().hex[:8].upper()}"
        patient_id = data.get("patient_id")
        encounter_id = data.get("encounter_id", "ENC-WALK-IN")
        instrument_id = data.get("instrument_id", "UNANI-QOL-VAS")
        raw_json = json.dumps(data.get("responses", {}))
        score = float(data.get("score", 75.0))
        baseline = float(data.get("baseline_score", 50.0))
        delta = score - baseline
        mode = data.get("collection_mode", "CLINIC_TABLET")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            INSERT INTO patient_prom_responses 
            (id, patient_id, encounter_id, instrument_id, instrument_version, language, raw_responses_json, calculated_score, baseline_score, mcid_delta, collection_mode, collected_at)
            VALUES (?, ?, ?, ?, 'v2.1', 'en', ?, ?, ?, ?, ?, ?)
        """, (prom_id, patient_id, encounter_id, instrument_id, raw_json, score, baseline, delta, mode, now_str))
        conn.commit()

        return {
            "id": prom_id,
            "patient_id": patient_id,
            "score": score,
            "delta": delta,
            "collected_at": now_str
        }

    @classmethod
    def get_patient_proms(cls, conn: sqlite3.Connection, patient_id: str) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, encounter_id, instrument_id, calculated_score, baseline_score, mcid_delta, collected_at
            FROM patient_prom_responses
            WHERE patient_id = ?
            ORDER BY collected_at DESC
        """, (patient_id,))
        cols = ["id", "encounter_id", "instrument", "score", "baseline", "delta", "collected_at"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    @classmethod
    def record_adherence(cls, conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
        cur = conn.cursor()
        adh_id = f"ADH-{uuid.uuid4().hex[:8].upper()}"
        patient_id = data.get("patient_id")
        rx_id = data.get("prescription_id", "RX-CURRENT")
        day_offset = int(data.get("day_offset", 1))
        status = data.get("status", "TAKEN")
        notes = data.get("notes", "")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            INSERT INTO patient_adherence_records
            (id, patient_id, prescription_id, day_offset, dose_scheduled_at, dose_taken_at, status, patient_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (adh_id, patient_id, rx_id, day_offset, now_str, now_str if status == "TAKEN" else None, status, notes))
        conn.commit()

        return {"id": adh_id, "patient_id": patient_id, "status": status, "recorded_at": now_str}

    @classmethod
    def get_patient_adherence(cls, conn: sqlite3.Connection, patient_id: str) -> List[Dict[str, Any]]:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, prescription_id, day_offset, dose_taken_at, status, patient_notes
            FROM patient_adherence_records
            WHERE patient_id = ?
            ORDER BY day_offset DESC
        """, (patient_id,))
        cols = ["id", "prescription_id", "day", "taken_at", "status", "notes"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
