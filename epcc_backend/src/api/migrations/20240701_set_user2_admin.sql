-- Migration: Set user with id=2 to admin role for EPCC bootstrap.

UPDATE users
SET role = 'admin'
WHERE id = 2;
