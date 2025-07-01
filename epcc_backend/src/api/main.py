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
    init_db
)

# --------------------------
# JWT, Security, Constants
# --------------------------
SECRET_KEY = os.environ.get("EPCC_SECRET_KEY", "devsecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 2  # 2 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    return LANG_MESSAGES.get(lang, LANG_MESSAGES[DEFAULT_LANG]).get(key, key)

# ---------------------------------
# Utility: password, jwt, roles
# ---------------------------------

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_lang(request: Request) -> str:
    lang = request.headers.get('accept-language', DEFAULT_LANG)
    if lang not in LANGS:
        lang = DEFAULT_LANG
    return lang

# ---------------------------------
# User, Auth, Bearer, Roles
# ---------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserRegister(UserBase):
    password: str = Field(..., min_length=6)

class UserResponse(UserBase):
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
    """Decode JWT token and return User object or raise."""
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
    """Dependency to require one of the roles for a route."""
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
# Certificate models
# --------------------
class CertificateApplicationRequest(BaseModel):
    details: str = Field(..., max_length=2048)
    # Possibly: supporting data fields here

class CertificateApplicationResponse(BaseModel):
    id: int
    status: str
    details: Optional[str]
    submission_time: datetime
    reviewed_by_id: Optional[int] = None

    class Config:
        orm_mode = True

class CertificateResponse(BaseModel):
    id: int
    certificate_number: str
    status: str
    issue_date: datetime
    expiry_date: Optional[datetime]
    owner_id: int

    class Config:
        orm_mode = True

class NotificationResponse(BaseModel):
    id: int
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        orm_mode = True

class AuditLogResponse(BaseModel):
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
    id: int
    filename: str
    url: str
    uploaded_at: datetime
    content_type: str

    class Config:
        orm_mode = True

# ----------------------
# FastAPI app startup
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    """PUBLIC_INTERFACE: Initialize database on startup."""
    init_db()
    os.makedirs("uploads", exist_ok=True)

@app.get("/")
def root():
    """PUBLIC_INTERFACE
    Returns server health."""
    return {"message": "Healthy"}

@app.get("/docs/lang", response_model=dict, tags=["auth"])
def get_langs():
    """PUBLIC_INTERFACE
    Returns supported languages."""
    return {"languages": LANGS}

# -------------------------
# AUTH: Registration/Login
# -------------------------

@app.post("/register", response_model=UserResponse, tags=["auth"], summary="Register new user")
def register_user(
    user_in: UserRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    """PUBLIC_INTERFACE
    Register a new user (default 'user' role).
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
    # Log registration
    db.add(AuditLog(user_id=user.id, action="register", timestamp=datetime.utcnow()))
    db.commit()
    return user

@app.post("/token", response_model=Token, tags=["auth"], summary="Login and get JWT token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """PUBLIC_INTERFACE
    Login to get JWT token (username: email, password: password).
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

@app.get("/me", response_model=UserResponse, tags=["user"], summary="Get my profile")
def get_me(
    current_user: User = Depends(get_current_user),
):
    """PUBLIC_INTERFACE
    Return info about current authenticated user.
    """
    return current_user

# ------------------------------------
# User: view their applications/docs
# ------------------------------------
@app.get("/applications", response_model=List[CertificateApplicationResponse], tags=["application"])
def list_my_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PUBLIC_INTERFACE
    List certificate applications submitted by user.
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
    """PUBLIC_INTERFACE
    Submit new certificate application as the logged-in user."""
    app = CertificateApplication(
        applicant_id=current_user.id,
        details=req.details,
        status=CertificateStatus.pending,
        submission_time=datetime.utcnow()
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    # Log event
    db.add(AuditLog(
        user_id=current_user.id,
        application_id=app.id,
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
    return app

@app.get("/applications/{application_id}", response_model=CertificateApplicationResponse, tags=["application"])
def get_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PUBLIC_INTERFACE
    Get single application by id, only owner or reviewers allowed.
    """
    app = db.query(CertificateApplication).filter(CertificateApplication.id == application_id).first()
    if not app or (app.applicant_id != current_user.id and current_user.role not in [UserRole.officer, UserRole.admin]):
        raise HTTPException(status_code=404, detail="Application not found or access denied.")
    return app

# -----------------------------------------
# Certificate: own and by application ID
# -----------------------------------------

@app.get("/certificates", response_model=List[CertificateResponse], tags=["certificate"])
def list_my_certificates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PUBLIC_INTERFACE
    List certificates owned by current user.
    """
    certs = db.query(Certificate).filter(Certificate.owner_id == current_user.id).all()
    return certs

@app.get("/certificates/{certificate_id}", response_model=CertificateResponse, tags=["certificate"])
def get_certificate(
    certificate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PUBLIC_INTERFACE
    Get a single certificate (if owned or admin/officer).
    """
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert or (cert.owner_id != current_user.id and current_user.role not in [UserRole.officer, UserRole.admin]):
        raise HTTPException(status_code=404, detail="Certificate not found or not allowed.")
    return cert

# --------------------------------------
# OFFICER/ADMIN OPERATIONS
# --------------------------------------

@app.get("/admin/applications", response_model=List[CertificateApplicationResponse], tags=["admin"])
def admin_list_applications(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.officer)),
):
    """PUBLIC_INTERFACE
    List all certificate applications (admin/officer access).
    """
    return db.query(CertificateApplication).all()

@app.patch("/admin/applications/{application_id}", response_model=CertificateApplicationResponse, tags=["admin"])
def admin_update_application_status(
    application_id: int,
    status: CertificateStatus = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.officer))
):
    """PUBLIC_INTERFACE
    Approve/reject application, update status (admin/officer only)."""
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
    """PUBLIC_INTERFACE
    Issue certificate for application (admin/officer only).
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
    """PUBLIC_INTERFACE
    Revoke a certificate, provide reason (admin/officer only).
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
# Notifications: user
# ------------------------------------------------
@app.get("/notifications", response_model=List[NotificationResponse], tags=["notification"])
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PUBLIC_INTERFACE
    Get notifications for current user.
    """
    return db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()

@app.patch("/notifications/{notification_id}/markread", response_model=NotificationResponse, tags=["notification"])
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """PUBLIC_INTERFACE
    Mark a notification as read (user).
    """
    # lang = get_lang(request)  # Removed unused variable assignment to fix linter error.
    note = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Not found.")
    note.is_read = True
    db.commit()
    return note

# ------------------------------------------
# DOCUMENT: Upload, Download
# ------------------------------------------
UPLOADS_DIR = "uploads"

@app.post("/documents/upload", response_model=DocumentResponse, tags=["document"])
async def upload_document(
    application_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """PUBLIC_INTERFACE
    Upload a document for a given application."""
    app = db.query(CertificateApplication).filter(
        CertificateApplication.id == application_id,
        CertificateApplication.applicant_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found or not owned by you.")
    # Save file to disk
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
    """PUBLIC_INTERFACE
    Download previously uploaded document (file access only by logged in user).
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
    """PUBLIC_INTERFACE
    List documents for an application (must be owner or admin/officer).
    """
    app = db.query(CertificateApplication).filter(CertificateApplication.id == application_id).first()
    if not app or (app.applicant_id != current_user.id and current_user.role not in [UserRole.admin, UserRole.officer]):
        raise HTTPException(status_code=404, detail="Not authorized or not found.")
    return db.query(Document).filter(Document.application_id == application_id).all()

# ---------------------------------------------------------
# AUDIT LOGS: for account/cert/app actions (admin view)
# ---------------------------------------------------------
@app.get("/admin/auditlogs", response_model=List[AuditLogResponse], tags=["audit"])
def get_audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.officer)),
    limit: int = 100,
):
    """PUBLIC_INTERFACE
    List recent audit logs (admin/officer only)."""
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return logs

# --------------------------------------
# MULTILINGUAL ERROR HANDLING
# --------------------------------------
@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException):
    lang = get_lang(request)
    msg_key = None
    # Map most common errors
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
    lang = get_lang(request)
    return JSONResponse(status_code=422, content={
        "detail": exc.errors(),
        "lang": lang
    })
