Backend diagnostics:
- diagnose_ps.sh: Shows running processes and listening ports inside the container.
- diagnose_logs.sh: Attempts to print FastAPI/uvicorn error logs, latest startup outputs, and installed dependencies.
Run with:
    bash diagnose_ps.sh
    bash diagnose_logs.sh
Useful for capturing container logs and process state after failure to start or persistent 502 Bad Gateway errors.
