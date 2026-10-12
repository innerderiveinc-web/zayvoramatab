# ADR-001: Standalone Architecture and Zero Runtime Dependency on Legacy Health OS

- **Status:** Accepted
- **Context:** The legacy ZAYVORA Health OS repository was an expansive multi-package monorepo containing complex graph services, simulated client fallbacks, and shared microservices. For practicing Hakeems and clinical deployments, this introduced significant instability and cascading failure modes.
- **Decision:** Build ZAYVORA MATAB OS as a completely independent, standalone product. It must maintain its own source repository, database schema, domain engines, REST APIs, authentication, and deployment lifecycle. It will not communicate with legacy private endpoints or import code from the old project. Any future integration with external hospital systems or ZAYVORA networks must be an optional, versioned, disabled-by-default adapter.
- **Consequences:** Eliminates external runtime failures, allows local clinic server deployment without Internet access, reduces attack surface, and ensures complete operational autonomy.
