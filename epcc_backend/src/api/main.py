""" 
E-Police Certificate Backend API (epcc_backend/src/api/main.py)

Main FastAPI application entry point for the E-Police Certificate system.
Handles all service endpoints for user registration/authentication, certificate application submission, approval/issuance, document upload/download,
notifications, and audit logging.

App structure:
    - Loads environment variables and main settings
    - Defines all API Pydantic models (request/response)
    - Sets up JWT/OAuth2 authentication and password hashing
    - Registers FastAPI routes for:
        • Auth (register, login, JWT issue)
        • User management (profile, role-check, applications/certificates)
        • Certificate applications (submit, list, get by ID, officer/admin review)
        • Certificate issue/revoke (admin/officer only)
        • Notification viewing and marking as read
        • Document upload/download tied to applications
        • Audit log retrieval (admin/officer only)
    - Multilingual support: status/error messages and certain endpoints localize based on Accept-Language
    - Central exception handler translates error details for common authentication/authorization flows
App configuration:
    - Loads SECRET_KEY and DB URL via environment (with reasonable dev defaults)
    - Supports CORS for all origins during development (adjust for production)
    - Database initialized with SQLAlchemy ORM; SQLite used unless env override.
    - All uploads saved under uploads/ directory

For new collaborators:
    - Refer to endpoint docstrings and inline comments for route purposes & auth rules.
    - All API errors use FastAPI HTTPException for consistent error handling.
    - Data validation is performed with Pydantic models and class configs.
    - Startup event auto-generates DB schema and uploads dir — no manual migration needed.
    - See README, deployment and docs for endpoint usage and sample flows.

See also: src/api/db.py (ORM models and DB layer), requirements.txt, deployment docs.

"""

