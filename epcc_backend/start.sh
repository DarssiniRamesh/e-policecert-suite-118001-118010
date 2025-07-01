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
    pip install --no-cache-dir -r requirements.txt
fi

# Ensure uploads dir exists
mkdir -p uploads

# Start FastAPI app using uvicorn
exec uvicorn src.api.main:app --host 0.0.0.0 --port 3001
