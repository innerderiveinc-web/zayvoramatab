"""Encounters Domain: OPD Queue, Clinical Encounter Lifecycle, Vitals, and History."""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3
from matab.core.errors import NotFoundError, ValidationError
from matab.core.audit import record_audit_event

VALID_STATUSES = ["ARRIVED", "IN_CONSULTATION", "SIGNED", "COMPLETED", "CANCELLED"]

class EncounterService:
    @staticmethod
    def get_today_queue(conn: sqlite3.Connection, facility_id: str) -> List[Dict[str, Any]]:
        """Fetch today's active waiting queue and OPD tokens for a facility."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.id, e.token_number, e.encounter_type, e.status, e.created_at, e.started_at,
                   p.id as patient_id, p.mrn, p.first_name, p.last_name, p.dob, p.gender, p.phone, p.is_synthetic,
                   u.full_name as hakeem_name,
                   n.chief_complaint,
                   pr.id as prescription_id, pr.status as prescription_status
            FROM encounters e
            JOIN patients p ON e.patient_id = p.id
            LEFT JOIN practitioners prac ON e.practitioner_id = prac.id
            LEFT JOIN users u ON prac.user_id = u.id
            LEFT JOIN clinical_notes n ON n.encounter_id = e.id
            LEFT JOIN prescriptions pr ON pr.encounter_id = e.id
            WHERE e.facility_id = ? AND date(e.created_at) = date('now')
            ORDER BY e.token_number ASC;
        """, (facility_id,))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def create_encounter(conn: sqlite3.Connection, organization_id: str, facility_id: str,
                         patient_id: str, practitioner_id: Optional[str], encounter_type: str = "WALK_IN",
                         actor_id: Optional[str] = None) -> Dict[str, Any]:
        """Issue an OPD token and start a new encounter."""
        cursor = conn.cursor()
        # Calculate next token number for today
        cursor.execute("""
            SELECT COALESCE(MAX(token_number), 0) + 1 as next_token
            FROM encounters 
            WHERE facility_id = ? AND date(created_at) = date('now');
        """, (facility_id,))
        token_number = cursor.fetchone()["next_token"]
        
        encounter_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, token_number, encounter_type, status, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'ARRIVED', CURRENT_TIMESTAMP);
        """, (encounter_id, organization_id, facility_id, patient_id, practitioner_id, token_number, encounter_type))
        
        record_audit_event(
            conn=conn,
            organization_id=organization_id,
            facility_id=facility_id,
            actor_id=actor_id,
            action_type="ENCOUNTER_CREATED",
            resource_type="ENCOUNTER",
            resource_id=encounter_id,
            details={"token_number": token_number, "patient_id": patient_id}
        )
        
        return EncounterService.get_encounter(conn, organization_id, encounter_id)

    @staticmethod
    def get_encounter(conn: sqlite3.Connection, organization_id: str, encounter_id: str) -> Dict[str, Any]:
        """Fetch complete encounter record with associated vitals, notes, unani assessment, and prescription."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.id, e.organization_id, e.facility_id, e.patient_id, e.practitioner_id, 
                   e.token_number, e.encounter_type, e.status, e.started_at, e.ended_at, e.created_at,
                   p.mrn, p.first_name, p.last_name, p.dob, p.gender, p.phone, p.blood_group, p.is_synthetic,
                   u.full_name as practitioner_name
            FROM encounters e
            JOIN patients p ON e.patient_id = p.id
            LEFT JOIN practitioners prac ON e.practitioner_id = prac.id
            LEFT JOIN users u ON prac.user_id = u.id
            WHERE e.id = ? AND e.organization_id = ?;
        """, (encounter_id, organization_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Encounter '{encounter_id}' not found.")
            
        enc = dict(row)
        
        # Load Patient Allergies
        cursor.execute("SELECT id, allergen_type, allergen_name, severity, reaction_description FROM patient_allergies WHERE patient_id = ?;", (enc["patient_id"],))
        enc["allergies"] = [dict(a) for a in cursor.fetchall()]
        
        # Load Vitals
        cursor.execute("""
            SELECT id, systolic_bp, diastolic_bp, pulse_bpm, temperature_f, respiratory_rate, weight_kg, height_cm, spo2_percent, recorded_at
            FROM vitals 
            WHERE encounter_id = ? 
            ORDER BY recorded_at DESC LIMIT 1;
        """, (encounter_id,))
        v_row = cursor.fetchone()
        enc["vitals"] = dict(v_row) if v_row else None
        
        # Load Clinical Notes
        cursor.execute("""
            SELECT id, chief_complaint, history_of_present_illness, past_medical_history, general_physical_exam, systemic_exam, created_at
            FROM clinical_notes 
            WHERE encounter_id = ? 
            ORDER BY created_at DESC LIMIT 1;
        """, (encounter_id,))
        n_row = cursor.fetchone()
        enc["clinical_notes"] = dict(n_row) if n_row else None
        
        # Load Unani Assessment
        cursor.execute("""
            SELECT id, dominant_mizaj, mizaj_secondary, su_e_mizaj_type, nabz_quality, baul_observations, baraz_observations, 
                   afaal_summary, asbab_sittah_assessment, clinical_interpretation, assessment_status
            FROM unani_assessments 
            WHERE encounter_id = ? 
            ORDER BY created_at DESC LIMIT 1;
        """, (encounter_id,))
        ua_row = cursor.fetchone()
        enc["unani_assessment"] = dict(ua_row) if ua_row else None
        
        # Load Care Plan
        cursor.execute("""
            SELECT id, usul_e_ilaj_summary, modality_flags, dietary_guidelines_ghiza, regimen_tadbeer_instructions, created_at
            FROM care_plans 
            WHERE encounter_id = ? 
            ORDER BY created_at DESC LIMIT 1;
        """, (encounter_id,))
        cp_row = cursor.fetchone()
        enc["care_plan"] = dict(cp_row) if cp_row else None
        
        # Load Active Prescription
        cursor.execute("""
            SELECT id, version_number, status, overall_safety_state, signature_timestamp, signature_hash
            FROM prescriptions 
            WHERE encounter_id = ? 
            ORDER BY version_number DESC LIMIT 1;
        """, (encounter_id,))
        pr_row = cursor.fetchone()
        if pr_row:
            pr_dict = dict(pr_row)
            cursor.execute("""
                SELECT pi.id, pi.item_type, pi.formulation_id, pi.custom_name, pi.dosage_form, pi.dose_amount,
                       pi.dose_unit, pi.frequency, pi.duration_days, pi.instructions, pi.anupan_vehicle,
                       COALESCE(f.name, pi.custom_name) as item_name
                FROM prescription_items pi
                LEFT JOIN formulations f ON pi.formulation_id = f.id
                WHERE pi.prescription_id = ?;
            """, (pr_dict["id"],))
            pr_dict["items"] = [dict(it) for it in cursor.fetchall()]
            enc["prescription"] = pr_dict
        else:
            enc["prescription"] = None
            
        return enc

    @staticmethod
    def update_vitals(conn: sqlite3.Connection, encounter_id: str, vitals_data: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """Record or update vital signs for an encounter."""
        vital_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO vitals (id, encounter_id, systolic_bp, diastolic_bp, pulse_bpm, temperature_f, respiratory_rate, weight_kg, height_cm, spo2_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            vital_id,
            encounter_id,
            vitals_data.get("systolic_bp"),
            vitals_data.get("diastolic_bp"),
            vitals_data.get("pulse_bpm"),
            vitals_data.get("temperature_f"),
            vitals_data.get("respiratory_rate"),
            vitals_data.get("weight_kg"),
            vitals_data.get("height_cm"),
            vitals_data.get("spo2_percent")
        ))
        return {"id": vital_id, "encounter_id": encounter_id, **vitals_data}

    @staticmethod
    def update_clinical_notes(conn: sqlite3.Connection, encounter_id: str, notes_data: Dict[str, Any], author_id: str) -> Dict[str, Any]:
        """Record or update clinical notes for an encounter."""
        chief_complaint = notes_data.get("chief_complaint", "").strip()
        if not chief_complaint:
            raise ValidationError("Chief complaint is required.")
            
        note_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO clinical_notes (id, encounter_id, chief_complaint, history_of_present_illness, past_medical_history, general_physical_exam, systemic_exam, author_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            note_id,
            encounter_id,
            chief_complaint,
            notes_data.get("history_of_present_illness"),
            notes_data.get("past_medical_history"),
            notes_data.get("general_physical_exam"),
            notes_data.get("systemic_exam"),
            author_id
        ))
        return {"id": note_id, "encounter_id": encounter_id, **notes_data}

    @staticmethod
    def transition_status(conn: sqlite3.Connection, encounter_id: str, new_status: str, actor_id: str) -> None:
        """Update encounter lifecycle status."""
        if new_status not in VALID_STATUSES:
            raise ValidationError(f"Invalid encounter status '{new_status}'.")
            
        conn.execute("""
            UPDATE encounters 
            SET status = ?, 
                ended_at = CASE WHEN ? IN ('SIGNED', 'COMPLETED', 'CANCELLED') THEN CURRENT_TIMESTAMP ELSE ended_at END
            WHERE id = ?;
        """, (new_status, new_status, encounter_id))
