# Standard Operating Procedure: Backup Execution Runbook

**Document Code:** SOP-OPS-BKP-001  
**Audience:** DevSecOps Engineers, Database Administrators, Matab IT Officers  
**System:** ZAYVORA MATAB OS (Prompt 56)

---

## 1. Overview & Principles

Live backups in ZAYVORA MATAB OS are executed without taking the clinical database offline or interrupting consultations. The process generates:
1. An online SQLite database snapshot (`.db`).
2. A companion cryptographic manifest file (`.manifest.json`).
3. A tamper-evident database catalog entry (`dr_backup_catalog`).
4. An immutable block in the DR governance audit ledger (`dr_governance_audit_ledger`).

---

## 2. Triggering Backups

### Method A: Via REST API
```bash
curl -X POST https://matab.example.com/api/v1/dr/coordinated-backups \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "backup_type": "full",
    "scope": "database_all",
    "retention_tier": "30_days_standard",
    "immutable_lock_days": 7
  }'
```

### Method B: Via Python CLI / Script
```python
from apps.api.domains.backup_restore_engine import BackupRestoreEngine

engine = BackupRestoreEngine("/path/to/production/zayvora.db")
result = engine.create_coordinated_backup(
    organization_id="org-matab-default",
    backup_type="full",
    retention_tier="30_days_standard",
    immutable_lock_days=7
)
print(f"Created Backup ID: {result['backup_id']}, Checksum: {result['checksum_sha256']}")
```

### Method C: Via Enterprise Web Console
1. Navigate to **Knowledge & System Admin Console**.
2. Select tab: **Enterprise Backup & Restore (P56)**.
3. Click button **+ Coordinated Backup**.
4. Choose retention tier (e.g. `30_days_standard`) and optional immutable lock days (e.g. `7`).

---

## 3. Independent Verification Procedure

Before trusting any backup snapshot for archiving or migration, verify its integrity:
```bash
curl -X POST https://matab.example.com/api/v1/dr/coordinated-backups/<BACKUP_ID>/verify \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### Verification Criteria
- [x] Physical artifact exists on storage media.
- [x] File SHA-256 matches catalog `checksum_sha256` and manifest `database_checksum_sha256`.
- [x] Manifest signature matches deterministic recomputation.
- [x] SQLite `PRAGMA integrity_check;` returns `ok`.

---

## 4. Retention & Lifecycle Tiers

| Tier Name | Duration | Regulatory Purpose |
|:---|:---|:---|
| `7_days_operational` | 7 Days | Daily rolling recovery points for fast rollback. |
| `30_days_standard` | 30 Days | Monthly business cycle recovery baseline. |
| `365_days_compliance` | 365 Days | Annual fiscal and operational compliance. |
| `7_years_clinical_legal` | 2555 Days | AYUSH & Statutory medical record retention requirements. |

### Retention Cleanup Execution
```bash
# Dry run audit (safe, reports reclaimable bytes)
curl -X POST https://matab.example.com/api/v1/dr/retention/cleanup \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -d '{"dry_run": true}'

# Execute purge of expired, non-locked backups
curl -X POST https://matab.example.com/api/v1/dr/retention/cleanup \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -d '{"dry_run": false}'
```
