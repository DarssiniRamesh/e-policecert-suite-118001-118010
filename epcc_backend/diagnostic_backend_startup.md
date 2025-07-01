# Backend Startup & Registration Error Diagnostic

## Issue:
No actionable Python traceback could be found in `backend_startup.log` because the file was not present; likely causes (startup never completed, permissions, or logging misdirection) remain unaddressed.

## Registration-Related 500 Error – Next Steps

- **There is no backend_startup.log or recent error stack from diagnose_logs.sh.**
- Most probable scenarios for FastAPI+SQLAlchemy registration 500 status:
  - IntegrityError at user creation (possibly duplicate email, table constraint)
  - ValidationError in the UserRegister schema
  - AttributeError or database connection error during ORM commit/refresh
- Since registration calls both "db.add(user)" and "db.add(AuditLog...)" before a double commit, the failure could be within these operations.

## What To Check Next

1. **FORCE* backend to (re-)generate logs:**
   - From the backend directory, run:
     ```bash
     bash start.sh
     cat backend_startup.log
     ```
   - *Confirm that backend_startup.log populates with any traceback or error—most important for POST /register!*

2. **Review DB File Existence & Permissions:**
   - Does `epcc.sqlite3` (or your DB) exist?
   - Is it writable by the backend service/container user?

3. **Check for Table Schema Mismatches:**
   - Run schema inspection on the DB (CLI or DB browser) to verify tables match SQLAlchemy models (esp. "users" and "audit_logs").

4. **If using SQLite WAL mode or external DB, check that the connection string is correct and DB dependencies are installed.**

5. **POST /register with unique (new) email:**
   - If you previously tried duplicate emails, clear DB or use a new test email.

6. **Look for any import/database-related errors in alternate logs, e.g.**
   - uvicorn.log
   - Docker `stdout` logs or journalctl
   - `diagnose_logs.sh` output appended below

## Additional Recommendation

- If backend_startup.log remains missing, log directory/ownership is likely the issue—check the `start.sh` execution environment and directory structure.
- If the log appears, inspect for the last Python traceback. Common error categories are:
  - sqlalchemy.exc.IntegrityError (email constraint)
  - sqlalchemy.exc.OperationalError (table or DB file)
  - pydantic.error_wrappers.ValidationError
  - AttributeError in custom register logic

---

*Next steps:* Ensure backend_startup.log is created, then POST /register again, and immediately review its tail for the traceback. Attach that log output for more precise diagnosis.
