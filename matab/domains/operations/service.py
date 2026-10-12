"""Operations Domain: Care Planning (Usul-e-Ilaj), Follow-up Task Tracking, and FEFO Inventory."""

import uuid
from typing import Dict, Any, List, Optional
import sqlite3
from matab.core.errors import ValidationError

class OperationsService:
    @staticmethod
    def save_care_plan(conn: sqlite3.Connection, encounter_id: str, patient_id: str, 
                       plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save patient care plan including Usul-e-Ilaj, Ghiza (diet), and Tadbeer (regimen)."""
        summary = plan_data.get("usul_e_ilaj_summary", "").strip()
        if not summary:
            raise ValidationError("Usul-e-Ilaj therapeutic summary is required.")
            
        plan_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO care_plans (id, encounter_id, patient_id, usul_e_ilaj_summary, modality_flags, dietary_guidelines_ghiza, regimen_tadbeer_instructions)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            plan_id,
            encounter_id,
            patient_id,
            summary,
            plan_data.get("modality_flags", "ILAJ_BIL_DAWA"),
            plan_data.get("dietary_guidelines_ghiza"),
            plan_data.get("regimen_tadbeer_instructions")
        ))
        return {"id": plan_id, "encounter_id": encounter_id, **plan_data}

    @staticmethod
    def schedule_follow_up(conn: sqlite3.Connection, encounter_id: str, patient_id: str,
                           due_date: str, objective: str) -> Dict[str, Any]:
        """Schedule a structured clinical follow-up task."""
        task_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO follow_up_tasks (id, encounter_id, patient_id, due_date, target_objective, status)
            VALUES (?, ?, ?, ?, ?, 'SCHEDULED');
        """, (task_id, encounter_id, patient_id, due_date, objective))
        return {"id": task_id, "due_date": due_date, "objective": objective, "status": "SCHEDULED"}

    @staticmethod
    def get_due_follow_ups(conn: sqlite3.Connection, facility_id: str) -> List[Dict[str, Any]]:
        """List due or pending follow-up review tasks."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ft.id, ft.due_date, ft.target_objective, ft.status, ft.created_at,
                   p.id as patient_id, p.mrn, p.first_name, p.last_name, p.phone, p.is_synthetic
            FROM follow_up_tasks ft
            JOIN patients p ON ft.patient_id = p.id
            JOIN encounters e ON ft.encounter_id = e.id
            WHERE e.facility_id = ?
            ORDER BY ft.due_date ASC;
        """, (facility_id,))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def get_inventory_batches(conn: sqlite3.Connection, facility_id: str) -> List[Dict[str, Any]]:
        """Retrieve inventory batches ordered by First-Expired-First-Out (FEFO)."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ib.id, ib.batch_number, ib.mfg_date, ib.expiry_date, ib.quantity_remaining, ib.unit,
                   ib.is_mudabbar_certified,
                   COALESCE(f.name, i.canonical_name) as item_name,
                   CASE WHEN f.id IS NOT NULL THEN 'COMPOUND' ELSE 'SINGLE_HERB' END as item_category
            FROM inventory_batches ib
            LEFT JOIN formulations f ON ib.formulation_id = f.id
            LEFT JOIN ingredients i ON ib.ingredient_id = i.id
            WHERE ib.facility_id = ?
            ORDER BY ib.expiry_date ASC;
        """, (facility_id,))
        return [dict(r) for r in cursor.fetchall()]
