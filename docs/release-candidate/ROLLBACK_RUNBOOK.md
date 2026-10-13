# ZAYVORA MATAB OS — Rollback & Emergency Recovery Runbook (Prompt 16)
## Safe Downgrade, Containment, and Point-in-Time Database Recovery Protocol

This runbook defines the exact operational procedure for rolling back an active deployment or reverting a corrupted database state during pilot operations.

---

## 1. Rollback Trigger Criteria
A rollback must be initiated immediately upon encountering any of the following P0 events:
- **Severe Patient Safety Hazard:** False-negative safety preflight pass allowing un-detoxified Schedule E(1) toxin dispensing.
- **Data Integrity Violation:** Database corruption detected via `PRAGMA integrity_check` failing or unrecoverable transaction aborts.
- **Tenant Isolation Breach:** Any data leak or unauthorized cross-facility access between tenant organizations.
- **Application Crashing on Core Flow:** Inability to create encounters or electronically sign prescriptions across all users.

---

## 2. Emergency Rollback Protocol (Step-by-Step)

### Step 1: Immediate Pilot Containment
Freeze application write traffic by putting the API service into read-only containment mode:
```bash
# In emergency containment: stop the systemd daemon or docker container
sudo systemctl stop zayvora-matab-api
```

### Step 2: Preserve Current Forensic State
Never overwrite the current database file before taking an immutable forensic copy:
```bash
# Create timestamped forensic snapshot of the degraded state
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp /var/lib/zayvora-matab/matab.db /var/lib/zayvora-matab/forensics_matab_${TIMESTAMP}.db
cp /var/lib/zayvora-matab/matab.db-wal /var/lib/zayvora-matab/forensics_matab_${TIMESTAMP}.db-wal 2>/dev/null || true
```

### Step 3: Identify Last Known Good (LKG) Backup
Locate the most recent verified backup file generated prior to the triggering incident:
```bash
ls -lth /var/backups/zayvora-matab/
# Verify candidate backup integrity
sqlite3 /var/backups/zayvora-matab/matab_backup_LKG.bak "PRAGMA integrity_check;"
# Output must be 'ok'
```

### Step 4: Revert Code Revision (if Software Regression)
If the incident was caused by a faulty code deployment, roll back Git revision to the previous stable release tag:
```bash
cd /opt/zayvora-matab-os
git checkout v1.0.0-rc0
```

### Step 5: Restore Database from LKG Backup
```bash
# Safely replace active database with verified backup
rm -f /var/lib/zayvora-matab/matab.db*
cp /var/backups/zayvora-matab/matab_backup_LKG.bak /var/lib/zayvora-matab/matab.db
chmod 640 /var/lib/zayvora-matab/matab.db
```

### Step 6: Verify Database Integrity & Schema Version
```bash
sqlite3 /var/lib/zayvora-matab/matab.db "PRAGMA integrity_check;"
sqlite3 /var/lib/zayvora-matab/matab.db "SELECT version, applied_at FROM schema_migrations ORDER BY version DESC LIMIT 5;"
```

### Step 7: Restart Service and Execute Health Check
```bash
sudo systemctl start zayvora-matab-api
curl -f http://127.0.0.1:8000/api/v1/health/ready
# Must return HTTP 200 {"status": "READY"}
```

---

## 3. Post-Rollback Review & Notification Protocol
1. Document the incident in the pilot evaluation ledger: `POST /api/v1/pilot-evaluations/{id}/incident-reviews`.
2. Notify the Clinical Governance Lead, Security Lead, and Operations Lead within 1 hour.
3. Keep the pilot program status at `PAUSED` or `ROLLED_BACK` until the root cause remediation action is formally closed with retest evidence.
