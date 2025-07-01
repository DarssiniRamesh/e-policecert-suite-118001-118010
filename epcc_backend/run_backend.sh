#!/bin/bash
# Run the FastAPI backend server with auto-reload, on port 3001
cd "$(dirname "$0")"

# If .env exists, load it; otherwise, continue (do not fail)
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Ensure that uploads directory exists to avoid startup or runtime errors
mkdir -p uploads

# Check if SQLite database path is writeable (if using SQLite)
EPCC_DB_FILE="./epcc.sqlite3"
if [[ "${EPCC_DATABASE_URL:-}" =~ sqlite://.*epcc.sqlite3 ]] && [ ! -f "$EPCC_DB_FILE" ]; then
  # Attempt to create an empty SQLite file (FastAPI will also do this, but this gives earlier error visibility)
  touch "$EPCC_DB_FILE"
fi

uvicorn src.api.main:app --reload --port 3001 --host 0.0.0.0
