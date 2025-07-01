# Backend Log/Startup Diagnostic Summary (epcc_backend)

## Scope
Post /register and /health/db failures – log and config error inspection  
(epcc_backend/backend_startup.log, diagnose_logs.sh, environment/config)

---

## Summary of Findings

### 1. **backend_startup.log Presence**
- The file `backend_startup.log` is not listed in the provided directory structure.
- The startup script (`start.sh`) is designed to redirect all FastAPI and uvicorn output (stdout and stderr) to `backend_startup.log`.
- If this log file remains missing after backend launch + API hits, possible explanations:
    - The backend never successfully started (fatal error).
    - File/directory permissions prevent creation.
    - The backend crashed before logging could occur.
    - Logging misdirection (UVicorn/OS misconfig).

### 2. **Error Tracebacks and Exception Analysis**
- No actionable Python tracebacks from `/register` or `/health/db` appear in the available logs.
- Based on backend code:
    - Failed `/register` always logs full exception and traceback to both stdout and `backend_startup.log`.
    - If nothing is written, backend execution likely never reached these routines (fatal startup/DB error).

### 3. **Database and Configuration Checks**
- Default DB is `sqlite:///./epcc.sqlite3` (should exist or auto-create in epcc_backend directory).
- Common startup/DB failure signatures (not shown in current logs but probable causes):
    - `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: users`
    - `sqlite3.OperationalError: unable to open database file`
    - **Missing SQLite file**, read-only directory, or uninitialized DB schema ("no such table" error).

### 4. **Permissions and Containerization**
- If running as non-root or in Docker, environment may lack write permission for the backend directory (prevents DB/log creation).
- If `backend_startup.log` is not created even after API hits, this is highly likely a permissions or path issue.

### 5. **Scripts and Diagnostic Tools**
- `diagnose_logs.sh`, `diagnose_ps.sh`, and the startup script all attempt to log errors, recent process states, and dependencies.
- README and deployment docs confirm backend will fail gracefully and **record a traceback in `backend_startup.log`** for most common code errors.

---

## Conclusion

- **If `backend_startup.log` is absent or empty after repeated /register or /health/db calls, the backend cannot write to this location, or it never reached code execution for these endpoints.**
- **No SQLAlchemy/ProgrammingError traces were present because the log file isn't present or endpoint logic is not invoked.**

## Clear Actionable Explanations

- **Database likely inaccessible, not created, or not writable due to missing file, directory, or permission issues.**
- If the backend cannot even create `backend_startup.log`, permission problems or a critical crash (before app init) are the main causes.
- All FastAPI errors on these endpoints should have been logged—silence from logs confirms a system-level or directory-level problem, not just a coding bug.

## Recommendations

1. **Ensure backend user has write permission to the epcc_backend directory.**
2. **Re-run `start.sh`, watch for creation of `backend_startup.log`.**
3. **If using Docker, check volume/mount for correct file system mapping and permissions.**
4. **Ensure SQLite file (`epcc.sqlite3`) exists or can be auto-created.**
5. **After hitting /register or /health/db, immediately check/tail `backend_startup.log` for errors or tracebacks.**
6. **If still blank, try launching FastAPI manually (not using redirect) to catch console errors.**

---

## Confirmation: Is DB Reachable?

**No definitive confirmation can be made due to missing logs.**  
**DB is most likely NOT reachable or is fundamentally misconfigured (file/permissions/ownership), OR server mis-start.**

---

*Next step: Fix directory permissions and/or DB file presence; observe backend_startup.log after a fresh backend start and endpoint invocation.*
