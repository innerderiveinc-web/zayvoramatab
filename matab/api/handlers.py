"""API Handlers for ZAYVORA MATAB OS."""

import json
from typing import Dict, Any, Tuple
import sqlite3
from matab.core.errors import AppError, ValidationError, AuthenticationError, ForbiddenError
from matab.core.registry import get_all_capabilities
from matab.domains.identity import IdentityService
from matab.domains.patients import PatientService
from matab.domains.encounters import EncounterService
from matab.domains.unani import UnaniService
from matab.domains.clinical_support import ClinicalSupportService
from matab.domains.knowledge import KnowledgeService
from matab.domains.prescriptions import PrescriptionService, SafetyPreflightEngine
from matab.domains.operations import OperationsService

def handle_system_health(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    # Execute simple select to verify DB connectivity
    cursor = conn.cursor()
    cursor.execute("SELECT 1;")
    return 200, {
        "status": "HEALTHY",
        "product": "ZAYVORA MATAB OS",
        "version": "1.1.0",
        "database": "CONNECTED_SQLITE_WAL"
    }

def handle_system_capabilities(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    capabilities = get_all_capabilities(conn)
    return 200, {"capabilities": capabilities}

def handle_auth_login(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    body = req.get("body", {})
    username = body.get("username", "")
    password = body.get("password", "")
    client_ip = req.get("client_ip")
    result = IdentityService.authenticate(conn, username, password, client_ip)
    return 200, result

def handle_auth_logout(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    token = req.get("auth_token")
    if token:
        IdentityService.logout(conn, token)
    return 200, {"message": "Logged out successfully"}

def handle_auth_me(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    if not user:
        raise AuthenticationError("Not authenticated")
    practitioner = IdentityService.get_practitioner_by_user(conn, user["user_id"])
    return 200, {"user": user, "practitioner": practitioner}

def handle_patients_search(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    q = req.get("query_params", {}).get("q", "")
    patients = PatientService.search_patients(conn, user["organization_id"], q)
    return 200, {"patients": patients}

def handle_patients_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    body = req.get("body", {})
    override = req.get("query_params", {}).get("override_duplicate") == "true"
    patient = PatientService.create_patient(conn, user["organization_id"], body, user["user_id"], override)
    return 201, {"patient": patient}

def handle_patients_duplicate_check(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    body = req.get("body", {})
    matches = PatientService.check_duplicates(
        conn,
        user["organization_id"],
        body.get("phone", ""),
        body.get("first_name", ""),
        body.get("dob")
    )
    return 200, {"matches": matches, "has_duplicates": len(matches) > 0}

def handle_patient_360(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    patient_id = req["path_params"]["id"]
    p360 = PatientService.get_patient_360(conn, user["organization_id"], patient_id)
    return 200, {"patient_360": p360}

def handle_encounters_queue(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    facility_id = user.get("facility_id") or "fac-matab-main"
    queue = EncounterService.get_today_queue(conn, facility_id)
    return 200, {"queue": queue}

def handle_encounters_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    body = req.get("body", {})
    facility_id = user.get("facility_id") or "fac-matab-main"
    enc = EncounterService.create_encounter(
        conn=conn,
        organization_id=user["organization_id"],
        facility_id=facility_id,
        patient_id=body.get("patient_id"),
        practitioner_id=body.get("practitioner_id"),
        encounter_type=body.get("encounter_type", "WALK_IN"),
        actor_id=user["user_id"]
    )
    return 201, {"encounter": enc}

def handle_encounter_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    encounter_id = req["path_params"]["id"]
    enc = EncounterService.get_encounter(conn, user["organization_id"], encounter_id)
    return 200, {"encounter": enc}

def handle_encounter_vitals_put(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})
    vitals = EncounterService.update_vitals(conn, encounter_id, body, user["user_id"])
    return 200, {"vitals": vitals}

def handle_encounter_notes_put(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})
    notes = EncounterService.update_clinical_notes(conn, encounter_id, body, user["user_id"])
    return 200, {"notes": notes}

def handle_unani_assessment_post(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    body = req.get("body", {})
    practitioner = IdentityService.get_practitioner_by_user(conn, user["user_id"])
    if not practitioner:
        raise ForbiddenError("Only licensed practitioners may submit Unani assessments.")
        
    assessment = UnaniService.save_unani_assessment(
        conn=conn,
        encounter_id=body.get("encounter_id"),
        patient_id=body.get("patient_id"),
        hakeem_id=practitioner["id"],
        assessment_data=body
    )
    return 201, {"assessment": assessment}

def handle_clinical_support_red_flags(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    body = req.get("body", {})
    text = body.get("clinical_text", "")
    vitals = body.get("vitals")
    alerts = ClinicalSupportService.evaluate_red_flags(text, vitals)
    return 200, {"red_flags": alerts, "has_critical": any(a["severity"] == "CRITICAL" for a in alerts)}

def handle_care_plans_post(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    body = req.get("body", {})
    plan = OperationsService.save_care_plan(
        conn=conn,
        encounter_id=body.get("encounter_id"),
        patient_id=body.get("patient_id"),
        plan_data=body
    )
    return 201, {"care_plan": plan}

def handle_knowledge_ingredients(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    q = req.get("query_params", {}).get("q", "")
    items = KnowledgeService.search_ingredients(conn, q)
    return 200, {"ingredients": items}

def handle_knowledge_formulations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    q = req.get("query_params", {}).get("q", "")
    items = KnowledgeService.search_formulations(conn, q)
    return 200, {"formulations": items}

def handle_prescriptions_draft_post(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    body = req.get("body", {})
    practitioner = IdentityService.get_practitioner_by_user(conn, user["user_id"])
    if not practitioner:
        raise ForbiddenError("Only licensed practitioners may draft prescriptions.")
        
    pr = PrescriptionService.save_prescription_draft(
        conn=conn,
        encounter_id=body.get("encounter_id"),
        patient_id=body.get("patient_id"),
        hakeem_id=practitioner["id"],
        items=body.get("items", []),
        prescription_id=body.get("prescription_id")
    )
    return 200, {"prescription": pr}

def handle_prescription_safety_check(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    prescription_id = req["path_params"]["id"]
    pr = PrescriptionService.get_prescription(conn, prescription_id)
    result = SafetyPreflightEngine.evaluate(conn, pr["patient_id"], pr["items"])
    return 200, {"preflight_result": result}

def handle_prescription_sign(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    prescription_id = req["path_params"]["id"]
    body = req.get("body", {})
    pin = body.get("pin", "")
    override_rationale = body.get("override_rationale")
    client_ip = req.get("client_ip")
    
    practitioner = IdentityService.get_practitioner_by_user(conn, user["user_id"])
    if not practitioner:
        raise ForbiddenError("Only licensed practitioners may electronically sign prescriptions.")
        
    signed_pr = PrescriptionService.sign_prescription(
        conn=conn,
        prescription_id=prescription_id,
        practitioner_id=practitioner["id"],
        pin=pin,
        override_rationale=override_rationale,
        client_ip=client_ip
    )
    return 200, {"prescription": signed_pr}

def handle_prescription_print(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    prescription_id = req["path_params"]["id"]
    print_data = PrescriptionService.get_printable_prescription(conn, prescription_id)
    return 200, {"printable_prescription": print_data}

def handle_operations_followups(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    facility_id = user.get("facility_id") or "fac-matab-main"
    followups = OperationsService.get_due_follow_ups(conn, facility_id)
    return 200, {"follow_ups": followups}

def handle_operations_inventory(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    facility_id = user.get("facility_id") or "fac-matab-main"
    batches = OperationsService.get_inventory_batches(conn, facility_id)
    return 200, {"batches": batches}