import os
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import (
    FastAPI, Request, Depends, HTTPException, status, UploadFile, File, Form, Body
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from jose import JWTError, jwt
from passlib.context import CryptContext

from .db import (
    get_db,
    User,
    CertificateApplication,
    Certificate,
    Document,
    Notification,
    AuditLog,
    UserRole,
    CertificateStatus,
    init_db,
    engine
)

# ----------------------------------------------------------------
# JWT tokens, security constants and password hashing configuration
# ----------------------------------------------------------------
# These drive authentication/security for all endpoints. SECRET_KEY should be replaced for production!
SECRET_KEY = os.environ.get("EPCC_SECRET_KEY", "devsecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 2  # 2 days by default

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --------------------------
# Multilingual support for user-facing messages.
# If new status or error keys are added, update the dictionaries below.
# Language is detected from Accept-Language header; default is EN.
LANGS = ['en', 'fr', 'ar']
DEFAULT_LANG = 'en'

LANG_MESSAGES = {
    "en": {
        "register_success": "Registration successful.",
        "login_success": "Login successful.",
        "invalid_credentials": "Invalid email or password.",
        "access_denied": "You do not have permission for this action.",
        "certificate_created": "Certificate application submitted.",
    },
    "fr": {
        "register_success": "Inscription réussie.",
        "login_success": "Connexion réussie.",
        "invalid_credentials": "Email ou mot de passe invalide.",
        "access_denied": "Vous n'avez pas la permission pour cette action.",
        "certificate_created": "Demande de certificat soumise.",
    },
    "ar": {
        "register_success": "تم التسجيل بنجاح.",
        "login_success": "تم تسجيل الدخول بنجاح.",
        "invalid_credentials": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
        "access_denied": "ليس لديك إذن لهذا الإجراء.",
        "certificate_created": "تم تقديم طلب الشهادة.",
    }
}

def get_message(key: str, lang: str) -> str:
    """
    Return a translated string for a given key/language.
    If translation is missing, fallback to English or the key itself.
    """
    return LANG_MESSAGES.get(lang, LANG_MESSAGES[DEFAULT_LANG]).get(key, key)

# ---------------------------------
# Utilities: password hashing, JWT handling, request language parsing
# ---------------------------------
# Used by authentication and app error handling for all credential/token flows.

def get_password_hash(password: str) -> str:
    """Return a secure password hash for storage."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the provided plain password matches the hashed version."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate a JWT access token containing the provided payload data.
    Optionally set expiration (default: 48h).
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_lang(request: Request) -> str:
    """
    Parse HTTP request for 'accept-language' header.
    Falls back to default if value not among supported codes.
    """
    lang = request.headers.get('accept-language', DEFAULT_LANG)
    if lang not in LANGS:
        lang = DEFAULT_LANG
    return lang

# ---------------------------------
# User Authentication & Role-Checking Dependencies and Pydantic token/user schemas
# ---------------------------------
# These are FastAPI dependencies and helper types for all endpoints requiring authentication.

class Token(BaseModel):
    """JWT Bearer token returned to client after login/registration."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Used internally to decode relevant info from JWT for fast token validation."""
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None

class UserBase(BaseModel):
    """Base schema for user-related requests/responses."""
    email: EmailStr
    full_name: Optional[str] = None

class UserRegister(UserBase):
    """Request schema for user registration."""
    password: str = Field(..., min_length=6)

class UserResponse(UserBase):
    """API response schema for full user details. Used by registration/login/profile endpoints."""
    id: int
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True

# PUBLIC_INTERFACE
def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    PUBLIC_INTERFACE

    FastAPI dependency. Checks JWT Bearer authorization token in the request,
    decodes it, validates user presence in DB, and returns User ORM instance.
    Raises 401 if unauthorized.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials, login required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
        email: str = payload.get("email")
    except (JWTError, Exception):
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None or user.email != email:
        raise credentials_exception
    return user

# PUBLIC_INTERFACE
def require_roles(*roles):
    """
    PUBLIC_INTERFACE

    Returns a FastAPI dependency which ensures that the current user has one
    of the allowed role(s). Raises 403 if not permitted.
    Example: @app.route(..., dependencies=[Depends(require_roles('admin'))])
    """
    def _role_dependency(
        current_user: User = Depends(get_current_user)
    ):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You lack sufficient permissions."
            )
        return current_user
    return _role_dependency

# --------------------
# Pydantic Models for API Exchange: Certificate, Application, Notification, etc.
# These schemas control API request/response serialization and validation.
# --------------------
class CertificateApplicationRequest(BaseModel):
    """Used for new certificate application creation."""
    details: str = Field(..., max_length=2048)

class CertificateApplicationResponse(BaseModel):
    """Serialized certificate application for API responses."""
    id: int
    status: str
    details: Optional[str]
    submission_time: datetime
    reviewed_by_id: Optional[int] = None

    class Config:
        orm_mode = True

class CertificateResponse(BaseModel):
    """API response schema for certificate records."""
    id: int
    certificate_number: str
    status: str
    issue_date: datetime
    expiry_date: Optional[datetime]
    owner_id: int

    class Config:
        orm_mode = True

class NotificationResponse(BaseModel):
    """API response schema for notifications."""
    id: int
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        orm_mode = True

class AuditLogResponse(BaseModel):
    """API response schema for audit log rows."""
    id: int
    user_id: Optional[int]
    application_id: Optional[int]
    certificate_id: Optional[int]
    action: str
    timestamp: datetime
    details: Optional[str]

    class Config:
        orm_mode = True

class DocumentResponse(BaseModel):
    """Response schema for uploaded document info."""
    id: int
    filename: str
    url: str
    uploaded_at: datetime
    content_type: str

    class Config:
        orm_mode = True

# ----------------------
# Main FastAPI app definition and settings, including OpenAPI metadata, tags, and CORS middleware.
# ----------------------
app = FastAPI(
    title="E-Police Certificate Backend",
    description=(
        "Backend API and service for E-Police Certificate operations. "
        "Provides endpoints for user management, certificate applications, verification, and admin actions. "
        "Database: SQLite, ORM: SQLAlchemy.\n\n"
        "Main tables: users, certificate_applications, certificates, documents, notifications, audit_logs."
    ),
    version="0.1.0",
    openapi_tags=[
        {"name": "auth", "description": "User registration/login"},
        {"name": "user", "description": "User dashboard/API"},
        {"name": "application", "description": "Certificate application endpoints"},
        {"name": "certificate", "description": "Certificate viewing and management"},
        {"name": "admin", "description": "Admin/Officer certificate & user management"},
        {"name": "notification", "description": "Notifications API"},
        {"name": "document", "description": "Document upload/download endpoints"},
        {"name": "audit", "description": "Audit/event logs"},
    ]
)

# Allow all CORS for frontend/backend local dev (adjust for production deployments as needed!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# ------------------------
# DB Health Check Endpoint
# ------------------------
# PUBLIC_INTERFACE
from sqlalchemy import text

@app.get("/health/db", tags=["admin"], summary="Check DB connectivity")
def health_db_check():
    """
    PUBLIC_INTERFACE

    Returns OK if the backend can establish a connection to the database.
    Use for admin/ops healthchecks and debugging 502/internal server errors.
    Response format:
        {
          "ok": true,
          "error": null
        }
        OR
        {
          "ok": false,
          "error": "error description"
        }
    """
    try:
        with engine.connect() as connection:
            # The recommended SQLAlchemy way: use sqlalchemy.text
            connection.execute(text("SELECT 1"))
        return {"ok": True, "error": None}
    except SQLAlchemyError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"Non-SQL error: {str(e)}"}

