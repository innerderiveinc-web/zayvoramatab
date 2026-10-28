"""ZAYVORA MATAB OS — Automated Database Snapshot & ACID Armor Daemon.

Runs in a low-priority background daemon thread to maintain continuous hot snapshots
of the SQLite WAL database with SHA-256 Merkle hashes.
Does NOT block active clinician operations or database reads/writes.
"""

import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime

# Reference to scripts/backup_db.py
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from scripts.backup_db import perform_backup
except ImportError:
    perform_backup = None

_daemon_started = False
_lock = threading.Lock()

def _backup_worker(interval_seconds: int = 3600):
    """Background worker loop taking hot rolling snapshots."""
    # Initial sleep of 20 seconds to allow clean application startup
    time.sleep(20)
    
    while True:
        try:
            if perform_backup:
                print("[ACID Armor] Taking automated scheduled database snapshot...")
                result = perform_backup(retention_days=30)
                if result.get("ok"):
                    print(f"[ACID Armor] ✓ Snapshot saved: {result.get('backup_path')} | SHA-256: {result.get('sha256', '')[:12]}...")
                else:
                    print(f"[ACID Armor] ⚠️ Snapshot warning: {result.get('error')}")
        except Exception as e:
            print(f"[ACID Armor] Snapshot daemon exception: {e}")

        # Sleep for interval (default: 1 hour)
        time.sleep(interval_seconds)

def start_backup_daemon(interval_seconds: int = 3600):
    """Start the background snapshot daemon if not already running."""
    global _daemon_started
    with _lock:
        if _daemon_started:
            return
        _daemon_started = True

        t = threading.Thread(
            target=_backup_worker,
            args=(interval_seconds,),
            name="MatabDbSnapshotDaemon",
            daemon=True
        )
        t.start()
        print(f"[ACID Armor] Automated hot database backup daemon started (Every {interval_seconds // 60} minutes).")

def trigger_manual_snapshot() -> dict:
    """Trigger an immediate manual snapshot (e.g. before major batch updates)."""
    if not perform_backup:
        return {"ok": False, "error": "Backup module unavailable"}
    return perform_backup(retention_days=30)
