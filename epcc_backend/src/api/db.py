"""
Database integration and core schema for E-Police Certificate application backend.

This module sets up SQLite, defines all ORM models for core tables, and provides initialization logic
to bootstrap the database on FastAPI startup.

PUBLIC INTERFACES:
- get_db: Dependency to provide a database session for requests.
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
    func
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    relationship
)
import enum
import os

# PUBLIC_INTERFACE
Base = declarative_base()

# Path to SQLite DB; will be created in project root if not overridden by env
DATABASE_URL = os.environ.get("EPCC_DATABASE_URL", "sqlite:///./epcc.sqlite3")

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Enum Types
class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    officer = "officer"

class CertificateStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    issued = "issued"
    revoked = "revoked"

# Models

class User(Base):
    """System user. Includes normal users, police officers, and admins."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.user, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    applications = relationship("CertificateApplication", back_populates="applicant")
    certificates = relationship("Certificate", back_populates="owner")
    notifications = relationship("Notification", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

class CertificateApplication(Base):
    """Stores user-submitted applications for E-Police Certificates."""
    __tablename__ = "certificate_applications"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(CertificateStatus), default=CertificateStatus.pending)
    details = Column(Text)
    submission_time = Column(DateTime, default=func.now())
    reviewed_by_id = Column(Integer, ForeignKey("users.id"))  # Officer/admin who reviewed

    applicant = relationship("User", foreign_keys=[applicant_id], back_populates="applications")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    certificate = relationship("Certificate", uselist=False, back_populates="application")
    documents = relationship("Document", back_populates="application")
    audit_logs = relationship("AuditLog", back_populates="application")

class Certificate(Base):
    """Issued certificate, may be linked to an application."""
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    application_id = Column(Integer, ForeignKey("certificate_applications.id"), nullable=True)
    certificate_number = Column(String, unique=True, index=True)
    status = Column(Enum(CertificateStatus), default=CertificateStatus.issued)
    issue_date = Column(DateTime, default=func.now())
    expiry_date = Column(DateTime, nullable=True)
    revocation_reason = Column(String, nullable=True)

    owner = relationship("User", back_populates="certificates")
    application = relationship("CertificateApplication", back_populates="certificate")
    audit_logs = relationship("AuditLog", back_populates="certificate")

class Document(Base):
    """Document uploads, e.g. scans of identity proofs, supporting files."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=func.now())
    application_id = Column(Integer, ForeignKey("certificate_applications.id"))

    application = relationship("CertificateApplication", back_populates="documents")

class Notification(Base):
    """Stores notifications for users about application/certificate status changes."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="notifications")

class AuditLog(Base):
    """Track actions performed on applications or certificates for auditing."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    application_id = Column(Integer, ForeignKey("certificate_applications.id"), nullable=True)
    certificate_id = Column(Integer, ForeignKey("certificates.id"), nullable=True)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=func.now())
    details = Column(Text, nullable=True)

    user = relationship("User", back_populates="audit_logs")
    application = relationship("CertificateApplication", back_populates="audit_logs")
    certificate = relationship("Certificate", back_populates="audit_logs")


# PUBLIC_INTERFACE
def get_db():
    """Yield a SQLAlchemy database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# PUBLIC_INTERFACE
def init_db():
    """Create all tables in the database if they do not exist."""
    Base.metadata.create_all(bind=engine)
