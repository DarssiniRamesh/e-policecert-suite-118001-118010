#!/bin/bash
cd /home/kavia/workspace/code-generation/e-policecert-suite-118001-118010/epcc_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

