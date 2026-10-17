# ZAYVORA MATAB OS — OBSERVABILITY, INCIDENT OPERATIONS & SLO GOVERNANCE SPECIFICATION

- **Document Version:** 1.0.0
- **Phase:** Prompt 39 (Phase 39)
- **Author:** Principal Reliability Engineer & Governance Architect
- **Status:** Approved Architecture Specification

---

## 1. Architectural Scope and Principles

The Observability, Incident Response, SLO Governance & Reliability Operations Engine provides ZAYVORA MATAB OS with:
1. **Four-Tier Health Assessment:**
   - **Liveness:** Lightweight check verifying the Python API process and event loop can process requests (`/api/v1/health/live`).
   - **Readiness:** Shallow dependency verification (database connection, schema migrations, configuration flags) safe for load balancers without leaking credentials or stack traces (`/api/v1/health/ready`).
   - **Deep Diagnostics:** Authenticated inspection of database query latency, pool saturation, queue backlog, safety firewall readiness, and feature flag engine (`/api/v1/observability/diagnostics/deep`).
   - **Workflow Correctness:** Probes that verify critical business state transitions without modifying clinical records.
2. **Data Minimization & Zero PHI:**
   - Observability records must scrub passwords, tokens, patient names, mobile numbers, national health IDs (ABHA), prescription formulations, and clinical notes before persistence.
   - Low-cardinality metric labels: Metrics are tagged by route template (e.g. `/api/v1/encounters/{id}`) and outcome class (`SUCCESS`, `CLIENT_ERROR`, `SERVER_ERROR`, `TIMEOUT`, `BLOCKED`).
3. **Actionable Alert Catalog with Mandatory Runbooks:**
   - Every alert defines an explicit condition, evaluation window, owner role, and actionable runbook (diagnostic steps, mitigation options, rollback paths, prohibited actions).
   - Alerts deduplicate on stable fingerprints and require resolution evidence before clearance.
4. **Governed Service-Level Objectives (SLOs):**
   - Explicit SLI definitions with good/total event counters.
   - Owner-approved target ratios (e.g. 99.5%).
   - Dynamic error-budget burn rate calculation.
   - Transparent reporting of measurement completeness and blind spots (missing telemetry intervals are marked `MEASUREMENT_GAP`, not assumed healthy).
5. **Formal Incident Lifecycle State Machine:**
   - Governed state transitions:
     $$\text{detected} \longrightarrow \text{triaged} \longrightarrow \text{acknowledged} \longrightarrow \text{investigating} \longrightarrow \text{mitigating} \longrightarrow \text{monitoring\_recovery} \longrightarrow \text{resolved} \longrightarrow \text{postmortem\_due} \longrightarrow \text{reviewed} \longrightarrow \text{closed}$$
   - Alternate terminal / disposition states: `false_positive`, `duplicate`.
6. **Bounded Automated Remediation Guardrails:**
   - Strictly allowlisted actions: `RESTART_BACKGROUND_CONSUMER`, `PAUSE_FAILING_CONNECTOR`, `TRIP_EMERGENCY_FEATURE_FLAG`, `CLEAR_TRANSIENT_CACHE`, `RECONCILE_STALE_TRANSACTION`.
   - Hard lockouts: Zero clinical interference (cannot prescribe, calculate dose, dispense, or edit chart records).
   - Pre-condition and post-verification checks, rate limits, and 300s cooldown windows.

---

## 2. Relational Database Schema Specification

### 2.1 Table: `observability_service_catalog`
- `id` (VARCHAR(64) PRIMARY KEY): E.g. `svc-auth`, `svc-encounters`, `svc-safety-firewall`.
- `organization_id` (VARCHAR(64) NOT NULL): Tenant boundary.
- `service_key` (VARCHAR(64) NOT NULL): Unique key within org.
- `name` (VARCHAR(128) NOT NULL): Display name.
- `description` (TEXT): Service role and user-facing capability.
- `owner_role` (VARCHAR(64) NOT NULL): Accountable owner (e.g. `PLATFORM_ENGINEER`).
- `tier` (VARCHAR(32) NOT NULL): `tier_1_mission_critical`, `tier_2_business_critical`, `tier_3_supporting`.
- `upstream_dependencies_json` (TEXT NOT NULL DEFAULT '[]'): JSON list of service keys.
- `downstream_dependencies_json` (TEXT NOT NULL DEFAULT '[]'): JSON list of service keys.
- `health_status` (VARCHAR(32) NOT NULL DEFAULT 'HEALTHY'): `HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `UNKNOWN`.
- `last_probed_at` (DATETIME): Timestamp of last probe.
- `is_active` (INTEGER NOT NULL DEFAULT 1).
- `created_at`, `updated_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).

