# Standard Operating Procedure: Restore & Recovery Runbook

**Document Code:** SOP-OPS-RST-002  
**Audience:** Site Reliability Engineers, Clinical Safety Officers, Database Administrators  
**System:** ZAYVORA MATAB OS (Prompt 56)

---

## 1. Principles of Safe Restore Operations

Restoring a database snapshot into active use is a high-risk operational event. Under no circumstances may an unverified backup snapshot be promoted directly to production.

### Cardinal Safety Rules
1. **Never Restore Over Live Production Without Prior Snapshot:** Always capture a final online snapshot of the live database before replacing it.
2. **Suppress Outbound Side Effects in Testing:** Isolated restore drills must never send SMS/WhatsApp notifications, fire outbound webhooks, or process billing transactions.
3. **Fail-Closed Promotion Gates:** Restores cannot be promoted if SQLite technical integrity, foreign key checks, clinical invariants, or multi-tenant boundary checks fail.
4. **Dual Authorization for Production Emergencies:** Restoring to `production_emergency` requires explicit credentials from the Chief Medical Officer (`CHIEF_MEDICAL_OFFICER`) or VP Security (`VP_SECURITY`).

---

## 2. 7-Phase Restore Drill Workflow

Every restore verification executes the following 7 deterministic steps:

```
[Phase 1: Preflight Authorization]
       │
[Phase 2: Cryptographic Manifest Verification]
       │
[Phase 3: Isolated Sandbox Restore with Side-Effect Suppression]
       │
[Phase 4: Technical Integrity & Foreign Key Constraint Checks]
       │
[Phase 5: Clinical Invariants Verification (Patients/Encounters/Prescriptions)]
       │
[Phase 6: Multi-Tenant Boundary Isolation Validation]
       │
[Phase 7: Empirical RTO/RPO Recording & Disposable Sandbox Cleanup]
```

### Executing an Isolated Drill via API
```bash
curl -X POST https://matab.example.com/api/v1/dr/verified-restore-drills \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "backup_id": "BKP-XXXXXXXXXXXX",
    "target_environment": "isolated_test_sandbox",
    "purpose": "Quarterly Regulatory Business Continuity Drill",
    "authorized_by": "CHIEF_COMPLIANCE_OFFICER"
  }'
```

---

## 3. Production Promotion Gatekeeper

Once an isolated restore passes verification, a qualified officer must evaluate the promotion gate before it can replace an operational instance:

```bash
curl -X POST https://matab.example.com/api/v1/dr/verified-restore-drills/<VERIFICATION_ID>/promotion-gate \
  -H "Authorization: Bearer <OFFICER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "PROMOTION_APPROVED",
    "notes": "Verified clean by Lead SRE and Chief Medical Officer. Approved for promotion."
  }'
```

If rejected:
```bash
curl -X POST https://matab.example.com/api/v1/dr/verified-restore-drills/<VERIFICATION_ID>/promotion-gate \
  -H "Authorization: Bearer <OFFICER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "PROMOTION_REJECTED",
    "notes": "Data loss window exceeds accepted operational tolerance."
  }'
```

---

## 4. Rollback and Abort Procedure
If a promoted database demonstrates unexpected regression post-promotion:
1. Revert application connection string to the pre-restore snapshot captured in Step 1.
2. Invalidate all active user sessions to force re-authentication.
3. Log an emergency incident in `dr_governance_audit_ledger`.
