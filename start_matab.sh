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
export MATAB_ENV="${MATAB_ENV:-production}"
export MATAB_PROFILE="${MATAB_PROFILE:-SOLO_MATAB}"
export MATAB_HOST="${MATAB_HOST:-127.0.0.1}"
export MATAB_PORT="${MATAB_PORT:-8080}"

echo "========================================================================"
echo "           🌿 STARTING ZAYVORA MATAB OS (Version 2.0)                   "
echo "========================================================================"
echo " - Environment: ${MATAB_ENV}"
echo " - Local URL: http://${MATAB_HOST}:${MATAB_PORT}"
echo " - Database: Local SQLite with WAL Multi-Room Concurrency"

if [ -n "$GEMINI_API_KEY" ] || [ -n "$GOOGLE_API_KEY" ]; then
  echo " - Clinical Advisor: 🟢 Configured (Requires Clinical Review)"
else
  echo " - Clinical Advisor: 🟡 Governed Offline Clinical RAG Mode"
fi

echo " - Prescriptions: 80mm Thermal Receipt + A4 Letterhead + WhatsApp Rx"
echo " - Hot Backup: 🛡️ Automatic Daily Snapshot with SHA-256 Merkle Checksum"
echo "========================================================================"

# Auto-initialize database on first run if not present
if [ ! -f "$DIR/matab.db" ]; then
  echo "Initializing clean clinical database with schema migrations..."
  "$PYTHON_BIN" -m apps.api.database.migrator
  if [ "$MATAB_ENV" != "production" ]; then
    echo "Seeding synthetic development dataset..."
    "$PYTHON_BIN" -m apps.api.database.seed
  fi
fi

# Auto-backup database on launch in background if db exists
if [ -f "$DIR/matab.db" ]; then
  "$PYTHON_BIN" scripts/backup_db.py > /dev/null 2>&1 &
fi

# Check if port is already in use by a process
EXISTING_PID=$(lsof -ti :${MATAB_PORT} 2>/dev/null)
if [ -n "$EXISTING_PID" ]; then
  echo "Port ${MATAB_PORT} is in use by PID $EXISTING_PID. Sending graceful termination (SIGTERM)..."
  kill -15 $EXISTING_PID 2>/dev/null || true
  sleep 1
fi

# Auto-open browser on macOS
if command -v open >/dev/null 2>&1; then
  (sleep 1.2 && open "http://127.0.0.1:${MATAB_PORT}") &
fi

"$PYTHON_BIN" "$DIR/apps/api/main.py"

