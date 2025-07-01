from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Database setup
from .db import init_db

app = FastAPI(
    title="E-Police Certificate Backend",
    description=(
        "Backend API and service for E-Police Certificate operations. "
        "Provides endpoints for user management, certificate applications, verification, and admin actions. "
        "Database: SQLite, ORM: SQLAlchemy.\n\n"
        "Main tables: users, certificate_applications, certificates, documents, notifications, audit_logs."
    ),
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """
    PUBLIC_INTERFACE

    On FastAPI startup, create (if needed) the SQLite schema for all main tables:
    - users (roles: user/admin/officer)
    - certificate_applications (with status enum: pending/approved/rejected/issued/revoked)
    - certificates (links to users and applications)
    - notifications (user notifications)
    - documents (uploaded support docs)
    - audit_logs (auditing actions)
    """
    init_db()

@app.get("/")
def health_check():
    """PUBLIC_INTERFACE

    Returns server health.
    """
    return {"message": "Healthy"}