### 2.2 Table: `observability_telemetry_metrics`
- `id` (VARCHAR(64) PRIMARY KEY).
- `organization_id` (VARCHAR(64) NOT NULL).
- `metric_name` (VARCHAR(128) NOT NULL): Low-cardinality metric identifier.
- `route_or_subsystem` (VARCHAR(128) NOT NULL): Sanitized route template or subsystem name.
- `outcome_class` (VARCHAR(32) NOT NULL): `SUCCESS`, `CLIENT_ERROR`, `SERVER_ERROR`, `TIMEOUT`, `BLOCKED`.
- `metric_value` (REAL NOT NULL).
- `unit` (VARCHAR(32) NOT NULL): `count`, `ms`, `ratio`, `gauge`.
- `measurement_type` (VARCHAR(32) NOT NULL DEFAULT 'MEASURED'): `MEASURED`, `DERIVED`, `ESTIMATED`.
- `timestamp` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).
- `created_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).

### 2.3 Table: `observability_alert_definitions`
- `id` (VARCHAR(64) PRIMARY KEY).
- `organization_id` (VARCHAR(64) NOT NULL).
- `alert_key` (VARCHAR(64) NOT NULL): Unique alert identifier (e.g. `ALERT-API-HIGH-5XX-RATE`).
- `title` (VARCHAR(128) NOT NULL).
- `description` (TEXT NOT NULL).
- `service_key` (VARCHAR(64) NOT NULL).
- `severity` (VARCHAR(32) NOT NULL): `P1_CRITICAL`, `P2_HIGH`, `P3_MEDIUM`, `P4_LOW`, `P5_INFO`.
- `metric_name` (VARCHAR(128) NOT NULL).
- `condition_operator` (VARCHAR(16) NOT NULL): `GT`, `GTE`, `LT`, `LTE`, `EQ`, `NEQ`.
- `threshold_value` (REAL NOT NULL).
- `evaluation_window_seconds` (INTEGER NOT NULL DEFAULT 300).
- `owner_role` (VARCHAR(64) NOT NULL).
- `runbook_markdown` (TEXT NOT NULL).
- `notification_channels_json` (TEXT NOT NULL DEFAULT '["ops_dashboard"]').
- `dedup_fingerprint_rule` (VARCHAR(128) NOT NULL DEFAULT 'alert_key+service_key').
- `is_enabled` (INTEGER NOT NULL DEFAULT 1).
- `version` (VARCHAR(16) NOT NULL DEFAULT '1.0.0').
- `created_by`, `updated_by` (VARCHAR(64) NOT NULL).
- `created_at`, `updated_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).

### 2.4 Table: `observability_alert_instances`
- `id` (VARCHAR(64) PRIMARY KEY).
- `organization_id` (VARCHAR(64) NOT NULL).
- `alert_definition_id` (VARCHAR(64) NOT NULL).
- `alert_key` (VARCHAR(64) NOT NULL).
- `fingerprint` (VARCHAR(128) NOT NULL).
- `severity` (VARCHAR(32) NOT NULL).
- `status` (VARCHAR(32) NOT NULL DEFAULT 'FIRING'): `FIRING`, `ACKNOWLEDGED`, `RESOLVED`, `SUPPRESSED`, `INDETERMINATE_STALE`.
- `current_value` (REAL NOT NULL).
- `threshold_value` (REAL NOT NULL).
- `firing_evidence_json` (TEXT NOT NULL DEFAULT '{}').
- `resolution_evidence_json` (TEXT NOT NULL DEFAULT '{}').
- `incident_id` (VARCHAR(64)): Linked incident if escalated.
- `fired_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).
- `acknowledged_at` (DATETIME).
- `acknowledged_by` (VARCHAR(64)).
- `resolved_at` (DATETIME).
- `resolved_by` (VARCHAR(64)).
- `created_at`, `updated_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).

