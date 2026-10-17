# Disaster Recovery & Major Incident Playbook

**Document Code:** SOP-OPS-DRP-003  
**Classification:** Restricted — Internal Security & Operations  
**System:** ZAYVORA MATAB OS (Prompt 56)

---

## 1. Disaster Severity Matrix & Declaring an Incident

| Incident Severity | Definition | Response Window | Authorized Lead |
|:---|:---|:---|:---|
| **SEV-1 (Critical)** | Complete Matab outage, physical disk failure, data corruption, or ransomware attack. | Immediate (< 5 min) | Chief Medical Officer & VP Security |
| **SEV-2 (Major)** | Primary OPD database inaccessible; replica or local node functioning. | < 15 min | Lead Site Reliability Engineer |
| **SEV-3 (Moderate)** | Integration or background queue failure; clinical consultation operational. | < 1 hour | Operations Lead |

---

## 2. Point-in-Time Recovery (PITR) & RPO Synchronization

During active operations, PITR markers are recorded periodically and before major changes:
```bash
curl -X POST https://matab.example.com/api/v1/dr/pitr-markers \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "marker_label": "pre_maintenance_checkpoint",
    "canary_payload": {"encounter_count": 1420, "pending_prescriptions": 3}
  }'
```

In a disaster scenario:
1. Query historical recovery markers: `GET /api/v1/dr/pitr-markers`.
2. Identify the latest valid marker prior to corruption/incident.
3. Supply `target_pitr_marker` to `POST /api/v1/dr/verified-restore-drills`.
4. Measure the precise data loss window in seconds ($RPO \le 300\text{s}$).

---

## 3. Disaster Scenarios & Recovery Workflows

### Scenario A: Local Edge Hardware / Disk Crash at Matab
1. Dispatch cold-standby hardware or provision cloud container instance.
2. Retrieve latest verified backup `.db` and companion `.manifest.json` from offsite storage.
3. Run verification check (`/api/v1/dr/coordinated-backups/:id/verify`).
4. Execute isolated restore drill (`/api/v1/dr/verified-restore-drills`).
5. Evaluate promotion gate (`PROMOTION_APPROVED`).
6. Point Matab edge client to the promoted database.
7. Collect downtime paper records and submit to downtime reconciliation queue (`/api/v1/dr/reconciliation`).

### Scenario B: Suspected Database Tampering / Ransomware
1. Immediately freeze production application traffic and disconnect network adapters.
2. Locate the latest immutable locked backup (`dr_backup_manifests.immutable_lock_until > CURRENT_TIMESTAMP`).
3. Verify blockchain audit ledger integrity (`GET /api/v1/dr/ledger/verify`) to detect the timestamp of tampering.
4. Execute 7-phase isolated restore into disposable sandbox.
5. Confirm technical integrity and clinical invariant counts match pre-incident records.
6. Re-provision application infrastructure with fresh credentials and promote clean snapshot.
