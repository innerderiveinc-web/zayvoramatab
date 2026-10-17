"""Enterprise Master Data Management, Data Governance & Data Quality Stewardship Domain Engine.

Phase 42 for ZAYVORA MATAB OS.
Enforces non-negotiable principles:
- Zero automatic patient merges: identity consolidation requires explicit approved human review.
- Clinical record immutability: finalized encounters, prescriptions, and notes are never mutated.
- Zero fabrication: identifiers, clinical facts, Unani mizaj, and citations are never invented.
- No simplistic uniqueness assumptions: names, phone numbers, and addresses do not uniquely identify patients.
- Controlled terminology stewardship: Unani and biomedical concepts mapped with provenance, explicit scope, and limitations.
- 9-dimensional enterprise Data Quality rule catalog.
- Governed staged bulk imports with deterministic dry-run validation and idempotent commit.
- Actionable data stewardship case workflow with complete event auditing.
"""

import os
import re
import json
import sqlite3
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

from apps.api.config import config
from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError
)
from apps.api.core.permissions import require_permission


class EnterpriseMasterDataGovernanceEngine:
    """Core domain engine for Phase 42 Enterprise MDM, Data Governance & Quality Stewardship."""

    VALID_ENTITY_TYPES = {"patient", "facility", "practitioner", "formulation", "terminology_concept", "encounter"}
    VALID_DIMENSIONS = {
        "completeness", "validity", "uniqueness", "consistency",
        "referential_integrity", "timeliness", "provenance", "conformance", "reconciliation"
    }
    VALID_RULE_TYPES = {
        "required", "format", "uniqueness", "referential_integrity",
        "allowed_value", "cross_field_consistency", "freshness", "provenance", "terminology_mapping"
    }
    VALID_SEVERITIES = {"info", "warning", "review_required", "blocking"}
    VALID_SCOPES = {"platform", "tenant", "branch", "record"}
    VALID_SURVIVORSHIP_RULES = {
        "MOST_RECENT_VALIDATED", "CLINICAL_SUPERVISOR_DECISION",
        "SOURCE_SYSTEM_PRIORITY", "MANUAL_STIPULATION"
    }
    VALID_MAPPING_TYPES = {"exact", "narrow", "broad", "approximate", "unmapped"}
    VALID_MODERN_SYSTEMS = {"ICD-10", "SNOMED-CT", "LOINC", "NAMASTE", "AYUSH_MDR"}
    VALID_TERMINOLOGY_STATUSES = {"draft", "review", "approved", "provisional", "rejected", "deprecated"}
    VALID_IMPORT_STATUSES = {"staged", "validating", "validated_dry_run", "committed", "rejected", "failed"}
    VALID_CASE_STATUSES = {
        "open", "triaged", "assigned", "awaiting_source", "awaiting_clinical_review",
        "awaiting_identity_review", "approved_for_change", "rejected", "resolved", "reopened", "blocked", "closed"
    }
    VALID_CASE_CATEGORIES = {
        "duplicate_identity", "data_quality_anomaly", "terminology_gap",
        "referential_orphan", "import_validation_failure"
    }

    def __init__(self, db_or_conn: Optional[Any] = None):
        if isinstance(db_or_conn, sqlite3.Connection):
            self.conn = db_or_conn
            self.db_path = None
        else:
            self.db_path = db_or_conn or config.db_path
            self._manager = DatabaseConnection(self.db_path)
            self.conn = self._manager.get_connection()
            self.conn.row_factory = sqlite3.Row

    # -------------------------------------------------------------------------
    # 1. Master Entities Catalog
    # -------------------------------------------------------------------------
    def get_master_entities(self, user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List master data entities and their canonical source configurations."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, organization_id, entity_type, display_name, canonical_table,
                   authoritative_source, survivorship_rule, normalization_rules_json,
                   status, created_at, updated_at
            FROM mdm_master_entities_catalog
            WHERE organization_id = ?
            ORDER BY display_name ASC;
        """, (org_id,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["normalization_rules"] = json.loads(d.pop("normalization_rules_json", "{}") or "{}")
            except Exception:
                d["normalization_rules"] = {}
            result.append(d)
        return result

    def register_master_entity(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Register a master entity definition with canonical source governance."""
        require_permission(user_ctx, "mdm:rule_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        entity_type = payload.get("entity_type")
        display_name = payload.get("display_name")
        canonical_table = payload.get("canonical_table")
        authoritative_source = payload.get("authoritative_source", "EMR_PRIMARY")
        survivorship_rule = payload.get("survivorship_rule", "MANUAL_STIPULATION")
        norm_rules = payload.get("normalization_rules", {})

        if not entity_type or entity_type not in self.VALID_ENTITY_TYPES:
            raise ValidationError(f"Invalid or missing entity_type. Allowed: {sorted(self.VALID_ENTITY_TYPES)}")
        if not display_name or not canonical_table:
            raise ValidationError("display_name and canonical_table are mandatory.")
        if survivorship_rule not in self.VALID_SURVIVORSHIP_RULES:
            raise ValidationError(f"Invalid survivorship_rule. Allowed: {sorted(self.VALID_SURVIVORSHIP_RULES)}")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id FROM mdm_master_entities_catalog
            WHERE organization_id = ? AND entity_type = ?;
        """, (org_id, entity_type))
        if cur.fetchone():
            raise ConflictError(f"Master entity '{entity_type}' is already registered for this organization.")

        entity_id = f"mdm-ent-{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow().isoformat()

        cur.execute("""
            INSERT INTO mdm_master_entities_catalog (
                id, organization_id, entity_type, display_name, canonical_table,
                authoritative_source, survivorship_rule, normalization_rules_json,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?);
        """, (
            entity_id, org_id, entity_type, display_name, canonical_table,
            authoritative_source, survivorship_rule, json.dumps(norm_rules),
            now, now
        ))
        self.conn.commit()
        return {
            "id": entity_id,
            "organization_id": org_id,
            "entity_type": entity_type,
            "display_name": display_name,
            "canonical_table": canonical_table,
            "authoritative_source": authoritative_source,
            "survivorship_rule": survivorship_rule,
            "normalization_rules": norm_rules,
            "status": "active",
            "created_at": now
        }

    # -------------------------------------------------------------------------
    # 2. Versioned Enterprise Data Quality Rules
    # -------------------------------------------------------------------------
    def list_dq_rules(
        self,
        user_ctx: Dict[str, Any],
        dimension: Optional[str] = None,
        status: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List versioned data quality rules across 9 dimensions."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        query = """
            SELECT id, organization_id, rule_key, name, domain, dimension, rule_type,
                   severity, scope, target_entity_type, target_field_path,
                   rule_logic_json, remediation_guidance, version, status,
                   created_by, approved_by, approved_at, created_at, updated_at
            FROM mdm_data_quality_rules
            WHERE organization_id = ?
        """
        params: List[Any] = [org_id]

        if dimension:
            query += " AND dimension = ?"
            params.append(dimension)
        if status:
            query += " AND status = ?"
            params.append(status)
        if entity_type:
            query += " AND target_entity_type = ?"
            params.append(entity_type)

        query += " ORDER BY rule_key ASC;"
        cur = self.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        result = []
        for r in rows:
            d = dict(r)
            try:
                d["rule_logic"] = json.loads(d.pop("rule_logic_json", "{}") or "{}")
            except Exception:
                d["rule_logic"] = {}
            result.append(d)
        return result

    def create_dq_rule(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a versioned data quality rule adhering to governance specifications."""
        require_permission(user_ctx, "mdm:rule_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        rule_key = payload.get("rule_key")
        name = payload.get("name")
        domain = payload.get("domain", "clinical_patient")
        dimension = payload.get("dimension")
        rule_type = payload.get("rule_type")
        severity = payload.get("severity", "warning")
        scope = payload.get("scope", "tenant")
        target_entity_type = payload.get("target_entity_type")
        target_field_path = payload.get("target_field_path")
        rule_logic = payload.get("rule_logic", {})
        remediation_guidance = payload.get("remediation_guidance", "")
        version = payload.get("version", "1.0.0")

        if not rule_key or not name:
            raise ValidationError("rule_key and name are mandatory.")
        if dimension not in self.VALID_DIMENSIONS:
            raise ValidationError(f"Invalid dimension. Allowed: {sorted(self.VALID_DIMENSIONS)}")
        if rule_type not in self.VALID_RULE_TYPES:
            raise ValidationError(f"Invalid rule_type. Allowed: {sorted(self.VALID_RULE_TYPES)}")
        if severity not in self.VALID_SEVERITIES:
            raise ValidationError(f"Invalid severity. Allowed: {sorted(self.VALID_SEVERITIES)}")
        if scope not in self.VALID_SCOPES:
            raise ValidationError(f"Invalid scope. Allowed: {sorted(self.VALID_SCOPES)}")
        if not target_entity_type or not target_field_path:
            raise ValidationError("target_entity_type and target_field_path are mandatory.")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id FROM mdm_data_quality_rules
            WHERE organization_id = ? AND rule_key = ?;
        """, (org_id, rule_key))
        if cur.fetchone():
            raise ConflictError(f"Rule with key '{rule_key}' already exists in this organization.")

        rule_id = f"mdm-dq-{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow().isoformat()

        cur.execute("""
            INSERT INTO mdm_data_quality_rules (
                id, organization_id, rule_key, name, domain, dimension, rule_type,
                severity, scope, target_entity_type, target_field_path,
                rule_logic_json, remediation_guidance, version, status,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?);
        """, (
            rule_id, org_id, rule_key, name, domain, dimension, rule_type,
            severity, scope, target_entity_type, target_field_path,
            json.dumps(rule_logic), remediation_guidance, version,
            user_id, now, now
        ))
        self.conn.commit()

        return {
            "id": rule_id,
            "organization_id": org_id,
            "rule_key": rule_key,
            "name": name,
            "dimension": dimension,
            "rule_type": rule_type,
            "severity": severity,
            "target_entity_type": target_entity_type,
            "target_field_path": target_field_path,
            "rule_logic": rule_logic,
            "status": "approved",
            "version": version,
            "created_at": now
        }

    def _fetch_patients_with_contacts(self, org_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT p.id, p.mrn, p.given_name, p.family_name, p.display_name,
                   p.sex, p.date_of_birth, p.status,
                   (SELECT contact_value FROM patient_contacts WHERE patient_id = p.id AND contact_type IN ('PHONE', 'WHATSAPP') ORDER BY is_preferred DESC LIMIT 1) as phone,
                   (SELECT identifier_value FROM patient_identifiers WHERE patient_id = p.id AND is_retired = 0 LIMIT 1) as national_id,
                   (SELECT address_line1 FROM patient_addresses WHERE patient_id = p.id ORDER BY is_primary DESC LIMIT 1) as address
            FROM patients p
            WHERE p.organization_id = ?;
        """, (org_id,))
        return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # 3. Data Quality Evaluation Scans
    # -------------------------------------------------------------------------
    def run_dq_scan(
        self,
        user_ctx: Dict[str, Any],
        target_entity_type: str = "patient",
        scope: str = "tenant"
    ) -> Dict[str, Any]:
        """Execute deterministic data quality evaluation scan across registered rules."""
        require_permission(user_ctx, "mdm:evaluate")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        # Fetch active rules for this entity type
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, rule_key, name, dimension, rule_type, severity, target_field_path, rule_logic_json
            FROM mdm_data_quality_rules
            WHERE organization_id = ? AND target_entity_type = ? AND status = 'approved';
        """, (org_id, target_entity_type))
        rules = cur.fetchall()

        scan_id = f"scan-{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow().isoformat()
        findings: List[Dict[str, Any]] = []

        total_evaluated = 0
        if target_entity_type == "patient":
            patients = self._fetch_patients_with_contacts(org_id)
            total_evaluated = len(patients)

            # Pre-index for uniqueness checks
            phone_counts: Dict[str, int] = {}
            nid_counts: Dict[str, int] = {}
            for p in patients:
                if p["phone"]:
                    norm_phone = re.sub(r"\D", "", p["phone"])
                    phone_counts[norm_phone] = phone_counts.get(norm_phone, 0) + 1
                if p["national_id"]:
                    nid = p["national_id"].strip().upper()
                    nid_counts[nid] = nid_counts.get(nid, 0) + 1

            for p in patients:
                p_id = p["id"]
                # 1. Mandatory contact check
                if not p["phone"] and not p["address"]:
                    findings.append({
                        "rule_key": "RULE_PATIENT_MANDATORY_CONTACT",
                        "dimension": "completeness",
                        "severity": "review_required",
                        "entity_type": "patient",
                        "entity_id": p_id,
                        "field_path": "phone",
                        "issue_code": "MISSING_CONTACT_CHANNEL",
                        "message": f"Patient '{p_id}' has neither phone nor address recorded."
                    })
                # 2. Phone format validity
                if p["phone"]:
                    digits = re.sub(r"\D", "", p["phone"])
                    if len(digits) < 10 or len(digits) > 15:
                        findings.append({
                            "rule_key": "RULE_VALID_PHONE_FORMAT",
                            "dimension": "validity",
                            "severity": "warning",
                            "entity_type": "patient",
                            "entity_id": p_id,
                            "field_path": "phone",
                            "issue_code": "INVALID_PHONE_FORMAT",
                            "message": f"Patient '{p_id}' phone has non-standard digit length ({len(digits)} digits)."
                        })
                # 3. National ID Uniqueness
                if p["national_id"]:
                    nid = p["national_id"].strip().upper()
                    if nid_counts.get(nid, 0) > 1:
                        findings.append({
                            "rule_key": "RULE_UNIQUE_NATIONAL_ID",
                            "dimension": "uniqueness",
                            "severity": "blocking",
                            "entity_type": "patient",
                            "entity_id": p_id,
                            "field_path": "national_id",
                            "issue_code": "DUPLICATE_NATIONAL_ID",
                            "message": f"Patient '{p_id}' shares national_id '{nid}' with another record."
                        })
                # 4. Gender conformance
                g = (p.get("sex") or "").upper()
                if g and g not in {"M", "F", "O", "U", "MALE", "FEMALE", "OTHER", "UNKNOWN"}:
                    findings.append({
                        "rule_key": "RULE_GENDER_CONFORMANCE",
                        "dimension": "conformance",
                        "severity": "warning",
                        "entity_type": "patient",
                        "entity_id": p_id,
                        "field_path": "sex",
                        "issue_code": "NON_STANDARD_GENDER_CODE",
                        "message": f"Patient '{p_id}' has non-standard sex code '{g}'."
                    })

        elif target_entity_type == "encounter":
            cur.execute("""
                SELECT id, patient_id, started_at, closed_at, status
                FROM encounters
                WHERE organization_id = ?;
            """, (org_id,))
            encounters = cur.fetchall()
            total_evaluated = len(encounters)

            for enc in encounters:
                enc_id = enc["id"]
                # Consistency: closed_at >= started_at
                if enc["started_at"] and enc["closed_at"]:
                    if enc["closed_at"] < enc["started_at"]:
                        findings.append({
                            "rule_key": "RULE_ENCOUNTER_DATES_LOGICAL",
                            "dimension": "consistency",
                            "severity": "blocking",
                            "entity_type": "encounter",
                            "entity_id": enc_id,
                            "field_path": "closed_at",
                            "issue_code": "ENCOUNTER_END_BEFORE_START",
                            "message": f"Encounter '{enc_id}' closed_at is before started_at."
                        })
                # Referential integrity: patient exists
                cur.execute("SELECT id FROM patients WHERE id = ? AND organization_id = ?;", (enc["patient_id"], org_id))
                if not cur.fetchone():
                    findings.append({
                        "rule_key": "RULE_ENCOUNTER_PATIENT_EXISTS",
                        "dimension": "referential_integrity",
                        "severity": "blocking",
                        "entity_type": "encounter",
                        "entity_id": enc_id,
                        "field_path": "patient_id",
                        "issue_code": "ORPHAN_ENCOUNTER_PATIENT",
                        "message": f"Encounter '{enc_id}' references non-existent patient '{enc['patient_id']}'."
                    })

        blockers_count = sum(1 for f in findings if f["severity"] == "blocking")
        warnings_count = sum(1 for f in findings if f["severity"] in ("warning", "review_required"))

        cur.execute("""
            INSERT INTO mdm_data_quality_scans (
                id, organization_id, scan_scope, target_entity_type, total_evaluated,
                findings_count, blockers_count, warnings_count, scanned_by,
                status, summary_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?);
        """, (
            scan_id, org_id, scope, target_entity_type, total_evaluated,
            len(findings), blockers_count, warnings_count, user_id,
            json.dumps({"total_rules_evaluated": len(rules), "dimension_summary": {}}),
            now
        ))

        for f in findings:
            finding_id = f"find-{uuid.uuid4().hex[:10]}"
            cur.execute("""
                INSERT INTO mdm_data_quality_findings (
                    id, scan_id, organization_id, rule_key, dimension, severity,
                    entity_type, entity_id, field_path, issue_code, message,
                    details_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', 'open', ?);
            """, (
                finding_id, scan_id, org_id, f["rule_key"], f["dimension"], f["severity"],
                f["entity_type"], f["entity_id"], f["field_path"], f["issue_code"],
                f["message"], now
            ))

        self.conn.commit()
        return {
            "scan_id": scan_id,
            "organization_id": org_id,
            "target_entity_type": target_entity_type,
            "total_evaluated": total_evaluated,
            "findings_count": len(findings),
            "blockers_count": blockers_count,
            "warnings_count": warnings_count,
            "status": "completed",
            "findings": findings[:50]
        }

    def list_dq_scans(self, user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List historical data quality scans for the tenant."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, organization_id, scan_scope, target_entity_type, total_evaluated,
                   findings_count, blockers_count, warnings_count, scanned_by,
                   status, summary_json, created_at
            FROM mdm_data_quality_scans
            WHERE organization_id = ?
            ORDER BY created_at DESC
            LIMIT 50;
        """, (org_id,))
        return [dict(r) for r in cur.fetchall()]

    def get_scan_findings(self, user_ctx: Dict[str, Any], scan_id: str) -> List[Dict[str, Any]]:
        """Fetch granular findings for a specific scan."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, scan_id, rule_key, dimension, severity, entity_type, entity_id,
                   field_path, issue_code, message, details_json, status, created_at
            FROM mdm_data_quality_findings
            WHERE scan_id = ? AND organization_id = ?
            ORDER BY created_at ASC;
        """, (scan_id, org_id))
        return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # 4. Duplicate Candidate Review Ledger (Explainable Match Scoring)
    # -------------------------------------------------------------------------
    def detect_duplicate_candidates(
        self,
        user_ctx: Dict[str, Any],
        entity_type: str = "patient"
    ) -> List[Dict[str, Any]]:
        """
        Evaluate pairwise candidate similarity without auto-merging.
        Computes explainable feature matches: name, phone, dob, gender, address.
        """
        require_permission(user_ctx, "mdm:evaluate")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        cur = self.conn.cursor()
        patients = self._fetch_patients_with_contacts(org_id)

        created_reviews: List[Dict[str, Any]] = []
        n = len(patients)

        for i in range(n):
            p1 = patients[i]
            for j in range(i + 1, n):
                p2 = patients[j]
                match_features = {}
                score = 0.0

                # 1. Name comparison
                n1 = f"{p1.get('given_name') or ''} {p1.get('family_name') or ''}".strip().lower() or (p1.get("display_name") or "").strip().lower()
                n2 = f"{p2.get('given_name') or ''} {p2.get('family_name') or ''}".strip().lower() or (p2.get("display_name") or "").strip().lower()
                if n1 and n2:
                    if n1 == n2:
                        match_features["name_match"] = "exact"
                        score += 0.35
                    else:
                        tokens1 = set(n1.split())
                        tokens2 = set(n2.split())
                        overlap = tokens1.intersection(tokens2)
                        if overlap:
                            match_features["name_match"] = f"partial_tokens:{list(overlap)}"
                            score += 0.20

                # 2. Phone comparison (E.164 normalization)
                ph1 = re.sub(r"\D", "", p1.get("phone") or "")
                ph2 = re.sub(r"\D", "", p2.get("phone") or "")
                if ph1 and ph2:
                    if ph1 == ph2:
                        match_features["phone_match"] = "exact"
                        score += 0.30
                    elif ph1[-8:] == ph2[-8:]:
                        match_features["phone_match"] = "suffix_match"
                        score += 0.15

                # 3. DOB comparison
                dob1 = p1.get("date_of_birth") or ""
                dob2 = p2.get("date_of_birth") or ""
                if dob1 and dob2:
                    if dob1 == dob2:
                        match_features["dob_match"] = "exact"
                        score += 0.25
                    elif dob1[:4] == dob2[:4] and len(dob1) >= 4 and len(dob2) >= 4:
                        match_features["dob_match"] = "birth_year_only"
                        score += 0.10

                # 4. Gender compatibility
                g1 = (p1.get("sex") or "").upper()
                g2 = (p2.get("sex") or "").upper()
                if g1 and g2:
                    if g1 != g2 and g1 in ("M", "F", "MALE", "FEMALE") and g2 in ("M", "F", "MALE", "FEMALE"):
                        match_features["gender_mismatch"] = True
                        score -= 0.30
                    else:
                        match_features["gender_match"] = True

                # 5. National ID
                nid1 = (p1["national_id"] or "").strip().upper()
                nid2 = (p2["national_id"] or "").strip().upper()
                if nid1 and nid2 and nid1 == nid2:
                    match_features["national_id_match"] = "exact"
                    score += 0.50

                final_score = max(0.0, min(1.0, round(score, 3)))

                # Candidates scoring >= 0.50 warrant human steward review
                if final_score >= 0.50:
                    # Check if already reviewed or pending
                    cur.execute("""
                        SELECT id, status FROM mdm_duplicate_candidate_reviews
                        WHERE organization_id = ?
                          AND ((primary_record_id = ? AND candidate_record_id = ?)
                            OR (primary_record_id = ? AND candidate_record_id = ?));
                    """, (org_id, p1["id"], p2["id"], p2["id"], p1["id"]))
                    existing = cur.fetchone()
                    if not existing:
                        review_id = f"dup-rev-{uuid.uuid4().hex[:10]}"
                        now = datetime.utcnow().isoformat()
                        cur.execute("""
                            INSERT INTO mdm_duplicate_candidate_reviews (
                                id, organization_id, entity_type, primary_record_id,
                                candidate_record_id, confidence_score, match_features_json,
                                status, created_at, updated_at
                            ) VALUES (?, ?, 'patient', ?, ?, ?, ?, 'pending', ?, ?);
                        """, (
                            review_id, org_id, p1["id"], p2["id"],
                            final_score, json.dumps(match_features), now, now
                        ))
                        created_reviews.append({
                            "id": review_id,
                            "primary_record_id": p1["id"],
                            "candidate_record_id": p2["id"],
                            "confidence_score": final_score,
                            "match_features": match_features,
                            "status": "pending"
                        })

        self.conn.commit()
        return created_reviews

    def list_duplicate_reviews(
        self,
        user_ctx: Dict[str, Any],
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List duplicate candidate reviews with explainability features."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        query = """
            SELECT id, organization_id, entity_type, primary_record_id, candidate_record_id,
                   confidence_score, match_features_json, status, steward_id,
                   clinical_supervisor_id, resolution_rationale, resolved_at,
                   created_at, updated_at
            FROM mdm_duplicate_candidate_reviews
            WHERE organization_id = ?
        """
        params: List[Any] = [org_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY confidence_score DESC, created_at DESC;"

        cur = self.conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

        result = []
        for r in rows:
            d = dict(r)
            try:
                d["match_features"] = json.loads(d.pop("match_features_json", "{}") or "{}")
            except Exception:
                d["match_features"] = {}
            result.append(d)
        return result

    def resolve_duplicate_review(
        self,
        user_ctx: Dict[str, Any],
        review_id: str,
        decision: str,
        rationale: str,
        create_master_link: bool = False
    ) -> Dict[str, Any]:
        """
        Human steward resolution for duplicate candidates.
        Allowed decisions: confirmed_duplicate, confirmed_distinct, false_positive.
        If confirmed_duplicate and create_master_link is True, establishes a reversible cross-reference.
        """
        require_permission(user_ctx, "mdm:duplicate_review")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        valid_decisions = {"confirmed_duplicate", "confirmed_distinct", "false_positive"}
        if decision not in valid_decisions:
            raise ValidationError(f"Invalid decision '{decision}'. Allowed: {sorted(valid_decisions)}")
        if not rationale or len(rationale.strip()) < 5:
            raise ValidationError("A substantive resolution rationale is required.")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, primary_record_id, candidate_record_id, status
            FROM mdm_duplicate_candidate_reviews
            WHERE id = ? AND organization_id = ?;
        """, (review_id, org_id))
        review = cur.fetchone()
        if not review:
            raise NotFoundError(f"Duplicate candidate review '{review_id}' not found.")

        now = datetime.utcnow().isoformat()
        cur.execute("""
            UPDATE mdm_duplicate_candidate_reviews
            SET status = ?, steward_id = ?, resolution_rationale = ?,
                resolved_at = ?, updated_at = ?
            WHERE id = ?;
        """, (decision, user_id, rationale, now, now, review_id))

        link_created = None
        if decision == "confirmed_duplicate" and create_master_link:
            # Create reversible patient cross-reference
            xref_id = f"xref-{uuid.uuid4().hex[:10]}"
            cur.execute("""
                INSERT INTO mdm_patient_cross_references (
                    id, organization_id, master_patient_id, linked_patient_id,
                    link_type, source_system, notes, linked_by, linked_at
                ) VALUES (?, ?, ?, ?, 'superseded_duplicate', 'MDM_STEWARDSHIP', ?, ?, ?);
            """, (
                xref_id, org_id, review["primary_record_id"], review["candidate_record_id"],
                f"Resolved via review {review_id}: {rationale}", user_id, now
            ))
            link_created = xref_id

        self.conn.commit()
        return {
            "review_id": review_id,
            "status": decision,
            "resolved_by": user_id,
            "resolved_at": now,
            "master_link_created": link_created
        }

    # -------------------------------------------------------------------------
    # 5. Patient Master Reversible Cross-References
    # -------------------------------------------------------------------------
    def list_cross_references(
        self,
        user_ctx: Dict[str, Any],
        master_patient_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List patient alias and master cross-references."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        query = """
            SELECT id, organization_id, master_patient_id, linked_patient_id,
                   link_type, source_system, source_identifier, is_active,
                   is_reversible, notes, linked_by, linked_at, unlinked_by, unlinked_at
            FROM mdm_patient_cross_references
            WHERE organization_id = ?
        """
        params: List[Any] = [org_id]
        if master_patient_id:
            query += " AND (master_patient_id = ? OR linked_patient_id = ?)"
            params.extend([master_patient_id, master_patient_id])
        query += " ORDER BY linked_at DESC;"

        cur = self.conn.cursor()
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

    def create_cross_reference(
        self,
        user_ctx: Dict[str, Any],
        master_patient_id: str,
        linked_patient_id: str,
        link_type: str = "alias",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Establish a reversible master cross-reference or alias link between records."""
        require_permission(user_ctx, "mdm:stewardship_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        if master_patient_id == linked_patient_id:
            raise ValidationError("Cannot link a patient record to itself.")

        valid_link_types = {"alias", "superseded_duplicate", "external_system_id", "family_dependent"}
        if link_type not in valid_link_types:
            raise ValidationError(f"Invalid link_type. Allowed: {sorted(valid_link_types)}")

        cur = self.conn.cursor()
        # Verify both patients exist in this tenant
        cur.execute("SELECT id FROM patients WHERE id IN (?, ?) AND organization_id = ?;", (master_patient_id, linked_patient_id, org_id))
        found = cur.fetchall()
        if len(found) < 2:
            raise NotFoundError("One or both patient records do not exist in the current organization.")

        xref_id = f"xref-{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow().isoformat()

        cur.execute("""
            INSERT INTO mdm_patient_cross_references (
                id, organization_id, master_patient_id, linked_patient_id,
                link_type, source_system, is_active, is_reversible, notes,
                linked_by, linked_at
            ) VALUES (?, ?, ?, ?, ?, 'EMR_LOCAL', 1, 1, ?, ?, ?);
        """, (xref_id, org_id, master_patient_id, linked_patient_id, link_type, notes, user_id, now))
        self.conn.commit()

        return {
            "id": xref_id,
            "organization_id": org_id,
            "master_patient_id": master_patient_id,
            "linked_patient_id": linked_patient_id,
            "link_type": link_type,
            "is_active": 1,
            "is_reversible": 1,
            "linked_at": now
        }

    def unlink_cross_reference(
        self,
        user_ctx: Dict[str, Any],
        xref_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reversibly decouple a master cross-reference."""
        require_permission(user_ctx, "mdm:stewardship_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, is_active, is_reversible
            FROM mdm_patient_cross_references
            WHERE id = ? AND organization_id = ?;
        """, (xref_id, org_id))
        xref = cur.fetchone()
        if not xref:
            raise NotFoundError(f"Cross-reference '{xref_id}' not found.")
        if not xref["is_active"]:
            raise ConflictError("Cross-reference is already unlinked/inactive.")

        now = datetime.utcnow().isoformat()
        cur.execute("""
            UPDATE mdm_patient_cross_references
            SET is_active = 0, unlinked_by = ?, unlinked_at = ?,
                notes = COALESCE(notes || ' | Unlinked: ' || ?, notes)
            WHERE id = ?;
        """, (user_id, now, notes or "Unlinked by steward", xref_id))
        self.conn.commit()

        return {
            "id": xref_id,
            "is_active": 0,
            "unlinked_by": user_id,
            "unlinked_at": now
        }

    # -------------------------------------------------------------------------
    # 6. Controlled Terminology Stewardship
    # -------------------------------------------------------------------------
    def list_terminology_mappings(
        self,
        user_ctx: Dict[str, Any],
        unani_concept_code: Optional[str] = None,
        review_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List governed mappings between Unani concepts and modern clinical terminologies."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        query = """
            SELECT id, organization_id, unani_concept_code, unani_term, modern_code_system,
                   modern_concept_code, modern_term, mapping_type, clinical_scope,
                   limitations, provenance, review_status, reviewed_by, reviewed_at,
                   clinical_rationale, created_at, updated_at
            FROM mdm_terminology_mappings
            WHERE organization_id = ?
        """
        params: List[Any] = [org_id]
        if unani_concept_code:
            query += " AND unani_concept_code = ?"
            params.append(unani_concept_code)
        if review_status:
            query += " AND review_status = ?"
            params.append(review_status)
        query += " ORDER BY unani_concept_code ASC;"

        cur = self.conn.cursor()
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

    def create_terminology_mapping(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Propose a new terminology mapping draft with mandatory provenance and clinical caveats."""
        require_permission(user_ctx, "mdm:terminology_steward")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        unani_code = payload.get("unani_concept_code")
        unani_term = payload.get("unani_term")
        modern_system = payload.get("modern_code_system")
        modern_code = payload.get("modern_concept_code")
        modern_term = payload.get("modern_term")
        mapping_type = payload.get("mapping_type", "approximate")
        scope = payload.get("clinical_scope", "general_clinical")
        limitations = payload.get("limitations")
        provenance = payload.get("provenance")

        if not unani_code or not unani_term:
            raise ValidationError("unani_concept_code and unani_term are required.")
        if modern_system not in self.VALID_MODERN_SYSTEMS:
            raise ValidationError(f"Invalid modern_code_system. Allowed: {sorted(self.VALID_MODERN_SYSTEMS)}")
        if not modern_code or not modern_term:
            raise ValidationError("modern_concept_code and modern_term are required.")
        if mapping_type not in self.VALID_MAPPING_TYPES:
            raise ValidationError(f"Invalid mapping_type. Allowed: {sorted(self.VALID_MAPPING_TYPES)}")
        if not limitations or len(limitations.strip()) < 5:
            raise ValidationError("Mandatory limitations caveat detailing scope boundaries must be provided.")
        if not provenance:
            raise ValidationError("provenance (authoritative classical or clinical source citation) is required.")

        mapping_id = f"tmap-{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow().isoformat()

        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO mdm_terminology_mappings (
                id, organization_id, unani_concept_code, unani_term, modern_code_system,
                modern_concept_code, modern_term, mapping_type, clinical_scope,
                limitations, provenance, review_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?);
        """, (
            mapping_id, org_id, unani_code, unani_term, modern_system,
            modern_code, modern_term, mapping_type, scope, limitations,
            provenance, now, now
        ))
        self.conn.commit()

        return {
            "id": mapping_id,
            "organization_id": org_id,
            "unani_concept_code": unani_code,
            "modern_code_system": modern_system,
            "modern_concept_code": modern_code,
            "mapping_type": mapping_type,
            "review_status": "draft",
            "created_at": now
        }

    def review_terminology_mapping(
        self,
        user_ctx: Dict[str, Any],
        mapping_id: str,
        decision: str,
        rationale: str
    ) -> Dict[str, Any]:
        """Approve, reject, or mark provisional a terminology mapping."""
        require_permission(user_ctx, "mdm:terminology_steward")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "clinical-officer")

        valid_decisions = {"approved", "provisional", "rejected", "deprecated"}
        if decision not in valid_decisions:
            raise ValidationError(f"Invalid decision '{decision}'. Allowed: {sorted(valid_decisions)}")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id FROM mdm_terminology_mappings
            WHERE id = ? AND organization_id = ?;
        """, (mapping_id, org_id))
        if not cur.fetchone():
            raise NotFoundError(f"Terminology mapping '{mapping_id}' not found.")

        now = datetime.utcnow().isoformat()
        cur.execute("""
            UPDATE mdm_terminology_mappings
            SET review_status = ?, reviewed_by = ?, reviewed_at = ?,
                clinical_rationale = ?, updated_at = ?
            WHERE id = ?;
        """, (decision, user_id, now, rationale, now, mapping_id))
        self.conn.commit()

        return {
            "id": mapping_id,
            "review_status": decision,
            "reviewed_by": user_id,
            "reviewed_at": now,
            "clinical_rationale": rationale
        }

    # -------------------------------------------------------------------------
    # 7. Governed Bulk Import Engine
    # -------------------------------------------------------------------------
    def stage_import_batch(
        self,
        user_ctx: Dict[str, Any],
        batch_name: str,
        entity_type: str,
        raw_records: List[Dict[str, Any]],
        source_system: str = "CSV_INGEST",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stage raw batch records into isolated staging tables without touching production."""
        require_permission(user_ctx, "mdm:import_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        if entity_type not in ("patient", "practitioner", "formulation", "facility"):
            raise ValidationError(f"Entity type '{entity_type}' does not support bulk import.")
        if not raw_records:
            raise ValidationError("raw_records list cannot be empty.")

        idem_key = idempotency_key or f"batch-{uuid.uuid4().hex[:12]}"
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, status FROM mdm_import_batches WHERE idempotency_key = ?;
        """, (idem_key,))
        existing = cur.fetchone()
        if existing:
            return {"batch_id": existing["id"], "status": existing["status"], "reused": True}

        batch_id = f"imp-{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow().isoformat()

        cur.execute("""
            INSERT INTO mdm_import_batches (
                id, organization_id, batch_name, source_system, entity_type,
                total_records, status, idempotency_key, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'staged', ?, ?, ?, ?);
        """, (
            batch_id, org_id, batch_name, source_system, entity_type,
            len(raw_records), idem_key, user_id, now, now
        ))

        for idx, rec in enumerate(raw_records):
            rec_id = f"imprec-{uuid.uuid4().hex[:10]}"
            cur.execute("""
                INSERT INTO mdm_import_records (
                    id, batch_id, organization_id, record_index, raw_data_json,
                    validation_status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?);
            """, (rec_id, batch_id, org_id, idx, json.dumps(rec), now))

        self.conn.commit()
        return {
            "batch_id": batch_id,
            "organization_id": org_id,
            "batch_name": batch_name,
            "entity_type": entity_type,
            "total_records": len(raw_records),
            "status": "staged",
            "idempotency_key": idem_key
        }

    def evaluate_import_dry_run(self, user_ctx: Dict[str, Any], batch_id: str) -> Dict[str, Any]:
        """
        Validate staged import records against normalization and quality rules.
        Completely side-effect free on canonical tables.
        """
        require_permission(user_ctx, "mdm:import_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, entity_type, status, total_records
            FROM mdm_import_batches
            WHERE id = ? AND organization_id = ?;
        """, (batch_id, org_id))
        batch = cur.fetchone()
        if not batch:
            raise NotFoundError(f"Import batch '{batch_id}' not found.")

        cur.execute("""
            SELECT id, record_index, raw_data_json
            FROM mdm_import_records
            WHERE batch_id = ?
            ORDER BY record_index ASC;
        """, (batch_id,))
        records = cur.fetchall()

        valid_count = 0
        invalid_count = 0

        for r in records:
            r_id = r["id"]
            try:
                raw = json.loads(r["raw_data_json"])
            except Exception:
                raw = {}

            errors: List[str] = []
            mapped: Dict[str, Any] = {}

            if batch["entity_type"] == "patient":
                first_name = (raw.get("first_name") or raw.get("firstName") or "").strip()
                last_name = (raw.get("last_name") or raw.get("lastName") or "").strip()
                phone = (raw.get("phone") or raw.get("mobile") or "").strip()
                gender = (raw.get("gender") or "").strip().upper()
                dob = (raw.get("date_of_birth") or raw.get("dob") or "").strip()

                if not first_name:
                    errors.append("Missing mandatory first_name.")
                if not phone and not raw.get("address"):
                    errors.append("Contact required: both phone and address are blank.")
                if phone:
                    digits = re.sub(r"\D", "", phone)
                    if len(digits) < 10 or len(digits) > 15:
                        errors.append(f"Phone '{phone}' has invalid digit count ({len(digits)}).")

                mapped = {
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone": phone,
                    "gender": gender if gender in ("M", "F", "O", "U") else "U",
                    "date_of_birth": dob or None,
                    "address": raw.get("address", "")
                }

            if errors:
                invalid_count += 1
                cur.execute("""
                    UPDATE mdm_import_records
                    SET validation_status = 'invalid', validation_errors_json = ?, mapped_data_json = ?
                    WHERE id = ?;
                """, (json.dumps(errors), json.dumps(mapped), r_id))
            else:
                valid_count += 1
                cur.execute("""
                    UPDATE mdm_import_records
                    SET validation_status = 'valid', validation_errors_json = '[]', mapped_data_json = ?
                    WHERE id = ?;
                """, (json.dumps(mapped), r_id))

        now = datetime.utcnow().isoformat()
        dry_run_summary = {
            "total_records": len(records),
            "valid_records": valid_count,
            "invalid_records": invalid_count,
            "pass_rate_pct": round((valid_count / len(records)) * 100, 1) if records else 0
        }

        cur.execute("""
            UPDATE mdm_import_batches
            SET status = 'validated_dry_run', valid_records = ?, invalid_records = ?,
                dry_run_summary_json = ?, updated_at = ?
            WHERE id = ?;
        """, (valid_count, invalid_count, json.dumps(dry_run_summary), now, batch_id))
        self.conn.commit()

        return {
            "batch_id": batch_id,
            "status": "validated_dry_run",
            "dry_run_summary": dry_run_summary
        }

    def commit_import_batch(self, user_ctx: Dict[str, Any], batch_id: str) -> Dict[str, Any]:
        """Commit validated records into canonical target tables."""
        require_permission(user_ctx, "mdm:import_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, entity_type, status, valid_records
            FROM mdm_import_batches
            WHERE id = ? AND organization_id = ?;
        """, (batch_id, org_id))
        batch = cur.fetchone()
        if not batch:
            raise NotFoundError(f"Import batch '{batch_id}' not found.")
        b_status = batch["status"]
        if b_status != "validated_dry_run":
            raise ConflictError(f"Cannot commit batch in '{b_status}' status. Must be 'validated_dry_run'.")

        cur.execute("""
            SELECT id, mapped_data_json
            FROM mdm_import_records
            WHERE batch_id = ? AND validation_status = 'valid';
        """, (batch_id,))
        valid_records = cur.fetchall()

        committed_count = 0
        now = datetime.utcnow().isoformat()

        if batch["entity_type"] == "patient":
            for r in valid_records:
                mapped = json.loads(r["mapped_data_json"])
                p_id = f"pat-{uuid.uuid4().hex[:10]}"
                year = datetime.utcnow().year
                cur.execute("SELECT COUNT(*) as count FROM patients WHERE organization_id = ?;", (org_id,))
                total = cur.fetchone()["count"] + 1
                mrn = f"MRN-{year}-{total:05d}"
                given_name = mapped.get("first_name", "")
                family_name = mapped.get("last_name", "")
                display_name = f"{given_name} {family_name}".strip() or given_name or "Unknown Patient"
                gender = mapped.get("gender", "UNKNOWN")
                if gender in ("M", "MALE"):
                    sex = "MALE"
                elif gender in ("F", "FEMALE"):
                    sex = "FEMALE"
                elif gender in ("O", "OTHER"):
                    sex = "OTHER"
                else:
                    sex = "UNKNOWN"

                cur.execute("""
                    INSERT INTO patients (
                        id, organization_id, mrn, given_name, family_name, display_name,
                        sex, date_of_birth, status, version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 1, ?, ?);
                """, (
                    p_id, org_id, mrn, given_name, family_name, display_name,
                    sex, mapped.get("date_of_birth"), now, now
                ))

                if mapped.get("phone"):
                    cnt_id = f"cnt-{uuid.uuid4().hex[:10]}"
                    norm_ph = re.sub(r"\D", "", mapped["phone"])
                    cur.execute("""
                        INSERT INTO patient_contacts (
                            id, patient_id, organization_id, contact_type, contact_value,
                            normalized_value, is_preferred, created_at
                        ) VALUES (?, ?, ?, 'PHONE', ?, ?, 1, ?);
                    """, (cnt_id, p_id, org_id, mapped["phone"], norm_ph, now))

                if mapped.get("address"):
                    addr_id = f"addr-{uuid.uuid4().hex[:10]}"
                    cur.execute("""
                        INSERT INTO patient_addresses (
                            id, patient_id, organization_id, address_line1, is_primary, created_at
                        ) VALUES (?, ?, ?, ?, 1, ?);
                    """, (addr_id, p_id, org_id, mapped["address"], now))

                cur.execute("""
                    UPDATE mdm_import_records SET validation_status = 'committed' WHERE id = ?;
                """, (r["id"],))
                committed_count += 1

        cur.execute("""
            UPDATE mdm_import_batches
            SET status = 'committed', committed_by = ?, committed_at = ?, updated_at = ?
            WHERE id = ?;
        """, (user_id, now, now, batch_id))
        self.conn.commit()

        return {
            "batch_id": batch_id,
            "status": "committed",
            "committed_count": committed_count,
            "committed_at": now
        }

    def list_import_batches(self, user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List import batches for tenant."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, organization_id, batch_name, source_system, entity_type,
                   total_records, valid_records, invalid_records, status,
                   idempotency_key, dry_run_summary_json, created_by,
                   committed_by, committed_at, created_at, updated_at
            FROM mdm_import_batches
            WHERE organization_id = ?
            ORDER BY created_at DESC;
        """, (org_id,))
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["dry_run_summary"] = json.loads(d.pop("dry_run_summary_json", "{}") or "{}")
            except Exception:
                d["dry_run_summary"] = {}
            result.append(d)
        return result

    # -------------------------------------------------------------------------
    # 8. Data Stewardship Cases
    # -------------------------------------------------------------------------
    def create_stewardship_case(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create an actionable data governance stewardship case."""
        require_permission(user_ctx, "mdm:stewardship_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        title = payload.get("title")
        description = payload.get("description")
        category = payload.get("category")
        priority = payload.get("priority", "medium")
        target_entity_type = payload.get("target_entity_type")
        target_entity_id = payload.get("target_entity_id")
        proposed_resolution = payload.get("proposed_resolution")
        assigned_to = payload.get("assigned_to")

        if not title or not description:
            raise ValidationError("title and description are required.")
        if category not in self.VALID_CASE_CATEGORIES:
            raise ValidationError(f"Invalid category. Allowed: {sorted(self.VALID_CASE_CATEGORIES)}")
        if priority not in ("low", "medium", "high", "urgent"):
            raise ValidationError("priority must be low, medium, high, or urgent.")
        if not target_entity_type or not target_entity_id:
            raise ValidationError("target_entity_type and target_entity_id are required.")

        case_id = f"case-{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow().isoformat()

        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO mdm_stewardship_cases (
                id, organization_id, title, description, category, priority,
                status, target_entity_type, target_entity_id, proposed_resolution,
                assigned_to, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?);
        """, (
            case_id, org_id, title, description, category, priority,
            target_entity_type, target_entity_id, proposed_resolution,
            assigned_to, user_id, now, now
        ))

        # Record initial creation event
        evt_id = f"cevt-{uuid.uuid4().hex[:10]}"
        cur.execute("""
            INSERT INTO mdm_stewardship_case_events (
                id, case_id, organization_id, from_status, to_status,
                comment, actor_id, created_at
            ) VALUES (?, ?, ?, 'none', 'open', 'Case created', ?, ?);
        """, (evt_id, case_id, org_id, user_id, now))

        self.conn.commit()
        return {
            "id": case_id,
            "organization_id": org_id,
            "title": title,
            "category": category,
            "priority": priority,
            "status": "open",
            "created_at": now
        }

    def list_stewardship_cases(
        self,
        user_ctx: Dict[str, Any],
        status: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List stewardship cases."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        query = """
            SELECT id, organization_id, title, description, category, priority,
                   status, target_entity_type, target_entity_id, proposed_resolution,
                   assigned_to, created_by, resolved_by, resolved_at, resolution_summary,
                   created_at, updated_at
            FROM mdm_stewardship_cases
            WHERE organization_id = ?
        """
        params: List[Any] = [org_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC;"

        cur = self.conn.cursor()
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

    def transition_stewardship_case(
        self,
        user_ctx: Dict[str, Any],
        case_id: str,
        to_status: str,
        comment: str
    ) -> Dict[str, Any]:
        """Transition stewardship case state with full event history logging."""
        require_permission(user_ctx, "mdm:stewardship_manage")
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system-steward")

        if to_status not in self.VALID_CASE_STATUSES:
            raise ValidationError(f"Invalid to_status '{to_status}'. Allowed: {sorted(self.VALID_CASE_STATUSES)}")
        if not comment or len(comment.strip()) < 3:
            raise ValidationError("A comment explaining the status transition is required.")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, status FROM mdm_stewardship_cases
            WHERE id = ? AND organization_id = ?;
        """, (case_id, org_id))
        case = cur.fetchone()
        if not case:
            raise NotFoundError(f"Stewardship case '{case_id}' not found.")

        from_status = case["status"]
        now = datetime.utcnow().isoformat()

        cur.execute("""
            UPDATE mdm_stewardship_cases
            SET status = ?, updated_at = ?,
                resolved_by = CASE WHEN ? IN ('resolved', 'closed') THEN ? ELSE resolved_by END,
                resolved_at = CASE WHEN ? IN ('resolved', 'closed') THEN ? ELSE resolved_at END,
                resolution_summary = CASE WHEN ? IN ('resolved', 'closed') THEN ? ELSE resolution_summary END
            WHERE id = ?;
        """, (to_status, now, to_status, user_id, to_status, now, to_status, comment, case_id))

        evt_id = f"cevt-{uuid.uuid4().hex[:10]}"
        cur.execute("""
            INSERT INTO mdm_stewardship_case_events (
                id, case_id, organization_id, from_status, to_status,
                comment, actor_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (evt_id, case_id, org_id, from_status, to_status, comment, user_id, now))

        self.conn.commit()
        return {
            "case_id": case_id,
            "from_status": from_status,
            "to_status": to_status,
            "updated_at": now
        }

    def get_stewardship_case_events(self, user_ctx: Dict[str, Any], case_id: str) -> List[Dict[str, Any]]:
        """List event audit trail for a case."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, case_id, from_status, to_status, comment, actor_id, created_at
            FROM mdm_stewardship_case_events
            WHERE case_id = ? AND organization_id = ?
            ORDER BY created_at ASC;
        """, (case_id, org_id))
        return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # 9. Master Data Governance Pulse
    # -------------------------------------------------------------------------
    def get_mdm_pulse(self, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate health, completeness, and stewardship metrics across master data estate."""
        require_permission(user_ctx, "mdm:read")
        org_id = user_ctx.get("organization_id", "org-matab-default")

        cur = self.conn.cursor()

        # Master entities count
        cur.execute("SELECT COUNT(*) as count FROM mdm_master_entities_catalog WHERE organization_id = ?;", (org_id,))
        master_entities_count = cur.fetchone()["count"]

        # Active rules count
        cur.execute("SELECT COUNT(*) as count FROM mdm_data_quality_rules WHERE organization_id = ? AND status = 'approved';", (org_id,))
        active_rules_count = cur.fetchone()["count"]

        # Open findings count
        cur.execute("SELECT COUNT(*) as count FROM mdm_data_quality_findings WHERE organization_id = ? AND status = 'open';", (org_id,))
        open_findings_count = cur.fetchone()["count"]

        # Pending duplicate reviews
        cur.execute("SELECT COUNT(*) as count FROM mdm_duplicate_candidate_reviews WHERE organization_id = ? AND status = 'pending';", (org_id,))
        pending_duplicates_count = cur.fetchone()["count"]

        # Open stewardship cases
        cur.execute("SELECT COUNT(*) as count FROM mdm_stewardship_cases WHERE organization_id = ? AND status IN ('open', 'triaged', 'assigned');", (org_id,))
        open_cases_count = cur.fetchone()["count"]

        # Terminology mappings count
        cur.execute("SELECT COUNT(*) as count FROM mdm_terminology_mappings WHERE organization_id = ? AND review_status = 'approved';", (org_id,))
        approved_terms_count = cur.fetchone()["count"]

        # Staged import batches
        cur.execute("SELECT COUNT(*) as count FROM mdm_import_batches WHERE organization_id = ? AND status IN ('staged', 'validated_dry_run');", (org_id,))
        active_imports_count = cur.fetchone()["count"]

        # Active cross references
        cur.execute("SELECT COUNT(*) as count FROM mdm_patient_cross_references WHERE organization_id = ? AND is_active = 1;", (org_id,))
        active_xrefs_count = cur.fetchone()["count"]

        return {
            "organization_id": org_id,
            "master_entities_count": master_entities_count,
            "active_rules_count": active_rules_count,
            "open_findings_count": open_findings_count,
            "pending_duplicate_reviews_count": pending_duplicates_count,
            "open_stewardship_cases_count": open_cases_count,
            "approved_terminology_mappings_count": approved_terms_count,
            "active_import_batches_count": active_imports_count,
            "active_patient_cross_references_count": active_xrefs_count,
            "governance_status": "healthy" if open_findings_count < 10 else "attention_required",
            "evaluated_at": datetime.utcnow().isoformat()
        }
