-- Phase 33 Schema: Enterprise Analytics, Operational Intelligence & Clinical Governance Dashboards
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Governed Metric Definitions Registry
CREATE TABLE IF NOT EXISTS governed_metric_definitions (
    id TEXT PRIMARY KEY,
    metric_key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    domain TEXT NOT NULL CHECK (
        domain IN ('OPERATIONS', 'CONTINUITY', 'FINANCE', 'INVENTORY', 'GOVERNANCE', 'DATA_QUALITY')
    ),
    metric_type TEXT NOT NULL CHECK (
        metric_type IN ('count', 'rate', 'duration', 'amount', 'ratio', 'status')
    ),
    unit TEXT,
    numerator_definition TEXT,
    denominator_definition TEXT,
    inclusion_rules_json TEXT NOT NULL DEFAULT '[]',
    exclusion_rules_json TEXT NOT NULL DEFAULT '[]',
    source_entities_json TEXT NOT NULL DEFAULT '[]',
    source_fields_json TEXT NOT NULL DEFAULT '[]',
    calculation_version TEXT NOT NULL DEFAULT '1.0.0',
    effective_from TEXT,
    effective_to TEXT,
    aggregation_grain TEXT NOT NULL DEFAULT 'DAY',
    refresh_policy TEXT NOT NULL DEFAULT 'ON_DEMAND',
    accountable_owner TEXT NOT NULL DEFAULT 'CLINICAL_OPS_DIRECTOR',
    permitted_roles_json TEXT NOT NULL DEFAULT '["ORG_ADMIN", "PRACTITIONER", "FACILITY_MANAGER"]',
    caveats_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'approved' CHECK (
        status IN ('draft', 'review', 'approved', 'retired')
    ),
    approved_by TEXT,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gov_metric_defs_domain ON governed_metric_definitions(domain, status);
CREATE INDEX IF NOT EXISTS idx_gov_metric_defs_key ON governed_metric_definitions(metric_key);

-- 2. Materialized Calculation Runs & Snapshots
CREATE TABLE IF NOT EXISTS metric_calculation_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    metric_id TEXT NOT NULL REFERENCES governed_metric_definitions(id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    computed_value_numeric REAL,
    computed_value_json TEXT, -- Structured breakdowns or dimensional series
    calculation_status TEXT NOT NULL DEFAULT 'available' CHECK (
        calculation_status IN ('available', 'insufficient_data', 'not_configured', 'stale', 'failed', 'not_authorized')
    ),
    error_details TEXT,
    data_freshness_as_of TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_watermark TEXT,
    run_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metric_runs_lookup ON metric_calculation_runs(
    organization_id, facility_id, metric_key, period_start, period_end
);

-- 3. Metric Reconciliation Discrepancies & Exceptions
CREATE TABLE IF NOT EXISTS metric_reconciliation_exceptions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    metric_key TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    canonical_value_decimal TEXT NOT NULL,
    derived_value_decimal TEXT NOT NULL,
    variance_decimal TEXT NOT NULL,
    exception_status TEXT NOT NULL DEFAULT 'OPEN' CHECK (
        exception_status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'DISMISSED')
    ),
    notes TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_by TEXT,
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_metric_recon_lookup ON metric_reconciliation_exceptions(
    organization_id, facility_id, metric_key, exception_status
);

-- 4. Analytics Export Audit (Zero PHI, Tamper-Evident Hashing)
CREATE TABLE IF NOT EXISTS analytics_export_audit (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    export_type TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT 'CSV' CHECK (format IN ('CSV', 'JSON')),
    metric_keys_json TEXT NOT NULL DEFAULT '[]',
    filters_json TEXT NOT NULL DEFAULT '{}',
    record_count INTEGER NOT NULL DEFAULT 0,
    sha256_hash TEXT NOT NULL,
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analytics_export_audit ON analytics_export_audit(
    organization_id, facility_id, user_id, exported_at
);

-- 5. Seed Canonical Metric Definitions into Registry
INSERT OR IGNORE INTO governed_metric_definitions (
    id, metric_key, name, description, domain, metric_type, unit,
    numerator_definition, denominator_definition, inclusion_rules_json, exclusion_rules_json,
    source_entities_json, source_fields_json, calculation_version, aggregation_grain,
    refresh_policy, accountable_owner, permitted_roles_json, caveats_json, status, approved_at
) VALUES 
(
    'm-ops-001', 'operations.appointments_completed', 'Completed Consultations',
    'Total count of clinical appointments successfully marked completed during the period.',
    'OPERATIONS', 'count', 'visits',
    'COUNT(id) WHERE status = "completed"', NULL,
    '["Status must equal completed", "Within period window by start_at"]',
    '["Cancelled appointments", "No-shows", "Test/Synthetic appointments"]',
    '["appointments"]', '["status", "start_at", "organization_id", "facility_id"]',
    '1.0.0', 'DAY', 'REALTIME', 'CLINICAL_DIRECTOR',
    '["ORG_ADMIN", "PRACTITIONER", "FACILITY_MANAGER", "RECEPTIONIST"]',
    '["Completed visit count does not reflect consultation duration or treatment outcomes."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-ops-002', 'operations.appointments_no_show_rate', 'No-Show Rate',
    'Ratio of recorded no-show appointments to total scheduled appointments (excluding cancellations).',
    'OPERATIONS', 'rate', '%',
    'COUNT(id) WHERE status = "no_show"',
    'COUNT(id) WHERE status IN ("completed", "no_show", "arrived")',
    '["Scheduled visits with conclusive arrival or no-show determinations"]',
    '["Visits cancelled prior to appointment time", "Walk-in slots not booked in advance"]',
    '["appointments"]', '["status", "start_at"]',
    '1.0.0', 'DAY', 'REALTIME', 'CLINIC_OPERATIONS_LEAD',
    '["ORG_ADMIN", "FACILITY_MANAGER", "RECEPTIONIST"]',
    '["Rate is sensitive to front-desk check-in discipline; unrecorded arrivals may inflate rate."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-ops-003', 'operations.queue_tokens_waiting', 'Current Waiting Queue',
    'Count of patients currently waiting in the OPD queue for active consultation.',
    'OPERATIONS', 'count', 'patients',
    'COUNT(id) WHERE status = "waiting" AND queue_date = CURRENT_DATE', NULL,
    '["Queue tokens in waiting state for today"]',
    '["Completed tokens", "Cancelled tokens", "Tokens in active consultation"]',
    '["queue_tokens"]', '["status", "queue_date"]',
    '1.0.0', 'INSTANT', 'REALTIME', 'FRONT_DESK_LEAD',
    '["ORG_ADMIN", "PRACTITIONER", "FACILITY_MANAGER", "RECEPTIONIST"]',
    '["Reflects physical queue size; does not distinguish expedited or emergency tokens."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-ops-004', 'operations.encounters_signed', 'Signed Encounters',
    'Total count of clinical encounters signed and finalized by treating practitioners.',
    'OPERATIONS', 'count', 'encounters',
    'COUNT(id) WHERE status = "signed"', NULL,
    '["Encounters with status = signed finalized within the period"]',
    '["Draft encounters", "Cancelled encounters"]',
    '["encounters"]', '["status", "signed_at"]',
    '1.0.0', 'DAY', 'REALTIME', 'CHIEF_MEDICAL_OFFICER',
    '["ORG_ADMIN", "PRACTITIONER", "FACILITY_MANAGER"]',
    '["Documentation signature is a legal completion indicator, not an efficacy measurement."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-cont-001', 'continuity.tasks_overdue', 'Overdue Follow-up Tasks',
    'Count of active care continuity tasks past their designated due date without recorded completion.',
    'CONTINUITY', 'count', 'tasks',
    'COUNT(id) WHERE status IN ("PENDING", "IN_PROGRESS") AND due_date < CURRENT_TIMESTAMP', NULL,
    '["Open tasks with due date strictly prior to current time"]',
    '["Completed tasks", "Cancelled tasks", "Tasks scheduled for future dates"]',
    '["care_continuity_tasks"]', '["status", "due_date"]',
    '1.0.0', 'DAY', 'REALTIME', 'CARE_COORDINATOR',
    '["ORG_ADMIN", "PRACTITIONER", "FACILITY_MANAGER"]',
    '["Overdue status indicates care coordination administrative workload, not clinical abandonment."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-fin-001', 'finance.gross_invoiced', 'Total Invoiced Amount',
    'Total currency value of finalized and paid invoices generated during the period.',
    'FINANCE', 'amount', 'INR',
    'SUM(total_decimal) WHERE status IN ("FINALIZED", "PARTIALLY_PAID", "PAID")', NULL,
    '["Finalized bills"]',
    '["Draft invoices", "Voided invoices"]',
    '["invoices"]', '["status", "total_decimal", "created_at"]',
    '1.0.0', 'DAY', 'REALTIME', 'FINANCE_MANAGER',
    '["ORG_ADMIN", "FINANCE_OFFICER", "FACILITY_MANAGER"]',
    '["Invoiced amount represents accrued billings, NOT realized cash collection or profit."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-fin-002', 'finance.net_collections', 'Net Cash Collections',
    'Actual payment receipts posted minus payment refunds issued during the period.',
    'FINANCE', 'amount', 'INR',
    'SUM(p.amount_decimal) - COALESCE(SUM(r.amount_decimal), 0)', NULL,
    '["Posted payments and completed refunds within period"]',
    '["Pending provider transactions", "Failed payments", "Voided records"]',
    '["payments", "payment_refunds"]', '["amount_decimal", "status", "recorded_at", "created_at"]',
    '1.0.0', 'DAY', 'REALTIME', 'FINANCE_MANAGER',
    '["ORG_ADMIN", "FINANCE_OFFICER", "FACILITY_MANAGER"]',
    '["Net collection represents cash ledger inflow, not tax-adjusted net profit."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-fin-003', 'finance.outstanding_balances', 'Total Outstanding Patient Balances',
    'Cumulative balance due remaining on non-voided finalized invoices.',
    'FINANCE', 'amount', 'INR',
    'SUM(balance_due_decimal) WHERE status IN ("FINALIZED", "PARTIALLY_PAID")', NULL,
    '["Invoices with active outstanding balances"]',
    '["Paid invoices", "Voided invoices", "Drafts"]',
    '["invoices"]', '["status", "balance_due_decimal"]',
    '1.0.0', 'DAY', 'REALTIME', 'BILLING_SUPERVISOR',
    '["ORG_ADMIN", "FINANCE_OFFICER"]',
    '["Aging accounts receivable requires routine reconciliation against patient payment plans."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-inv-001', 'inventory.batches_near_expiry', 'Batches Near Expiry (90-Day Horizon)',
    'Count of available inventory batches whose recorded expiry date falls within the next 90 days.',
    'INVENTORY', 'count', 'batches',
    'COUNT(id) WHERE status = "AVAILABLE" AND expiry_date BETWEEN CURRENT_DATE AND DATE(CURRENT_DATE, "+90 days")', NULL,
    '["Available dispensary batches with positive stock on hand"]',
    '["Depleted batches", "Quarantined batches", "Recalled items"]',
    '["inventory_batches"]', '["status", "expiry_date", "quantity_on_hand_decimal"]',
    '1.0.0', 'DAY', 'DAILY_SYNC', 'PHARMACY_SUPERVISOR',
    '["ORG_ADMIN", "PHARMACIST", "FACILITY_MANAGER"]',
    '["Near-expiry batches require FEFO prioritization or return to vendor."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-gov-001', 'governance.safety_cases_open', 'Open Pharmacovigilance Safety Cases',
    'Count of adverse event reports and safety incidents currently under investigation or triage.',
    'GOVERNANCE', 'count', 'cases',
    'COUNT(id) WHERE case_status IN ("INTAKE", "TRIAGED", "UNDER_INVESTIGATION")', NULL,
    '["Open safety cases in active investigation"]',
    '["Closed cases", "Duplicate reports merged"]',
    '["safety_cases"]', '["case_status", "intake_date"]',
    '1.0.0', 'DAY', 'REALTIME', 'SAFETY_OFFICER',
    '["ORG_ADMIN", "PRACTITIONER", "GOVERNANCE_REVIEWER"]',
    '["A zero count does not prove absolute clinical safety when reporting compliance is unknown."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-gov-002', 'governance.rules_pending_review', 'Safety Rules Pending Review',
    'Count of clinical rules or safety firewall adjustments awaiting committee validation.',
    'GOVERNANCE', 'count', 'rules',
    'COUNT(id) WHERE lifecycle_state IN ("DRAFT", "SUBMITTED", "VALIDATED")', NULL,
    '["Rules not yet released to production clinical firewall"]',
    '["Released active rules", "Retired rules", "Rejected proposals"]',
    '["governed_clinical_rules"]', '["lifecycle_state"]',
    '1.0.0', 'DAY', 'REALTIME', 'CLINICAL_GOVERNANCE_LEAD',
    '["ORG_ADMIN", "GOVERNANCE_REVIEWER"]',
    '["Unreviewed rules are held in sandbox; they do NOT alter active clinical prescribing."]',
    'approved', CURRENT_TIMESTAMP
),
(
    'm-dq-001', 'data_quality.integration_dead_letter_count', 'Unresolved Dead-Letter Queue Items',
    'Count of outbound integration transactions permanently failed and held in the DLQ workbench.',
    'DATA_QUALITY', 'count', 'items',
    'COUNT(id) WHERE resolution_status = "PENDING"', NULL,
    '["Dead letter items awaiting operator inspection and resolution"]',
    '["Resolved/replayed items", "Acknowledged cancelled transactions"]',
    '["dead_letter_items"]', '["resolution_status"]',
    '1.0.0', 'DAY', 'REALTIME', 'INTEGRATION_SRE',
    '["ORG_ADMIN", "INTEGRATION_ADMIN", "FACILITY_MANAGER"]',
    '["Every DLQ item requires root-cause categorization before safe replay or dismissal."]',
    'approved', CURRENT_TIMESTAMP
);
