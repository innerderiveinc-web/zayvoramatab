"""Patients Domain: Master Patient Index (MPI), Duplicate Resolution, and Patient 360."""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3
from matab.core.errors import NotFoundError, ConflictError, ValidationError
from matab.core.audit import record_audit_event

class PatientService:
    @staticmethod
    def check_duplicates(conn: sqlite3.Connection, organization_id: str, phone: str, 
                         first_name: str, dob: Optional[str] = None) -> List[Dict[str, Any]]:
        """Evaluate prospective patient demographics against existing records."""
        cursor = conn.cursor()
        matches = []
        
        # 1. Exact phone match (high confidence)
        cursor.execute("""
            SELECT id, mrn, first_name, last_name, phone, dob, is_synthetic 
            FROM patients 
            WHERE organization_id = ? AND phone = ?;
        """, (organization_id, phone.strip()))
        for row in cursor.fetchall():
            matches.append({
                "patient": dict(row),
                "confidence": 0.95,
                "reasons": ["Exact phone number match"]
            })
            
        # 2. Similar name and DOB match
        if dob:
            cursor.execute("""
                SELECT id, mrn, first_name, last_name, phone, dob, is_synthetic 
                FROM patients 
                WHERE organization_id = ? AND dob = ? AND lower(first_name) = lower(?);
            """, (organization_id, dob, first_name.strip()))
            for row in cursor.fetchall():
                if not any(m["patient"]["id"] == row["id"] for m in matches):
                    matches.append({
                        "patient": dict(row),
                        "confidence": 0.85,
                        "reasons": ["Matching First Name and Date of Birth"]
                    })
                    
        return matches

    @staticmethod
    def create_patient(conn: sqlite3.Connection, organization_id: str, data: Dict[str, Any],
                       actor_id: str, force_duplicate_override: bool = False) -> Dict[str, Any]:
        """Register a new patient with duplicate heuristic validation."""
        phone = data.get("phone", "").strip()
        first_name = data.get("first_name", "").strip()
        dob = data.get("dob")
        
        if not phone or not first_name:
            raise ValidationError("Patient first name and phone number are required.")
            
        # Check duplicate matches unless explicitly overridden
        duplicates = PatientService.check_duplicates(conn, organization_id, phone, first_name, dob)
        if duplicates and not force_duplicate_override:
            raise ConflictError(
                "Possible duplicate patient detected. Please review or confirm override.",
                details={"matches": duplicates}
            )
            
        patient_id = str(uuid.uuid4())
        
        # Generate sequential MRN
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM patients WHERE organization_id = ?;", (organization_id,))
        count = cursor.fetchone()["total"] + 1
        mrn = f"MRN-{datetime.utcnow().year}-{count:04d}"
        
        conn.execute("""
            INSERT INTO patients (id, organization_id, mrn, first_name, last_name, dob, gender, phone, email, blood_group, primary_language, is_synthetic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            patient_id,
            organization_id,
            mrn,
            first_name,
            data.get("last_name", "").strip(),
            dob,
            data.get("gender", "OTHER"),
            phone,
            data.get("email"),
            data.get("blood_group"),
            data.get("primary_language", "UR"),
            1 if data.get("is_synthetic") else 0
        ))
        
        # Optional initial allergies
        if "allergies" in data and isinstance(data["allergies"], list):
            for allg in data["allergies"]:
                conn.execute("""
                    INSERT INTO patient_allergies (id, patient_id, allergen_type, allergen_name, severity, reaction_description)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()),
                    patient_id,
                    allg.get("allergen_type", "HERBAL"),
                    allg.get("allergen_name"),
                    allg.get("severity", "MODERATE"),
                    allg.get("reaction_description")
                ))
                
        record_audit_event(
            conn=conn,
            organization_id=organization_id,
            actor_id=actor_id,
            action_type="PATIENT_CREATED",
            resource_type="PATIENT",
            resource_id=patient_id,
            details={"mrn": mrn, "first_name": first_name}
        )
        
        return PatientService.get_patient_by_id(conn, organization_id, patient_id)

    @staticmethod
    def get_patient_by_id(conn: sqlite3.Connection, organization_id: str, patient_id: str) -> Dict[str, Any]:
        """Fetch patient demographic record."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, organization_id, mrn, first_name, last_name, dob, gender, phone, email, 
                   blood_group, primary_language, is_synthetic, created_at
            FROM patients 
            WHERE organization_id = ? AND id = ?;
        """, (organization_id, patient_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Patient '{patient_id}' not found.")
            
        patient = dict(row)
        
        # Load allergies
        cursor.execute("""
            SELECT id, allergen_type, allergen_name, severity, reaction_description, recorded_at 
            FROM patient_allergies 
            WHERE patient_id = ?;
        """, (patient_id,))
        patient["allergies"] = [dict(a) for a in cursor.fetchall()]
        
        return patient

    @staticmethod
    def search_patients(conn: sqlite3.Connection, organization_id: str, query: str = "") -> List[Dict[str, Any]]:
        """Search patients by name, MRN, or phone number."""
        cursor = conn.cursor()
        q = f"%{query.strip().lower()}%"
        cursor.execute("""
            SELECT p.id, p.mrn, p.first_name, p.last_name, p.dob, p.gender, p.phone, p.email, p.blood_group, p.is_synthetic,
                   (SELECT COUNT(*) FROM encounters WHERE patient_id = p.id) as visit_count
            FROM patients p
            WHERE p.organization_id = ? 
              AND (lower(p.first_name) LIKE ? OR lower(p.last_name) LIKE ? OR lower(p.phone) LIKE ? OR lower(p.mrn) LIKE ?)
            ORDER BY p.created_at DESC
            LIMIT 50;
        """, (organization_id, q, q, q, q))
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_patient_360(conn: sqlite3.Connection, organization_id: str, patient_id: str) -> Dict[str, Any]:
        """Longitudinal Patient 360: demographics, visit history, vitals trend, past prescriptions, and assessments."""
        patient = PatientService.get_patient_by_id(conn, organization_id, patient_id)
        cursor = conn.cursor()
        
        # Encounters history
        cursor.execute("""
            SELECT e.id, e.token_number, e.encounter_type, e.status, e.created_at,
                   u.full_name as hakeem_name,
                   n.chief_complaint,
                   v.systolic_bp, v.diastolic_bp, v.pulse_bpm, v.weight_kg
            FROM encounters e
            LEFT JOIN practitioners p ON e.practitioner_id = p.id
            LEFT JOIN users u ON p.user_id = u.id
            LEFT JOIN clinical_notes n ON n.encounter_id = e.id
            LEFT JOIN vitals v ON v.encounter_id = e.id
            WHERE e.patient_id = ? AND e.organization_id = ?
            ORDER BY e.created_at DESC;
        """, (patient_id, organization_id))
        patient["encounters"] = [dict(r) for r in cursor.fetchall()]
        
        # Prescriptions history
        cursor.execute("""
            SELECT pr.id, pr.encounter_id, pr.version_number, pr.status, pr.overall_safety_state,
                   pr.signature_timestamp, pr.signature_hash, pr.created_at,
                   u.full_name as hakeem_name
            FROM prescriptions pr
            LEFT JOIN practitioners p ON pr.hakeem_id = p.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE pr.patient_id = ?
            ORDER BY pr.created_at DESC;
        """, (patient_id,))
        prescriptions = []
        for pr_row in cursor.fetchall():
            pr_dict = dict(pr_row)
            cursor.execute("""
                SELECT pi.id, pi.item_type, pi.dosage_form, pi.dose_amount, pi.dose_unit, 
                       pi.frequency, pi.duration_days, pi.instructions, pi.anupan_vehicle,
                       COALESCE(f.name, pi.custom_name) as item_name
                FROM prescription_items pi
                LEFT JOIN formulations f ON pi.formulation_id = f.id
                WHERE pi.prescription_id = ?;
            """, (pr_dict["id"],))
            pr_dict["items"] = [dict(it) for it in cursor.fetchall()]
            prescriptions.append(pr_dict)
        patient["prescriptions"] = prescriptions
        
        # Historical Unani assessments
        cursor.execute("""
            SELECT ua.id, ua.dominant_mizaj, ua.mizaj_secondary, ua.nabz_quality, ua.clinical_interpretation, ua.created_at
            FROM unani_assessments ua
            WHERE ua.patient_id = ?
            ORDER BY ua.created_at DESC;
        """, (patient_id,))
        patient["unani_assessments"] = [dict(a) for a in cursor.fetchall()]
        
        return patient
