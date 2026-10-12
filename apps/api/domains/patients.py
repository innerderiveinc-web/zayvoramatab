"""Patient Domain Service: Master Patient Index (MPI), Duplicate Resolution, Demographics, Identifiers, and Consents."""

import uuid
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import sqlite3
from apps.api.core.errors import NotFoundError, ConflictError, ValidationError, ForbiddenError
from apps.api.core.audit import log_audit_event

def normalize_phone(phone: str) -> str:
    """Normalize phone number by removing punctuation, spaces, and country code prefixes."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone.strip())
    # If 12 digits starting with 91 (India mobile 6-9), extract 10-digit national number
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return digits[2:]
    # If 11 digits starting with 0 followed by mobile digit 6-9, extract 10-digit national number
    if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return digits[1:]
    return digits

def normalize_string(val: Optional[str]) -> str:
    """Normalize string for search: lowercase, collapse whitespace, strip accents/symbols."""
    if not val:
        return ""
    return re.sub(r"\s+", " ", val.strip()).lower()

class PatientService:
    @staticmethod
    def generate_mrn(conn: sqlite3.Connection, organization_id: str) -> str:
        """Generate a sequential, tenant-scoped Medical Record Number (MRN)."""
        year = datetime.utcnow().strftime("%Y")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT count(*) as total
            FROM patients
            WHERE organization_id = ?;
        """, (organization_id,))
        count = cursor.fetchone()["total"] + 1
        return f"MRN-{year}-{count:05d}"

    @staticmethod
    def check_duplicates(conn: sqlite3.Connection, organization_id: str, 
                         phone: Optional[str] = None, 
                         given_name: Optional[str] = None,
                         family_name: Optional[str] = None,
                         date_of_birth: Optional[str] = None,
                         national_id: Optional[str] = None,
                         exclude_patient_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Deterministic duplicate candidate detection using explainable clinical matching rules.
        Does NOT perform automatic merge. Returns candidate matches with rules and confidence scores.
        """
        cursor = conn.cursor()
        candidates: List[Dict[str, Any]] = []
        candidate_ids = set()

        norm_phone = normalize_phone(phone) if phone else ""
        norm_given = normalize_string(given_name) if given_name else ""
        norm_national_id = normalize_string(national_id) if national_id else ""

        # Signal 1: Exact Phone Number Match (high confidence score 0.90)
        if norm_phone:
            query = """
                SELECT p.id, p.mrn, p.display_name, p.given_name, p.family_name, p.date_of_birth, p.sex, c.contact_value as phone
                FROM patients p
                JOIN patient_contacts c ON p.id = c.patient_id
                WHERE p.organization_id = ? AND c.contact_type IN ('PHONE', 'WHATSAPP') AND c.normalized_value = ?
            """
            params = [organization_id, norm_phone]
            if exclude_patient_id:
                query += " AND p.id != ?"
                params.append(exclude_patient_id)

            cursor.execute(query, params)
            for row in cursor.fetchall():
                pid = row["id"]
                if pid not in candidate_ids:
                    candidate_ids.add(pid)
                    candidates.append({
                        "candidate_patient": dict(row),
                        "match_score": 0.90,
                        "rules": ["EXACT_PHONE_MATCH"],
                        "explanation": f"Exact phone match ({row['phone']})"
                    })

        # Signal 2: Exact National / ABHA Identifier Match (high confidence score 0.98)
        if norm_national_id:
            query = """
                SELECT p.id, p.mrn, p.display_name, p.given_name, p.family_name, p.date_of_birth, p.sex
                FROM patients p
                JOIN patient_identifiers i ON p.id = i.patient_id
                WHERE p.organization_id = ? AND i.is_retired = 0 AND i.normalized_value = ?
            """
            params = [organization_id, norm_national_id]
            if exclude_patient_id:
                query += " AND p.id != ?"
                params.append(exclude_patient_id)

            cursor.execute(query, params)
            for row in cursor.fetchall():
                pid = row["id"]
                if pid not in candidate_ids:
                    candidate_ids.add(pid)
                    candidates.append({
                        "candidate_patient": dict(row),
                        "match_score": 0.98,
                        "rules": ["EXACT_IDENTIFIER_MATCH"],
                        "explanation": f"Exact identifier match ({national_id})"
                    })
                else:
                    # Append rule to existing candidate
                    for cand in candidates:
                        if cand["candidate_patient"]["id"] == pid:
                            cand["rules"].append("EXACT_IDENTIFIER_MATCH")
                            cand["match_score"] = max(cand["match_score"], 0.98)

        # Signal 3: Matching Given Name + Exact Date of Birth (moderate confidence score 0.85)
        if norm_given and date_of_birth:
            query = """
                SELECT p.id, p.mrn, p.display_name, p.given_name, p.family_name, p.date_of_birth, p.sex
                FROM patients p
                WHERE p.organization_id = ? AND p.date_of_birth = ? AND lower(p.given_name) = ?
            """
            params = [organization_id, date_of_birth, norm_given]
            if exclude_patient_id:
                query += " AND p.id != ?"
                params.append(exclude_patient_id)

            cursor.execute(query, params)
            for row in cursor.fetchall():
                pid = row["id"]
                if pid not in candidate_ids:
                    candidate_ids.add(pid)
                    candidates.append({
                        "candidate_patient": dict(row),
                        "match_score": 0.85,
                        "rules": ["SIMILAR_NAME_SAME_DOB"],
                        "explanation": f"Matching name '{given_name}' and date of birth '{date_of_birth}'"
                    })
                else:
                    for cand in candidates:
                        if cand["candidate_patient"]["id"] == pid:
                            if "SIMILAR_NAME_SAME_DOB" not in cand["rules"]:
                                cand["rules"].append("SIMILAR_NAME_SAME_DOB")
                            cand["match_score"] = min(cand["match_score"] + 0.05, 0.99)

        return candidates

    @staticmethod
    def create_patient(conn: sqlite3.Connection, organization_id: str, facility_id: Optional[str],
                       data: Dict[str, Any], actor_id: str, request_id: Optional[str] = None,
                       client_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new patient with validation, duplicate detection, contacts, and audit.
        If duplicates exist and override_decision is absent, raises ConflictError with candidate details.
        """
        given_name = data.get("given_name", "").strip()
        family_name = data.get("family_name", "").strip() if data.get("family_name") else None
        display_name = data.get("display_name", "").strip()
        if not display_name:
            display_name = f"{given_name} {family_name}".strip() if family_name else given_name

        phone = data.get("phone", "").strip() if data.get("phone") else None
        dob = data.get("date_of_birth", "").strip() if data.get("date_of_birth") else None
        estimated_age = data.get("estimated_age")
        sex = data.get("sex", "UNKNOWN").upper()
        preferred_lang = data.get("preferred_language", "ur")
        national_id = data.get("national_id", "").strip() if data.get("national_id") else None
        override_decision = data.get("override_decision") or data.get("duplicate_override_decision") # 'CONFIRMED_DIFFERENT', 'DEFERRED_FOR_REVIEW'

        # Validation
        if not given_name:
            raise ValidationError("Patient given name is required.", request_id=request_id)
        if sex not in ["MALE", "FEMALE", "OTHER", "UNKNOWN"]:
            raise ValidationError("Invalid sex. Must be MALE, FEMALE, OTHER, or UNKNOWN.", request_id=request_id)
        if dob:
            try:
                datetime.strptime(dob, "%Y-%m-%d")
            except ValueError:
                raise ValidationError("Invalid date_of_birth format. Expected YYYY-MM-DD.", request_id=request_id)
        if estimated_age is not None:
            try:
                estimated_age = int(estimated_age)
                if estimated_age < 0 or estimated_age > 130:
                    raise ValueError()
            except ValueError:
                raise ValidationError("Estimated age must be an integer between 0 and 130.", request_id=request_id)

        # Duplicate Candidate Check
        candidates = PatientService.check_duplicates(
            conn=conn,
            organization_id=organization_id,
            phone=phone,
            given_name=given_name,
            family_name=family_name,
            date_of_birth=dob,
            national_id=national_id
        )

        if candidates and override_decision not in ["CONFIRMED_DIFFERENT", "DEFERRED_FOR_REVIEW"]:
            raise ConflictError(
                "Potential duplicate patient detected. Human operator decision required.",
                details={"duplicate_candidates": candidates},
                request_id=request_id
            )

        # Create Patient Record
        patient_id = str(uuid.uuid4())
        mrn = PatientService.generate_mrn(conn, organization_id)
        age_recorded_at = datetime.utcnow().isoformat() if estimated_age is not None else None

        conn.execute("""
            INSERT INTO patients (
                id, organization_id, facility_id, mrn, given_name, family_name, display_name,
                date_of_birth, estimated_age, age_recorded_at, sex, preferred_language, status,
                version, created_by, updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 1, ?, ?);
        """, (
            patient_id, organization_id, facility_id, mrn, given_name, family_name, display_name,
            dob, estimated_age, age_recorded_at, sex, preferred_lang, actor_id, actor_id
        ))

        # Add Contact (Phone)
        if phone:
            norm_phone = normalize_phone(phone)
            contact_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO patient_contacts (id, patient_id, organization_id, contact_type, contact_value, normalized_value, is_preferred, use)
                VALUES (?, ?, ?, 'PHONE', ?, ?, 1, 'MOBILE');
            """, (contact_id, patient_id, organization_id, phone, norm_phone))

        # Add Contact (Email if provided)
        email = data.get("email", "").strip() if data.get("email") else None
        if email:
            conn.execute("""
                INSERT INTO patient_contacts (id, patient_id, organization_id, contact_type, contact_value, normalized_value, is_preferred, use)
                VALUES (?, ?, ?, 'EMAIL', ?, ?, 0, 'HOME');
            """, (str(uuid.uuid4()), patient_id, organization_id, email, email.lower()))

        # Add National Identifier if provided
        if national_id:
            conn.execute("""
                INSERT INTO patient_identifiers (id, patient_id, organization_id, identifier_type, identifier_value, normalized_value, issuer)
                VALUES (?, ?, ?, 'NATIONAL_ID', ?, ?, ?);
            """, (str(uuid.uuid4()), patient_id, organization_id, national_id, normalize_string(national_id), data.get("id_issuer", "GOVT")))

        # Add Primary Address if provided
        address_line1 = data.get("address_line1", "").strip() if data.get("address_line1") else None
        city = data.get("city", "").strip() if data.get("city") else None
        if address_line1 or city:
            conn.execute("""
                INSERT INTO patient_addresses (id, patient_id, organization_id, address_line1, city, state, postal_code, country, is_primary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1);
            """, (str(uuid.uuid4()), patient_id, organization_id, address_line1, city, data.get("state"), data.get("postal_code"), data.get("country", "IN")))

        # Record Initial Explicit Consent if provided
        consent_status = data.get("consent_general_care", "GRANTED") # Defaults to GRANTED when patient requests care
        conn.execute("""
            INSERT INTO patient_consents (id, patient_id, organization_id, purpose, status, source_method, recorded_by)
            VALUES (?, ?, ?, 'GENERAL_CARE', ?, 'VERBAL_PATIENT', ?);
        """, (str(uuid.uuid4()), patient_id, organization_id, consent_status, actor_id))

        # If duplicate candidates were flagged and human confirmed override, log the candidate resolution pair
        if candidates and override_decision:
            for cand in candidates:
                cand_id = str(uuid.uuid4())
                cand_patient_id = cand["candidate_patient"]["id"]
                conn.execute("""
                    INSERT OR IGNORE INTO patient_duplicate_candidates (
                        id, organization_id, patient_id_a, patient_id_b, match_score, match_rules,
                        status, reviewed_by, reviewed_at, review_notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """, (
                    cand_id, organization_id, patient_id, cand_patient_id, cand["match_score"],
                    ",".join(cand["rules"]), override_decision, actor_id,
                    data.get("override_notes", "Operator confirmed distinct patient at registration")
                ))

        # Audit Event
        log_audit_event(
            conn=conn,
            action_type="PATIENT_CREATED",
            target_entity_type="PATIENT",
            target_entity_id=patient_id,
            organization_id=organization_id,
            facility_id=facility_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"mrn": mrn, "display_name": display_name, "duplicate_override": bool(override_decision)}
        )

        return PatientService.get_patient_by_id(conn, organization_id, patient_id)

    @staticmethod
    def get_patient_by_id(conn: sqlite3.Connection, organization_id: str, patient_id: str) -> Dict[str, Any]:
        """Fetch patient base record strictly scoped to organization."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, organization_id, facility_id, mrn, given_name, family_name, display_name,
                   date_of_birth, estimated_age, age_recorded_at, sex, preferred_language, status,
                   version, created_by, updated_by, created_at, updated_at
            FROM patients
            WHERE id = ? AND organization_id = ?;
        """, (patient_id, organization_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Patient '{patient_id}' not found.")
        return dict(row)

    @staticmethod
    def search_patients(conn: sqlite3.Connection, organization_id: str,
                        q: Optional[str] = None, phone: Optional[str] = None,
                        mrn: Optional[str] = None, limit: int = 20, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """Scoped, paginated search by name, MRN, or phone number."""
        cursor = conn.cursor()
        conditions = ["p.organization_id = ?"]
        params: List[Any] = [organization_id]

        if mrn:
            conditions.append("p.mrn LIKE ?")
            params.append(f"%{mrn.strip()}%")

        if phone:
            norm_phone = normalize_phone(phone)
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM patient_contacts c 
                    WHERE c.patient_id = p.id AND c.normalized_value LIKE ?
                )
            """)
            params.append(f"%{norm_phone}%")

        if q:
            clean_q = q.strip()
            norm_q_digits = normalize_phone(clean_q)
            if norm_q_digits:
                # Match name, MRN, raw contact, or normalized phone
                conditions.append("""
                    (
                        p.display_name LIKE ? OR 
                        p.mrn LIKE ? OR 
                        EXISTS (
                            SELECT 1 FROM patient_contacts c 
                            WHERE c.patient_id = p.id AND (c.contact_value LIKE ? OR c.normalized_value LIKE ?)
                        )
                    )
                """)
                params.extend([f"%{clean_q}%", f"%{clean_q}%", f"%{clean_q}%", f"%{norm_q_digits}%"])
            else:
                # Text-only query: match display name, MRN, or raw contact value
                conditions.append("""
                    (
                        p.display_name LIKE ? OR 
                        p.mrn LIKE ? OR 
                        EXISTS (
                            SELECT 1 FROM patient_contacts c 
                            WHERE c.patient_id = p.id AND c.contact_value LIKE ?
                        )
                    )
                """)
                params.extend([f"%{clean_q}%", f"%{clean_q}%", f"%{clean_q}%"])

        where_clause = " AND ".join(conditions)

        # Count total matches
        cursor.execute(f"SELECT count(*) as total FROM patients p WHERE {where_clause};", params)
        total = cursor.fetchone()["total"]

        # Fetch page with primary contact
        query = f"""
            SELECT p.id, p.organization_id, p.facility_id, p.mrn, p.given_name, p.family_name, p.display_name,
                   p.date_of_birth, p.estimated_age, p.sex, p.preferred_language, p.status, p.created_at,
                   (
                       SELECT c.contact_value FROM patient_contacts c
                       WHERE c.patient_id = p.id AND c.is_preferred = 1
                       LIMIT 1
                   ) as primary_phone
            FROM patients p
            WHERE {where_clause}
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?;
        """
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

        return rows, total

    @staticmethod
    def get_patient_360(conn: sqlite3.Connection, organization_id: str, patient_id: str,
                        actor_id: str, request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Fetch comprehensive Patient 360 overview: demographics, identifiers, contacts, address, consents."""
        patient = PatientService.get_patient_by_id(conn, organization_id, patient_id)
        cursor = conn.cursor()

        # Contacts
        cursor.execute("""
            SELECT id, contact_type, contact_value, is_preferred, is_verified, use
            FROM patient_contacts
            WHERE patient_id = ?
            ORDER BY is_preferred DESC, created_at ASC;
        """, (patient_id,))
        contacts = [dict(r) for r in cursor.fetchall()]

        # Identifiers
        cursor.execute("""
            SELECT id, identifier_type, identifier_value, issuer, is_verified, is_retired, retired_reason, retired_at
            FROM patient_identifiers
            WHERE patient_id = ?
            ORDER BY is_retired ASC, created_at ASC;
        """, (patient_id,))
        identifiers = [dict(r) for r in cursor.fetchall()]

        # Addresses
        cursor.execute("""
            SELECT id, address_line1, address_line2, city, state, postal_code, country, is_primary
            FROM patient_addresses
            WHERE patient_id = ?
            ORDER BY is_primary DESC;
        """, (patient_id,))
        addresses = [dict(r) for r in cursor.fetchall()]

        # Consents
        cursor.execute("""
            SELECT id, purpose, status, policy_version, source_method, recorded_at, withdrawn_at, withdrawal_reason
            FROM patient_consents
            WHERE patient_id = ?
            ORDER BY recorded_at DESC;
        """, (patient_id,))
        consents = [dict(r) for r in cursor.fetchall()]

        # Recent Encounters (summary count and latest 5)
        cursor.execute("""
            SELECT id, facility_id, encounter_type, status, reason_for_visit, started_at, ended_at, created_at
            FROM encounters
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT 5;
        """, (patient_id,))
        recent_encounters = [dict(r) for r in cursor.fetchall()]

        # Allergies (Prompt 03)
        allergies = []
        try:
            cursor.execute("""
                SELECT id, allergen_name, severity, reaction, recorded_at
                FROM patient_allergies
                WHERE patient_id = ?
                ORDER BY severity DESC, recorded_at DESC;
            """, (patient_id,))
            allergies = [dict(r) for r in cursor.fetchall()]
        except sqlite3.OperationalError:
            pass

        # Recent Prescriptions (Prompt 03)
        recent_prescriptions = []
        try:
            cursor.execute("""
                SELECT id, prescription_number, status, overall_safety_state, signed_at, created_at
                FROM prescriptions
                WHERE patient_id = ?
                ORDER BY created_at DESC
                LIMIT 5;
            """, (patient_id,))
            recent_prescriptions = [dict(r) for r in cursor.fetchall()]
        except sqlite3.OperationalError:
            pass

        # Latest Unani Assessment (Prompt 04)
        latest_unani_assessment = None
        try:
            cursor.execute("""
                SELECT id, status, assessment_date, dominant_mizaj, secondary_mizaj,
                       mizaj_uncertainty, mizaj_rationale, clinical_reasoning,
                       signed_at, created_at
                FROM unani_assessments
                WHERE patient_id = ?
                ORDER BY created_at DESC
                LIMIT 1;
            """, (patient_id,))
            r = cursor.fetchone()
            if r:
                latest_unani_assessment = dict(r)
        except sqlite3.OperationalError:
            pass

        # Active Care Plans (Prompt 04)
        active_care_plans = []
        try:
            cursor.execute("""
                SELECT id, title, status, overall_goal, review_date, created_at
                FROM care_plans
                WHERE patient_id = ? AND status IN ('ACTIVE', 'PROPOSED', 'DRAFT')
                ORDER BY created_at DESC;
            """, (patient_id,))
            active_care_plans = [dict(r) for r in cursor.fetchall()]
        except sqlite3.OperationalError:
            pass

        # Log Access Audit Event
        log_audit_event(
            conn=conn,
            action_type="PATIENT_ACCESSED",
            target_entity_type="PATIENT",
            target_entity_id=patient_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"mrn": patient["mrn"]}
        )

        return {
            "patient": patient,
            "contacts": contacts,
            "identifiers": identifiers,
            "addresses": addresses,
            "consents": consents,
            "recent_encounters": recent_encounters,
            "allergies": allergies,
            "recent_prescriptions": recent_prescriptions,
            "latest_unani_assessment": latest_unani_assessment,
            "active_care_plans": active_care_plans
        }

    @staticmethod
    def update_demographics(conn: sqlite3.Connection, organization_id: str, patient_id: str,
                            data: Dict[str, Any], current_version: int, actor_id: str,
                            request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Update demographic fields with optimistic concurrency version checking.
        If version does not match, raises ConflictError.
        """
        patient = PatientService.get_patient_by_id(conn, organization_id, patient_id)

        if patient["version"] != current_version:
            raise ConflictError(
                "Patient record has been modified by another user. Please reload and review changes.",
                details={"server_version": patient["version"], "submitted_version": current_version},
                request_id=request_id
            )

        given_name = data.get("given_name", patient["given_name"]).strip()
        family_name = data.get("family_name", patient["family_name"]).strip() if data.get("family_name") is not None else patient["family_name"]
        display_name = data.get("display_name")
        if not display_name:
            display_name = f"{given_name} {family_name}".strip() if family_name else given_name

        date_of_birth = data.get("date_of_birth", patient["date_of_birth"])
        estimated_age = data.get("estimated_age", patient["estimated_age"])
        sex = data.get("sex", patient["sex"]).upper()
        preferred_lang = data.get("preferred_language", patient["preferred_language"])
        status = data.get("status", patient["status"]).upper()

        if sex not in ["MALE", "FEMALE", "OTHER", "UNKNOWN"]:
            raise ValidationError("Invalid sex value.", request_id=request_id)
        if status not in ["ACTIVE", "INACTIVE"]:
            raise ValidationError("Invalid status value. Must be ACTIVE or INACTIVE.", request_id=request_id)

        new_version = patient["version"] + 1

        conn.execute("""
            UPDATE patients
            SET given_name = ?, family_name = ?, display_name = ?, date_of_birth = ?,
                estimated_age = ?, sex = ?, preferred_language = ?, status = ?,
                version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?;
        """, (
            given_name, family_name, display_name, date_of_birth, estimated_age,
            sex, preferred_lang, status, new_version, actor_id, patient_id, organization_id
        ))

        # Audit Event with changed field names
        changed_fields = []
        for k in ["given_name", "family_name", "display_name", "date_of_birth", "sex", "status"]:
            if data.get(k) is not None and data.get(k) != patient[k]:
                changed_fields.append(k)

        log_audit_event(
            conn=conn,
            action_type="PATIENT_DEMOGRAPHICS_UPDATED",
            target_entity_type="PATIENT",
            target_entity_id=patient_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"changed_fields": changed_fields, "version": new_version}
        )

        return PatientService.get_patient_by_id(conn, organization_id, patient_id)

    @staticmethod
    def add_identifier(conn: sqlite3.Connection, organization_id: str, patient_id: str,
                       id_type: str, id_val: str, issuer: Optional[str] = None,
                       actor_id: str = None, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Add identifier to patient with duplicate check among active identifiers."""
        PatientService.get_patient_by_id(conn, organization_id, patient_id)
        norm_val = normalize_string(id_val)

        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM patient_identifiers
            WHERE organization_id = ? AND identifier_type = ? AND normalized_value = ? AND is_retired = 0;
        """, (organization_id, id_type, norm_val))
        if cursor.fetchone():
            raise ConflictError(f"Active identifier '{id_type}' with this value already exists in organization.", request_id=request_id)

        ident_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO patient_identifiers (id, patient_id, organization_id, identifier_type, identifier_value, normalized_value, issuer)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (ident_id, patient_id, organization_id, id_type, id_val.strip(), norm_val, issuer))

        log_audit_event(
            conn=conn,
            action_type="PATIENT_IDENTIFIER_ADDED",
            target_entity_type="PATIENT_IDENTIFIER",
            target_entity_id=ident_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            details={"patient_id": patient_id, "identifier_type": id_type}
        )

        return {"id": ident_id, "identifier_type": id_type, "identifier_value": id_val, "is_retired": 0}

    @staticmethod
    def retire_identifier(conn: sqlite3.Connection, organization_id: str, patient_id: str,
                          identifier_id: str, reason: str, actor_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Retire an identifier without hard-deleting the audit trail."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, identifier_type, is_retired
            FROM patient_identifiers
            WHERE id = ? AND patient_id = ? AND organization_id = ?;
        """, (identifier_id, patient_id, organization_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError("Identifier not found for this patient.", request_id=request_id)

        if row["is_retired"]:
            raise ConflictError("Identifier is already retired.", request_id=request_id)

        conn.execute("""
            UPDATE patient_identifiers
            SET is_retired = 1, retired_reason = ?, retired_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (reason.strip(), identifier_id))

        log_audit_event(
            conn=conn,
            action_type="PATIENT_IDENTIFIER_RETIRED",
            target_entity_type="PATIENT_IDENTIFIER",
            target_entity_id=identifier_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            details={"patient_id": patient_id, "reason": reason}
        )

        return {"id": identifier_id, "identifier_id": identifier_id, "retired": True, "is_retired": 1}

    @staticmethod
    def record_consent(conn: sqlite3.Connection, organization_id: str, patient_id: str,
                       purpose: str, status: str, source_method: str = "VERBAL_PATIENT",
                       policy_version: str = "v1.0", actor_id: str = None, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Record explicit patient consent decision."""
        PatientService.get_patient_by_id(conn, organization_id, patient_id)

        valid_purposes = ["GENERAL_CARE", "COMMUNICATION_SMS", "COMMUNICATION_WHATSAPP", "DATA_SHARING_RESEARCH", "EXTERNAL_REFERRAL"]
        if purpose not in valid_purposes:
            raise ValidationError(f"Invalid consent purpose. Must be one of: {', '.join(valid_purposes)}", request_id=request_id)

        if status not in ["GRANTED", "REFUSED"]:
            raise ValidationError("Consent status must be GRANTED or REFUSED.", request_id=request_id)

        consent_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO patient_consents (id, patient_id, organization_id, purpose, status, policy_version, source_method, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (consent_id, patient_id, organization_id, purpose, status, policy_version, source_method, actor_id))

        log_audit_event(
            conn=conn,
            action_type="PATIENT_CONSENT_RECORDED",
            target_entity_type="PATIENT_CONSENT",
            target_entity_id=consent_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            details={"patient_id": patient_id, "purpose": purpose, "status": status}
        )

        return {"id": consent_id, "purpose": purpose, "status": status}

    @staticmethod
    def withdraw_consent(conn: sqlite3.Connection, organization_id: str, patient_id: str,
                         consent_id: str, reason: str, actor_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Withdraw previously recorded consent."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, purpose, status
            FROM patient_consents
            WHERE id = ? AND patient_id = ? AND organization_id = ?;
        """, (consent_id, patient_id, organization_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError("Consent record not found.", request_id=request_id)

        if row["status"] == "WITHDRAWN":
            raise ConflictError("Consent is already withdrawn.", request_id=request_id)

        conn.execute("""
            UPDATE patient_consents
            SET status = 'WITHDRAWN', withdrawn_at = CURRENT_TIMESTAMP, withdrawal_reason = ?
            WHERE id = ?;
        """, (reason.strip(), consent_id))

        log_audit_event(
            conn=conn,
            action_type="PATIENT_CONSENT_WITHDRAWN",
            target_entity_type="PATIENT_CONSENT",
            target_entity_id=consent_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            details={"patient_id": patient_id, "purpose": row["purpose"], "reason": reason}
        )

        return {"withdrawn": True, "consent_id": consent_id, "status": "WITHDRAWN"}

    @staticmethod
    def get_duplicate_candidates_for_patient(conn: sqlite3.Connection, organization_id: str, patient_id: str) -> List[Dict[str, Any]]:
        """Fetch candidate duplicate pairs flagged for this patient."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.patient_id_a, c.patient_id_b, c.match_score, c.match_rules, c.status,
                   c.reviewed_at, c.review_notes,
                   p.mrn as candidate_mrn, p.display_name as candidate_name, p.date_of_birth as candidate_dob
            FROM patient_duplicate_candidates c
            JOIN patients p ON (p.id = CASE WHEN c.patient_id_a = ? THEN c.patient_id_b ELSE c.patient_id_a END)
            WHERE c.organization_id = ? AND (c.patient_id_a = ? OR c.patient_id_b = ?)
            ORDER BY c.match_score DESC;
        """, (patient_id, organization_id, patient_id, patient_id))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def resolve_duplicate_candidate(conn: sqlite3.Connection, organization_id: str, candidate_id: str,
                                    decision: str, notes: str, actor_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Record human operator resolution for duplicate candidate (No automatic merge!)."""
        if decision not in ["CONFIRMED_DIFFERENT", "DEFERRED", "MERGED_FUTURE"]:
            raise ValidationError("Invalid resolution decision. Must be CONFIRMED_DIFFERENT or DEFERRED.", request_id=request_id)
        if decision == "MERGED_FUTURE":
            raise ValidationError("Automatic data merge is not supported in this phase.", request_id=request_id)

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, patient_id_a, patient_id_b, status
            FROM patient_duplicate_candidates
            WHERE id = ? AND organization_id = ?;
        """, (candidate_id, organization_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError("Duplicate candidate record not found.", request_id=request_id)

        conn.execute("""
            UPDATE patient_duplicate_candidates
            SET status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, review_notes = ?
            WHERE id = ?;
        """, (decision, actor_id, notes.strip(), candidate_id))

        log_audit_event(
            conn=conn,
            action_type="PATIENT_DUPLICATE_RESOLVED",
            target_entity_type="DUPLICATE_CANDIDATE",
            target_entity_id=candidate_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            details={"decision": decision, "patient_a": row["patient_id_a"], "patient_b": row["patient_id_b"]}
        )

        return {"resolved": True, "candidate_id": candidate_id, "status": decision}
