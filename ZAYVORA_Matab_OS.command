#!/bin/bash
# ==============================================================================
# ZAYVORA MATAB OS — 1-Click Desktop Launcher
# Double-click this file to launch Matab OS with automatic browser opening.
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "========================================================================"
echo "          🌿 LAUNCHING ZAYVORA MATAB CLINICAL OS...                     "
echo "========================================================================"

# Check if port 8080 is occupied, if so kill stale process gracefully
STALE_PID=$(lsof -ti:8080 2>/dev/null)
if [ -n "$STALE_PID" ]; then
  echo "[*] Cleaning up prior instance on port 8080 (PID: $STALE_PID)..."
  kill -9 $STALE_PID 2>/dev/null
  sleep 1
fi

./start_matab.sh
