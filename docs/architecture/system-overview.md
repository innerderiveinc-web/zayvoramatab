# System Architecture Overview — ZAYVORA MATAB OS (Phase 1)

**Architecture Style:** Modular Monolith with Clean Boundary Decoupling  
**Primary Language:** Python 3.9+  
**Database Architecture:** PostgreSQL 16 compatible ANSI SQL / Embedded SQLite WAL for Edge Clinics  
**Web Architecture:** Standards-based Responsive Web Shell (HTML5, Modern CSS Design Tokens, Vanilla ES Modules)  

---

## 1. System Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ZAYVORA MATAB OS SHELL                          │
│     (Responsive Desktop / Tablet / Mobile, WCAG AAA High Contrast)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / JSON REST
                                    │ Bearer / Session Auth
┌───────────────────────────────────▼────────────────────────────────────┐
│                       MATAB OS BACKEND GATEWAY                         │
│  - Correlation / Request ID Middleware                                 │
│  - Deny-by-Default Permission & Role Verification                      │
│  - Organization & Facility Tenancy Boundary Scope                      │
│  - Rate Limiting on Authentication Endpoints                           │
└──────────┬────────────────────────┬────────────────────────┬───────────┘
           │                        │                        │
┌──────────▼───────────┐ ┌──────────▼───────────┐ ┌──────────▼───────────┐
│   IDENTITY & ACCESS  │ │  TENANCY & FACILITIES│ │  AUDIT & GOVERNANCE  │
│ - Users & Roles      │ │ - Organizations      │ │ - Append-only Events │
│ - Permissions Check  │ │ - Facilities (OPD)   │ │ - Capability Registry│
│ - Practitioner Prof. │ │ - Memberships        │ │ - Health / Readiness │
└──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │ ACID Relational Transactions
┌───────────────────────────────────▼────────────────────────────────────┐
│                      RELATIONAL PERSISTENCE LAYER                      │
│ - Strict Foreign Keys & Unique Constraints                             │
│ - Append-only Audit Records with Request IDs                           │
│ - Normalized Tenancy Boundaries                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Layout & Monorepo Structure

```
matab-os/
  apps/
    web/                 # Responsive web application, design tokens & views
    api/                 # REST API services, routers, security & migrations
  packages/
    ui/                  # Shared design tokens & CSS component library
    api-client/          # Typed JavaScript API client
  infra/
    docker-compose.yml   # PostgreSQL & backend orchestration
    Dockerfile           # Application container definition
    scripts/             # Database initialization and seed scripts
  docs/
    architecture/        # System topology & ADRs
    security/            # STRIDE threat model & tenant isolation
    product/             # Phase scope & product requirements
    operations/          # Local development and deployment instructions
  tests/
    unit/                # Security, auth, and capability unit tests
    integration/         # Multi-tenant boundary and API tests
    e2e/                 # End-to-end smoke tests
  .env.example           # Canonical environment configuration
  README.md              # Master entry point
```
