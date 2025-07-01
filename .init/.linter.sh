#!/bin/bash
cd /home/kavia/workspace/code-generation/e-policecert-suite-118001-118010/epcc_backend

# Attempt to source correct venv location (one level up from epcc_backend)
if [ -f ../venv/bin/activate ]; then
  source ../venv/bin/activate
  echo "Activated venv from ../venv/bin/activate"
else
  echo "WARNING: ../venv/bin/activate not found, trying system python..."
fi

# Run flake8 on the backend API codebase
if command -v flake8 > /dev/null 2>&1; then
  flake8 src/api
else
  echo "flake8 not found"
  exit 1
fi
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

