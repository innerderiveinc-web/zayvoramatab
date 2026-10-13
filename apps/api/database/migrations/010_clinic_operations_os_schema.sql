-- Phase 10 Schema: Clinic Operations OS (Appointments, Queue, Billing, Pharmacy Inventory & Dispensing)
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Facility Operational Settings & Module Configuration
CREATE TABLE IF NOT EXISTS facility_settings (
    facility_id TEXT PRIMARY KEY REFERENCES facilities(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    currency TEXT NOT NULL DEFAULT 'INR',
    tax_enabled INTEGER NOT NULL DEFAULT 0,
    default_tax_rate_bp INTEGER NOT NULL DEFAULT 0, -- Basis points: 500 = 5.00%
    billing_enabled INTEGER NOT NULL DEFAULT 1,
    billing_optional_for_consultation INTEGER NOT NULL DEFAULT 1, -- Clinical care separated from payment
    inventory_enabled INTEGER NOT NULL DEFAULT 1,
    public_queue_display_enabled INTEGER NOT NULL DEFAULT 1,
    allow_negative_stock_override INTEGER NOT NULL DEFAULT 0, -- Admin policy, default false
    near_expiry_warning_days INTEGER NOT NULL DEFAULT 90,
    default_slot_duration_mins INTEGER NOT NULL DEFAULT 15,
    buffer_time_mins INTEGER NOT NULL DEFAULT 0,
    working_days_json TEXT NOT NULL DEFAULT '["MON","TUE","WED","THU","FRI","SAT"]',
    working_hours_start TEXT NOT NULL DEFAULT '09:00',
    working_hours_end TEXT NOT NULL DEFAULT '17:00',
    receipt_header_title TEXT DEFAULT 'ZAYVORA Matab Dawakhana',
    receipt_footer_note TEXT DEFAULT 'Computer generated receipt. Clinical care is independent of billing.',
    inventory_valuation_method TEXT NOT NULL DEFAULT 'FEFO_BATCH_COST',
    updated_by TEXT REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Practitioner Schedules & Working Hours
CREATE TABLE IF NOT EXISTS practitioner_schedules (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    practitioner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day_of_week TEXT NOT NULL DEFAULT 'ALL', -- 'MON','TUE','WED','THU','FRI','SAT','SUN','ALL'
    start_time TEXT NOT NULL DEFAULT '09:00',
    end_time TEXT NOT NULL DEFAULT '17:00',
    break_start_time TEXT DEFAULT '13:00',
    break_end_time TEXT DEFAULT '14:00',
    slot_duration_mins INTEGER NOT NULL DEFAULT 15,
    buffer_time_mins INTEGER NOT NULL DEFAULT 0,
    slot_capacity INTEGER NOT NULL DEFAULT 1,
    room_resource TEXT DEFAULT 'Room-1',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, practitioner_id, day_of_week)
);

CREATE INDEX IF NOT EXISTS idx_prac_sched_lookup ON practitioner_schedules(facility_id, practitioner_id, is_active);

-- 3. Practitioner Leave / Holiday / Resource Blocks
CREATE TABLE IF NOT EXISTS practitioner_schedule_blocks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    practitioner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    block_start_at TEXT NOT NULL, -- ISO-8601 timestamp
    block_end_at TEXT NOT NULL,   -- ISO-8601 timestamp
    block_type TEXT NOT NULL DEFAULT 'LEAVE', -- 'LEAVE', 'HOLIDAY', 'ADMINISTRATIVE_BLOCK'
    reason TEXT NOT NULL,
    conflict_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prac_blocks_lookup ON practitioner_schedule_blocks(facility_id, practitioner_id, block_start_at, block_end_at);

-- 4. Clinic Appointments (Full Scheduling & State Machine)
CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    practitioner_id TEXT NOT NULL REFERENCES users(id),
    room_resource TEXT DEFAULT 'Room-1',
    start_at TEXT NOT NULL, -- ISO-8601
    end_at TEXT NOT NULL,   -- ISO-8601
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    appointment_type TEXT NOT NULL DEFAULT 'INITIAL_CONSULTATION', -- 'INITIAL_CONSULTATION', 'FOLLOW_UP', 'PROCEDURE_TADBIR', 'TELECONSULTATION', 'WALK_IN_SLOT'
    status TEXT NOT NULL DEFAULT 'booked', -- 'requested', 'booked', 'confirmed', 'arrived', 'in_progress', 'completed', 'cancelled', 'rescheduled', 'no_show'
    reason_category TEXT NOT NULL DEFAULT 'GENERAL_CONSULTATION', -- Privacy-safe category
    clinical_reason_notes TEXT, -- Restricted from public/unprivileged views
    booking_source TEXT NOT NULL DEFAULT 'FRONT_DESK', -- 'FRONT_DESK', 'CLINICIAN_FOLLOWUP', 'PHONE', 'WALK_IN'
    followup_task_id TEXT REFERENCES follow_up_tasks(id) ON DELETE SET NULL,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    rescheduled_from_id TEXT REFERENCES appointments(id) ON DELETE SET NULL,
    cancellation_reason TEXT,
    reschedule_reason TEXT,
    reminder_eligible INTEGER NOT NULL DEFAULT 1,
    reminder_status TEXT NOT NULL DEFAULT 'NOT_QUEUED', -- 'NOT_QUEUED', 'QUEUED', 'SENT', 'OPTED_OUT'
    slot_lock_key TEXT UNIQUE, -- Active lock: facility_id|practitioner_id|start_at when status IN ('requested','booked','confirmed','arrived','in_progress'); NULL when cancelled/rescheduled/no_show
    idempotency_key TEXT UNIQUE,
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    updated_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_appointments_calendar ON appointments(organization_id, facility_id, practitioner_id, start_at, status);
CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(organization_id, patient_id, start_at);

-- 5. Appointment Audit Events
CREATE TABLE IF NOT EXISTS appointment_events (
    id TEXT PRIMARY KEY,
    appointment_id TEXT NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'CREATED', 'CONFIRMED', 'CHECKED_IN', 'STARTED', 'COMPLETED', 'CANCELLED', 'RESCHEDULED', 'NO_SHOW'
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT,
    metadata_json TEXT,
    actor_id TEXT NOT NULL REFERENCES users(id),
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_appt_events_appt ON appointment_events(appointment_id, occurred_at);

-- 6. OPD Token & Waiting Queue
CREATE TABLE IF NOT EXISTS queue_tokens (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    queue_date TEXT NOT NULL, -- YYYY-MM-DD in facility timezone
    token_number INTEGER NOT NULL,
    token_code TEXT NOT NULL, -- e.g. 'T-001'
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    appointment_id TEXT REFERENCES appointments(id) ON DELETE SET NULL,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    practitioner_id TEXT NOT NULL REFERENCES users(id),
    department_queue TEXT NOT NULL DEFAULT 'GENERAL_OPD',
    visit_type TEXT NOT NULL DEFAULT 'WALK_IN', -- 'WALK_IN', 'SCHEDULED'
    priority TEXT NOT NULL DEFAULT 'NORMAL', -- 'NORMAL', 'ELDERLY_ASSISTED', 'CLINICAL_URGENT'
    priority_reason TEXT,
    priority_authorized_by TEXT REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'waiting', -- 'checked_in', 'waiting', 'called', 'in_consultation', 'paused', 'completed', 'cancelled', 'no_show'
    arrival_at TEXT NOT NULL,
    called_at TEXT,
    consultation_started_at TEXT,
    consultation_ended_at TEXT,
    pause_reason TEXT,
    cancel_reason TEXT,
    active_patient_queue_lock TEXT UNIQUE, -- Prevents accidental duplicate active token for same patient/practitioner/date
    idempotency_key TEXT UNIQUE,
    created_by TEXT NOT NULL REFERENCES users(id),
    updated_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, queue_date, practitioner_id, token_number)
);

CREATE INDEX IF NOT EXISTS idx_queue_tokens_live ON queue_tokens(organization_id, facility_id, queue_date, practitioner_id, status);
CREATE INDEX IF NOT EXISTS idx_queue_tokens_patient ON queue_tokens(patient_id, queue_date);

-- 7. Queue Token Audit Events
CREATE TABLE IF NOT EXISTS queue_token_events (
    id TEXT PRIMARY KEY,
    token_id TEXT NOT NULL REFERENCES queue_tokens(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT,
    actor_id TEXT NOT NULL REFERENCES users(id),
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_queue_token_events_tok ON queue_token_events(token_id, occurred_at);

-- 8. Service & Fee Catalog
CREATE TABLE IF NOT EXISTS fee_catalog_items (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'CONSULTATION', -- 'CONSULTATION', 'FOLLOW_UP_CONSULTATION', 'PROCEDURE_TADBIR', 'DISPENSARY_MEDICATION', 'OTHER'
    currency TEXT NOT NULL DEFAULT 'INR',
    unit_price_decimal TEXT NOT NULL, -- Exact decimal string e.g. '300.00'
    tax_rate_bp INTEGER NOT NULL DEFAULT 0, -- Basis points (e.g. 500 = 5.00%)
    is_active INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);

-- 9. Invoices (Draft -> Finalized -> Paid / Voided / Refunded)
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    invoice_number TEXT NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    appointment_id TEXT REFERENCES appointments(id) ON DELETE SET NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'FINALIZED', 'PARTIALLY_PAID', 'PAID', 'VOIDED', 'REFUNDED'
    subtotal_decimal TEXT NOT NULL DEFAULT '0.00',
    discount_decimal TEXT NOT NULL DEFAULT '0.00',
    discount_reason TEXT,
    tax_decimal TEXT NOT NULL DEFAULT '0.00',
    total_decimal TEXT NOT NULL DEFAULT '0.00',
    paid_decimal TEXT NOT NULL DEFAULT '0.00',
    refunded_decimal TEXT NOT NULL DEFAULT '0.00',
    balance_due_decimal TEXT NOT NULL DEFAULT '0.00',
    notes TEXT,
    finalized_at TEXT,
    finalized_by TEXT REFERENCES users(id),
    finalized_snapshot_json TEXT, -- Immutable snapshot upon finalization
    voided_at TEXT,
    voided_by TEXT REFERENCES users(id),
    void_reason TEXT,
    idempotency_key TEXT UNIQUE,
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, invoice_number)
);

CREATE INDEX IF NOT EXISTS idx_invoices_lookup ON invoices(organization_id, facility_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_invoices_patient ON invoices(organization_id, patient_id, created_at);

-- 10. Invoice Line Items
CREATE TABLE IF NOT EXISTS invoice_lines (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    fee_item_id TEXT REFERENCES fee_catalog_items(id) ON DELETE SET NULL,
    inventory_item_id TEXT,
    description TEXT NOT NULL,
    quantity_decimal TEXT NOT NULL DEFAULT '1.00',
    unit_price_decimal TEXT NOT NULL,
    discount_decimal TEXT NOT NULL DEFAULT '0.00',
    tax_rate_bp INTEGER NOT NULL DEFAULT 0,
    tax_amount_decimal TEXT NOT NULL DEFAULT '0.00',
    line_total_decimal TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_invoice_lines_inv ON invoice_lines(invoice_id, sort_order);

-- 11. Payments & Receipts (Immutable once posted)
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    payment_number TEXT NOT NULL,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    currency TEXT NOT NULL DEFAULT 'INR',
    amount_decimal TEXT NOT NULL,
    refunded_amount_decimal TEXT NOT NULL DEFAULT '0.00',
    payment_method TEXT NOT NULL, -- 'CASH', 'UPI', 'CARD', 'BANK_TRANSFER', 'MANUAL_OTHER'
    provider_mode TEXT NOT NULL DEFAULT 'MANUAL_RECORDED', -- 'MANUAL_RECORDED', 'EXTERNAL_PROVIDER'
    provider_reference TEXT,
    status TEXT NOT NULL DEFAULT 'POSTED', -- 'POSTED', 'PENDING_PROVIDER', 'FAILED', 'UNKNOWN', 'PARTIALLY_REFUNDED', 'REFUNDED'
    failure_reason TEXT,
    receipt_number TEXT UNIQUE,
    receipt_snapshot_json TEXT,
    recorded_by TEXT NOT NULL REFERENCES users(id),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    idempotency_key TEXT UNIQUE,
    UNIQUE(organization_id, payment_number)
);

CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id, status);
CREATE INDEX IF NOT EXISTS idx_payments_facility_date ON payments(organization_id, facility_id, status, recorded_at);

-- 12. Payment Allocations
CREATE TABLE IF NOT EXISTS payment_allocations (
    id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    allocated_amount_decimal TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. Refunds / Credit Adjustments (Auditable, Permission-Controlled)
CREATE TABLE IF NOT EXISTS payment_refunds (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    refund_number TEXT NOT NULL,
    payment_id TEXT NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    currency TEXT NOT NULL DEFAULT 'INR',
    amount_decimal TEXT NOT NULL,
    refund_method TEXT NOT NULL DEFAULT 'CASH',
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'COMPLETED', -- 'COMPLETED', 'FAILED'
    authorized_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    idempotency_key TEXT UNIQUE,
    UNIQUE(organization_id, refund_number)
);

CREATE INDEX IF NOT EXISTS idx_refunds_payment ON payment_refunds(payment_id);

-- 14. Daily Shift & Terminal Reconciliation
CREATE TABLE IF NOT EXISTS billing_reconciliations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    reconciliation_date TEXT NOT NULL, -- YYYY-MM-DD
    shift_code TEXT NOT NULL DEFAULT 'FULL_DAY',
    currency TEXT NOT NULL DEFAULT 'INR',
    expected_cash_decimal TEXT NOT NULL,
    counted_cash_decimal TEXT NOT NULL,
    variance_decimal TEXT NOT NULL,
    total_collections_decimal TEXT NOT NULL,
    total_refunds_decimal TEXT NOT NULL,
    notes TEXT,
    reconciled_by TEXT NOT NULL REFERENCES users(id),
    reconciled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 15. Suppliers & Vendors
CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    license_number TEXT,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);

-- 16. Inventory Storage Locations
CREATE TABLE IF NOT EXISTS inventory_locations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    location_type TEXT NOT NULL DEFAULT 'MAIN_DISPENSARY', -- 'MAIN_DISPENSARY', 'QUARANTINE_HOLD', 'BULK_STORE'
    is_dispensable INTEGER NOT NULL DEFAULT 1, -- 0 for QUARANTINE_HOLD
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, code)
);

