#!/bin/bash
# Entrypoint script for epcc_backend FastAPI application with improved diagnostics and reliability

set -e

echo "=== [start.sh] Invoked at $(date) ===" | tee -a backend_startup.log

# Activate virtualenv if present (optional; non-fatal if missing)
if [ -d "venv" ]; then
    . venv/bin/activate || echo "[WARNING] venv exists but failed to activate; using system Python." | tee -a backend_startup.log
else
    echo "[INFO] venv not present, will use system Python." | tee -a backend_startup.log
fi

# Install Python dependencies (optional: comment if container builds handle this)
if [ -f "requirements.txt" ]; then
    echo "[INFO] Installing dependencies from requirements.txt." | tee -a backend_startup.log
    pip install --no-cache-dir -r requirements.txt >> backend_startup.log 2>&1 || { echo "[FATAL] pip install failed." | tee -a backend_startup.log ; exit 1; }
else
    echo "[WARN] requirements.txt not found, skipping pip install!" | tee -a backend_startup.log
fi

# Ensure uploads dir exists
mkdir -p uploads
echo "[INFO] uploads/ directory ensured." | tee -a backend_startup.log

# Kill any process occupying port 3001 before starting (avoid conflicts)
PID_ON_3001=$(lsof -ti tcp:3001 || echo "")
if [ ! -z "$PID_ON_3001" ]; then
    echo "[WARN] Killing process(es) on port 3001: $PID_ON_3001" | tee -a backend_startup.log
    kill -9 $PID_ON_3001 || true
    sleep 1
fi

# Print diagnostic info
echo "--- Process/user: $(whoami), PWD: $(pwd)" | tee -a backend_startup.log
echo "--- Python: $(which python3) / $(python3 --version)" | tee -a backend_startup.log
echo "--- Permissions for backend dir:" | tee -a backend_startup.log
ls -lah . | tee -a backend_startup.log
echo "--- Permissions for uploads/:" | tee -a backend_startup.log
ls -lah uploads | tee -a backend_startup.log

# Confirm expected files exist
for f in backend_startup.log requirements.txt start.sh src/api/main.py src/api/db.py ; do
    if [ -f "$f" ]; then
        echo "[INFO] Found file: $f" | tee -a backend_startup.log
    else
        echo "[ERROR] Missing file: $f" | tee -a backend_startup.log
    fi
done

echo "========== Backend manual startup at $(date) ==========" | tee -a backend_startup.log

# Defensive: run uvicorn, if crash, log and run in foreground to catch error output
echo "[INFO] Attempting to start Uvicorn on port 3001 (FastAPI backend)..." | tee -a backend_startup.log
if ! uvicorn src.api.main:app --host 0.0.0.0 --port 3001 >> backend_startup.log 2>&1 ; then
    echo "[ERROR] uvicorn failed, launching again in foreground for error display." | tee -a backend_startup.log
    uvicorn src.api.main:app --host 0.0.0.0 --port 3001
fi

echo "[BOOT_COMPLETE] FastAPI backend brought up (exited script at $(date))" | tee -a backend_startup.log
