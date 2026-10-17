# ZAYVORA MATAB OS — Release Blocker & Launch Gap Register (Table B)

**Audit Version:** 1.0.0 (Prompt 50 Repository-Wide Baseline)  
**Classification Rules:**
- **P0 (Release Blocker):** Must be resolved before any real clinical traffic or real patient data touches the software. Non-negotiable for patient safety, legal compliance, or core security.
- **P1 (Launch Scope):** Required for a complete and polished V1 release. Can be temporarily bounded in an initial controlled single-clinic pilot with clear operational procedures.
- **P2 (Deferred / Post-V1):** Valuable enhancements, multi-hospital enterprise scaling, or advanced simulation engines scheduled for subsequent phases.

---

## Table B: P0 & P1 Findings and Remediation Register

| Finding ID | Severity | Area & Title | Root-Cause Hypothesis | Accountable Owner Role | Concrete Acceptance Criteria | Required Regression Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GAP-P0-01** | **P0** | **Clinical Safety:** Production Unani Monograph Sign-Off by Accredited Tabib | Clinical monographs and posology thresholds were seeded from published pharmacopoeias (NFUM, UPI) but lack cryptographically signed clinical sign-off from an AYUSH-accredited practitioner. | Chief Medical Officer / AYUSH Governance Lead | A formal digital attestation record signed by an accredited Tabib must be stored in `clinical_rule_proposals` and `clinical_safety_cases` with tamper-evident hash chaining. | `test_clinical_safety.py`<br>`test_governance.py` |
| **GAP-P0-02** | **P0** | **Security:** Secret Key & JWT Salt Environmental Enforcement | Development uses safe local fallback secret keys if environment variables (`JWT_SECRET`, `SESSION_KEY`) are omitted, which presents a risk of default secret reuse in deployment. | Principal DevSecOps Engineer | Application startup must fail-closed with a fatal error if `ENVIRONMENT=production` and `JWT_SECRET` contains default or known insecure placeholder values. | `test_security_posture.py`<br>`test_config_governance.py` |
| **GAP-P0-03** | **P0** | **Clinical Safety:** Mudabbar Purification Physical Batch Attestation | The Mudabbar purification check validates that toxic Schedule E(1) botanicals (e.g., Azaraqi) require detoxification, but pharmacy dispensary workflow needs physical batch certificate verification before dispensing. | Chief Pharmacist / Dispensary Officer | Dispensation of Schedule E(1) formulations must enforce both clinician PIN signing at prescribing time and pharmacist physical batch number entry at dispensing time. | `test_safety_firewall.py`<br>`test_inventory.py` |
| **GAP-P0-04** | **P0** | **Data Integrity:** SQLite WAL Mode Automated Periodic Checkpointing & Backup Hook | SQLite database relies on filesystem-level writes; ungraceful host shutdown during high-throughput consultation hours could leave uncommitted WAL frames. | SRE / Database Administrator | Background cron/scheduler must trigger `PRAGMA wal_checkpoint(TRUNCATE)` every 60 minutes and run automated `PRAGMA integrity_check` before snapshot backup creation. | `test_disaster_recovery.py` |
| **GAP-P1-01** | **P1** | **External Comms:** Live SMS & WhatsApp Gateway Production Credentials | Patient appointment reminders and Parhez diet instructions operate through an isolated synthetic sandbox adapter (`SANDBOX_MOCKED`). | Lead Integration Engineer | Configured production SMS gateway (Twilio / SMS-Country) and WhatsApp Cloud API with valid webhook HMAC verification and automated retry circuit breaker. | `test_continuity.py`<br>`test_integration_ops.py` |
| **GAP-P1-02** | **P1** | **Interoperability:** ABDM Production Bridge Certification | ABDM M1, M2, and M3 workflows are fully implemented against the synthetic ABDM sandbox; live NHA gateway requires governmental sandbox clearance. | Interoperability Lead | Complete formal NHA sandbox compliance testing, obtain production client ID/secret, and switch `ABDM_ENVIRONMENT` from `SANDBOX` to `PRODUCTION`. | `test_abdm.py`<br>`test_interoperability.py` |
| **GAP-P1-03** | **P1** | **Payment Operations:** Live Payment Gateway Webhook Signature Verification | Billing receipts and online payments operate in synthetic mode with pre-approved callbacks; live Razorpay/Stripe webhook signatures require runtime validation. | Financial Systems Lead | Enable cryptographic HMAC-SHA256 signature verification for inbound payment webhooks, storing transaction IDs in `payment_records` with zero secret exposure. | `test_billing.py` |
| **GAP-P1-04** | **P1** | **Identity:** Multi-Factor Authentication (MFA) for Administrative Roles | Administrative and Super-Admin access currently relies on strong password authentication with rate limiting; enterprise governance recommends TOTP MFA for admins. | Platform Security Architect | Implement time-based one-time password (TOTP) authenticator app enrollment for users with `admin` or `compliance_officer` roles. | `test_identity_governance.py`<br>`test_auth.py` |
| **GAP-P1-05** | **P1** | **Ergonomics:** Bilingual PDF Prescription Font Packaging | Urdu / Arabic Nastaliq font rendering in prescription PDFs relies on system-installed fonts; missing fonts on minimal Linux container images cause fallback to sans-serif. | Frontend / UX Engineer | Bundle embedded WOFF2 / TTF open-source Nastaliq fonts (e.g., Noto Nastaliq Urdu) within the Docker container build image to ensure 100% typographic consistency. | `test_prescription_pdf.py` |

---

## 2. Risk Mitigation & Resolution Strategy

1. **Phase 0 (Security & Safety Lock):**
   - Resolve **GAP-P0-01**, **GAP-P0-02**, **GAP-P0-03**, and **GAP-P0-04** prior to any live clinical pilot.
   - Fail-closed release gate checks implemented in `EnterpriseSecurityPostureEngine` and `ClinicalSafetyCaseService` ensure that software deployments automatically reject builds with unresolved P0 items.

2. **Phase 1 (Operational Readiness):**
   - Address **GAP-P1-01** through **GAP-P1-05** prior to public clinic launch.
   - In a single-clinic closed pilot, synthetic SMS and manual receipt printouts serve as acceptable bounded operational fallbacks.
