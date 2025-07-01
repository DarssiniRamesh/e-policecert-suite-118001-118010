# E-Police Certificate Backend API – Route Documentation

This document lists all implemented API routes in the `epcc_backend` (FastAPI) backend, with details on HTTP method, path, expected parameters (query, path, body), authentication/roles, and a summary of each route's purpose.

_Last generated directly from backend code. For precise payloads and schemas, refer to code and OpenAPI docs._

---

## Index

- [General/Health Endpoints](#generalhealth-endpoints)
- [Authentication & Registration](#authentication--registration)
- [User Endpoints](#user-endpoints)
- [Certificate Applications](#certificate-applications)
- [Certificates](#certificates)
- [Documents (Uploads/Downloads)](#documents-upload-download)
- [Notifications](#notifications)
- [Admin/Officer Endpoints](#adminofficer-endpoints)
- [Audit Logs](#audit-logs)
- [Error Handling](#error-handling)

---

## General/Health Endpoints

### `GET /`
- **Summary**: Healthcheck endpoint. Backend is running.
- **Auth**: None
- **Response**: `{ "message": "Healthy" }`

### `GET /health/db`
- **Summary**: Check DB connectivity.
- **Auth**: None (admin tag)
- **Response**: `{ "ok": true/false, "error": str | null }`


### `GET /docs/lang`
- **Summary**: Get supported languages.
- **Auth**: None
- **Response**: `{ "languages": ["en", "fr", "ar"] }`

---

## Authentication & Registration

### `POST /register`
- **Summary**: Register new user.
- **Body**: JSON `{ email: string, full_name?: string, password: string }`
- **Returns**: User object
- **Notes**: Fails if user/email exists.

### `POST /token`
- **Summary**: Login and get JWT token (OAuth2 password flow).
- **Body**: Form `{ username: str, password: str }` (_not_ JSON!)  
- **Returns**: `{ access_token: string, token_type: "bearer" }`
- **Notes**: Attach JWT as `Authorization: Bearer <token>` to protected endpoints.

---

## User Endpoints

### `GET /me`
- **Summary**: Get my profile (user from JWT).
- **Auth**: Bearer JWT required.
- **Returns**: Full user object: `{ id, email, full_name, role, is_active, created_at }`

---

## Certificate Applications

### `GET /applications`
- **Summary**: List current user's certificate applications.
- **Auth**: Bearer JWT required.
- **Returns**: Array of applications for logged-in user.

### `POST /applications`
- **Summary**: Submit a new certificate application.
- **Auth**: Bearer JWT required.
- **Body**: JSON `{ details: string }`
- **Returns**: Application object (pending status).

### `GET /applications/{application_id}`
- **Summary**: Retrieve single application by ID.
- **Auth**: Bearer JWT. Only applicant, officers, or admin allowed.
- **Response**: Application object.

---

## Certificates

### `GET /certificates`
- **Summary**: List all certificates owned by current user.
- **Auth**: Bearer JWT required.
- **Response**: Array of certificates.

### `GET /certificates/{certificate_id}`
- **Summary**: Get certificate info by ID (if owned OR officer/admin).
- **Auth**: Bearer JWT required.
- **Response**: Certificate object.

---

## Documents (Upload/Download)

### `POST /documents/upload`
- **Summary**: Upload document to a specific application.
- **Auth**: Bearer JWT, owner of application.
- **Body**: Multi-part form:
    - `application_id` (int, required)
    - `file` (file, required)
- **Response**: Document object

### `GET /documents/download/{filename}`
- **Summary**: Download a document by server-stored filename.
- **Auth**: Bearer JWT. Only allowed if file owned/officer/admin (owner check, to be expanded for further auditing).
- **Returns**: File (octet-stream/binary data).

### `GET /applications/{application_id}/documents`
- **Summary**: List all documents for a certificate application.
- **Auth**: Bearer JWT. Owner, admin, or officer required.
- **Response**: List of document objects.

---

## Notifications

### `GET /notifications`
- **Summary**: List all notifications for current user.
- **Auth**: Bearer JWT required.
- **Response**: Array of notifications.

### `PATCH /notifications/{notification_id}/markread`
- **Summary**: Mark notification as read for this user.
- **Auth**: Bearer JWT required.
- **Returns**: The updated notification object.

---

## Admin/Officer Endpoints

(All require JWT and user role to be admin or officer.)

### `GET /admin/applications`
- **Summary**: List all certificate applications (all users).
- **Auth**: Bearer JWT, admin or officer only.
- **Returns**: Array of all applications.

### `PATCH /admin/applications/{application_id}`
- **Summary**: Officer/admin updates application status (approve, reject, etc).
- **Auth**: Bearer JWT, admin/officer only.
- **Body**: `{ status: string }` (certificate status)
- **Returns**: Updated application object.

### `POST /admin/applications/{application_id}/certificates`
- **Summary**: Issue certificate for application (must be approved).
- **Auth**: Bearer JWT, admin/officer only.
- **Body**: `{ expiry_date?: ISODate string }` (optional)
- **Returns**: New certificate object.

### `PATCH /admin/certificates/{certificate_id}/revoke`
- **Summary**: Revoke a certificate and give a reason.
- **Auth**: Bearer JWT, admin/officer only.
- **Body**: `{ reason: string }`
- **Returns**: Revoked certificate object.

---

## Audit Logs

### `GET /admin/auditlogs`
- **Summary**: Return latest audit log entries (defaults: latest 100).
- **Auth**: Bearer JWT, admin/officer only.
- **Query**: limit (default/optional)
- **Returns**: Array of audit log records.

---

## Error Handling

- All endpoints use FastAPI exception handling. Error responses:
    - `401`: Not authenticated (missing/expired/wrong JWT)
    - `403`: Permission denied (wrong role)
    - `422`: Invalid request schema/body
    - `404`: Not found or access denied for resource

- Most errors return JSON: `{ detail: string }` or `{ error: string, reason: string, traceback?: string }` on critical internal errors (e.g., registration).

---

## Notes

- All protected endpoints require passing a valid JWT token as `Authorization: Bearer <token>`.
- Admin/officer endpoints strictly require proper roles (access will be denied otherwise).
- All user/profile/app/cert status changes are recorded in the audit log implicitly (backend).
- For schemas of objects (User, Application, Certificate, etc.) refer to backend `/docs` path.
- Document endpoints save files under local server `uploads/` directory.

---

_Last updated: [Automated extraction from backend codebase (src/api/main.py)]_
