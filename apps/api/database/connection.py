import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional
from apps.api.config import config

# Register robust timestamp and date converters to support ISO-8601 strings
def _convert_timestamp(val: bytes) -> str:
    return val.decode("utf-8")

sqlite3.register_converter("TIMESTAMP", _convert_timestamp)
sqlite3.register_converter("timestamp", _convert_timestamp)

class DatabaseConnection:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        # Enforce foreign key constraints, high-concurrency Write-Ahead Logging, and cache
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")  # 30-second busy timeout for hospital-scale multi-user concurrency
        conn.execute("PRAGMA wal_autocheckpoint = 1000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA mmap_size = 268435456;")  # 256MB memory-mapped I/O
        return conn

@contextmanager
def get_db(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """Obtain a transactional database connection with auto-commit and rollback on error."""
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
