#!/bin/bash
# Entrypoint script for epcc_backend FastAPI application

set -e

# Activate virtualenv if present (optional; non-fatal if missing)
if [ -d "venv" ]; then
    # shellcheck disable=SC1091
    . venv/bin/activate || echo "venv exists but failed to activate; using system Python."
fi

# Install Python dependencies (optional: comment if container builds handle this)
if [ -f "requirements.txt" ]; then
    pip install --no-cache-dir -r requirements.txt >> backend_startup.log 2>&1 || { echo "[pip failed]" >> backend_startup.log ; exit 1; }
fi

# Ensure uploads dir exists
mkdir -p uploads

# Kill any process occupying port 3001 before starting (avoid conflicts)
PID_ON_3001=$(lsof -ti tcp:3001 || echo "")
if [ ! -z "$PID_ON_3001" ]; then
    echo "Killing process(es) on port 3001: $PID_ON_3001" >> backend_startup.log
    kill -9 $PID_ON_3001 || true
    sleep 1
fi

# Start FastAPI app using uvicorn
echo "========== Backend manual startup at $(date) ==========" >> backend_startup.log

# Redirect ALL output of uvicorn (including stdout and stderr) to backend_startup.log for persistent debugging
# This allows both manual print() output and Python tracebacks to be captured
uvicorn src.api.main:app --host 0.0.0.0 --port 3001 >> backend_startup.log 2>&1 || { echo "[uvicorn failed to start]" >> backend_startup.log ; exit 2; }