-- 17. Dispensary / Pharmacy Inventory Item Catalog
CREATE TABLE IF NOT EXISTS inventory_items (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    formulation_id TEXT REFERENCES formulations(id) ON DELETE SET NULL,
    ingredient_id TEXT REFERENCES ingredient_catalog(id) ON DELETE SET NULL,
    dosage_form TEXT NOT NULL DEFAULT 'MAJOON',
    strength TEXT,
    unit TEXT NOT NULL DEFAULT 'g', -- 'g', 'mg', 'ml', 'bottle', 'pack', 'hab', 'qurs'
    reorder_threshold_decimal TEXT NOT NULL DEFAULT '100.00',
    standard_cost_decimal TEXT NOT NULL DEFAULT '0.00',
    selling_price_decimal TEXT NOT NULL DEFAULT '0.00',
    manufacturer_name TEXT,
    is_controlled_mudabbar INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, sku)
);

CREATE INDEX IF NOT EXISTS idx_inv_items_lookup ON inventory_items(organization_id, facility_id, is_active);
CREATE INDEX IF NOT EXISTS idx_inv_items_formulation ON inventory_items(formulation_id);

-- 18. Purchase Orders
CREATE TABLE IF NOT EXISTS purchase_orders (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    po_number TEXT NOT NULL,
    supplier_id TEXT NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'RECEIVED', -- 'ORDERED', 'RECEIVED', 'CANCELLED'
    invoice_reference TEXT,
    notes TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, po_number)
);

