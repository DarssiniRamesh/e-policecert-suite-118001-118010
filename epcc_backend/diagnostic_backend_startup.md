# Backend Startup Log Missing – Diagnostic Summary

**Issue:**  
No `backend_startup.log` file was found in the backend container at startup, so no logs could be analyzed for FastAPI/Uvicorn errors, import problems, or Python tracebacks.

## Root Causes & What to Check Next

1. **Backend Never Started or Failed Before Logging:**
   - The backend process may have failed before producing any log output.
   - Check if the `start.sh` script is being invoked at container or service startup.

2. **Log Path or Permissions Issue:**
   - The backend's start command (see `start.sh`) appends output/errors to `backend_startup.log`.
   - Ensure the service has write permission in `epcc_backend/`.

3. **Misconfiguration in Entrypoint:**
   - Verify the container/service entrypoint matches the provided `start.sh` script.
   - Confirm `uvicorn ... >> backend_startup.log 2>&1` really points here and isn't redirected elsewhere.

4. **Immediate Crash (e.g. Missing Interpreter/Dependency):**
   - If Python itself or `pip` is missing, the script might fail before logs are written.

## Next Recommended Steps

- **Manual log generation:**  
  Run this from the backend directory to attempt fresh log output:
  ```bash
  bash start.sh
  cat backend_startup.log
  ```
  Or check for Docker/container error logs if running in a managed environment.

- **Check for STDOUT logs or alternate log files:**  
  Look for `uvicorn.log` or system/service logs via `journalctl` or `docker logs`.

- **Verify requirements installation:**  
  Ensure `requirements.txt` dependencies are installed as expected. See the deployment documentation for steps.

- **Permissions:**  
  Ensure the executing user in the container can write to the backend directory.

- **Process Status:**  
  Run the following to confirm if FastAPI/Uvicorn is running or was killed:
  ```bash
  bash diagnose_ps.sh
  ```

## Reference

See also:  
- `diagnose_logs.sh` and `diagnose_ps.sh` for additional diagnostic commands.
- `start.sh` for backend startup process and log output location.

---

**Summary:**  
No actionable tracebacks or errors could be found because the log was not present. The startup process should be reviewed and rerun to produce logs for further analysis.