@app.on_event("startup")
def on_startup():
    """
    PUBLIC_INTERFACE

    FastAPI startup hook: initializes DB schema and uploads directory, ensuring
    backend is ready to serve requests after a cold start or deployment.
    Run this only once on process startup, not per-request.
    """
    init_db()
    os.makedirs("uploads", exist_ok=True)

@app.get("/")
def root():
    """
    PUBLIC_INTERFACE

    Healthcheck endpoint. Shows backend service is running.
    Simple check used by orchestrators and uptime monitoring.
    """
    return {"message": "Healthy"}

@app.get("/docs/lang", response_model=dict, tags=["auth"])
def get_langs():
    """
    PUBLIC_INTERFACE

    API endpoint to enumerate supported languages for translation.
    Used for client-side language selector and diagnostics.
    """
    return {"languages": LANGS}

# =============================
# AUTH: Registration/Login endpoints
# Endpoints for user registration, authentication, and token issuance.
# =============================

@app.post("/register", response_model=UserResponse, tags=["auth"], summary="Register new user")
def register_user(
    user_in: UserRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    Register a new user (default role: user).
    Checks for existing email, hashes password, creates User in DB.
    """
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists.")
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # Log registration event in audit log for traceability
    db.add(AuditLog(user_id=user.id, action="register", timestamp=datetime.utcnow()))
    db.commit()
    return user

@app.post("/token", response_model=Token, tags=["auth"], summary="Login and get JWT token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    Authenticates user, issues JWT token for use in future Bearer requests.
    User is identified by email. Account must be active.
    """
    lang = get_lang(request)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail=get_message("invalid_credentials", lang))
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive account.")
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )
    db.add(AuditLog(user_id=user.id, action="login", timestamp=datetime.utcnow(), details="User login"))
    db.commit()
    return {"access_token": access_token, "token_type": "bearer"}

# --------------------------------------
# USER/PROFILE: endpoints to fetch profile, and endpoints providing the current user's view into the system.
# --------------------------------------

@app.get("/me", response_model=UserResponse, tags=["user"], summary="Get my profile")
def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    PUBLIC_INTERFACE

    Returns the data of the currently authenticated user (from JWT token).
    """
    return current_user

# ------------------------------------
# APPLICATIONS: all certificate application creation and query endpoints
# (User-facing and officer/admin-facing)
# ------------------------------------
@app.get("/applications", response_model=List[CertificateApplicationResponse], tags=["application"])
def list_my_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    Returns a list of all certificate applications submitted by current user.
    """
    apps = db.query(CertificateApplication).filter(CertificateApplication.applicant_id == current_user.id).all()
    return apps

