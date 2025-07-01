#!/bin/bash
# Diagnostic: List all processes relevant to the FastAPI/Uvicorn backend and system.
echo "======= Process list (ps aux) ======="
ps aux
echo ""
echo "======= Listening Ports (netstat -plnt or ss) ======="
if command -v netstat >/dev/null; then
    netstat -plnt
else
    ss -plnt
fi
