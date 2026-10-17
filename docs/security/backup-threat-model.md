# Threat Model: Backup, Disaster Recovery & Restore Perimeter

**Document Code:** SEC-THM-BKP-007  
**Framework:** STRIDE + Healthcare Safety Hazards (IEC 62304 / ISO 14971)  
**System:** ZAYVORA MATAB OS (Prompt 56)

---

## 1. Threat Identification & STRIDE Matrix

| Threat ID | STRIDE Category | Threat Description | Attack Vector | Architectural Mitigation in ZAYVORA | Residual Risk |
|:---|:---|:---|:---|:---|:---|
| **TH-BKP-01** | **Spoofing** | Adversary fabricates a malicious backup manifest claiming authentic status. | Submitting forged JSON manifest with arbitrary table counts. | Deterministic HMAC-like SHA-256 signature binding manifest ID, backup ID, org ID, checksums, and schema. Recomputed on verify. | Negligible |
| **TH-BKP-02** | **Tampering** | Byte-level corruption, bit-rot, or malware modification of `.db` file. | Appending or altering bytes in SQLite storage file. | Recomputing SHA-256 against `dr_backup_manifests.database_checksum_sha256`; status marked `tamper_detected`. | Negligible |
| **TH-BKP-03** | **Repudiation** | Administrator denies restoring an unauthorized snapshot or purging audit logs. | Unlogged file deletion or restoration. | Append-only SHA-256 chained ledger (`dr_governance_audit_ledger`) rooted at genesis block `DGL-GENESIS-0001`. | Negligible |
| **TH-BKP-04** | **Information Disclosure** | Cross-tenant data leakage during restore drill or snapshot recovery. | Restoring a shared multi-tenant database into an unauthorized tenant's environment. | Phase 6 Multi-tenant isolation verification and strict `organization_id` isolation checks. | Very Low |
| **TH-BKP-05** | **Denial of Service** | Ransomware adversary prematurely deleting historical backups. | Invoking automated retention cleanup to purge active data. | Immutable retention lock (`immutable_lock_until`) strictly blocking deletion until expiration date. | Low |
| **TH-BKP-06** | **Elevation of Privilege** | Attacker triggering production emergency restore without clinical approval. | API call specifying `production_emergency`. | Code-level enforcement requiring `authorized_by` in `("CHIEF_MEDICAL_OFFICER", "VP_SECURITY")`. | Very Low |
| **TH-BKP-07** | **Safety Hazard (Clinical)** | Restored database executing queued notifications, messaging real patients during test drill. | Test drill triggers production notification dispatch worker. | Hard side-effect suppression in Phase 3 (`outbound_messaging_suppressed=True`, sandbox stubbing). | Negligible |
