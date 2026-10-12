# REST API Specification — ZAYVORA MATAB OS v1.1

All requests and responses use `application/json`.
Authentication uses Bearer token (`Authorization: Bearer <session_token>`).
All write endpoints support optional `Idempotency-Key` header.
Error responses follow RFC 7807 problem details: `{ "error": true, "code": "ERROR_CODE", "message": "Human readable details", "details": {} }`.

---

## 1. Core Endpoints Table

| Method | Path | Required Role | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public | Authenticate user with credentials; returns session token & tenant context |
| `POST` | `/api/v1/auth/logout` | Authenticated | Terminate session and invalidate token |
| `GET`  | `/api/v1/auth/me` | Authenticated | Return active user, practitioner info, facilities, and active profile |
| `GET`  | `/api/v1/patients` | All Roles | Search & list patients by name, phone, or MRN |
| `POST` | `/api/v1/patients` | Reception, Hakeem | Register a new patient with duplicate checking |
| `GET`  | `/api/v1/patients/{id}/360` | All Clinical | Longitudinal Patient 360 (vitals history, past prescriptions, Mizaj trend) |
| `POST` | `/api/v1/patients/duplicate-check` | Reception, Hakeem | Evaluate prospective patient demographics against duplicate heuristics |
| `GET`  | `/api/v1/encounters/queue` | All Roles | Fetch today's OPD waiting queue, tokens, and attention-needed list |
| `POST` | `/api/v1/encounters` | Reception, Hakeem | Create new encounter / issue OPD token |
| `GET`  | `/api/v1/encounters/{id}` | All Roles | Fetch single encounter with notes, vitals, assessments, and prescription |
| `PUT`  | `/api/v1/encounters/{id}/vitals` | Nurse, Hakeem | Save or update vital signs |
| `PUT`  | `/api/v1/encounters/{id}/notes` | Hakeem | Save structured clinical history & examination notes |
| `POST` | `/api/v1/unani-assessments` | Hakeem | Submit Mizaj questionnaire responses & qualitative observations |
| `POST` | `/api/v1/clinical-support/red-flags` | Hakeem | Evaluate patient history against deterministic red-flag rules |
| `POST` | `/api/v1/care-plans` | Hakeem | Document Usul-e-Ilaj modalities, Ghiza (diet) & Tadbeer (regimen) |
| `GET`  | `/api/v1/knowledge/ingredients` | All Roles | Search approved Mufradat (single drugs) catalog |
| `GET`  | `/api/v1/knowledge/formulations` | All Roles | Search approved Murakkabat (compounds) catalog with standard doses |
| `POST` | `/api/v1/prescriptions` | Hakeem | Create or update prescription draft items |
| `POST` | `/api/v1/prescriptions/{id}/safety-check` | Hakeem | Run deterministic preflight safety check (`PASS`, `WARN`, `BLOCK`, `UNKNOWN`) |
| `POST` | `/api/v1/prescriptions/{id}/sign` | Hakeem | Electronically sign prescription with practitioner PIN; produces SHA-256 hash |
| `GET`  | `/api/v1/prescriptions/{id}/print` | All Roles | Generate printable verified prescription payload |
| `GET`  | `/api/v1/operations/follow-ups` | All Roles | Get due clinical follow-ups and missed appointments |
| `GET`  | `/api/v1/operations/inventory` | Pharmacist, Admin | View batch inventory with FEFO expiry tracking |
| `GET`  | `/api/v1/system/capabilities` | Public / All | Get Feature & Engine Capability Registry statuses |
| `GET`  | `/api/v1/system/health` | Public | System liveness, database connectivity, and readiness check |
