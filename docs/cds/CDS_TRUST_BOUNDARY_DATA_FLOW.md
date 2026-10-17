# CDS Trust Boundary & Clinical Data-Flow Architecture

**Document ID:** CDS-TB-DF-2026-01  
**Project:** ZAYVORA MATAB OS  
**Phase:** 23 — Clinical Decision Support Orchestrator & Clinician Approval Workflow  
**Status:** Approved & Enforced

---

## 1. Architectural Philosophy & Zero-Trust Perimeter

In ZAYVORA MATAB OS, AI models, knowledge embeddings, external FHIR transfers, and client browsers operate strictly **outside** the privileged clinical authority boundary. 

1. **Client UI is Untrusted:** The frontend cannot assert that safety checks passed, that an identity is verified, or that an encounter is signed.
2. **AI / RAG Layer is Advisory Only:** The Hybrid RAG engine (Prompt 22) synthesizes cited information; it cannot execute database writes, change encounter status, or approve its own draft suggestions.
3. **Deterministic Safety Firewall is Independent:** Prompt 07 safety checks run on server-side relational tables; their findings cannot be silenced or bypassed by language models.
4. **Relational Database is Authoritative:** SQLite in WAL mode guarantees ACID persistence, foreign-key referential integrity, and verifiable immutability.

---

## 2. Trust Boundary Diagram

```mermaid
flowchart TD
    subgraph UNTRUSTED_CLIENT_TIER["Untrusted Client Tier (Web Browser / Tablet)"]
        UI["Clinician Consultation Canvas (HTML5/ES6)"]
        PIN_INPUT["Clinician Electronic Signature PIN"]
    end

    subgraph API_GATEWAY_TIER["API Gateway & Authorization Perimeter"]
        GW["REST API Router & Session Validator"]
        RBAC["RBAC / ABAC Scope Enforcement"]
    end

    subgraph CDS_ORCHESTRATION_TIER["Privileged CDS Orchestration Tier (Server)"]
        ECR["Encounter Context Resolver"]
        WSM["Workflow State Machine"]
        COMP["Decision-Support Composer"]
        GATE["6-Dimension Readiness Gatekeeper"]
        SIGN["Cryptographic Sign-off Service (SHA-256)"]
        KILL["Administrative Kill Switch"]
    end

    subgraph GOVERNED_SERVICES_TIER["Governed Services Tier"]
        RAG["Evidence-Aware Hybrid RAG Engine (P22)"]
        KAVS["KAVS Foundation & Catalog (P17-21)"]
        FIREWALL["Deterministic Safety Firewall (P07)"]
        RX["Prescription Engine & Nuskha Builder (P03)"]
    end

    subgraph PERSISTENCE_TIER["Authoritative Relational Persistence"]
        DB[(matab.db - Relational Store)]
        AUDIT[(Audit Ledger & Tamper-Evident Events)]
    end

    %% Flows
    UI -->|1. Charting & CDS Request| GW
    PIN_INPUT -->|8. Sign Request + PIN| GW
    GW --> RBAC
    RBAC -->|Authorized Call| ECR
    
    ECR -->|2. Resolve Snapshot Version| WSM
    WSM -->|3. Fetch Approved Knowledge| RAG
    RAG -->|Read-Only Lookup| KAVS
    WSM -->|4. Run Safety Preflight| FIREWALL
    
    RAG -->|5. Structured Cards & Citations| COMP
    FIREWALL -->|Structured Safety Findings| COMP
    
    COMP -->|6. Render Reviewable Cards| UI
    UI -->|7. Clinician Action: Accept / Reject / Edit| WSM
    
    WSM -->|Draft Hand-off| RX
    RX -->|Validate Draft Items| FIREWALL
    
    WSM -->|Evaluate Pre-Signature| GATE
    GATE -->|Verify Prerequisites| SIGN
    SIGN -->|Write Signed Snapshot & Hash| DB
    SIGN -->|Emit Immutable Event| AUDIT
    KILL -.->|Emergency Disconnect| COMP
```

---

## 3. Data Flow Steps & Invariants

| Step | Action | Trust Boundary Crossing | Security & Clinical Guarantees |
|---|---|---|---|
| **1. Request** | Clinician opens encounter and triggers CDS run. | Untrusted Client $\rightarrow$ API Gateway | Enforces tenant isolation, session freshness, and `cds:run` permission. |
| **2. Snapshot** | Context Resolver pulls patient vitals, allergies, active meds, and diagnosis. | API Gateway $\rightarrow$ Orchestration Tier | Locks encounter snapshot version ($N$). Conflicting data flagged explicitly. |
| **3. Knowledge** | Retrieval Adapter requests cited literature. | Orchestrator $\rightarrow$ Hybrid RAG (P22) | Minimum necessary patient context passed. Zero patient data leakage into global index. |
| **4. Safety** | Safety Evaluation Adapter invokes Prompt 07 firewall. | Orchestrator $\rightarrow$ Safety Firewall | Deterministic rule execution against canonical substances. Distinguishes `completed_within_scope` from absolute safety. |
| **5. Synthesis** | Decision-Support Composer formats typed cards. | Governed Services $\rightarrow$ Composer | Cards bind triggering inputs, evidence IDs, limitations, and severities. |
| **6. Review** | Cards rendered on Zone 3 guidance rail. | Composer $\rightarrow$ Clinician UI | No card defaults to accepted. Strong alerts reserved for blockers. |
| **7. Decision** | Clinician records accept, reject, edit, or defer action with mandatory rationale for blockers. | Clinician UI $\rightarrow$ Orchestrator | Attributed to clinician ID, timestamp, and review hash. Stored in `cds_reviews`. |
| **8. Sign-off** | Clinician enters signature PIN to finalize encounter. | Clinician UI $\rightarrow$ Readiness Gate | Evaluates all 6 readiness dimensions. Computes canonical SHA-256 digital fingerprint. |
| **9. Commit** | Encounter marked `signed`; immutable audit event emitted. | Orchestrator $\rightarrow$ Relational DB | Record becomes write-protected. Subsequent modifications require versioned amendment. |
