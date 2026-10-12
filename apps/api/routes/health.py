"""Health and Readiness Endpoints for Observability."""

import time
from typing import Dict, Any, Tuple
import sqlite3
from apps.api.config import config

START_TIME = time.time()

def handle_health_live(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Process liveness check: confirms web process is alive."""
    return 200, {
        "status": "LIVE",
        "service": "ZAYVORA MATAB OS API",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "request_id": req.get("request_id")
    }

def handle_health_ready(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Readiness check: confirms database connectivity, schema migrations, and valid config."""
    issues = []
    
    # 1. Check database connectivity
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        db_connected = True
    except Exception as e:
        db_connected = False
        issues.append(f"Database error: {str(e)}")

    # 2. Check migrations
    migrations_count = 0
    if db_connected:
        try:
            cursor.execute("SELECT COUNT(*) as count FROM schema_migrations;")
            migrations_count = cursor.fetchone()["count"]
            if migrations_count == 0:
                issues.append("Database schema has zero applied migrations.")
        except Exception:
            issues.append("schema_migrations table missing.")

    # 3. Check configuration safety
    config_errors = config.validate_production_readiness()
    if config_errors:
        issues.extend(config_errors)

    if issues:
        return 503, {
            "status": "NOT_READY",
            "service": "ZAYVORA MATAB OS API",
            "database_connected": db_connected,
            "migrations_applied": migrations_count,
            "issues": issues,
            "request_id": req.get("request_id")
        }

    return 200, {
        "status": "READY",
        "service": "ZAYVORA MATAB OS API",
        "database_connected": True,
        "migrations_applied": migrations_count,
        "environment": config.env,
        "request_id": req.get("request_id")
    }
