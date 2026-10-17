# Architecture Reference: Recovery Dependency Map

**Document Code:** ARC-REF-REC-006  
**System:** ZAYVORA MATAB OS (Prompt 56)

---

## 1. System Recovery Dependency Graph

```mermaid
graph TD
    classDef infra fill:#1e293b,stroke:#475569,stroke-width:2px,color:#fff;
    classDef storage fill:#065f46,stroke:#059669,stroke-width:2px,color:#fff;
    classDef core fill:#1e40af,stroke:#2563eb,stroke-width:2px,color:#fff;
    classDef clinical fill:#831843,stroke:#db2777,stroke-width:2px,color:#fff;
    classDef edge fill:#78350f,stroke:#d97706,stroke-width:2px,color:#fff;

    OS[Host Operating System / POSIX]:::infra --> FS[Encrypted Local Filesystem / ZFS]:::infra
    FS --> DB[(SQLite Database File + WAL)]:::storage
    FS --> ATTACH[(Clinical Attachments Directory)]:::storage
    
    DB --> ENGINE[BackupRestoreEngine / Core Database Connection]:::core
    ATTACH --> ENGINE
    
    ENGINE --> AUTH[Authentication & Session Validation]:::core
    AUTH --> PATIENTS[Patients & Longitudinal Timeline Domain]:::clinical
    AUTH --> ENCOUNTERS[Consultation & Clinical Assessment Domain]:::clinical
    AUTH --> PRESCRIBE[Formulation & Safety Firewall]:::clinical
    
    PATIENTS --> UI[Web Frontend Single Consultation Canvas]:::edge
    ENCOUNTERS --> UI
    PRESCRIBE --> UI
    
    subgraph Isolated_Restore_Sandbox [Isolated Restore Sandbox (Zero Side-Effects)]
        SANDBOX_DIR[Disposable Temp Directory]:::storage
        REST_DB[(Restored SQLite Sandbox)]:::storage
        NO_SMS[Outbound SMS Suppressed]:::infra
        NO_HOOKS[Webhooks Suppressed]:::infra
        NO_PAY[Payment Gateways Stubbed]:::infra
    end
    
    ENGINE -.->|Phase 3 Restore| Isolated_Restore_Sandbox
```

---

## 2. Bootstrapping Sequence & Recovery Ordering

1. **Step 0: Storage Layer Verification**
   - Ensure target mount points exist with $\ge 200\%$ free space of the uncompressed backup size.
   - Verify SQLite version $\ge 3.35.0$ support (math functions, RETURNING clause, WAL).
2. **Step 1: Manifest Integrity Verification**
   - Validate companion `.manifest.json` SHA-256 against database file before attaching to database connection.
3. **Step 2: Database Schema & Migration Alignment**
   - Confirm migration level is 053. If older, run incremental forward migrations (`apps/api/database/migrator.py`).
4. **Step 3: Technical Integrity PRAGMA Checks**
   - Run `PRAGMA integrity_check;` and `PRAGMA foreign_key_check;`. Must return 0 errors.
5. **Step 4: Clinical Provenance Assertion**
   - Assert record counts for `patients`, `encounters`, `prescriptions`, and `clinical_monographs` match manifest counts.
6. **Step 5: Multi-Tenant Boundary Validation**
   - Assert all entity `organization_id` foreign keys match the tenant scope.
7. **Step 6: Routing & Service Initialization**
   - Mount API router and start web server processes.
