# ZAYVORA MATAB OS — Threat Model & Security Architecture (Phase 30)

## 1. Protected Assets Classification

| Data Classification Tier | Assets Included | Encryption & Security Controls |
|---|---|---|
| **Tier 1: Highly Restricted (Credentials & Secrets)** | User password hashes, session tokens, digital signature PIN hashes, API integration keys, cryptographic private keys. | PBKDF2-HMAC-SHA256, memory-only session handling, strict redaction in logs/prompts/telemetry, no plaintext persistence. |
| **Tier 2: Sensitive Personal & Clinical Data (PHI/PII)** | Patient MRN, demographic identifiers, clinical notes, Unani mizaj assessments, diagnoses, prescriptions, lab results, safety reports. | AES-256 / SQLite WAL file permissions, strict tenant & branch scoping, field-level access control, data minimization, consent gating. |
| **Tier 3: Governed Clinical Knowledge & Rules** | KAVS source registries, canonical Unani catalog, organ-axis mappings, clinical rules, release manifests, CDS policies. | Append-only database tables, cryptographic manifest SHA-256 bindings, role-separated approval, immutable versioning. |
| **Tier 4: Audit & Regulatory Compliance Evidence** | Tamper-evident ledger events, verification checkpoints, dispute annotations, legal holds, compliance export packages. | Continuous SHA-256 cryptographic hash chaining ($H_i = \text{SHA-256}(C_i \parallel H_{i-1})$), deletion prohibition, write-once semantics. |
| **Tier 5: Operational & Non-Sensitive Administrative** | Clinic facilities, room names, service schedules, non-identifying aggregations, public terminology codes. | Standard RBAC, tenant isolation, rate limiting. |

---

## 2. Threat Actors & Failure Modes

1. **Malicious External Attacker / Credential Stuffer:**
   - *Attack:* Automated password guessing, session token brute-forcing, IDOR attempts on patient IDs.
   - *Controls:* In-memory IP rate limiting, 256-bit cryptographically random tokens (`secrets.token_hex`), server-side object authorization.
2. **Curious or Unauthorized Staff Member (Insider):**
   - *Attack:* Browsing patient charts outside assigned branch or clinical relationship; manipulating URL/payload IDs.
   - *Controls:* Deny-by-default RBAC, active facility membership check, tenant isolation, auditable access logging.
3. **Compromised Clinician Account:**
   - *Attack:* Signing fraudulent prescriptions or altering clinical histories using compromised credentials.
   - *Controls:* Step-up authentication for prescription signing, digital signature PIN hash validation, continuous audit ledger chaining.
4. **Discredited or Suspended Clinician:**
   - *Attack:* Continuing to practice or sign medical orders after license suspension or expiration.
   - *Controls:* Professional credential registry verification gate: prevents signing if credential status is not `verified`.
5. **Privileged Administrator Abuse:**
   - *Attack:* Silently altering historical clinical or audit records; creating unmonitored backdoors.
   - *Controls:* Append-only ledger architecture; silent updates/deletes are cryptographically detected during integrity sweeps; separation of administrative duties.
6. **Break-Glass Emergency Abuse:**
   - *Attack:* Invoking emergency access to view VIP patient records without genuine medical emergency.
   - *Controls:* Mandatory documented reason code & rationale, automatic time expiration, strict audit ledger logging, and mandatory post-access review workflow.
7. **Downstream Privacy Leakage via Caches / AI:**
   - *Attack:* Patient charts leaking into shared RAG embeddings, search indexes, or external AI model logs.
   - *Controls:* Patient context isolation; no patient PHI ingested into global knowledge graphs; prompt sanitization; disable-switch for third-party AI.

---

## 3. Incident Response Playbooks

### Playbook 1: Compromised Account Containment
1. **Immediate Revocation:** Invoke `POST /api/v1/security/sessions/revoke` with `user_id` to terminate all active sessions across all devices.
2. **Account Suspension:** Update `users.is_active = 0`.
3. **Audit Sweep:** Run `ClinicalAuditLedgerEngine.query_ledger` filtered by `actor_principal_id` to trace all records accessed or modified during the compromise window.
4. **Forensic Report:** Generate a compliance evidence export package bound to root checkpoint hash.

### Playbook 2: Unauthorized Break-Glass Investigation
1. **Notification:** Break-glass grant triggers high-priority alert to Chief Medical Officer and Security Officer.
2. **Review Campaign:** If unjustified, invoke `POST /api/v1/security/break-glass/{id}/review` with decision `ABUSE_CONFIRMED`.
3. **Revocation & Disciplinary Referral:** Revoke remaining emergency access and initiate statutory reporting.

### Playbook 3: Credential Suspension Synchronization
1. **Regulatory Update:** When licensing council suspends a practitioner, invoke `POST /api/v1/security/credentials/{id}/suspend`.
2. **Runtime Gating:** Immediate revocation of prescription signing authority across all branches.
