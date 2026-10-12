# Local Development Guide — ZAYVORA MATAB OS

---

## 1. Prerequisites
- Python 3.9+ (Standard Library)
- (Optional) Docker & Docker Compose for containerized PostgreSQL deployment

---

## 2. Quick Setup (Local Standalone Mode)

### Step 1: Clone & Configure Environment
```bash
cp .env.example .env
```

### Step 2: Apply Database Migrations
```bash
make migrate
# or: python3 -m apps.api.database.migrator
```

### Step 3: Seed Synthetic Development Data
```bash
make seed
# or: python3 -m apps.api.database.seed
```
> **Notice:** The seed script creates strictly synthetic demo accounts clearly marked with `[SYNTHETIC TEST ACCOUNT]`. The seed script will refuse to execute if `MATAB_ENV=production`.

### Step 4: Run the Automated Test Suite
```bash
make test
# or: python3 -m unittest discover -s tests -p "test_*.py" -v
```

### Step 5: Start the Local Development Server
```bash
make run
# or: python3 -m apps.api.main
```
Open `http://127.0.0.1:8000` in your web browser.

---

## 3. Seed Accounts for Testing

| Username | Role | Default Password | Scoped Facility |
|---|---|---|---|
| `admin` | `ORG_ADMIN` | `matab123` | All Facilities |
| `hakeem` | `PRACTITIONER` | `matab123` | Central Matab OPD |
| `reception` | `RECEPTIONIST` | `matab123` | Central Matab OPD |
| `pharmacy` | `PHARMACIST` | `matab123` | Central Matab OPD |
| `auditor` | `READ_ONLY_AUDITOR` | `matab123` | Read-only Audit Log |

---

## 4. Synthetic Patient Test Fixtures

The synthetic development seeder provisions 4 representative test patients:

| Patient ID | Name | MRN | Phone | Purpose / Test Scenario |
|---|---|---|---|---|
| `pat-syn-001` | فاطمہ زہرا (Fatima Zahra) | `MRN-2026-00001` | `+91-9876543210` | Multilingual Unicode name; matches `dup-pair-001` on phone |
| `pat-syn-002` | Zayd Farooq | `MRN-2026-00002` | `+91-9876543210` | Co-habitant / shared family phone; matches `dup-pair-001` |
| `pat-syn-003` | Maryam Khatoon | `MRN-2026-00003` | `+91-9811122233` | Single consultation encounter (`enc-syn-003`) |
| `pat-syn-004` | Ibrahim Qureshi | `MRN-2026-00004` | `+91-9822233344` | Clean record; estimated age with recorded age timestamp |

---

## 5. Granular Test Suites

```bash
# Run unit tests only (validation, normalization, transition rules)
make test-unit

# Run integration tests (registry, duplicates, encounters, tenancy security)
make test-integration

# Run end-to-end smoke workflows
make test-e2e
```

