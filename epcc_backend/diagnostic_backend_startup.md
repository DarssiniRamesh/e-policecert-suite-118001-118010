# Backend Startup & Registration Error Diagnostic

## Issue:
No actionable Python traceback could be found in `backend_startup.log` because the file was not present; likely causes (startup never completed, permissions, or logging misdirection) remain unaddressed.

## ERROR SUMMARY (from backend diagnostics)

- backend_startup.log is missing or empty, so Python tracebacks for `/register` and `/health/db` failures cannot be found there.
- This suggests one (or more) of the following:
    1. The backend crashed on startup and logging output was not written, OR
    2. The FastAPI/Uvicorn server output is not routed to backend_startup.log (logging misdirection), OR
    3. File/directory permissions prevent log file creation (particularly if running in non-root or Docker context).
    4. The backend never started at all due to a fatal error.

## Symptom: `/register` returns 500, `/health/db` fails ("Failed to fetch")

- The registration endpoint is coded to log **all** exceptions to both stdout/stderr and backend_startup.log.
- If backend_startup.log and diagnose_logs.sh remain empty, this suggests the registration function or even the entire backend never got to run: a severe startup or DB issue.

## Top Probable Causes Based on Current Evidence

- **Database Not Accessible or Missing:**
  - The default DB is `epcc.sqlite3` in the backend directory.
  - If this file does NOT exist, or is not writable by the backend, all DB-dependent endpoints will fail.
  - If the DB schema did not initialize (e.g., missing tables, migration not run), then registration and health check will raise OperationalError (`no such table: users`, etc).

- **Network/Container Misconfiguration:**
  - If running under Docker (not shown here), the volume or directory with the SQLite file could be missing or read-only.
  - If a custom `EPCC_DATABASE_URL` is set to a non-existent resource, OperationalError is expected.

## Diagnosing Next Steps (Required for Further Progress)

1. **Run `start.sh` and observe whether backend_startup.log is created and populated.**
   - If it is not, there is a fatal environment, directory, or Python error.
2. **Inspect (or create) the SQLite DB file:** Does ./epcc.sqlite3 exist, and is it accessible with read/write permissions?
3. **Check that the models are being initialized:** According to DB logic, all tables should auto-create on startup via `init_db()` in FastAPI `@app.on_event('startup')`. If this fails, check logs or rerun startup script in debug mode.
4. **If possible, invoke registration with a clean (never-used) email, and after, check for new error output in backend_startup.log.**

---

#### Actionable Advice

- If the backend_startup.log remains absent after hitting /register, log creation or directory permissions are 99% likely to be at fault. Fix permissions.
- If it appears, tail the last lines—look for errors like:
  - `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: users`
  - `sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed`
  - `sqlite3.ProgrammingError`
  - Python exceptions for missing imports or DB engine setup failures

If you see `'no such table'` or `'unable to open database file'` in logs, the DB setup/init sequence is broken. If nothing logs at all, check file paths and start.sh/uvicorn invocation logic.

---

*Next steps:* Ensure backend_startup.log is created and writable on backend startup. Hit /register or /health/db, then review the tail of that log for a Python traceback and error summary. Attach that log or error for next round diagnostics.
