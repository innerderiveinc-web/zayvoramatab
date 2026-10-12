"""SQLite Database Connection Manager with WAL mode and Foreign Keys enforced."""

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator
from matab.config import config

_local = threading.local()

class DatabaseConnection:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        # Enforce foreign key constraints and Write-Ahead Logging for high concurrency
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

@contextmanager
def get_db(db_path: str = None) -> Iterator[sqlite3.Connection]:
    """Context manager for obtaining a database connection with auto-commit/rollback."""
    manager = DatabaseConnection(db_path)
    conn = manager.get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str = None) -> None:
    """Initialize database and run migrations."""
    from matab.database.migrator import run_migrations
    run_migrations(db_path)
