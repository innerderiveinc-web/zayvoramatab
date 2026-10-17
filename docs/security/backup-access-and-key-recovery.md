# Security Policy: Backup Access Control, Encryption & Key Recovery

**Document Code:** SEC-POL-BKP-005  
**Classification:** Confidential — Security & Compliance Architecture  
**System:** ZAYVORA MATAB OS (Prompt 56)

---

## 1. Access Control & Role-Based Permissions (RBAC)

Access to backup, restore, and disaster-recovery operations is governed by the centralized RBAC and session validation middleware (`apps/api/core/permissions.py`).

| Permission Code | Minimum Role | Allowed Operations |
|:---|:---|:---|
| `dr:read` | `CLINICAL_AUDITOR`, `ORG_ADMIN`, `PLATFORM_ENGINEER` | List backups, view manifests, list restore drills, verify ledger. |
| `dr:backup` | `ORG_ADMIN`, `PLATFORM_ENGINEER` | Create online coordinated backups, record PITR markers. |
| `dr:drill` | `PLATFORM_ENGINEER`, `SECURITY_OFFICER` | Execute 7-phase isolated restore drills in sandboxes. |
| `dr:manage` | `CHIEF_MEDICAL_OFFICER`, `VP_SECURITY`, `ORG_ADMIN` | Authorize/reject production promotion gates, retention cleanups. |
| `dr:reconcile` | `PRACTITIONER`, `CHIEF_HAKEEM` | Ingest and resolve offline downtime clinical records. |

Dual authorization is enforced for `target_environment="production_emergency"`, which requires explicit sign-off from `CHIEF_MEDICAL_OFFICER` or `VP_SECURITY`.

---

## 2. Storage Encryption at Rest & in Transit

1. **Storage at Rest:**
   - On Linux/Unix edge appliances, backups reside on LUKS-encrypted partitions (`AES-XTS-256`).
   - In cloud tiers, backups are stored in customer-managed key (CMK) encrypted object stores.
2. **Transit Encryption:**
   - All REST API communications require TLS 1.3.
   - Remote replication transfers use SSH/SFTP with Ed25519 authentication or HTTPS over AWS SigV4 / GCP IAM.

---

## 3. Cryptographic Key Recovery & Escrow

1. **HMAC/Signature Key Hierarchy:**
   - Manifest signatures are computed with deterministic HMAC-like SHA-256 bindings.
   - Ledger blocks link hashes hierarchically to prevent rollback or insertion.
2. **Key Escrow & Break-Glass:**
   - Database recovery keys and operational credentials are split using Shamir's Secret Sharing (3-of-5 quorum) among executive officers:
     - Chief Medical Officer
     - VP Engineering / DevSecOps Lead
     - Data Protection Officer
     - Head of Clinical Operations
     - External Legal Counsel
   - Reconstitution of production emergency keys requires physical or cryptographic presentation of at least 3 shards.
