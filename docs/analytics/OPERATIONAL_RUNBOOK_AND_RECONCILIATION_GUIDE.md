# Operational Intelligence Runbook & Metric Reconciliation Guide

**Document Type:** SRE & Operational Runbook  
**Product:** ZAYVORA MATAB OS — Standalone Clinic & Matab Operating System  
**Phase:** 33 — Enterprise Analytics, Operational Intelligence & Clinical Governance Dashboards  
**Target Audience:** Site Reliability Engineers, Database Administrators, Clinic Directors, Finance Controllers  

---

## 1. Overview & Operational Contract

The Analytics & Operational Intelligence engine computes mission-critical metrics directly from canonical operational ledgers. Because clinic management, staffing, inventory procurement, and statutory reporting rely on these metrics, operational teams require strict guidelines for detecting data drift, reconciling ledger discrepancies, and troubleshooting aggregation anomalies.

---

## 2. Daily & Shift Reconciliation Procedures

### 2.1 Daily Financial Settlement Reconciliation (T+0 End-of-Day)
At the conclusion of each clinic operating day (21:00 local time):
1. **Trigger Reconciliation Query:**
   Execute financial reconciliation between posted payments and issued refunds:
   ```sql
   SELECT 
       payment_method,
       COALESCE(SUM(CAST(amount_decimal AS REAL)), 0.0) as total_collected
   FROM payments
   WHERE organization_id = :org_id 
     AND status IN ('POSTED', 'COMPLETED')
     AND recorded_at >= :day_start AND recorded_at <= :day_end
   GROUP BY payment_method;
   ```
2. **Compare Against Physical Cash & Gateway Settlement:**
   - Physical cash drawer count must equal `total_collected` where `payment_method = 'CASH'`.
   - UPI/Card settlement reports must equal `total_collected` where `payment_method IN ('UPI', 'CARD')`.
3. **Record Exceptions:**
   If variance exceeds $\pm \text{₹} 1.00$ (due to rounding or cash drawer discrepancy), invoke `POST /api/v1/analytics/reconciliation-exceptions` with `metric_key: "finance.net_collections"`, the detected variance, and initial investigation notes.

### 2.2 Shift Token & Encounter Clearance Audit
1. Verify all OPD tokens issued today have reached terminal status (`completed`, `cancelled`, or `no_show`).
2. Any tokens remaining in `waiting` or `in_progress` past clinic closing hours must be audited:
   ```sql
   SELECT id, token_number, practitioner_id, status 
   FROM queue_tokens 
   WHERE organization_id = :org_id 
     AND queue_date = CURRENT_DATE 
     AND status IN ('waiting', 'in_progress');
   ```
3. Front-desk supervisor must either finalize the consultation record or mark the token expired/cancelled.

---

## 3. Discrepancy Detection & Exception Resolution Runbook

When an automated sweep or financial audit identifies a discrepancy between primary operational records and derived dashboard metrics, execute the following 4-step workflow:

```
[ Automated Sweep / Manual Audit ]
                 |
                 v
   Variance > Threshold?
    /                 \
  YES                  NO
  /                     \
[ Record Exception ]    [ Log Clean Run in metric_calculation_runs ]
        |
        v
[ Investigate Root Cause (ID / Timestamp Mismatch) ]
        |
        v
[ Remediate Primary Record / Apply Correction Entry ]
        |
        v
[ Resolve Exception via POST /api/v1/analytics/reconciliation-exceptions/{id}/resolve ]
```

### 3.1 Exception Statuses
- **`OPEN`**: Exception recorded by system or staff; awaiting investigation.
- **`INVESTIGATING`**: Finance or clinical governance team actively reviewing transactions.
- **`RESOLVED`**: Discrepancy identified, ledger adjusted, and notes recorded by an authorized user (`analytics:manage`).
- **`DISMISSED`**: Identified variance deemed immaterial or an authorized test artifact.

### 3.2 Resolving an Exception via API
```bash
POST /api/v1/analytics/reconciliation-exceptions/{exception_id}/resolve
Authorization: Bearer <ADMIN_OR_FINANCE_TOKEN>
Content-Type: application/json

{
  "status": "RESOLVED",
  "notes": "Verified against bank settlement statement for 2026-10-14. UPI transaction TXN-9981 delayed settlement reconciled."
}
```

---

## 4. Performance & Query Optimization Guidelines

### 4.1 Index Maintenance
Ensure the following composite indexes remain healthy and analyze stats periodically:
- `idx_payments_facility_date` on `payments(organization_id, facility_id, status, recorded_at)`
- `idx_invoices_status_date` on `invoices(organization_id, facility_id, status, created_at)`
- `idx_appointments_facility_date` on `appointments(organization_id, facility_id, status, start_at)`
- `idx_metric_recon_lookup` on `metric_reconciliation_exceptions(organization_id, facility_id, metric_key, exception_status)`

### 4.2 Handling High-Volume Date Ranges
- Queries spanning $>90$ days should specify a facility filter (`facility_id`) where possible to partition table scans.
- Avoid unrestricted full-database scans; always supply explicit `period` or `start_date` and `end_date` parameters.

---

## 5. Security & Privacy Incident Runbook

### 5.1 Accidental PHI Exposure Prevention
- If an export is found to contain identifiable patient information (name, phone number, address, or full clinical text), immediately invoke emergency containment:
  1. Record security incident in the tamper-evident ledger.
  2. Revoke the download link and purge the temporary export buffer.
  3. Validate that `analytics_export_audit` correctly hashes payloads without retaining raw text.
  4. File an incident review with the Enterprise Security & Privacy Officer (Prompt 30).
