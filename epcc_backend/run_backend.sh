#!/bin/bash
# Run the FastAPI backend server with auto-reload, on port 3001
cd "$(dirname "$0")"
export $(grep -v '^#' .env | xargs)
uvicorn src.api.main:app --reload --port 3001
