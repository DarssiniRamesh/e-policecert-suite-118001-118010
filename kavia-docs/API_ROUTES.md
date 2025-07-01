# E-Police Certificate Backend API Documentation

This document provides a detailed reference for all REST API endpoints implemented in the FastAPI-based backend (`epcc_backend`). Each route is described by path, HTTP method, parameters, authentication/role requirements, request/response schemas, and a summary of its purpose.

**Source:** `epcc_backend/src/api/main.py`  
_Last update: [automatically generated]_

---

## Table of Contents

- [Authentication & User Management](#authentication--user-management)
- [Certificate Applications](#certificate-applications)
- [Certificate Operations](#certificate-operations)
- [Admin/Officer Endpoints](#adminofficer-endpoints)
- [Document Upload/Download](#document-uploaddownload)
- [Notifications](#notifications)
- [Audit Logs](#audit-logs)
- [Health & Utility Endpoints](#health--utility-endpoints)

---

## Authentication & User Management

### POST `/register`
**Summary:** Register a new user (default role: `user`)
- **Body:** JSON (`UserRegister` schema: `{email, full_name, password (min 6 chars)}`)
- **Response:** `UserResponse` (user object: id, email, full_name, role, is_active, created_at)
- **Permissions:** None (open)
- **Errors:** 400 if user already exists, 500 on server error
- **Side Effects:** Logs registration in audit log, writes to `backend_startup.log` on error

---

### POST `/token`
**Summary:** User login; returns a JWT token
- **Body:** Form (`username` (email), `password`)
- **Response:** `{access_token: str, token_type: "bearer"}`
- **Permissions:** None
- **Errors:** 401 for invalid credentials, 403 for inactive accounts
- **Audit Log:** User login event

---

### GET `/me`
**Summary:** Get current user profile
- **Authentication:** Bearer JWT required
- **Response:** `UserResponse` (full user details)
- **Permissions:** Any authenticated user

---

### GET `/docs/lang`
**Summary:** List supported languages (for translation/localization)
- **Response:** `{languages: ["en", "fr", "ar"]}`
- **Permissions:** None

---

## Certificate Applications

### GET `/applications`
**Summary:** List certificate applications submitted by current user
- **Authentication:** Bearer JWT required
- **Response:** `List[CertificateApplicationResponse]`
- **Permissions:** Authenticated user

---

### POST `/applications`
**Summary:** Submit a new certificate application
- **Authentication:** Bearer JWT required
- **Body:** JSON, `{details: str (max 2048 chars)}`
- **Response:** `CertificateApplicationResponse`
- **Permissions:** Authenticated user
- **Side Effects:** Triggers notification, logs submission in audit logs

---

### GET `/applications/{application_id}`
**Summary:** Get application by ID, if owned or officer/admin
- **Authentication:** Bearer JWT required
- **Path Parameters:** `application_id: int`
- **Response:** `CertificateApplicationResponse`
- **Permissions:** Owner of the application, or officer/admin

---

### GET `/applications/{application_id}/documents`
**Summary:** List all documents for an application
- **Authentication:** Bearer JWT required
- **Path Parameters:** `application_id: int`
- **Response:** `List[DocumentResponse]`
- **Permissions:** Application owner, officer, or admin

---

## Certificate Operations

### GET `/certificates`
**Summary:** List certificates owned by current user
- **Authentication:** Bearer JWT required
- **Response:** `List[CertificateResponse]`
- **Permissions:** Authenticated user

---

### GET `/certificates/{certificate_id}`
**Summary:** View a certificate by ID (must be owner, officer, or admin)
- **Authentication:** Bearer JWT required
- **Path Parameters:** `certificate_id: int`
- **Response:** `CertificateResponse`
- **Permissions:** Owner, officer, or admin

---

## Document Upload/Download

### POST `/documents/upload`
**Summary:** Upload a document to a certificate application
- **Authentication:** Bearer JWT required
- **Form Data:** `application_id: int`, `file: UploadFile`
- **Response:** `DocumentResponse` (file metadata, download URL)
- **Permissions:** Must be the owner of the target application

---

### GET `/documents/download/{filename}`
**Summary:** Download previously uploaded document
- **Authentication:** Bearer JWT required
- **Path Parameters:** `filename: str`
- **Response:** File download (`application/octet-stream`)
- **Permissions:** Document owner, officer/admin (checks advised)

---

## Notifications

### GET `/notifications`
**Summary:** Get all notifications for current user (newest first)
- **Authentication:** Bearer JWT required
- **Response:** `List[NotificationResponse]`
- **Permissions:** Authenticated user

---

### PATCH `/notifications/{notification_id}/markread`
**Summary:** Mark a notification as read
- **Authentication:** Bearer JWT required
- **Path Parameters:** `notification_id: int`
- **Response:** `NotificationResponse`

---

## Admin/Officer Endpoints

> These endpoints **require** elevated roles (officer or admin).

### GET `/admin/applications`
**Summary:** List all certificate applications
- **Authentication:** Bearer JWT required
- **Permissions:** Officer, Admin
- **Response:** `List[CertificateApplicationResponse]`

---

### PATCH `/admin/applications/{application_id}`
**Summary:** Officer/Admin updates application status (approve/reject)
- **Authentication:** Bearer JWT required
- **Path Parameters:** `application_id: int`
- **Body:** `{status: "approved"|"rejected"|...}`
- **Permissions:** Officer, Admin
- **Response:** `CertificateApplicationResponse`
- **Side Effects:** Sends notification to applicant, logs audit

---

### POST `/admin/applications/{application_id}/certificates`
**Summary:** Issue a certificate for an application
- **Authentication:** Bearer JWT required
- **Path Parameters:** `application_id: int`
- **Body:** `expiry_date: Optional[datetime]` (optional)
- **Permissions:** Officer, Admin (application must be approved)
- **Response:** `CertificateResponse`

---

### PATCH `/admin/certificates/{certificate_id}/revoke`
**Summary:** Revoke a certificate (provide reason)
- **Authentication:** Bearer JWT required
- **Path Parameters:** `certificate_id: int`
- **Body:** `{reason: str}`
- **Permissions:** Officer, Admin
- **Response:** `CertificateResponse`

---

### GET `/admin/auditlogs`
**Summary:** View recent audit logs (default 100)
- **Authentication:** Bearer JWT required
- **Permissions:** Officer, Admin
- **Query Parameters:** `limit: int` (default: 100)
- **Response:** `List[AuditLogResponse]`

---

## Health & Utility Endpoints

### GET `/health/db`
**Summary:** DB health check (admin/ops, monitors basic DB connectivity)
- **Response:** `{ok: bool, error: Optional[str]}`
- **Permissions:** None

---

### GET `/`
**Summary:** Basic backend health (shows that the backend is running)
- **Response:** `{message: "Healthy"}`
- **Permissions:** None

---

## Models and Schemas (Summarized)

**UserRegister**  
- email: EmailStr  
- full_name: Optional[str]  
- password: str (min 6 chars)  

**UserResponse**  
- id: int  
- email: EmailStr  
- full_name: Optional[str]  
- role: str  
- is_active: bool  
- created_at: datetime  

**CertificateApplicationRequest**  
- details: str (max 2048 chars)  

**CertificateApplicationResponse**  
- id: int  
- status: str  
- details: Optional[str]  
- submission_time: datetime  
- reviewed_by_id: Optional[int]  

**CertificateResponse**  
- id: int  
- certificate_number: str  
- status: str  
- issue_date: datetime  
- expiry_date: Optional[datetime]  
- owner_id: int  

**NotificationResponse**  
- id: int  
- message: str  
- is_read: bool  
- created_at: datetime  

**DocumentResponse**  
- id: int  
- filename: str  
- url: str  
- uploaded_at: datetime  
- content_type: str  

**AuditLogResponse**  
- id: int  
- user_id: Optional[int]  
- application_id: Optional[int]  
- certificate_id: Optional[int]  
- action: str  
- timestamp: datetime  
- details: Optional[str]  

---

## Authentication & Role Requirements Quick Reference

- Endpoints without explicit authentication (`/`, `/health/db`, `/docs/lang`, `/register`, `/token`) are open or public.
- All other endpoints **require** a valid JWT token in the `Authorization: Bearer <token>` header.
- Admin/Officer endpoints require role-based permissions, enforced with dependency injections:
    - Officer or Admin: `/admin/*` endpoints
    - User endpoints: current user or resource owner

---

## Notes

- All API error responses are returned in consistent JSON format (some errors translated based on Accept-Language).
- State-changing endpoints are logged in the audit log.
- Uploaded files are stored in backend-local `uploads/` directory and require access control.
- The OpenAPI/Swagger UI (auto-generated) is available at `/docs` on the running backend.

---

_This file provides the canonical reference for backend/frontend integration. For further details on database models, see `src/api/db.py` or refer to the OpenAPI spec hosted at `/docs` when the backend is running._