@app.post("/applications", response_model=CertificateApplicationResponse, tags=["application"])
def submit_application(
    req: CertificateApplicationRequest,
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    Submit a new certificate application for the logged-in user.
    Sets status to pending, initializes records, and delivers a notification.
    """
    app_obj = CertificateApplication(
        applicant_id=current_user.id,
        details=req.details,
        status=CertificateStatus.pending,
        submission_time=datetime.utcnow()
    )
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    # Log event for auditing
    db.add(AuditLog(
        user_id=current_user.id,
        application_id=app_obj.id,
        action="application_submitted",
        timestamp=datetime.utcnow(),
        details="User submitted certificate application"
    ))
    notif_message = get_message("certificate_created", get_lang(request))
    db.add(Notification(
        user_id=current_user.id,
        message=notif_message,
        is_read=False,
        created_at=datetime.utcnow()
    ))
    db.commit()
    return app_obj

@app.get("/applications/{application_id}", response_model=CertificateApplicationResponse, tags=["application"])
def get_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    Retrieve a single application by its ID if the user is owner, officer, or admin.
    Enforces access control.
    """
    app = db.query(CertificateApplication).filter(CertificateApplication.id == application_id).first()
    if not app or (app.applicant_id != current_user.id and current_user.role not in [UserRole.officer, UserRole.admin]):
        raise HTTPException(status_code=404, detail="Application not found or access denied.")
    return app

# -----------------------------------------
# CERTIFICATES: endpoints for listing and getting certificates by user, officer or admin
# -----------------------------------------

@app.get("/certificates", response_model=List[CertificateResponse], tags=["certificate"])
def list_my_certificates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    List all certificates owned by the authenticated user.
    """
    certs = db.query(Certificate).filter(Certificate.owner_id == current_user.id).all()
    return certs

@app.get("/certificates/{certificate_id}", response_model=CertificateResponse, tags=["certificate"])
def get_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    Get a single certificate by ID if owned or if the user is officer/admin.
    """
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert or (cert.owner_id != current_user.id and current_user.role not in [UserRole.officer, UserRole.admin]):
        raise HTTPException(status_code=404, detail="Certificate not found or not allowed.")
    return cert

# --------------------------------------
# OFFICER/ADMIN OPERATIONS: endpoints accessible to admin and officers only; use require_roles
# --------------------------------------

@app.get("/admin/applications", response_model=List[CertificateApplicationResponse], tags=["admin"])
def admin_list_applications(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.officer)),
):
    """
    PUBLIC_INTERFACE

    Return full list of all certificate applications (restricted to officers/admin).
    """
    return db.query(CertificateApplication).all()

@app.patch("/admin/applications/{application_id}", response_model=CertificateApplicationResponse, tags=["admin"])
def admin_update_application_status(
    application_id: int,
    status: CertificateStatus = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.officer))
):
    """
    PUBLIC_INTERFACE

    Allow officer or admin to approve/reject an application (by status).
    Sends notification to the applicant.
    """
    app = db.query(CertificateApplication).filter(CertificateApplication.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Not found.")
    app.status = status
    app.reviewed_by_id = current_user.id
    db.add(AuditLog(
        user_id=current_user.id,
        application_id=application_id,
        action=f"application_{status.value}",
        timestamp=datetime.utcnow()
    ))
    db.add(Notification(
        user_id=app.applicant_id,
        message=f"Your application status updated: {status.value}",
        created_at=datetime.utcnow()
    ))
    db.commit()
    db.refresh(app)
    return app

@app.post("/admin/applications/{application_id}/certificates", response_model=CertificateResponse, tags=["admin"])
def admin_issue_certificate(
    application_id: int,
    expiry_date: Optional[datetime] = Body(None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.officer))
):
    """
    PUBLIC_INTERFACE

    Issue a certificate document for a given application.
    Application must already be approved.
    """
    app_obj = db.query(CertificateApplication).filter(CertificateApplication.id == application_id).first()
    if not app_obj or app_obj.status != CertificateStatus.approved:
        raise HTTPException(status_code=400, detail="Application not approved or not found.")
    cert_number = f"EPC-{int(datetime.utcnow().timestamp())}-{application_id}"
    cert = Certificate(
        owner_id=app_obj.applicant_id,
        application_id=application_id,
        certificate_number=cert_number,
        status=CertificateStatus.issued,
        issue_date=datetime.utcnow(),
        expiry_date=expiry_date
    )
    app_obj.status = CertificateStatus.issued
    db.add(cert)
    db.add(AuditLog(
        user_id=current_user.id,
        application_id=application_id,
        certificate_id=cert.id,
        action="certificate_issued",
        timestamp=datetime.utcnow()
    ))
    db.add(Notification(
        user_id=app_obj.applicant_id,
        message="Certificate issued for your application.",
        created_at=datetime.utcnow()
    ))
    db.commit()
    db.refresh(cert)
    return cert

@app.patch("/admin/certificates/{certificate_id}/revoke", response_model=CertificateResponse, tags=["admin"])
def admin_revoke_certificate(
    certificate_id: int,
    reason: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.officer))
):
    """
    PUBLIC_INTERFACE

    Revoke a certificate and supply a mandatory reason.
    """
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Not found.")
    cert.status = CertificateStatus.revoked
    cert.revocation_reason = reason
    db.add(AuditLog(
        user_id=current_user.id,
        certificate_id=certificate_id,
        action="certificate_revoked",
        timestamp=datetime.utcnow(),
        details=reason
    ))
    db.commit()
    db.refresh(cert)
    return cert

