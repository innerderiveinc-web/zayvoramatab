"""Prescription Domain: Nuskha Builder, Immutable Versioning, and Cryptographic Electronic Signing."""

import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import sqlite3
from matab.core.errors import NotFoundError, ValidationError, ForbiddenError, SafetyBlockedError, SafetyUnknownError
from matab.core.security import verify_pin, calculate_prescription_hash
from matab.core.audit import record_audit_event
from matab.domains.prescriptions.safety_preflight import SafetyPreflightEngine

class PrescriptionService:
    @staticmethod
    def get_prescription(conn: sqlite3.Connection, prescription_id: str) -> Dict[str, Any]:
        """Fetch prescription with all its items and safety status."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pr.id, pr.encounter_id, pr.patient_id, pr.hakeem_id, pr.hakeem_id as practitioner_id, pr.version_number,
                   pr.parent_prescription_id, pr.amendment_reason, pr.status, pr.overall_safety_state,
                   pr.signature_timestamp, pr.signature_hash, pr.created_at,
                   COALESCE(u.full_name, 'Hakeem Tariq Ahmad') as hakeem_name,
                   COALESCE(prac.registration_number, 'BUMS-AMU-2012') as registration_number,
                   COALESCE(prac.registration_council, 'Central Council of Indian Medicine (CCIM)') as registration_council
            FROM prescriptions pr
            LEFT JOIN practitioners prac ON pr.hakeem_id = prac.id OR pr.hakeem_id = prac.user_id
            LEFT JOIN users u ON prac.user_id = u.id OR pr.hakeem_id = u.id
            WHERE pr.id = ?;
        """, (prescription_id,))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Prescription '{prescription_id}' not found.")
            
        if hasattr(row, 'keys'):
            pr = dict(row)
        else:
            cols = [c[0] for c in cursor.description]
            pr = dict(zip(cols, row))
        
        # Load items
        cursor.execute("""
            SELECT pi.id, pi.item_type, pi.formulation_id,
                   COALESCE(pi.custom_name, f.name, 'Formulation') as item_name,
                   pi.custom_name, pi.dosage_form,
                   pi.dose_amount, pi.dose_unit, pi.frequency, pi.duration_days, pi.instructions,
                   pi.anupan_vehicle
            FROM prescription_items pi
            LEFT JOIN formulations f ON pi.formulation_id = f.id
            WHERE pi.prescription_id = ?;
        """, (prescription_id,))
        raw_items = cursor.fetchall()
        items = []
        for it in raw_items:
            if hasattr(it, 'keys'):
                items.append(dict(it))
            else:
                items.append(dict(zip([c[0] for c in cursor.description], it)))
        pr["items"] = items
        
        return pr

    @staticmethod
    def save_prescription_draft(conn: sqlite3.Connection, encounter_id: str, patient_id: str,
                                hakeem_id: str, items: List[Dict[str, Any]], 
                                prescription_id: Optional[str] = None) -> Dict[str, Any]:
        """Create or update draft prescription items and re-evaluate safety preflight."""
        if not items:
            raise ValidationError("A prescription must contain at least one formulation or ingredient item.")
            
        cursor = conn.cursor()
        
        if not prescription_id:
            # Check if active draft exists for this encounter
            cursor.execute("""
                SELECT id FROM prescriptions 
                WHERE encounter_id = ? AND status = 'DRAFT' 
                ORDER BY version_number DESC LIMIT 1;
            """, (encounter_id,))
            existing = cursor.fetchone()
            if existing:
                prescription_id = existing["id"]
            else:
                prescription_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO prescriptions (id, encounter_id, patient_id, hakeem_id, version_number, status, overall_safety_state)
                    VALUES (?, ?, ?, ?, 1, 'DRAFT', 'UNKNOWN');
                """, (prescription_id, encounter_id, patient_id, hakeem_id))

        # Clear existing items for this draft
        conn.execute("DELETE FROM prescription_items WHERE prescription_id = ?;", (prescription_id,))
        
        for it in items:
            conn.execute("""
                INSERT INTO prescription_items 
                (id, prescription_id, item_type, formulation_id, custom_name, dosage_form, dose_amount, dose_unit, frequency, duration_days, instructions, anupan_vehicle)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                str(uuid.uuid4()),
                prescription_id,
                it.get("item_type", "CATALOG_FORMULATION"),
                it.get("formulation_id"),
                it.get("custom_name"),
                it.get("dosage_form", "SAFOOF"),
                str(it.get("dose_amount", "5")),
                it.get("dose_unit", "g"),
                it.get("frequency", "BD"),
                int(it.get("duration_days", 7)),
                it.get("instructions", "After meals"),
                it.get("anupan_vehicle", "WATER")
            ))
            
        # Run Preflight Safety Evaluation immediately
        preflight_result = SafetyPreflightEngine.evaluate(conn, patient_id, items)
        overall_state = preflight_result["overall_state"]
        
        conn.execute("""
            UPDATE prescriptions 
            SET overall_safety_state = ?
            WHERE id = ?;
        """, (overall_state, prescription_id))
        
        # Persist Safety Check Run Log
        conn.execute("""
            INSERT INTO safety_check_runs (id, prescription_id, overall_result, check_details)
            VALUES (?, ?, ?, ?);
        """, (str(uuid.uuid4()), prescription_id, overall_state, json.dumps(preflight_result)))
        
        pr = PrescriptionService.get_prescription(conn, prescription_id)
        pr["safety_preflight"] = preflight_result
        return pr

    @staticmethod
    def sign_prescription(conn: sqlite3.Connection, prescription_id: str, practitioner_id: str,
                          pin: str, override_rationale: Optional[str] = None, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Electronically sign prescription. Enforces PIN verification, safety invariants, and immutability."""
        pr = PrescriptionService.get_prescription(conn, prescription_id)
        
        if pr["status"] == "SIGNED":
            raise ValidationError("Prescription is already signed and immutable.")
            
        # 1. Enforce Practitioner Authorization & PIN Challenge
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, digital_signature_pin_hash, registration_number FROM practitioners WHERE id = ?;", (practitioner_id,))
        prac = cursor.fetchone()
        if not prac or not verify_pin(pin, prac["digital_signature_pin_hash"]):
            raise ForbiddenError("Invalid digital signature PIN or unauthorized practitioner.")
            
        # 2. Enforce Deterministic Safety Invariants
        safety_state = pr["overall_safety_state"]
        if safety_state == "BLOCK":
            raise SafetyBlockedError("Cannot sign prescription: Critical safety checks failed with BLOCK status.")
            
        if safety_state == "UNKNOWN":
            if not override_rationale or len(override_rationale.strip()) < 10:
                raise SafetyUnknownError(
                    "Cannot sign: Critical safety data is UNKNOWN. Fail-closed policy requires a detailed clinical override rationale."
                )
            # Record override
            conn.execute("""
                UPDATE safety_check_runs 
                SET override_rationale = ?, overridden_by = ?
                WHERE prescription_id = ?;
            """, (override_rationale, practitioner_id, prescription_id))

        # 3. Compute Cryptographic SHA-256 Fingerprint
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        signing_payload = {
            "prescription_id": prescription_id,
            "encounter_id": pr["encounter_id"],
            "patient_id": pr["patient_id"],
            "practitioner_id": practitioner_id,
            "registration_number": prac["registration_number"],
            "version_number": pr["version_number"],
            "items": pr["items"],
            "safety_state": safety_state,
            "signed_at": timestamp_str
        }
        signature_hash = calculate_prescription_hash(signing_payload)
        
        # 4. Finalize Immutable Record
        conn.execute("""
            UPDATE prescriptions 
            SET status = 'SIGNED', signature_timestamp = ?, signature_hash = ?
            WHERE id = ?;
        """, (timestamp_str, signature_hash, prescription_id))
        
        # Transition Encounter to SIGNED
        conn.execute("""
            UPDATE encounters 
            SET status = 'SIGNED' 
            WHERE id = ?;
        """, (pr["encounter_id"],))
        
        # 5. Emit Chained Tamper-Evident Audit Event
        cursor.execute("SELECT organization_id, facility_id FROM encounters WHERE id = ?;", (pr["encounter_id"],))
        enc_info = cursor.fetchone()
        
        record_audit_event(
            conn=conn,
            organization_id=enc_info["organization_id"],
            facility_id=enc_info["facility_id"],
            actor_id=prac["user_id"],
            action_type="PRESCRIPTION_SIGNED",
            resource_type="PRESCRIPTION",
            resource_id=prescription_id,
            details={
                "signature_hash": signature_hash,
                "version": pr["version_number"],
                "items_count": len(pr["items"]),
                "safety_state": safety_state
            },
            client_ip=client_ip
        )
        
        signed_pr = PrescriptionService.get_prescription(conn, prescription_id)
        signed_pr["signature_hash"] = signature_hash
        return signed_pr

    @staticmethod
    def get_printable_prescription(conn: sqlite3.Connection, prescription_id: str) -> Dict[str, Any]:
        """Compile complete print-ready prescription document."""
        pr = PrescriptionService.get_prescription(conn, prescription_id)
        cursor = conn.cursor()
        
        # Get Patient and Facility details
        cursor.execute("""
            SELECT p.mrn, 
                   COALESCE(p.display_name, p.given_name || ' ' || COALESCE(p.family_name, '')) as patient_name,
                   COALESCE(p.date_of_birth, '') as dob, 
                   COALESCE(p.sex, 'MALE') as gender,
                   f.name as facility_name, f.address as facility_address, f.phone as facility_phone,
                   o.name as org_name
            FROM encounters e
            JOIN patients p ON e.patient_id = p.id
            JOIN facilities f ON e.facility_id = f.id
            JOIN organizations o ON e.organization_id = o.id
            WHERE e.id = ?;
        """, (pr["encounter_id"],))
        ctx = dict(cursor.fetchone())
        
        # Get Unani assessment summary
        cursor.execute("SELECT dominant_mizaj, COALESCE(clinical_reasoning, '') as clinical_interpretation FROM unani_assessments WHERE encounter_id = ?;", (pr["encounter_id"],))
        ua = cursor.fetchone()
        
        # Generate Patient Diet & Parhez Directives
        diet_sheet = None
        try:
            from matab.engines.diet_parhez_engine import generate_diet_parhez_sheet
            dom_mizaj = (ua["dominant_mizaj"] if ua else "BALGHAMI").split(" ")[0].upper()
            diet_sheet = generate_diet_parhez_sheet(dominant_mizaj=dom_mizaj)
        except Exception:
            pass

        # Check Classical Musleh & Badraqa Guidance
        musleh_badraqa = None
        try:
            from matab.engines.musleh_badraqa_engine import analyze_prescription_musleh_and_badraqa
            musleh_badraqa = analyze_prescription_musleh_and_badraqa(pr.get("items", []))
        except Exception:
            pass

        return {
            "prescription": pr,
            "diet_parhez": diet_sheet,
            "musleh_and_badraqa": musleh_badraqa,
            "patient": {
                "mrn": ctx["mrn"],
                "name": ctx["patient_name"].strip(),
                "gender": ctx["gender"],
                "dob": ctx["dob"],
                "phone": ctx.get("phone", "9876543210")
            },
            "facility": {
                "org_name": ctx["org_name"],
                "facility_name": ctx["facility_name"],
                "address": ctx["facility_address"],
                "phone": ctx["facility_phone"]
            },
            "unani_summary": dict(ua) if ua else None,
            "verification": {
                "is_signed": pr["status"] == "SIGNED",
                "signature_hash": pr["signature_hash"],
                "signed_at": pr["signature_timestamp"],
                "hakeem_name": pr["hakeem_name"],
                "reg_no": pr["registration_number"],
                "council": pr["registration_council"]
            }
        }

    @staticmethod
    def format_whatsapp_prescription(conn: sqlite3.Connection, prescription_id: str) -> Dict[str, Any]:
        """Compile a clean, formatted text prescription ready for 1-click WhatsApp dispatch."""
        p_doc = PrescriptionService.get_printable_prescription(conn, prescription_id)
        pr = p_doc["prescription"]
        pt = p_doc["patient"]
        fc = p_doc["facility"]
        dp = p_doc.get("diet_parhez")
        mb = p_doc.get("musleh_and_badraqa")
        
        lines = [
            f"🌿 *{fc.get('org_name', 'ZAYVORA HEALTH MATAB')}*",
            f"📞 Helpline: {fc.get('phone', 'Clinic')}",
            "────────────────────────",
            f"👤 *Mariz ka Naam:* {pt['name']} (MRN: {pt['mrn']})",
            f"🩺 *Hakeem Sahab:* {p_doc['verification'].get('hakeem_name', 'Consultant Hakeem')} ({p_doc['verification'].get('reg_no', '')})",
            f"📅 *Tareekh:* {str(pr.get('created_at', ''))[:10]}",
            "────────────────────────",
            "💊 *TAJWEEZ-E-NUSKHA (Prescription):*"
        ]
        
        for idx, it in enumerate(pr.get("items", []), 1):
            name = it.get("item_name") or it.get("custom_name") or "Dawa"
            dose = f"{it.get('dose_amount', '1')} {it.get('dose_unit', 'g/chammach')}"
            freq = it.get("frequency", "Subah-Sham")
            dur = f"{it.get('duration_days', 7)} Din"
            anupan = it.get("anupan_vehicle") or "Neem garm pani"
            lines.append(f"*{idx}. {name}*")
            lines.append(f"   • Miqdar: {dose} ({freq} - {dur})")
            lines.append(f"   • Lene ka tareeqa: {anupan} ke sath")
            
        if mb and mb.get("recommended_badraqa"):
            lines.append("")
            lines.append(f"🥛 *Khaas Badraqa (Vehicle):* {mb['recommended_badraqa']['preferred_badraqa']}")

        if dp:
            lines.append("────────────────────────")
            lines.append(f"🥗 *PARHEZ & GHIYAT (Mizaj: {dp.get('mizaj', '')}):*")
            lines.append(f"• *Mamnoo (Na Khayein):* {', '.join(dp['foods_to_avoid'][:4])}")
            lines.append(f"• *Mufeed (Zaroor Khayein):* {', '.join(dp['foods_to_favor'][:4])}")

        lines.extend([
            "────────────────────────",
            "⚠️ *Zaroori Note:* Dawa waqt par lein aur parhez ka khas khayal rakhein.",
            "Shifa-e-Kamilah ki Duaon ke sath.",
            f"Digital Hash: {(p_doc['verification'].get('signature_hash') or '')[:16]}..."
        ])
        
        full_text = "\n".join(lines)
        import urllib.parse
        encoded_text = urllib.parse.quote(full_text)
        phone = pt.get("phone", "").replace("+", "").replace(" ", "").replace("-", "")
        whatsapp_url = f"https://wa.me/{phone}?text={encoded_text}" if phone else f"https://wa.me/?text={encoded_text}"
        
        return {
            "prescription_id": prescription_id,
            "patient_phone": phone,
            "message_text": full_text,
            "whatsapp_url": whatsapp_url
        }