-- 19. Inventory Batches / Lots (FEFO, Expiry & Quarantine Governed)
CREATE TABLE IF NOT EXISTS inventory_batches (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    inventory_item_id TEXT NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    location_id TEXT NOT NULL REFERENCES inventory_locations(id) ON DELETE RESTRICT,
    supplier_id TEXT REFERENCES suppliers(id) ON DELETE SET NULL,
    purchase_order_id TEXT REFERENCES purchase_orders(id) ON DELETE SET NULL,
    batch_number TEXT NOT NULL,
    manufactured_date TEXT, -- YYYY-MM-DD
    expiry_date TEXT NOT NULL, -- YYYY-MM-DD
    status TEXT NOT NULL DEFAULT 'AVAILABLE', -- 'AVAILABLE', 'QUARANTINED', 'RECALLED', 'EXPIRED_HOLD', 'DEPLETED'
    quarantine_reason TEXT,
    quantity_on_hand_decimal TEXT NOT NULL DEFAULT '0.00',
    quantity_reserved_decimal TEXT NOT NULL DEFAULT '0.00',
    unit_cost_decimal TEXT NOT NULL DEFAULT '0.00',
    selling_price_decimal TEXT NOT NULL DEFAULT '0.00',
    vendor_compliance_note TEXT,
    version INTEGER NOT NULL DEFAULT 1, -- Optimistic concurrency lock for simultaneous dispensing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, inventory_item_id, batch_number, location_id)
);