# ------------------------------------------------
# NOTIFICATIONS: endpoints for users to get and update notification states
# ------------------------------------------------
@app.get("/notifications", response_model=List[NotificationResponse], tags=["notification"])
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    Returns all notifications for current user (newest first).
    """
    return db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()

@app.patch("/notifications/{notification_id}/markread", response_model=NotificationResponse, tags=["notification"])
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    PUBLIC_INTERFACE

    Mark the supplied notification as 'read' for this user.
    """
    note = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Not found.")
    note.is_read = True
    db.commit()
    return note

# ------------------------------------------
# DOCUMENTS: Upload and Download endpoints for application-linked files
# Security: Only file owner, officer or admin can access respective endpoints
# Files are placed in uploads/, direct download supported (ensure permissions!)
# ------------------------------------------
UPLOADS_DIR = "uploads"

@app.post("/documents/upload", response_model=DocumentResponse, tags=["document"])
async def upload_document(
    application_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PUBLIC_INTERFACE

    Upload a document to a specific application owned by the current user.
    Stores file on disk (uploads/) and makes it available for future download.
    Ownership is strictly enforced; user must own the given application.
    """
    app = db.query(CertificateApplication).filter(
        CertificateApplication.id == application_id,
        CertificateApplication.applicant_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not owned by you.")
    # Save file to disk with unique timestamp prefix for filename safety
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    path = os.path.join(UPLOADS_DIR, filename)
    with open(path, "wb") as f:
        f.write(await file.read())
    url = f"/documents/download/{filename}"
    doc = Document(
        filename=filename,
        content_type=file.content_type,
        url=url,
        application_id=application_id,
    )
    db.add(doc)
    db.add(AuditLog(
        user_id=current_user.id,
        application_id=application_id,
        action="document_uploaded",
        timestamp=datetime.utcnow(),
        details=filename
    ))
    db.commit()
    db.refresh(doc)
    return doc

@app.get("/documents/download/{filename}", response_class=FileResponse, tags=["document"])
def download_document(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """
    PUBLIC_INTERFACE

    Download a previously uploaded document file.
    File must exist on local disk (“uploads/” directory by default).
    Access should require document ownership (in production environments consider checks/auditing).
    """
    path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path, media_type='application/octet-stream', filename=filename)


@app.get("/applications/{application_id}/documents", response_model=List[DocumentResponse], tags=["document"])
def get_application_documents(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    PUBLIC_INTERFACE

    List all documents for an application (requires owner, admin or officer).
    Used for viewing receipts/proofs submitted with user's certificate application.
    """
    app = db.query(CertificateApplication).filter(CertificateApplication.id == application_id).first()
    if not app or (app.applicant_id != current_user.id and current_user.role not in [UserRole.admin, UserRole.officer]):
        raise HTTPException(status_code=404, detail="Not authorized or not found.")
    return db.query(Document).filter(Document.application_id == application_id).all()

# ---------------------------------------------------------
# AUDIT LOGS: endpoints for admin/officer audit viewing
# ---------------------------------------------------------
@app.get("/admin/auditlogs", response_model=List[AuditLogResponse], tags=["audit"])
def get_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.officer)),
    limit: int = 100,
):
    """
    PUBLIC_INTERFACE

    Return recent audit log entries (admin/officer only).
    """
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return logs

# --------------------------------------
# EXCEPTION HANDLING: Multilingual error formatting for UX; extend as app expands.
# --------------------------------------
@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    """
    HTTP error handler for common application exceptions.
    Translates some messages to user's preferred language.
    Extend msg_key/name set above to expand the dictionary of translated error keys.
    """
    lang = get_lang(request)
    msg_key = None
    # Translate most common errors (credentials/permission)
    if "credential" in str(exc.detail).lower():
        msg_key = "invalid_credentials"
    elif "permission" in str(exc.detail).lower() or "access" in str(exc.detail).lower():
        msg_key = "access_denied"
    if msg_key:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": get_message(msg_key, lang)}
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(ValidationError)
def validation_exception_handler(request: Request, exc: ValidationError):
    """
    Handles input validation errors, returning field error info and user language code.
    """
    lang = get_lang(request)
    return JSONResponse(status_code=422, content={
        "detail": exc.errors(),
        "lang": lang
    })
