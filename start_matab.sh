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

# Auto-generate or load persistent secure MATAB_SECRET_KEY if not supplied
if [ -z "$MATAB_SECRET_KEY" ]; then
  if [ -f "$DIR/.matab_secret" ]; then
    export MATAB_SECRET_KEY="$(cat "$DIR/.matab_secret")"
  else
    NEW_KEY="$("$PYTHON_BIN" -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32 2>/dev/null || echo "matab_prod_key_$(date +%s)_autosecure_64char_token_value_randomized")"
    echo "$NEW_KEY" > "$DIR/.matab_secret"
    chmod 600 "$DIR/.matab_secret" 2>/dev/null || true
    export MATAB_SECRET_KEY="$NEW_KEY"
  fi
fi

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

# ==============================================================================
# Layer 2: Self-Healing Process Supervisor Watchdog
# Automatically recovers the server if it terminates unexpectedly,
# logs crash diagnostics, and enforces rate-limited restart backoff.
# ==============================================================================
CRASH_LOG="$DIR/logs/crash_supervisor.log"
mkdir -p "$DIR/logs"

MAX_RETRIES=5
RETRY_COUNT=0
LAST_CRASH_TIME=0

cleanup() {
  echo ""
  echo "[*] Graceful shutdown signal received. Stopping ZAYVORA MATAB OS..."
  if [ -n "$SERVER_PID" ]; then
    kill -15 "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup SIGINT SIGTERM SIGHUP

echo "🛡️ Supervisor Watchdog: Self-healing process recovery active."

while true; do
  "$PYTHON_BIN" "$DIR/apps/api/main.py" &
  SERVER_PID=$!
  wait "$SERVER_PID"
  EXIT_CODE=$?

  # Exit code 0 or 130 (SIGINT Ctrl+C) means clean intentional shutdown
  if [ "$EXIT_CODE" -eq 0 ] || [ "$EXIT_CODE" -eq 130 ]; then
    echo "[*] Server stopped cleanly (Exit code: $EXIT_CODE)."
    break
  fi

  CURRENT_TIME=$(date +%s)
  echo "[!] [CRASH DETECTED] Server process terminated abnormally with exit code $EXIT_CODE at $(date)." | tee -a "$CRASH_LOG"

  # Reset retry counter if last crash was > 60 seconds ago
  TIME_DIFF=$((CURRENT_TIME - LAST_CRASH_TIME))
  if [ "$TIME_DIFF" -gt 60 ]; then
    RETRY_COUNT=0
  fi
  LAST_CRASH_TIME=$CURRENT_TIME
  RETRY_COUNT=$((RETRY_COUNT + 1))

  if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
    echo "❌ FATAL: Server crashed $MAX_RETRIES times in short succession. Halting auto-restart to protect system." | tee -a "$CRASH_LOG"
    echo "Inspect $CRASH_LOG for detailed diagnostics."
    exit 1
  fi

  echo "🔄 [SELF-HEALING] Auto-recovering server in 2 seconds (Attempt $RETRY_COUNT of $MAX_RETRIES)..."
  sleep 2
done

