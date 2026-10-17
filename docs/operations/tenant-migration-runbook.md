# ZAYVORA MATAB OS — Tenant Migration, Backfill & Rollout Runbook

**Document ID:** OPS-RUNBOOK-MIGRATE-001  
**Phase:** 9 — Safe Migration and Rollout  
**Date:** 2026-10-15  
**Author:** Principal DevSecOps & Database Operations Lead  
**Status:** Approved  

---

## 1. Migration Overview

Migration `052_enterprise_multitenant_isolation_saas_governance_schema.sql` extends ZAYVORA MATAB OS to enforce multi-tenant SaaS governance without breaking existing single-clinic or multi-branch installations.

### 1.1 Tables Introduced
1. `saas_tenant_lifecycle`: Tracks explicit lifecycle state (`PROVISIONING`, `ACTIVE`, `SUSPENDED`, `OFFBOARDING`, `DECOMMISSIONED`), reason codes, and transition timestamps.
2. `saas_tenant_entitlements`: Enforces plan tiers (`STARTER`, `PROFESSIONAL`, `ENTERPRISE`, `CUSTOM`), max practitioners, max facilities, API quotas, and storage limits.
3. `saas_break_glass_tickets`: Time-bounded, reason-coded, audited support access sessions ($\le 60\text{ min}$ max TTL).
4. `saas_governance_audit_ledger`: SHA-256 tamper-evident cryptographic blockchain chaining all tenancy operations.

---

## 2. Preflight & Data Integrity Check

Before applying migration `052`, execute the preflight check script:
```bash
PYTHONPATH=. .venv/bin/python3 -c "
import sqlite3
conn = sqlite3.connect('matab.db')
cur = conn.cursor()

# Check for orphaned facilities
cur.execute('SELECT COUNT(*) FROM facilities WHERE organization_id NOT IN (SELECT id FROM organizations);')
orphaned_facilities = cur.fetchone()[0]

# Check for orphaned patients
cur.execute('SELECT COUNT(*) FROM patients WHERE organization_id NOT IN (SELECT id FROM organizations);')
orphaned_patients = cur.fetchone()[0]

# Check for orphaned encounters
cur.execute('SELECT COUNT(*) FROM encounters WHERE organization_id NOT IN (SELECT id FROM organizations);')
orphaned_encounters = cur.fetchone()[0]

print(f'Preflight Check: {orphaned_facilities} orphaned facilities, {orphaned_patients} orphaned patients, {orphaned_encounters} orphaned encounters')
assert orphaned_facilities == 0 and orphaned_patients == 0 and orphaned_encounters == 0, 'Orphaned records detected! Stop migration.'
print('Preflight PASSED. Safe to proceed.')
"
```

---

## 3. Backfill Execution for Existing Organizations

Migration `052` automatically backfills all pre-existing records in `organizations`:
- Every existing organization in `organizations` receives an active record in `saas_tenant_lifecycle` with `status = 'ACTIVE'`.
- Every existing organization receives a default baseline plan in `saas_tenant_entitlements` with `plan_tier = 'PROFESSIONAL'`, `max_active_practitioners = 10`, `max_facilities = 5`, `api_rate_limit_rpm = 120`.
- The genesis block `SGL-GENESIS-0001` is seeded into `saas_governance_audit_ledger` with hash linking.

---

## 4. Rollback Plan

If an operational anomaly or lock contention is detected during rollout:
1. The migration relies strictly on standard ANSI DDL (`CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`).
2. Existing tables (`organizations`, `facilities`, `users`, `encounters`, `prescriptions`) are never dropped or altered destructively.
3. In case of emergency rollback, the application continues to operate on `051` baseline schema while the new tables remain inert.
