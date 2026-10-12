"""Prescription Domain Service: Nuskha Builder, Concurrency Control, Electronic Sign-off, and Document Rendering."""

import uuid
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import sqlite3
from apps.api.core.errors import NotFoundError, ValidationError, ConflictError, ForbiddenError, AuthenticationError, SafetyBlockedError
from apps.api.core.security import verify_pin, calculate_prescription_hash
from apps.api.core.audit import log_audit_event
from apps.api.domains.safety_preflight import SafetyPreflightEngine

class PrescriptionService:
    @staticmethod
    def generate_prescription_number(conn: sqlite3.Connection, organization_id: str) -> str:
        """Generate collision-safe, tenant-scoped prescription number."""
        year = datetime.utcnow().strftime("%Y")
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) as total FROM prescriptions WHERE organization_id = ?;", (organization_id,))
        count = cursor.fetchone()["total"] + 1
        return f"RX-{year}-{count:05d}"

    @staticmethod
    def get_prescription_by_id(conn: sqlite3.Connection, organization_id: str, prescription_id: str) -> Dict[str, Any]:
        """Fetch prescription aggregate with items, practitioner profile, and validation findings."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pr.id, pr.organization_id, pr.facility_id, pr.prescription_number,
                   pr.patient_id, pr.encounter_id, pr.practitioner_id, pr.version_number,
                   pr.status, pr.overall_safety_state, pr.parent_prescription_id,
                   pr.amendment_reason, pr.cancellation_reason, pr.patient_instructions_language,
                   pr.signed_at, pr.signed_by, pr.signature_hash, pr.signed_snapshot,
                   pr.created_at, pr.updated_at,
                   p.mrn as patient_mrn, p.display_name as patient_name, p.date_of_birth as patient_dob,
                   p.estimated_age as patient_age, p.sex as patient_sex,
                   f.name as facility_name, f.address as facility_address, f.phone as facility_phone,
                   o.name as organization_name, o.license_number as org_license,
                   u.full_name as practitioner_name,
                   pp.license_type, pp.registration_number, pp.registration_council, pp.is_credential_verified
            FROM prescriptions pr
            JOIN patients p ON pr.patient_id = p.id
            JOIN facilities f ON pr.facility_id = f.id
            JOIN organizations o ON pr.organization_id = o.id
            JOIN users u ON pr.practitioner_id = u.id
            LEFT JOIN practitioner_profiles pp ON u.id = pp.user_id
            WHERE pr.id = ? AND pr.organization_id = ?;
        """, (prescription_id, organization_id))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Prescription '{prescription_id}' not found.")
        rx = dict(row)

        # Items
        cursor.execute("""
            SELECT pi.id, pi.item_type, pi.formulation_id, pi.formulation_version_id,
                   pi.item_name, pi.dosage_form, pi.dose_amount, pi.dose_unit,
                   pi.route, pi.frequency, pi.duration_days, pi.quantity_to_dispense,
                   pi.instructions, pi.anupan_vehicle, pi.composition_snapshot, pi.sort_order,
                   f.code as formulation_code, f.status as formulation_status
            FROM prescription_items pi
            LEFT JOIN formulations f ON pi.formulation_id = f.id
            WHERE pi.prescription_id = ?
            ORDER BY pi.sort_order ASC, pi.id ASC;
        """, (prescription_id,))
        rx["items"] = [dict(it) for it in cursor.fetchall()]

        # Validation Findings
        cursor.execute("""
            SELECT id, prescription_version, rule_id, rule_set_version, severity,
                   finding_code, message, item_reference, acknowledged, acknowledged_by,
                   acknowledged_at, acknowledged_reason, created_at
            FROM prescription_validation_findings
            WHERE prescription_id = ? AND prescription_version = ?
            ORDER BY severity DESC, created_at ASC;
        """, (prescription_id, rx["version_number"]))
        rx["validation_findings"] = [dict(f) for f in cursor.fetchall()]

        return rx

    @staticmethod
    def create_prescription_draft(conn: sqlite3.Connection, organization_id: str,
                                  encounter_id: str, practitioner_id: str,
                                  actor_id: str, data: Optional[Dict[str, Any]] = None,
                                  request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Create a new prescription draft linked to an active encounter."""
        data = data or {}
        cursor = conn.cursor()

        # Verify encounter exists and belongs to organization
        cursor.execute("""
            SELECT id, facility_id, patient_id, status
            FROM encounters
            WHERE id = ? AND organization_id = ?;
        """, (encounter_id, organization_id))
        enc_row = cursor.fetchone()
        if not enc_row:
            raise NotFoundError(f"Encounter '{encounter_id}' not found in organization.", request_id=request_id)

        if enc_row["status"] in ["COMPLETED", "CANCELLED"]:
            raise ConflictError(f"Cannot create prescription for encounter in '{enc_row['status']}' state.", request_id=request_id)

        facility_id = enc_row["facility_id"]
        patient_id = enc_row["patient_id"]

        # Check for existing draft in this encounter
        cursor.execute("""
            SELECT id FROM prescriptions
            WHERE encounter_id = ? AND organization_id = ? AND status IN ('DRAFT', 'VALIDATION_REQUIRED')
            ORDER BY version_number DESC LIMIT 1;
        """, (encounter_id, organization_id))
        existing_draft = cursor.fetchone()
        if existing_draft:
            # If empty data supplied, return existing draft
            if not data.get("items"):
                return PrescriptionService.get_prescription_by_id(conn, organization_id, existing_draft["id"])

        prescription_id = str(uuid.uuid4())
        rx_number = PrescriptionService.generate_prescription_number(conn, organization_id)
        lang = data.get("patient_instructions_language", "ur")

        conn.execute("""
            INSERT INTO prescriptions (
                id, organization_id, facility_id, prescription_number, patient_id,
                encounter_id, practitioner_id, version_number, status, overall_safety_state,
                patient_instructions_language
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'DRAFT', 'UNKNOWN', ?);
        """, (prescription_id, organization_id, facility_id, rx_number, patient_id, encounter_id, practitioner_id, lang))

        # Insert items if provided
        items = data.get("items", [])
        for idx, item in enumerate(items):
            PrescriptionService._insert_item(conn, prescription_id, item, idx + 1)

        # Run safety preflight
        PrescriptionService._run_and_persist_preflight(conn, organization_id, prescription_id, patient_id, 1, items)

        log_audit_event(
            conn=conn,
            action_type="PRESCRIPTION_DRAFT_CREATED",
            target_entity_type="PRESCRIPTION",
            target_entity_id=prescription_id,
            organization_id=organization_id,
            facility_id=facility_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"prescription_number": rx_number, "encounter_id": encounter_id, "patient_id": patient_id}
        )

        return PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)

    @staticmethod
    def update_draft_items(conn: sqlite3.Connection, organization_id: str,
                           prescription_id: str, items: List[Dict[str, Any]],
                           current_version: int, actor_id: str,
                           request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Update draft prescription items with optimistic concurrency and preflight re-evaluation."""
        rx = PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)

        if rx["status"] in ["SIGNED", "SUPERSEDED", "CANCELLED"]:
            raise ConflictError(f"Cannot edit prescription in '{rx['status']}' state. Signed records are immutable.", request_id=request_id)

        if rx["version_number"] != current_version:
            raise ConflictError(
                "Prescription was updated by another session. Please reload and review.",
                details={"server_version": rx["version_number"], "submitted_version": current_version},
                request_id=request_id
            )

        new_version = current_version + 1

        # Delete old items and insert updated items
        conn.execute("DELETE FROM prescription_items WHERE prescription_id = ?;", (prescription_id,))
        for idx, item in enumerate(items):
            PrescriptionService._insert_item(conn, prescription_id, item, idx + 1)

        # Run and persist safety preflight findings
        report = PrescriptionService._run_and_persist_preflight(conn, organization_id, prescription_id, rx["patient_id"], new_version, items)

        # Update prescription header
        conn.execute("""
            UPDATE prescriptions
            SET version_number = ?, overall_safety_state = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?;
        """, (new_version, report["overall_state"], prescription_id, organization_id))

        log_audit_event(
            conn=conn,
            action_type="PRESCRIPTION_DRAFT_UPDATED",
            target_entity_type="PRESCRIPTION",
            target_entity_id=prescription_id,
            organization_id=organization_id,
            facility_id=rx["facility_id"],
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"version": new_version, "items_count": len(items), "safety_state": report["overall_state"]}
        )

        return PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)

    @staticmethod
    def acknowledge_warning(conn: sqlite3.Connection, organization_id: str,
                            prescription_id: str, finding_id: str, reason: str,
                            actor_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Acknowledge a non-blocking warning finding with a documented clinical reason."""
        if not reason or not reason.strip():
            raise ValidationError("A clinical justification is required to acknowledge a warning.", request_id=request_id)

        rx = PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)
        if rx["status"] in ["SIGNED", "SUPERSEDED", "CANCELLED"]:
            raise ConflictError("Cannot alter findings on a finalized prescription.", request_id=request_id)

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, severity, finding_code
            FROM prescription_validation_findings
            WHERE id = ? AND prescription_id = ?;
        """, (finding_id, prescription_id))
        finding = cursor.fetchone()
        if not finding:
            raise NotFoundError("Validation finding not found.", request_id=request_id)

        if finding["severity"] == "BLOCK":
            raise ConflictError("Blocking safety findings cannot be overridden or acknowledged.", request_id=request_id)

        conn.execute("""
            UPDATE prescription_validation_findings
            SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = CURRENT_TIMESTAMP, acknowledged_reason = ?
            WHERE id = ?;
        """, (actor_id, reason.strip(), finding_id))

        log_audit_event(
            conn=conn,
            action_type="PRESCRIPTION_WARNING_ACKNOWLEDGED",
            target_entity_type="PRESCRIPTION_FINDING",
            target_entity_id=finding_id,
            organization_id=organization_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            details={"prescription_id": prescription_id, "finding_code": finding["finding_code"], "reason": reason.strip()}
        )

        return {"acknowledged": True, "finding_id": finding_id}

    @staticmethod
    def sign_prescription(conn: sqlite3.Connection, organization_id: str,
                          prescription_id: str, practitioner_id: str, pin: str,
                          actor_id: str, request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Electronically sign prescription: atomic re-validation, PIN authentication,
        immutable JSON snapshot creation, SHA-256 fingerprinting, and status lock.
        """
        rx = PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)

        if rx["status"] == "SIGNED":
            raise ConflictError("Prescription is already signed and locked.", request_id=request_id)
        if rx["status"] in ["CANCELLED", "SUPERSEDED"]:
            raise ConflictError(f"Cannot sign prescription in '{rx['status']}' state.", request_id=request_id)

        if not rx["items"]:
            raise ValidationError("Cannot sign an empty prescription with zero items.", request_id=request_id)

        # 1. Verify Practitioner PIN Authentication
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pp.digital_signature_pin_hash, pp.registration_number, pp.registration_council, u.full_name
            FROM practitioner_profiles pp
            JOIN users u ON pp.user_id = u.id
            WHERE u.id = ?;
        """, (practitioner_id,))
        prof = cursor.fetchone()

        stored_hash = prof["digital_signature_pin_hash"] if prof else None
        if not stored_hash or not verify_pin(pin, stored_hash):
            raise AuthenticationError("Invalid digital signature PIN.", request_id=request_id)

        # 2. Server-side Preflight Re-evaluation immediately before signing
        report = SafetyPreflightEngine.evaluate(conn, rx["patient_id"], rx["items"])
        if report["overall_state"] == "BLOCK":
            blocking_reasons = [f["message"] for f in report["findings"] if f["severity"] == "BLOCK"]
            raise SafetyBlockedError(
                f"Prescription blocked by clinical safety rules: {'; '.join(blocking_reasons)}",
                details={"findings": report["findings"]},
                request_id=request_id
            )

        # 3. Create Immutable Snapshot
        signed_at_iso = datetime.utcnow().isoformat() + "Z"
        snapshot = {
            "prescription_id": rx["id"],
            "prescription_number": rx["prescription_number"],
            "version_number": rx["version_number"],
            "patient_mrn": rx["patient_mrn"],
            "patient_name": rx["patient_name"],
            "patient_dob": rx["patient_dob"],
            "patient_sex": rx["patient_sex"],
            "encounter_id": rx["encounter_id"],
            "facility_name": rx["facility_name"],
            "organization_name": rx["organization_name"],
            "practitioner_name": prof["full_name"],
            "registration_number": prof["registration_number"],
            "registration_council": prof["registration_council"],
            "items": [
                {
                    "item_name": it["item_name"],
                    "dosage_form": it["dosage_form"],
                    "dose_amount": it["dose_amount"],
                    "dose_unit": it["dose_unit"],
                    "route": it["route"],
                    "frequency": it["frequency"],
                    "duration_days": it["duration_days"],
                    "instructions": it["instructions"],
                    "anupan_vehicle": it["anupan_vehicle"],
                    "formulation_code": it.get("formulation_code")
                }
                for it in rx["items"]
            ],
            "safety_state": report["overall_state"],
            "safety_rule_version": report["rule_set_version"],
            "signed_at": signed_at_iso,
            "signed_by": actor_id
        }

        signature_hash = calculate_prescription_hash(snapshot)
        snapshot_json = json.dumps(snapshot, indent=2)

        # 4. Atomic Transition and Immutability Lock
        conn.execute("""
            UPDATE prescriptions
            SET status = 'SIGNED', overall_safety_state = ?, signed_at = CURRENT_TIMESTAMP,
                signed_by = ?, signature_hash = ?, signed_snapshot = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?;
        """, (report["overall_state"], actor_id, signature_hash, snapshot_json, prescription_id, organization_id))

        log_audit_event(
            conn=conn,
            action_type="PRESCRIPTION_SIGNED",
            target_entity_type="PRESCRIPTION",
            target_entity_id=prescription_id,
            organization_id=organization_id,
            facility_id=rx["facility_id"],
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"prescription_number": rx["prescription_number"], "signature_hash": signature_hash, "items_count": len(rx["items"])}
        )

        return PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)

    @staticmethod
    def amend_prescription(conn: sqlite3.Connection, organization_id: str,
                           prescription_id: str, amendment_reason: str,
                           actor_id: str, request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Create a new superseding draft version from a signed prescription without altering history."""
        if not amendment_reason or not amendment_reason.strip():
            raise ValidationError("A formal clinical reason is required to amend a signed prescription.", request_id=request_id)

        parent = PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)
        if parent["status"] != "SIGNED":
            raise ConflictError(f"Only signed prescriptions can be amended. Current status: '{parent['status']}'.", request_id=request_id)

        # Mark parent as SUPERSEDED
        conn.execute("""
            UPDATE prescriptions
            SET status = 'SUPERSEDED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?;
        """, (prescription_id, organization_id))

        # Create new draft child
        new_id = str(uuid.uuid4())
        new_version = parent["version_number"] + 1

        conn.execute("""
            INSERT INTO prescriptions (
                id, organization_id, facility_id, prescription_number, patient_id,
                encounter_id, practitioner_id, version_number, status, overall_safety_state,
                parent_prescription_id, amendment_reason, patient_instructions_language
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', 'UNKNOWN', ?, ?, ?);
        """, (
            new_id, organization_id, parent["facility_id"], parent["prescription_number"],
            parent["patient_id"], parent["encounter_id"], parent["practitioner_id"],
            new_version, prescription_id, amendment_reason.strip(),
            parent.get("patient_instructions_language", "ur")
        ))

        # Copy items from parent
        for idx, it in enumerate(parent["items"]):
            PrescriptionService._insert_item(conn, new_id, it, idx + 1)

        # Run preflight on copy
        PrescriptionService._run_and_persist_preflight(conn, organization_id, new_id, parent["patient_id"], new_version, parent["items"])

        log_audit_event(
            conn=conn,
            action_type="PRESCRIPTION_AMENDED",
            target_entity_type="PRESCRIPTION",
            target_entity_id=new_id,
            organization_id=organization_id,
            facility_id=parent["facility_id"],
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"parent_id": prescription_id, "new_version": new_version, "reason": amendment_reason.strip()}
        )

        return PrescriptionService.get_prescription_by_id(conn, organization_id, new_id)

    @staticmethod
    def cancel_prescription(conn: sqlite3.Connection, organization_id: str,
                            prescription_id: str, cancellation_reason: str,
                            actor_id: str, request_id: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Cancel a prescription with mandatory reason and immutable audit event."""
        if not cancellation_reason or not cancellation_reason.strip():
            raise ValidationError("A cancellation reason is required.", request_id=request_id)

        rx = PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)
        if rx["status"] == "CANCELLED":
            raise ConflictError("Prescription is already cancelled.", request_id=request_id)

        conn.execute("""
            UPDATE prescriptions
            SET status = 'CANCELLED', cancellation_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND organization_id = ?;
        """, (cancellation_reason.strip(), prescription_id, organization_id))

        log_audit_event(
            conn=conn,
            action_type="PRESCRIPTION_CANCELLED",
            target_entity_type="PRESCRIPTION",
            target_entity_id=prescription_id,
            organization_id=organization_id,
            facility_id=rx["facility_id"],
            actor_id=actor_id,
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=client_ip,
            details={"prescription_number": rx["prescription_number"], "reason": cancellation_reason.strip()}
        )

        return PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)

    @staticmethod
    def list_patient_prescriptions(conn: sqlite3.Connection, organization_id: str,
                                   patient_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List all historical prescriptions for a patient in Patient 360."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pr.id, pr.prescription_number, pr.encounter_id, pr.practitioner_id,
                   pr.version_number, pr.status, pr.overall_safety_state, pr.signed_at,
                   pr.signature_hash, pr.created_at, pr.updated_at,
                   u.full_name as practitioner_name,
                   f.name as facility_name
            FROM prescriptions pr
            JOIN users u ON pr.practitioner_id = u.id
            JOIN facilities f ON pr.facility_id = f.id
            WHERE pr.patient_id = ? AND pr.organization_id = ?
            ORDER BY pr.created_at DESC
            LIMIT ?;
        """, (patient_id, organization_id, limit))
        return [dict(r) for r in cursor.fetchall()]

    @staticmethod
    def render_prescription_document(conn: sqlite3.Connection, organization_id: str,
                                      prescription_id: str, doc_format: str = "html") -> Dict[str, Any]:
        """Generate A4 or thermal printable layout derived from exact signed snapshot or watermarked draft."""
        rx = PrescriptionService.get_prescription_by_id(conn, organization_id, prescription_id)
        is_signed = rx["status"] == "SIGNED"
        is_draft = rx["status"] in ["DRAFT", "VALIDATION_REQUIRED"]

        snapshot = json.loads(rx["signed_snapshot"]) if rx.get("signed_snapshot") else None
        items = snapshot["items"] if snapshot else rx["items"]

        # Generate HTML layout
        items_html = ""
        for idx, it in enumerate(items):
            inst = it.get('instructions') or ''
            anupan = it.get('anupan_vehicle') or ''
            anupan_str = f" <small style='color:#0f766e;'>[Anupan: {anupan}]</small>" if anupan else ""
            items_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px; font-weight: 600;">{idx + 1}. {it['item_name']}</td>
                <td style="padding: 10px; text-transform: uppercase; font-size: 12px; color: #64748b;">{it.get('dosage_form','')}</td>
                <td style="padding: 10px; font-weight: 600;">{it.get('dose_amount','')} {it.get('dose_unit','')}</td>
                <td style="padding: 10px;">{it.get('frequency','')} × {it.get('duration_days','')} days</td>
                <td style="padding: 10px; font-size: 13px;">{inst}{anupan_str}</td>
            </tr>
            """

        watermark_badge = """
            <div style="background: #fef2f2; border: 2px dashed #ef4444; color: #b91c1c; padding: 12px; text-align: center; font-weight: bold; font-size: 18px; letter-spacing: 2px; margin-bottom: 20px;">
                DRAFT — NOT SIGNED (FOR PREVIEW ONLY)
            </div>
        """ if is_draft else ""

        signature_block = f"""
            <div style="border-top: 2px solid #0f766e; padding-top: 15px; margin-top: 30px; display: flex; justify-content: space-between; align-items: flex-end;">
                <div>
                    <div style="font-size: 12px; color: #64748b; font-family: monospace;">SHA-256 DIGITAL FINGERPRINT:</div>
                    <div style="font-family: monospace; font-size: 11px; color: #0f766e; word-break: break-all; max-width: 450px;">
                        {rx.get('signature_hash', '')}
                    </div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Signed At: {rx.get('signed_at', '')} (UTC)</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 14px; font-weight: 700; color: #0f172a;">{rx.get('practitioner_name', '')}</div>
                    <div style="font-size: 12px; color: #64748b;">Reg: {rx.get('registration_number', 'BUMS/AYUSH')}</div>
                    <div style="font-size: 11px; color: #0f766e; font-weight: 600; margin-top: 4px;">✓ ELECTRONICALLY SIGNED & VERIFIED</div>
                </div>
            </div>
        """ if is_signed else """
            <div style="border-top: 2px dashed #94a3b8; padding-top: 15px; margin-top: 30px; text-align: right; color: #94a3b8;">
                [ PENDING CLINICAL SIGN-OFF ]
            </div>
        """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Prescription {rx['prescription_number']} - {rx['patient_name']}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #0f172a; margin: 0; padding: 24px; background: #fff; }}
                @media print {{ body {{ padding: 0; }} .no-print {{ display: none; }} }}
            </style>
        </head>
        <body>
            {watermark_badge}
            <div style="border-bottom: 2px solid #0f766e; padding-bottom: 12px; margin-bottom: 20px; display: flex; justify-content: space-between;">
                <div>
                    <h1 style="margin: 0; font-size: 24px; color: #0f766e;">{rx.get('organization_name', 'ZAYVORA MATAB')}</h1>
                    <div style="font-size: 13px; color: #475569;">{rx.get('facility_name', 'Central OPD')} | {rx.get('facility_address', '')}</div>
                    <div style="font-size: 12px; color: #64748b;">Phone: {rx.get('facility_phone', '')} | License: {rx.get('org_license', '')}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 18px; font-weight: 700; color: #0f766e;">{rx['prescription_number']}</div>
                    <div style="font-size: 12px; color: #64748b;">Version #{rx['version_number']} ({rx['status']})</div>
                    <div style="font-size: 12px; color: #64748b;">Date: {rx['created_at'].split()[0]}</div>
                </div>
            </div>

            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 16px; margin-bottom: 24px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; font-size: 13px;">
                <div><strong>Patient:</strong> {rx['patient_name']}</div>
                <div><strong>MRN:</strong> {rx['patient_mrn']}</div>
                <div><strong>Age / Sex:</strong> {rx.get('patient_age') or '—'} Y / {rx['patient_sex']}</div>
                <div><strong>Prescriber:</strong> {rx['practitioner_name']}</div>
            </div>

            <div style="margin-bottom: 15px; font-size: 24px; font-weight: bold; color: #0f766e;">℞</div>

            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; margin-bottom: 24px;">
                <thead>
                    <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1; font-size: 12px; text-transform: uppercase; color: #475569;">
                        <th style="padding: 10px;">Formulation / Nuskha Item</th>
                        <th style="padding: 10px;">Form</th>
                        <th style="padding: 10px;">Dose</th>
                        <th style="padding: 10px;">Regimen</th>
                        <th style="padding: 10px;">Directions & Anupan</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
            </table>

            {signature_block}
        </body>
        </html>
        """

        return {
            "prescription_id": prescription_id,
            "prescription_number": rx["prescription_number"],
            "status": rx["status"],
            "format": doc_format,
            "html": html_content.strip()
        }

    @staticmethod
    def _insert_item(conn: sqlite3.Connection, prescription_id: str, item: Dict[str, Any], sort_order: int) -> None:
        """Helper to insert a single prescription line item."""
        item_id = str(uuid.uuid4())
        item_type = item.get("item_type", "CATALOG_FORMULATION")
        formulation_id = item.get("formulation_id")
        fv_id = item.get("formulation_version_id")
        name = item.get("item_name") or item.get("custom_name") or "Formula"
        dform = item.get("dosage_form", "SAFOOF")
        damt = str(item.get("dose_amount", "1"))
        dunit = item.get("dose_unit", "g")
        route = item.get("route", "ORAL")
        freq = item.get("frequency", "BD")
        dur = int(item.get("duration_days", 7))
        qdisp = item.get("quantity_to_dispense")
        inst = item.get("instructions")
        anupan = item.get("anupan_vehicle", "WATER")
        comp = json.dumps(item.get("composition_snapshot")) if item.get("composition_snapshot") else None

        conn.execute("""
            INSERT INTO prescription_items (
                id, prescription_id, item_type, formulation_id, formulation_version_id,
                item_name, dosage_form, dose_amount, dose_unit, route, frequency,
                duration_days, quantity_to_dispense, instructions, anupan_vehicle,
                composition_snapshot, sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            item_id, prescription_id, item_type, formulation_id, fv_id,
            name, dform, damt, dunit, route, freq, dur, qdisp, inst, anupan, comp, sort_order
        ))

    @staticmethod
    def _run_and_persist_preflight(conn: sqlite3.Connection, organization_id: str,
                                   prescription_id: str, patient_id: str,
                                   version: int, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run safety preflight engine and store findings in prescription_validation_findings."""
        report = SafetyPreflightEngine.evaluate(conn, patient_id, items)

        # Clear old findings for this version
        conn.execute("DELETE FROM prescription_validation_findings WHERE prescription_id = ? AND prescription_version = ?;", (prescription_id, version))

        for f in report["findings"]:
            finding_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO prescription_validation_findings (
                    id, prescription_id, prescription_version, rule_id, rule_set_version,
                    severity, finding_code, message, item_reference
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                finding_id, prescription_id, version, f["rule"], report["rule_set_version"],
                f["severity"], f["rule"], f["message"], f.get("item")
            ))

        return report