### 2.5 Table: `observability_slo_registry`
- `id` (VARCHAR(64) PRIMARY KEY).
- `organization_id` (VARCHAR(64) NOT NULL).
- `slo_key` (VARCHAR(64) NOT NULL): Unique key (e.g. `SLO-API-AVAILABILITY`).
- `name` (VARCHAR(128) NOT NULL).
- `service_key` (VARCHAR(64) NOT NULL).
- `sli_description` (TEXT NOT NULL).
- `target_ratio` (REAL NOT NULL): E.g. 0.995 (99.5%).
- `window_days` (INTEGER NOT NULL DEFAULT 30).
- `owner_role` (VARCHAR(64) NOT NULL).
- `approval_status` (VARCHAR(32) NOT NULL DEFAULT 'DRAFT'): `DRAFT`, `APPROVED`, `RETIRED`.
- `approved_by` (VARCHAR(64)).
- `approved_at` (DATETIME).
- `total_events` (INTEGER NOT NULL DEFAULT 0).
- `good_events` (INTEGER NOT NULL DEFAULT 0).
- `error_budget_total` (REAL NOT NULL DEFAULT 0.0).
- `error_budget_remaining` (REAL NOT NULL DEFAULT 0.0).
- `burn_rate` (REAL NOT NULL DEFAULT 0.0).
- `compliance_status` (VARCHAR(32) NOT NULL DEFAULT 'HEALTHY'): `HEALTHY`, `AT_RISK`, `BREACHED`, `MEASUREMENT_GAP`.
- `known_gaps_notes` (TEXT).
- `version` (VARCHAR(16) NOT NULL DEFAULT '1.0.0').
- `created_at`, `updated_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).

### 2.6 Table: `observability_incidents`
- `id` (VARCHAR(64) PRIMARY KEY).
- `organization_id` (VARCHAR(64) NOT NULL).
- `incident_code` (VARCHAR(64) NOT NULL): Sequential code (e.g. `INC-20261014-01`).
- `title` (VARCHAR(256) NOT NULL).
- `summary` (TEXT NOT NULL).
- `service_key` (VARCHAR(64) NOT NULL).
- `environment` (VARCHAR(32) NOT NULL): `local`, `ci_test`, `staging`, `pilot`, `production`.
- `severity` (VARCHAR(32) NOT NULL): `P1_CRITICAL`, `P2_HIGH`, `P3_MEDIUM`, `P4_LOW`.
- `status` (VARCHAR(32) NOT NULL DEFAULT 'detected'): State machine enum.
- `commander_user_id` (VARCHAR(64) NOT NULL).
- `commander_role` (VARCHAR(64) NOT NULL).
- `responders_json` (TEXT NOT NULL DEFAULT '[]').
- `impact_scope` (TEXT NOT NULL).
- `source_alert_id` (VARCHAR(64)).
- `runbook_url_or_key` (VARCHAR(128)).
- `mitigation_summary` (TEXT).
- `root_cause_summary` (TEXT).
- `resolution_evidence_json` (TEXT NOT NULL DEFAULT '{}').
- `detected_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).
- `acknowledged_at` (DATETIME).
- `mitigated_at` (DATETIME).
- `resolved_at` (DATETIME).
- `closed_at` (DATETIME).
- `created_by`, `updated_by` (VARCHAR(64) NOT NULL).
- `created_at`, `updated_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).

### 2.7 Table: `observability_incident_timeline`
- `id` (VARCHAR(64) PRIMARY KEY).
- `incident_id` (VARCHAR(64) NOT NULL).
- `actor_id` (VARCHAR(64) NOT NULL).
- `actor_role` (VARCHAR(64) NOT NULL).
- `entry_type` (VARCHAR(32) NOT NULL): `STATE_CHANGE`, `COMMUNICATION`, `EVIDENCE_ATTACHED`, `REMEDIATION_TRIGGERED`, `RUNBOOK_STEP`, `POSTMORTEM_NOTE`.
- `message` (TEXT NOT NULL).
- `payload_json` (TEXT NOT NULL DEFAULT '{}').
- `created_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).

### 2.8 Table: `observability_remediation_actions`
- `id` (VARCHAR(64) PRIMARY KEY).
- `organization_id` (VARCHAR(64) NOT NULL).
- `incident_id` (VARCHAR(64)).
- `action_type` (VARCHAR(64) NOT NULL): Allowlist only (`RESTART_BACKGROUND_CONSUMER`, `PAUSE_FAILING_CONNECTOR`, `TRIP_EMERGENCY_FEATURE_FLAG`, `CLEAR_TRANSIENT_CACHE`, `RECONCILE_STALE_TRANSACTION`).
- `target_resource` (VARCHAR(128) NOT NULL).
- `environment` (VARCHAR(32) NOT NULL).
- `status` (VARCHAR(32) NOT NULL DEFAULT 'REQUESTED'): `REQUESTED`, `EXECUTING`, `COMPLETED`, `FAILED`, `COOLDOWN_BLOCKED`, `REVERTED`.
- `precondition_check_passed` (INTEGER NOT NULL DEFAULT 1).
- `post_verification_passed` (INTEGER NOT NULL DEFAULT 1).
- `side_effect_summary` (TEXT NOT NULL).
- `retry_count` (INTEGER NOT NULL DEFAULT 0).
- `max_retries` (INTEGER NOT NULL DEFAULT 2).
- `cooldown_seconds` (INTEGER NOT NULL DEFAULT 300).
- `executed_by` (VARCHAR(64) NOT NULL).
- `error_message` (TEXT).
- `created_at`, `updated_at` (DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP).

---

## 3. Incident State Machine & Transitions

The incident state transitions must strictly validate allowed moves:
- `detected` $\to$ `triaged`, `acknowledged`, `false_positive`, `duplicate`
- `triaged` $\to$ `acknowledged`, `investigating`, `false_positive`
- `acknowledged` $\to$ `investigating`, `mitigating`
- `investigating` $\to$ `mitigating`, `monitoring_recovery`
- `mitigating` $\to$ `monitoring_recovery`, `investigating`
- `monitoring_recovery` $\to$ `resolved`, `investigating`
- `resolved` $\to$ `postmortem_due`, `closed`, `reopened`
- `postmortem_due` $\to$ `reviewed`, `closed`, `reopened`
- `reviewed` $\to$ `closed`
- `reopened` $\to$ `investigating`
- Any non-closed state $\to$ `cancelled`

**Resolution Proof Invariant:** Transitioning to `resolved` requires `resolution_evidence_json` containing proof of restored service (e.g. passing readiness probe, zero active firing alerts on the service, or confirmed test ping).
