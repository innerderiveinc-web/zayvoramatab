# Clinic Downtime Continuity & Offline Reconciliation Protocol

**Document Code:** SOP-CLN-CNT-004  
**Applicability:** Matab Front Desk, Consulting Hakeems, Dispensary Staff  
**System:** ZAYVORA MATAB OS (Prompt 56)

---

## 1. Triggering Clinical Downtime Mode

When the electronic medical record system is inaccessible due to power outage, hardware failure, or network disruption:
1. The Senior Hakeem or Clinic Administrator declares **Clinical Downtime Mode**.
2. Front desk staff retrieve the physical **Downtime Continuity Binder** containing pre-printed, serialized paper forms:
   - Form A: Emergency Patient Intake & Demographics.
   - Form B: Clinical Consultation & Usul-e-Ilaj Worksheet.
   - Form C: Nuskha Prescription & Dispensing Record (with allergy checks).

---

## 2. In-Downtime Patient Care Safeguards

1. **Allergy & Toxicity Verification:**
   - Clinicians must consult the laminated **AYUSH Schedule E(1) & Toxic Mineral Precaution Card** stored in the downtime kit before prescribing Mudabbar or mineral formulations (e.g., Samm-ul-Far, Shangraf, Hartal).
2. **Serial Number Tracking:**
   - Every physical encounter is assigned an offline tracking code in format `DOWN-YYYYMMDD-XXXX`.
3. **Emergency Dispensing:**
   - Pharmacists log medications dispensed against the serialized paper prescription, recording batch numbers manually.

---

## 3. Post-Restoration Ingestion & Reconciliation Workflow

Once system restoration is promoted and operational availability is re-established:
1. Dedicated staff ingest each paper record via the Downtime Reconciliation API:
```bash
curl -X POST https://matab.example.com/api/v1/dr/reconciliation \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "record_type": "encounter",
    "offline_ref": "DOWN-20261015-0012",
    "patient_id": "pat-001",
    "raw_payload": {
      "chief_complaint": "Severe Su-e-Hazm with epigastric burning",
      "vitals": {"bp": "120/80", "pulse": "74"},
      "prescribed_items": ["Jawarish Kamuni", "Sharbat Bazoori"]
    }
  }'
```
2. The system checks for duplicate offline references (`409 Conflict` on duplicates).
3. A clinical supervisor reviews pending records in `/api/v1/dr/reconciliation` queue.
4. Each record is reconciled with canonical records via `/api/v1/dr/reconciliation/:id/resolve` with action `reconcile` or `merge`.
