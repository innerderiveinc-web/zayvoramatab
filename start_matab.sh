# ==============================================================================
# ZAYVORA MATAB OS — Standalone Launch Script
# Starts the Unani Clinical Operating System on http://localhost:8080
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

PYTHON_BIN="python3"
if [ -f "$DIR/.venv/bin/python3" ]; then
  PYTHON_BIN="$DIR/.venv/bin/python3"
fi

if [ -f "$DIR/.env" ]; then
  set -a
  source "$DIR/.env"
  set +a
fi

export PYTHONPATH="$DIR:$PYTHONPATH"
export MATAB_ENV="development"
export MATAB_PROFILE="SOLO_MATAB"
export MATAB_HOST="${MATAB_HOST:-0.0.0.0}"
export MATAB_PORT="${MATAB_PORT:-8080}"

echo "========================================================================"
echo "           🌿 STARTING ZAYVORA MATAB OS (Version 2.0)                   "
echo "========================================================================"
echo " - Mode: Solo Clinic / Local Matab (Zero Cloud Dependency)"
echo " - Local URL: http://127.0.0.1:${MATAB_PORT} or http://localhost:${MATAB_PORT}"
echo " - Database: Local SQLite with WAL Multi-Room Concurrency"

if [ -n "$GEMINI_API_KEY" ] || [ -n "$GOOGLE_API_KEY" ]; then
  echo " - Clinical Advisor: 🟢 Live Medical Knowledge Base (Online Reference Active)"
else
  echo " - Clinical Advisor: 🟡 Classical Unani Compendia (Offline Reference Active)"
fi

echo " - Prescriptions: 80mm Thermal Receipt + A4 Letterhead + WhatsApp Rx"
echo " - Hot Backup: 🛡️ Automatic Daily Snapshot with SHA-256 Merkle Checksum"
echo "========================================================================"

# Auto-backup database on launch in background
"$PYTHON_BIN" scripts/backup_db.py > /dev/null 2>&1 &

# Free port if already in use by a stale process
EXISTING_PID=$(lsof -ti :${MATAB_PORT} 2>/dev/null)
if [ -n "$EXISTING_PID" ]; then
  echo "Reclaiming port ${MATAB_PORT} from stale process (PID: $EXISTING_PID)..."
  kill -9 $EXISTING_PID 2>/dev/null || true
  sleep 0.5
fi

# Auto-open browser on macOS
if command -v open >/dev/null 2>&1; then
  (sleep 1.2 && open "http://127.0.0.1:${MATAB_PORT}") &
fi

"$PYTHON_BIN" "$DIR/apps/api/main.py"

