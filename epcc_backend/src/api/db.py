"""
Database integration and ORM models for the E-Police Certificate backend.

This module configures the SQLAlchemy engine for database access (using SQLite by default, but supports override via env var).
Defines all core ORM entity classes (User, CertificateApplication, Certificate, Document, Notification, AuditLog) and their
relationships, as well as enum types for user roles and certificate/application status.

Initialization logic is provided for database bootstrap on application startup.

PUBLIC INTERFACES:
- get_db(): FastAPI dependency yielding a session per request
- init_db(): Initializes all tables if not yet present
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Enum,
    func,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    relationship,
)
import enum
import os

# PUBLIC_INTERFACE
Base = declarative_base()  # Used as a base class for all ORM models

# Path to SQLite DB; can be overridden by setting EPCC_DATABASE_URL environment variable.
DATABASE_URL = os.environ.get("EPCC_DATABASE_URL", "sqlite:///./epcc.sqlite3")

# SQLAlchemy DB engine and session factory. SQLite disables check_same_thread for FastAPI async compatibility.
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)  # Main DB engine, special param for SQLite+threads with FastAPI
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Enum Types (used for DB model columns)
class UserRole(str, enum.Enum):
    """Possible roles for users in the system."""
    user = "user"       # Standard user
    admin = "admin"     # Administrator with all privileges
    officer = "officer" # Officer or police reviewer

class CertificateStatus(str, enum.Enum):
    """State of a certificate application or actual certificate."""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    issued = "issued"
    revoked = "revoked"

#############
# Models
#############

class User(Base):
    """System user record. Includes standard applicants, officers, and admin users."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.user, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    applications = relationship("CertificateApplication", back_populates="applicant")
    certificates = relationship("Certificate", back_populates="owner")
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

class CertificateApplication(Base):
    """
    Stores user-submitted certificate application.
    - applicant_id: user who applied
    - reviewed_by_id: officer or admin who reviewed (nullable until reviewed)
    - documents: uploaded files supporting the application
    """
    __tablename__ = "certificate_applications"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(CertificateStatus), default=CertificateStatus.pending)
    details = Column(Text)
    submission_time = Column(DateTime, default=func.now())
    reviewed_by_id = Column(Integer, ForeignKey("users.id"))  #  Officer/admin reviewer (nullable)

    # Relationships
    applicant = relationship("User", foreign_keys=[applicant_id], back_populates="applications")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    certificate = relationship(
        "Certificate",
        uselist=False,
        back_populates="application"
    )   # One-to-one application to certificate link

    documents = relationship("Document", back_populates="application")
    audit_logs = relationship("AuditLog", back_populates="application")

class Certificate(Base):
    """
    Represents an issued certificate.
    - Linked to CertificateApplication via application_id
    - owner_id: user to whom the certificate is issued
    """
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    application_id = Column(Integer, ForeignKey("certificate_applications.id"), nullable=True)
    certificate_number = Column(String, unique=True, index=True)
    status = Column(Enum(CertificateStatus), default=CertificateStatus.issued)
    issue_date = Column(DateTime, default=func.now())
    expiry_date = Column(DateTime, nullable=True)
    revocation_reason = Column(String, nullable=True)

    # Relationships
    owner = relationship("User", back_populates="certificates")
    application = relationship("CertificateApplication", back_populates="certificate")
    audit_logs = relationship("AuditLog", back_populates="certificate")

class Document(Base):
    """
    Uploaded document (such as scans, photos, proof).
    Each document is linked to one CertificateApplication.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    url = Column(String, nullable=False)  # Local API path for download
    uploaded_at = Column(DateTime, default=func.now())
    application_id = Column(Integer, ForeignKey("certificate_applications.id"))

    # Relationships
    application = relationship("CertificateApplication", back_populates="documents")

class Notification(Base):
    """
    Stores notifications about app/certificate events for users.
    Used for status changes, success/failure, etc.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="notifications")

class AuditLog(Base):
    """
    Records actions/events for audit trail.
    Any model modification should be logged (user registration, app submission, cert issuance).
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    application_id = Column(Integer, ForeignKey("certificate_applications.id"), nullable=True)
    certificate_id = Column(Integer, ForeignKey("certificates.id"), nullable=True)
    action = Column(String, nullable=False)  # Log event type (register, login, etc)
    timestamp = Column(DateTime, default=func.now())
    details = Column(Text, nullable=True)  # May hold summary (reason or payload data)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
    application = relationship("CertificateApplication", back_populates="audit_logs")
    certificate = relationship("Certificate", back_populates="audit_logs")

# PUBLIC_INTERFACE
def get_db():
    """
    Yield a SQLAlchemy database session to use within FastAPI requests.

    Usage (as dependency):
       db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# PUBLIC_INTERFACE
def init_db():
    """
    Create all database tables (if not existing).

    Called automatically on FastAPI startup to ensure schema is present.
    """
    Base.metadata.create_all(bind=engine)