CREATE INDEX IF NOT EXISTS idx_inv_batches_fefo ON inventory_batches(facility_id, inventory_item_id, status, expiry_date);

-- 20. Inventory Movements Ledger (Immutable Append-Only Stock History)
CREATE TABLE IF NOT EXISTS inventory_movements (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    movement_number TEXT NOT NULL,
    movement_type TEXT NOT NULL, -- 'STOCK_RECEIPT', 'DISPENSE_ISSUE', 'ADJUSTMENT_GAIN', 'ADJUSTMENT_LOSS', 'TRANSFER_OUT', 'TRANSFER_IN', 'QUARANTINE_HOLD', 'RETURN_FROM_PATIENT', 'EXPIRY_WRITEOFF', 'REVERSAL'
    inventory_item_id TEXT NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    batch_id TEXT NOT NULL REFERENCES inventory_batches(id) ON DELETE RESTRICT,
    from_location_id TEXT REFERENCES inventory_locations(id),
    to_location_id TEXT REFERENCES inventory_locations(id),
    quantity_delta_decimal TEXT NOT NULL, -- Signed decimal string (+ for receipt/gain, - for dispense/loss/writeoff)
    balance_after_decimal TEXT NOT NULL,
    unit TEXT NOT NULL,
    unit_cost_decimal TEXT NOT NULL DEFAULT '0.00',
    source_reference_type TEXT NOT NULL, -- 'PURCHASE_RECEIPT', 'DISPENSE_RECORD', 'STOCKTAKE', 'MANUAL_ADJUSTMENT', 'QUARANTINE_ACTION', 'EXPIRY_ACTION', 'MOVEMENT_REVERSAL'
    source_reference_id TEXT,
    reversal_of_movement_id TEXT REFERENCES inventory_movements(id),
    reason TEXT NOT NULL,
    authorized_by TEXT REFERENCES users(id),
    actor_id TEXT NOT NULL REFERENCES users(id),
    idempotency_key TEXT UNIQUE,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, movement_number)
);

