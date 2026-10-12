# ADR-002: Relational-First Persistence over Vector/Graph Stores

- **Status:** Accepted
- **Context:** Graph databases and vector stores were previously proposed for unified clinical knowledge and patient records. However, clinical encounters, prescriptions, stock inventory, and user identities require strict ACID guarantees, foreign-key referential integrity, and atomic transactions.
- **Decision:** The relational database (PostgreSQL 16 in enterprise environments, SQLite in WAL mode for Matab/Clinic edge nodes) is the single authoritative source of truth for all clinical transactions, patient data, prescriptions, and audit events. Graph or vector stores may only be utilized as read-only auxiliary indexes for literature search and similarity retrieval.
- **Consequences:** Ensures non-repudiation, referential integrity, zero data loss during power outages on edge hardware, and simplified backup/restore workflows.
