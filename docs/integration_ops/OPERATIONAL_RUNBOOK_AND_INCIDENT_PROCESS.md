# Integration Operations Runbook & Incident Management Guide

**Product:** ZAYVORA MATAB OS  
**Phase:** 32 — Enterprise Integration Operations & Reliability  
**Target Audience:** Site Reliability Engineers, Clinical Operations Administrators, Integration Engineers  
**Classification:** Operational Runbook  

---

## 1. Scope & Objective

This runbook defines standard operating procedures (SOPs) for monitoring, managing, and troubleshooting external integration failures, circuit breaker trips, dead-letter items, and ambiguous delivery states within ZAYVORA MATAB OS.

---

## 2. Real-Time Telemetry & Dashboards

Operations engineers monitor integration health via:
1. **Web Console:** Open the **Knowledge Admin** workspace $\to$ **Integration Operations (P32)** tab.
2. **Operations API:** `GET /api/v1/ops/dashboard` (Requires `ops:read` permission).

### Key Performance Indicators (KPIs) & Alert Thresholds

| Metric | Target | Warning Threshold | Critical Incident Threshold |
| :--- | :--- | :--- | :--- |
| **Outcome Unknown Jobs** | 0 | $> 0$ for 5 minutes | $> 5$ jobs or any high-priority prescription |
| **Open DLQ Items** | 0 | $> 5$ unresolved | $> 20$ unresolved or unowned items |
| **Circuit Breakers Open** | 0 | 1 open for $> 2$ minutes | 2+ partner gateways open simultaneously |
| **Queue Dispatch Latency** | $< 250$ms | $> 2000$ms | $> 10000$ms sustained for 5 minutes |

---

## 3. Standard Incident Response Playbooks

### Playbook 1: Connector Circuit Breaker Tripped (OPEN)

**Symptoms:**
- The dashboard indicates `Circuit Breakers Open: 1/x`.
- Outbound jobs targeting the connector accumulate in `blocked_by_authorization`.

**Procedure:**
1. **Identify Root Cause:**
   - Run: `GET /api/v1/ops/connectors/{id}` to inspect `last_error_message` and consecutive failure counts.
   - Run a synthetic probe: `POST /api/v1/ops/connectors/{id}/health-snapshot` with probe type `CONNECTIVITY`.
2. **Diagnose Partner Gateway:**
   - If partner is down: Contact the partner's technical contact / NOC. Do NOT manually reset the breaker while the upstream outage persists.
   - If network route was restored: The circuit breaker will automatically enter `HALF_OPEN` after 60 seconds of cooldown and attempt a probe.
3. **Manual Override (Privileged):**
   - If connectivity is verified: An operator with `ops:manage` may reset the breaker:
     ```http
     POST /api/v1/ops/connectors/{connector_id}/circuit-breaker
     Content-Type: application/json
     
     { "state": "CLOSED" }
     ```

---

### Playbook 2: Resolving Jobs in `outcome_unknown`

**Symptoms:**
- Red alert badge on the Operations Dashboard indicating `Outcome Unknown (Action Req.)`.
- Job is paused; retry is blocked to prevent double-prescription or duplicate lab dispatch.

**Procedure:**
1. **Locate the Job:**
   - Go to the **Integration Jobs Queue** in the UI. Locate the job highlighted in red.
2. **Initiate Formal Reconciliation:**
   - Click **Reconcile** or call the API:
     ```http
     POST /api/v1/ops/jobs/{job_id}/reconcile
     Content-Type: application/json
     
     {
       "reconciliation_method": "STATUS_QUERY",
       "trigger_reason": "Read timeout during prescription dispatch"
     }
     ```
3. **Gather Evidence:**
   - Check partner administration portal or run status inquiry.
   - Confirm whether the external system received transaction ID `provider_tx_id` or correlation ID.
4. **Submit Resolution:**
   - Click **Resolve Reconciliation** or submit via API:
     ```http
     POST /api/v1/ops/reconciliations/{recon_id}/resolve
     Content-Type: application/json
     
     {
       "determination": "confirmed_completed",
       "decision_notes": "Partner gateway confirmed receipt via transaction ref ACK-99201",
       "evidence_references": ["ACK-99201"]
     }
     ```
   - If partner confirmed transaction was NOT received: Select `confirmed_not_completed`. This safely reschedules the job for retry (`retry_scheduled`).

---

### Playbook 3: Dead-Letter Queue (DLQ) Remediation

**Symptoms:**
- Items appear in the **Dead-Letter Workbench (DLQ)** with status `OPEN`.

**Procedure:**
1. **Analyze Structured Error Category:**
   - `SCHEMA_INVALID`: The outgoing payload violated partner JSON schema requirements. Fix the data/mapping before replaying.
   - `RETRY_BUDGET_EXHAUSTED`: Transient downtime exceeded maximum retry limit. Check if partner is now online.
   - `AUTH_FAILURE`: Credentials expired or revoked. Update connector configuration first.
2. **Determine Replay Eligibility:**
   - Check the `safe_replay_eligible` column. If `SAFE_REPLAY`, the operation is deterministic and idempotent.
3. **Remediate and Replay:**
   - Once the root cause is addressed, click **Replay** in the UI or call:
     ```http
     POST /api/v1/ops/dead-letter/{dlq_id}/resolve
     Content-Type: application/json
     
     {
       "action": "REPLAY",
       "rationale": "Partner rate-limit window cleared; approved for replay"
     }
     ```
   - If the job is invalid or duplicate: Select `CANCEL` or `ACKNOWLEDGE_TERMINATED` with documented rationale.

---

## 4. Emergency Procedures: Total Connector Shutdown

If a compromised partner endpoint, data leakage event, or uncontrolled runaway traffic occurs:
1. Trigger emergency connector disablement immediately:
   ```http
   POST /api/v1/ops/connectors/{id}/disable
   Content-Type: application/json
   
   {
     "reason": "Emergency security quarantine due to partner endpoint compromise"
   }
   ```
2. This atomically transitions `lifecycle_state` to `DISABLED`, preventing any outbound requests.
3. The event is permanently logged with operator ID and timestamp in the immutable audit ledger.
