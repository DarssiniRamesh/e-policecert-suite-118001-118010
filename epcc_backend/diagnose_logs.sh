#!/bin/bash
# Diagnostic: Try to gather recent logs and installed package state.
echo "======= Uvicorn/FastAPI (if running in foreground) ======="
# Try to find uvicorn logs (stdout fallback, docker logs, journalctl); if not found just echo lines as best effort.
logfile="uvicorn.log"
if [ -f "$logfile" ]; then
  tail -n 50 "$logfile"
else
  echo "No uvicorn.log present, checking dmesg & journalctl fallback..."
  dmesg | tail -n 30
  journalctl -u uvicorn.service 2>/dev/null | tail -n 30
fi

echo ""
echo "======= Recent Startup Script Output (start.sh) ======="
if [ -f "start.sh" ]; then
    tail -n 50 start.sh
else
    echo "start.sh not found"
fi

echo ""
echo "======= Python Dependencies (pip freeze) ======="
pip freeze
