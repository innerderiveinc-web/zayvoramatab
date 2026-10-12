# ADR-003: Modular Monolith Domain Architecture

- **Status:** Accepted
- **Context:** Premature microservice decomposition introduces high operational overhead, distributed network failures, complex orchestration, and difficult local clinic deployments.
- **Decision:** Structure ZAYVORA MATAB OS as a modular monolith. Domain boundaries (`identity`, `tenancy`, `audit`, `capabilities`) communicate through in-process contracts and shared relational transactions. Do not create separate microservices per clinical engine.
- **Consequences:** Simplifies local clinic deployment, enables atomic ACID transactions across domain tables, avoids distributed transaction failures, and lowers hosting costs.
