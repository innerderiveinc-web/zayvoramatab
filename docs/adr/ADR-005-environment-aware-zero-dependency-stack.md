# ADR-005: Environment-Aware Standard Stack with Zero-Dependency Fallback

- **Status:** Accepted
- **Context:** The standard product blueprint targets Next.js + FastAPI + PostgreSQL + Docker. However, in certain constrained development, local clinic edge servers, or secure air-gapped sandboxes, external package registries, Node.js runtimes, and Docker daemons may not be pre-installed or network-reachable.
- **Decision:** Architect ZAYVORA MATAB OS to support dual-runtime deployment:
  1. **Containerized Multi-Tier Target:** Docker Compose with PostgreSQL 16, FastAPI backend, and Next.js frontend assets (definitions provided in `infra/docker-compose.yml`).
  2. **Zero-Dependency Native Python 3.9+ Engine:** A self-contained, high-performance HTTP REST and static file serving engine built on Python standard library modules (`http.server`, `sqlite3` WAL mode, `hashlib`, `json`, `urllib`).
  3. The database migration scripts and domain schemas are ANSI SQL compliant, enabling direct portability between SQLite (edge clinics) and PostgreSQL (hospital data centers).
- **Consequences:** Eliminates external build tool rot, ensures instant zero-dependency execution anywhere (<50ms boot), while preserving the exact modular monorepo structure (`apps/api`, `apps/web`, `packages/`, `infra/`, `docs/`, `tests/`).
