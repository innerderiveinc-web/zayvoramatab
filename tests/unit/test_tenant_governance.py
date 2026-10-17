"""Unit Tests for Enterprise Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance Engine.

Phase 55 Verification Suite for ZAYVORA MATAB OS.
"""

import json
import sqlite3
import unittest

from apps.api.domains.tenant_governance_engine import TenantGovernanceEngine
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
)


class TestTenantGovernanceEngine(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._setup_schema()
        self.engine = TenantGovernanceEngine(self.conn)

    def tearDown(self):
        self.conn.close()

    def _setup_schema(self):
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                license_number TEXT,
                profile_type TEXT NOT NULL DEFAULT 'MATAB',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                username TEXT NOT NULL,
                email TEXT,
                password_hash TEXT,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'PRACTITIONER',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS facilities (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                name TEXT NOT NULL,
                code TEXT,
                address TEXT,
                phone TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                facility_id TEXT,
                full_name TEXT NOT NULL,
                phone TEXT
            );

            CREATE TABLE IF NOT EXISTS encounters (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                patient_id TEXT,
                facility_id TEXT,
                status TEXT NOT NULL DEFAULT 'COMPLETED'
            );

            CREATE TABLE IF NOT EXISTS prescriptions (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                patient_id TEXT,
                encounter_id TEXT,
                status TEXT NOT NULL DEFAULT 'ACTIVE'
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                organization_id TEXT NOT NULL
            );
        """)

        # Execute migration 052
        with open("apps/api/database/migrations/052_enterprise_multitenant_isolation_saas_governance_schema.sql") as f:
            cursor.executescript(f.read())
        self.conn.commit()

    def test_tenant_provisioning_success_and_idempotency(self):
        """Test standard tenant provisioning and idempotency key handling."""
        res = self.engine.provision_tenant(
            data={
                "code": "CLINIC-ALPHA",
                "name": "Alpha Comprehensive Matab",
                "plan_tier": "PROFESSIONAL",
                "admin_name": "Dr. Hakim Alpha",
                "admin_email": "hakim@alpha-matab.pk",
                "max_active_practitioners": 12,
                "max_facilities": 4,
                "idempotency_key": "IDEMP-ALPHA-001",
            },
            actor_id="SUPER-ADMIN-01"
        )
        self.assertIn("tenant_id", res)
        self.assertEqual(res["code"], "CLINIC-ALPHA")
        self.assertEqual(res["lifecycle_status"], "ACTIVE")
        self.assertEqual(res["entitlements"]["plan_tier"], "PROFESSIONAL")
        self.assertEqual(res["entitlements"]["max_active_practitioners"], 12)

        # Re-provision with identical idempotency key returns same tenant
        repeat = self.engine.provision_tenant(
            data={
                "code": "CLINIC-ALPHA",
                "name": "Alpha Comprehensive Matab",
                "idempotency_key": "IDEMP-ALPHA-001",
            },
            actor_id="SUPER-ADMIN-01"
        )
        self.assertEqual(repeat["tenant_id"], res["tenant_id"])

    def test_tenant_provisioning_validations(self):
        """Test validations for missing fields and duplicate code."""
        with self.assertRaises(ValidationError):
            self.engine.provision_tenant(data={"name": ""}, actor_id="SUPER-ADMIN")

        with self.assertRaises(ValidationError):
            self.engine.provision_tenant(data={"name": "Alpha", "plan_tier": "INVALID_TIER"}, actor_id="SUPER-ADMIN")

        # Provision once
        self.engine.provision_tenant(
            data={"code": "CLINIC-BETA", "name": "Beta Matab Clinic"},
            actor_id="SUPER-ADMIN"
        )

        # Duplicate code without same idempotency key raises ConflictError
        with self.assertRaises(ConflictError):
            self.engine.provision_tenant(
                data={"code": "CLINIC-BETA", "name": "Duplicate Clinic"},
                actor_id="SUPER-ADMIN"
            )

    def test_tenant_lifecycle_transitions_and_rules(self):
        """Test tenant status transitions and enforcement of state machine rules."""
        prov = self.engine.provision_tenant(
            data={"code": "CLINIC-GAMMA", "name": "Gamma Matab Clinic"},
            actor_id="SUPER-ADMIN"
        )
        t_id = prov["tenant_id"]

        # Insert active session
        self.conn.execute("INSERT INTO sessions (id, user_id, organization_id) VALUES ('sess-g-1', 'u-g-1', ?)", (t_id,))
        self.conn.commit()
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sessions WHERE organization_id = ?", (t_id,)).fetchone()[0], 1)

        # Transition ACTIVE -> SUSPENDED
        res = self.engine.transition_tenant_status(
            tenant_id=t_id,
            new_status="SUSPENDED",
            reason="Delinquent subscription invoice past 60 days grace",
            actor_id="SUPER-ADMIN"
        )
        self.assertEqual(res["lifecycle_status"], "SUSPENDED")

        # Verify sessions purged and organization marked inactive
        org = self.conn.execute("SELECT is_active FROM organizations WHERE id = ?", (t_id,)).fetchone()
        self.assertEqual(org["is_active"], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sessions WHERE organization_id = ?", (t_id,)).fetchone()[0], 0)

        # Transition SUSPENDED -> ACTIVE
        res = self.engine.transition_tenant_status(
            tenant_id=t_id,
            new_status="ACTIVE",
            reason="Outstanding invoice settled in full",
            actor_id="SUPER-ADMIN"
        )
        self.assertEqual(res["lifecycle_status"], "ACTIVE")

        # Transition ACTIVE -> OFFBOARDING
        res = self.engine.transition_tenant_status(
            tenant_id=t_id,
            new_status="OFFBOARDING",
            reason="Customer requested contract termination",
            actor_id="SUPER-ADMIN"
        )
        self.assertEqual(res["lifecycle_status"], "OFFBOARDING")

        # Transition OFFBOARDING -> DECOMMISSIONED
        res = self.engine.transition_tenant_status(
            tenant_id=t_id,
            new_status="DECOMMISSIONED",
            reason="Data retention period expired and final export delivered",
            actor_id="SUPER-ADMIN"
        )
        self.assertEqual(res["lifecycle_status"], "DECOMMISSIONED")

        # Illegal transition: DECOMMISSIONED -> ACTIVE raises ValidationError
        with self.assertRaises(ValidationError):
            self.engine.transition_tenant_status(
                tenant_id=t_id,
                new_status="ACTIVE",
                reason="Attempt resurrect decommissioned tenant",
                actor_id="SUPER-ADMIN"
            )

    def test_entity_ownership_and_cross_tenant_validation(self):
        """Test cross-tenant IDOR shielding and relationship validation."""
        # Provision two separate tenants
        t1 = self.engine.provision_tenant(data={"code": "T-001", "name": "Tenant One"}, actor_id="ADMIN")["tenant_id"]
        t2 = self.engine.provision_tenant(data={"code": "T-002", "name": "Tenant Two"}, actor_id="ADMIN")["tenant_id"]

        # Insert records for Tenant One
        self.conn.execute("INSERT INTO facilities (id, organization_id, name) VALUES ('fac-1', ?, 'Clinic 1')", (t1,))
        self.conn.execute("INSERT INTO patients (id, organization_id, facility_id, full_name) VALUES ('pat-1', ?, 'fac-1', 'Patient One')", (t1,))
        self.conn.execute("INSERT INTO encounters (id, organization_id, patient_id, facility_id) VALUES ('enc-1', ?, 'pat-1', 'fac-1')", (t1,))

        # Insert records for Tenant Two
        self.conn.execute("INSERT INTO facilities (id, organization_id, name) VALUES ('fac-2', ?, 'Clinic 2')", (t2,))
        self.conn.execute("INSERT INTO patients (id, organization_id, facility_id, full_name) VALUES ('pat-2', ?, 'fac-2', 'Patient Two')", (t2,))
        self.conn.commit()

        # Validate entity ownership for T1
        self.assertTrue(self.engine.validate_entity_ownership(tenant_id=t1, entity_type="patient", entity_id="pat-1"))

        # T2 attempting to access T1 patient raises ForbiddenError
        with self.assertRaises(ForbiddenError):
            self.engine.validate_entity_ownership(tenant_id=t2, entity_type="patient", entity_id="pat-1")

        # Non-existent entity raises NotFoundError
        with self.assertRaises(NotFoundError):
            self.engine.validate_entity_ownership(tenant_id=t1, entity_type="patient", entity_id="pat-999")

        # Cross-tenant relationship validation:
        # All valid within T1
        self.assertTrue(self.engine.validate_cross_tenant_relationship(
            tenant_id=t1,
            parent_type="facility",
            parent_id="fac-1",
            child_type="patient",
            child_id="pat-1"
        ))

        # Poisoned cross-tenant relationship: T1 facility with T2 patient raises ForbiddenError
        with self.assertRaises(ForbiddenError):
            self.engine.validate_cross_tenant_relationship(
                tenant_id=t1,
                parent_type="facility",
                parent_id="fac-1",
                child_type="patient",
                child_id="pat-2"
            )

    def test_offboarding_impact_and_formula_injection_sanitization(self):
        """Test offboarding impact calculation and formula injection protection in CSV export."""
        prov = self.engine.provision_tenant(data={"code": "T-SEC", "name": "Secure Matab"}, actor_id="ADMIN")
        t_id = prov["tenant_id"]

        # Insert records including malicious formula strings
        self.conn.execute(
            "INSERT INTO facilities (id, organization_id, name) VALUES ('fac-sec', ?, ?)",
            (t_id, "=cmd|' /C calc'!A0")
        )
        self.conn.execute(
            "INSERT INTO patients (id, organization_id, facility_id, full_name, phone) VALUES ('pat-sec', ?, 'fac-sec', ?, ?)",
            (t_id, "@SUM(1+1)", "+923001234567")
        )
        self.conn.execute(
            "INSERT INTO encounters (id, organization_id, patient_id, facility_id) VALUES ('enc-sec', ?, 'pat-sec', 'fac-sec')",
            (t_id,)
        )
        self.conn.commit()

        # Impact summary
        impact = self.engine.get_offboarding_impact_summary(t_id)
        self.assertGreaterEqual(impact["data_summary"]["facilities"], 1)
        self.assertEqual(impact["data_summary"]["patients"], 1)
        self.assertEqual(impact["data_summary"]["encounters"], 1)

        # Export tenant data
        export = self.engine.export_tenant_data(t_id, actor_id="COMPLIANCE-OFFICER")
        self.assertIn("patients", export)
        self.assertIn("encounters", export)
        self.assertIn("facilities", export)
        self.assertIn("export_id", export)

        patients = export["patients"]
        self.assertEqual(len(patients), 1)
        # Formula injection mitigation checks:
        # Starting with @ should be prepended with '
        self.assertEqual(patients[0]["full_name"], "'@SUM(1+1)")
        # Starting with + should be prepended with '
        self.assertEqual(patients[0]["phone"], "'+923001234567")

        # Facility with =cmd should be prepended with '
        fac_sec = next(f for f in export["facilities"] if f["id"] == "fac-sec")
        self.assertEqual(fac_sec["name"], "'=cmd|' /C calc'!A0")

    def test_break_glass_support_tickets_lifecycle(self):
        """Test break-glass support ticket issuance, duration limits, and revocation."""
        prov = self.engine.provision_tenant(data={"code": "T-BG", "name": "Break Glass Matab"}, actor_id="ADMIN")
        t_id = prov["tenant_id"]

        # Create support user
        self.conn.execute(
            "INSERT INTO users (id, organization_id, username, full_name, email, role) VALUES ('sup-01', ?, 'sup', 'Tier 3 Support Lead', 'sup@zayvora.com', 'SYSTEM_ADMIN')",
            (t_id,)
        )
        self.conn.commit()

        # Ticket with duration > 60m rejected
        with self.assertRaises(ValidationError):
            self.engine.create_break_glass_ticket(
                target_tenant_id=t_id,
                support_user_id="sup-01",
                reason_code="EMERGENCY_CLINICAL_INVESTIGATION",
                justification="Investigating critical prescription mismatch reported by chief hakim",
                duration_minutes=90,
                approved_by="VP-SECURITY"
            )

        # Short justification (< 15 chars) rejected
        with self.assertRaises(ValidationError):
            self.engine.create_break_glass_ticket(
                target_tenant_id=t_id,
                support_user_id="sup-01",
                reason_code="EMERGENCY_CLINICAL_INVESTIGATION",
                justification="too short",
                duration_minutes=30,
                approved_by="VP-SECURITY"
            )

        # Invalid reason code rejected
        with self.assertRaises(ValidationError):
            self.engine.create_break_glass_ticket(
                target_tenant_id=t_id,
                support_user_id="sup-01",
                reason_code="CURIOUS_LOOK",
                justification="Investigating critical prescription mismatch reported by chief hakim",
                duration_minutes=30,
                approved_by="VP-SECURITY"
            )

        # Valid ticket creation
        ticket = self.engine.create_break_glass_ticket(
            target_tenant_id=t_id,
            support_user_id="sup-01",
            reason_code="EMERGENCY_CLINICAL_INVESTIGATION",
            justification="Investigating critical prescription mismatch reported by chief hakim",
            duration_minutes=45,
            approved_by="VP-SECURITY"
        )
        self.assertEqual(ticket["status"], "ACTIVE")
        self.assertEqual(ticket["duration_minutes"], 45)
        self.assertTrue(ticket["ticket_id"].startswith("BGT-"))

        # Revoke ticket
        revoked = self.engine.revoke_break_glass_ticket(
            ticket_id=ticket["ticket_id"],
            actor_id="VP-SECURITY",
            reason="Investigation completed; root cause identified in dosage calculation rule"
        )
        self.assertEqual(revoked["status"], "REVOKED")

    def test_entitlements_and_quota_enforcement(self):
        """Test tier entitlements and quota verification."""
        prov = self.engine.provision_tenant(data={"code": "T-ENT", "name": "Entitlements Matab"}, actor_id="ADMIN")
        t_id = prov["tenant_id"]

        # Update entitlements
        updated = self.engine.update_entitlements(
            tenant_id=t_id,
            data={
                "plan_tier": "STARTER",
                "max_active_practitioners": 2,
                "max_facilities": 1,
                "max_storage_mb": 1000,
                "api_rate_limit_rpm": 60
            },
            actor_id="ADMIN"
        )
        self.assertEqual(updated["plan_tier"], "STARTER")
        self.assertEqual(updated["max_active_practitioners"], 2)

        # Insert 1 practitioner -> Quota not exceeded
        self.conn.execute("INSERT INTO users (id, organization_id, username, full_name, role, is_active) VALUES ('p-1', ?, 'u1', 'Dr 1', 'PRACTITIONER', 1)", (t_id,))
        self.conn.commit()

        q1 = self.engine.check_quota(tenant_id=t_id, resource_type="practitioners")
        self.assertFalse(q1["quota_exceeded"])
        self.assertEqual(q1["current_usage"], 1)
        self.assertEqual(q1["remaining"], 1)

        # Insert 2nd practitioner -> Reaches limit (exceeded/at capacity)
        self.conn.execute("INSERT INTO users (id, organization_id, username, full_name, role, is_active) VALUES ('p-2', ?, 'u2', 'Dr 2', 'PRACTITIONER', 1)", (t_id,))
        self.conn.commit()

        q2 = self.engine.check_quota(tenant_id=t_id, resource_type="practitioners")
        self.assertTrue(q2["quota_exceeded"])
        self.assertEqual(q2["current_usage"], 2)
        self.assertEqual(q2["remaining"], 0)

    def test_tamper_evident_governance_audit_ledger_integrity(self):
        """Test SHA-256 blockchain audit ledger chaining and tamper detection."""
        # Initial verification (genesis block + any seeded/provisioned events)
        res = self.engine.verify_audit_ledger_integrity()
        self.assertTrue(res["verified"])
        self.assertEqual(res["status"], "CHAIN_INTEGRITY_VERIFIED")
        self.assertGreaterEqual(res["blocks_checked"], 1)

        # Trigger several governance events
        prov = self.engine.provision_tenant(data={"code": "T-LEDGER", "name": "Ledger Clinic"}, actor_id="ADMIN")
        t_id = prov["tenant_id"]

        self.engine.transition_tenant_status(
            tenant_id=t_id,
            new_status="SUSPENDED",
            reason="Routine maintenance test",
            actor_id="ADMIN"
        )

        res_after = self.engine.verify_audit_ledger_integrity()
        self.assertTrue(res_after["verified"])
        self.assertGreaterEqual(res_after["blocks_checked"], 3)

        # Tamper test: Alter payload in a block
        self.conn.execute("UPDATE saas_governance_audit_ledger SET payload_json = '{\"tampered\": true}' WHERE tenant_id = ?", (t_id,))
        self.conn.commit()

        tampered_res = self.engine.verify_audit_ledger_integrity()
        self.assertFalse(tampered_res["verified"])
        self.assertTrue(tampered_res["tamper_detected"])
        self.assertIn("Record hash mismatch", tampered_res["reason"])


if __name__ == "__main__":
    unittest.main()
