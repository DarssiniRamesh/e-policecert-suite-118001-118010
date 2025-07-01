#!/bin/bash
# Robust flake8 runner: uses venv if present, falls back to system if not.
set -e
cd "$(dirname "$0")"
if [ -d "venv" ]; then
    export PATH="$(pwd)/venv/bin:$PATH"
fi
# Try venv's flake8 or fallback to system flake8
if command -v flake8 > /dev/null 2>&1; then
    flake8 epcc_backend/src/api --count --select=E9,F63,F7,F82 --show-source --statistics
else
    echo "flake8 not found in venv or system PATH"
    exit 1
fi
