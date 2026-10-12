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