CREATE INDEX IF NOT EXISTS idx_inv_movements_batch ON inventory_movements(batch_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_inv_movements_item ON inventory_movements(organization_id, facility_id, inventory_item_id, occurred_at);

-- 21. Stocktake Sessions & Reconciliation Lines
CREATE TABLE IF NOT EXISTS stocktake_sessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    session_number TEXT NOT NULL,
    location_id TEXT NOT NULL REFERENCES inventory_locations(id),
    status TEXT NOT NULL DEFAULT 'COMPLETED', -- 'OPEN', 'COMPLETED', 'CANCELLED'
    notes TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    approved_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    UNIQUE(organization_id, session_number)
);

CREATE TABLE IF NOT EXISTS stocktake_lines (
    id TEXT PRIMARY KEY,
    stocktake_id TEXT NOT NULL REFERENCES stocktake_sessions(id) ON DELETE CASCADE,
    batch_id TEXT NOT NULL REFERENCES inventory_batches(id),
    inventory_item_id TEXT NOT NULL REFERENCES inventory_items(id),
    expected_qty_decimal TEXT NOT NULL,
    counted_qty_decimal TEXT NOT NULL,
    variance_qty_decimal TEXT NOT NULL,
    adjustment_movement_id TEXT REFERENCES inventory_movements(id),
    reason TEXT
);

