# EPCC User Role Migration Scripts

This folder contains SQL migration scripts for database modifications that cannot be handled purely via ORM autogeneration, or for one-time bootstrapping operations.

## To promote user id=2 to admin:

1. **Ensure backend and database are stopped or in single-user mode (to avoid race conditions).**
2. Run the migration SQL on your SQLite3 database:
   
   ```bash
   cd e-policecert-suite-118001-118010/epcc_backend
   sqlite3 epcc.sqlite3 < src/api/migrations/20240701_set_user2_admin.sql
   ```

   - If your database file is elsewhere or using a different database, adapt the connection and SQL as appropriate.
   - For production (PostgreSQL/MySQL), run the SQL directly using their respective clients.

3. **Verify:** Check with a SELECT:

   ```bash
   sqlite3 epcc.sqlite3 "SELECT id, email, role FROM users WHERE id=2;"
   # Should show 'admin' in the 'role' column.
   ```

**This script should be run once, immediately after initial user creation (id=2), to bootstrap the first admin account.**

## Notes

- Future migrations should be tracked/sequenced for evolving schema changes.
- For automated migrations, integrate with Alembic or your migration tool.
