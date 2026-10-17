# ADR-072: Enterprise Performance, Scalability & Capacity Engineering Engine

## Status
Accepted

## Date
2026-10-15

## Context
As ZAYVORA MATAB OS prepares for enterprise deployment across single-facility community matabs and multi-branch clinical setups, empirical guarantees surrounding response times, database scalability, background task throughput, external dependency circuit breaking, and capacity headroom become non-negotiable.

Historically, complex healthcare software systems suffer from "vanity benchmarks" and speculative capacity claims—such as marketing numbers asserting support for "10,000 concurrent users" without empirical profiling of actual clinical transaction latencies, lock contention, or memory constraints. In a clinical environment, performance failures directly compromise patient safety: slow drug-interaction or posology checks lead to clinician bypasses or alarm fatigue, whereas database thread exhaustion can result in lost consultation notes or delayed emergency referrals.

Prompt 54 mandates an Enterprise Performance, Scalability & Capacity Engineering Engine to enforce evidence-based performance governance without fabricated claims.

## Decision
1. **Migration 051 Schema:**
   - `perf_benchmark_scenarios`: Standardized clinical workload scenarios specifying target $p_{95}$ and $p_{99}$ latency ceilings, maximum allowed error rate, concurrency level, and graceful degradation fallback.
   - `perf_benchmark_runs`: Telemetry logs storing empirical latency percentiles ($p_{50}, p_{95}, p_{99}$), min/max latency, throughput (RPS), error rates, resource utilization (CPU, memory), and fail-closed SLA status (`PASS`, `WARNING`, `BREACH`).
   - `perf_slow_query_registry`: Fingerprinted SQL queries with parameter normalization (literal stripping), execution counting, latency tracking ($t_{\text{avg}}, t_{\text{max}}$), and explicit indexing advisory recommendations.
   - `perf_capacity_profiles`: Bounded operational models (e.g., `CAP-OPD-SINGLE-CLINIC`) specifying assumed concurrent practitioners, daily consultations, bottleneck resources, and recommended max concurrency limits.
   - `perf_circuit_breaker_states`: State machines for external dependencies (`DEP-ABDM`, `DEP-TWILIO`, `DEP-RAZORPAY`) supporting `CLOSED`, `OPEN`, and `HALF_OPEN` states with automated recovery timeouts and clinical fallback actions.
   - `perf_governance_audit_ledger`: SHA-256 tamper-evident cryptographic blockchain recording every scenario creation, benchmark run, slow query triage, capacity evaluation, and circuit breaker trip/reset.

2. **Domain Engine (`PerformanceScalabilityEngine`):**
   - Implements linear-interpolation deterministic percentile calculations ($p_{50}, p_{95}, p_{99}$).
   - Enforces fail-closed SLA evaluation: a run breaches SLA (`BREACH`) if measured $p_{95} > \text{target\_p95\_ms}$ or $\text{error\_rate\_pct} > \text{max\_error\_rate\_pct}$, and issues a warning (`WARNING`) if $p_{99} > \text{target\_p99\_ms}$.
   - Provides an in-process live microbenchmark runner that executes repeated real queries against active database tables and collects genuine empirical latency metrics.
   - Computes capacity headroom dynamically: $\text{headroom\_pct} = \max(0.0, (1.0 - \text{active\_users} / \text{max\_concurrency}) \times 100\%)$. If measured $p_{95} \ge \text{threshold}$ or headroom $\le 10\%$, it prescribes graceful degradation actions (`ENABLE_READ_STALE_AND_DEFER_ANALYTICS` or `THROTTLE_NEW_SESSIONS_AND_QUEUE`).
   - Provides unbroken cryptographic chain verification over `perf_governance_audit_ledger`.

3. **REST Route Layer & RBAC:**
   - 14 REST endpoints mounted under `/api/v1/performance/`.
   - RBAC enforced via `performance:read`, `performance:manage`, `performance:benchmark_run`, `performance:circuit_manage`, and `performance:profile_manage`.

4. **Frontend Workbench:**
   - Dedicated tab in Knowledge Base Admin workspace displaying performance KPIs, benchmark scenarios table with in-process microbenchmark trigger, recent empirical telemetry runs table, capacity sizing profiles with interactive headroom evaluator, external dependency circuit breaker controls, and tamper-evident audit ledger verifier.

## Consequences
- **Positive:**
  - Absolute elimination of speculative or fabricated performance and capacity figures.
  - Fail-closed SLA enforcement protects clinical safety workflows from silent degradation.
  - Slow-query fingerprinting provides database administrators with actionable indexing recommendations.
  - External dependencies fail safely without cascading into the core clinical consultation engine.
  - Full auditability via cryptographic SHA-256 block chaining.
- **Negative / Operational Requirements:**
  - Requires continuous empirical load generation in isolated staging environments before major releases.
  - External dependency trips require operational staff to monitor recovery transitions to `HALF_OPEN` and `CLOSED`.
