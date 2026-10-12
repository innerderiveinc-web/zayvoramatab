"""Versioned Database Migrator for ZAYVORA MATAB OS."""

import os
from pathlib import Path
from apps.api.config import config
from apps.api.database.connection import DatabaseConnection

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

def run_migrations(db_path: str = None) -> int:
    """Execute all pending SQL migrations in alphabetical order."""
    manager = DatabaseConnection(db_path or config.db_path)
    conn = manager.get_connection()
    applied_count = 0
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
        applied = {row["version"] for row in cursor.fetchall()}

        migration_files = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")])

        for fname in migration_files:
            if fname not in applied:
                fpath = MIGRATIONS_DIR / fname
                with open(fpath, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                conn.executescript(sql_content)
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (fname,))
                conn.commit()
                applied_count += 1
                print(f"[MIGRATOR] Applied migration: {fname}")
    finally:
        conn.close()

    return applied_count

if __name__ == "__main__":
    count = run_migrations()
    print(f"Total migrations applied: {count}")
