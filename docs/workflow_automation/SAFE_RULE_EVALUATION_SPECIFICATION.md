# Safe Rule Evaluation Specification & Condition Language

**Product:** ZAYVORA MATAB OS — Standalone Unani Clinic & Practice Operating System  
**Phase:** 35 — Clinical Workflow Automation, Rules Engine & Human-Approved Task Orchestration  
**Status:** Approved Technical Specification  

---

## 1. Safety Principles & Execution Constraints

1. **No Dynamic Code Execution:** The rule evaluator strictly forbids `eval()`, `exec()`, arbitrary JavaScript, dynamic module imports, regex compilation from untrusted strings, or raw SQL queries.
2. **Deterministic Evaluation:** For a given event payload, rule definition, and system context, evaluation is a pure function that returns the exact same outcome every time.
3. **Fail-Closed on Ambiguity:** If a required field is missing, null, or has an unexpected type, conditions evaluate to `False` (or `needs_review` when a mandatory condition cannot be assessed). Permissive truth is prohibited.
4. **No LLM / AI in Evaluation Path:** Rule conditions do not query LLMs, web search, or probabilistic heuristics during operational execution.

---

## 2. Bounded Condition Grammar

Each condition in a rule's `conditions_json` array has the schema:

```json
{
  "field": "event.appointment.status",
  "operator": "equals",
  "value": "booked"
}
```

### Supported Operators:

| Operator | Type Applicability | Semantics | Example |
| :--- | :--- | :--- | :--- |
| `equals` | String, Number, Boolean | Exact value equality. | `{"field": "status", "operator": "equals", "value": "booked"}` |
| `not_equals` | String, Number, Boolean | Inverted equality. Returns `True` if field does not equal value. | `{"field": "status", "operator": "not_equals", "value": "cancelled"}` |
| `in` | Array / List | Field value is an element of the provided array. | `{"field": "visit_type", "operator": "in", "value": ["INITIAL", "FOLLOW_UP"]}` |
| `not_in` | Array / List | Field value is NOT an element of the provided array. | `{"field": "status", "operator": "not_in", "value": ["cancelled", "no_show"]}` |
| `exists` | Any | Target field is present and not `null`. | `{"field": "patient.phone", "operator": "exists", "value": true}` |
| `not_exists` | Any | Target field is absent, null, or empty string. | `{"field": "patient.phone", "operator": "not_exists", "value": true}` |
| `greater_than` | Number | Numeric comparison: `field > value`. | `{"field": "elapsed_mins", "operator": "greater_than", "value": 45}` |
| `less_than` | Number | Numeric comparison: `field < value`. | `{"field": "stock_count", "operator": "less_than", "value": 10}` |
| `before` | ISO-8601 Datetime | Timestamp comparison: `field < value`. | `{"field": "due_at", "operator": "before", "value": "2026-10-15T00:00:00Z"}` |
| `after` | ISO-8601 Datetime | Timestamp comparison: `field > value`. | `{"field": "created_at", "operator": "after", "value": "2026-10-01T00:00:00Z"}` |

---

## 3. Dot-Notation Field Resolution

The evaluator resolves nested fields safely using an allowlisted root dictionary:
- `event.*`: Fields from the triggering domain event payload.
- `context.*`: System context (e.g. `current_time`, `facility_id`, `organization_id`).

Path traversal is bounded to maximum 4 levels deep and protects against `__proto__`, `__class__`, or private attributes.

---

## 4. Rule Lifecycle & Versioning State Machine

```
      ┌───────────┐
      │   DRAFT   │ ──(submit_for_review)──> ┌─────────────┐
      └─────┬─────┘                          │  IN_REVIEW  │
            │                                └──────┬──────┘
            │                                       │
     (dry_run_test)                               (approve)
            │                                       │
            ▼                                       ▼
      ┌───────────┐                          ┌─────────────┐
      │  PREVIEW  │                          │  APPROVED   │
      └───────────┘                          └──────┬──────┘
                                                    │
                                                (activate)
                                                    │
                                                    ▼
      ┌───────────┐                          ┌─────────────┐
      │  RETIRED  │ <───────(retire)──────── │   ACTIVE    │
      └───────────┘                          └──────┬──────┘
                                                    │
                                                 (pause)
                                                    │
                                                    ▼
                                             ┌─────────────┐
                                             │   PAUSED    │
                                             └─────────────┘
```

---

## 5. Dry-Run Sandbox Isolation

When a user executes a dry run via `POST /api/v1/workflow/rules/{id}/dry-run`:
- The evaluator runs against the provided test event.
- It returns matched rules, conditions met, and proposed actions.
- **Zero Side Effects:** No tasks are inserted into production tables, no messages are sent to the outbox, and no external adapters are invoked.
- The dry-run result is labeled `is_dry_run: true` and can be attached to the rule as immutable validation evidence.
