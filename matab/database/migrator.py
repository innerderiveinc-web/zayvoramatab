"""Database Migrator for ZAYVORA MATAB OS."""

import os
from pathlib import Path
import sqlite3
from matab.config import config
from matab.database.connection import DatabaseConnection

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

def run_migrations(db_path: str = None) -> None:
    """Execute all pending SQL migrations in alphabetical order."""
    manager = DatabaseConnection(db_path or config.db_path)
    conn = manager.get_connection()
    try:
        # Ensure migrations table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

        # Get already applied migrations
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
        applied = {row["version"] for row in cursor.fetchall()}

        # Find migration files
        migration_files = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")])

        for fname in migration_files:
            if fname not in applied:
                fpath = MIGRATIONS_DIR / fname
                with open(fpath, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                # Execute migration script in transaction
                conn.executescript(sql_content)
                conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (fname,))
                conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migrations()
    print("Database migrations applied successfully.")