-- 22. Prescription Dispensing Records & Line Items (Strictly linked to SIGNED prescriptions)
CREATE TABLE IF NOT EXISTS dispense_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    dispense_number TEXT NOT NULL,
    prescription_id TEXT NOT NULL REFERENCES prescriptions(id) ON DELETE RESTRICT,
    prescription_version INTEGER NOT NULL DEFAULT 1,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    prescriber_id TEXT NOT NULL REFERENCES users(id),
    dispenser_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'DISPENSED', -- 'DISPENSED', 'PARTIALLY_DISPENSED', 'REFUSED_OR_UNAVAILABLE', 'RETURNED'
    verification_notes TEXT,
    label_payload_json TEXT NOT NULL, -- Reviewed patient label & instructions
    idempotency_key TEXT UNIQUE,
    dispensed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, dispense_number)
);

CREATE INDEX IF NOT EXISTS idx_dispense_rx ON dispense_records(prescription_id, status);
CREATE INDEX IF NOT EXISTS idx_dispense_patient ON dispense_records(organization_id, patient_id, dispensed_at);

CREATE TABLE IF NOT EXISTS dispense_lines (
    id TEXT PRIMARY KEY,
    dispense_id TEXT NOT NULL REFERENCES dispense_records(id) ON DELETE CASCADE,
    prescription_item_id TEXT REFERENCES prescription_items(id) ON DELETE SET NULL,
    inventory_item_id TEXT REFERENCES inventory_items(id) ON DELETE RESTRICT,
    batch_id TEXT REFERENCES inventory_batches(id) ON DELETE RESTRICT,
    movement_id TEXT REFERENCES inventory_movements(id) ON DELETE RESTRICT,
    line_status TEXT NOT NULL DEFAULT 'DISPENSED', -- 'DISPENSED', 'PARTIAL_FILL', 'SUBSTITUTED_APPROVED', 'UNAVAILABLE', 'REFUSED', 'RETURNED'
    prescribed_item_name TEXT NOT NULL,
    prescribed_dose_instructions TEXT,
    dispensed_qty_decimal TEXT NOT NULL DEFAULT '0.00',
    returned_qty_decimal TEXT NOT NULL DEFAULT '0.00',
    unit TEXT NOT NULL DEFAULT 'g',
    is_substituted INTEGER NOT NULL DEFAULT 0,
    substitution_reason TEXT,
    substitution_approved_by TEXT REFERENCES users(id), -- Mandatory clinician/pharmacist approval when is_substituted=1
    label_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dispense_lines_disp ON dispense_lines(dispense_id);
