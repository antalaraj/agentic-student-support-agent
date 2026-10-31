"""Authentication service.
Handles user retrieval, login validation, session tokens, and account creation.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from audit.service import log_security_event
from auth.models import AuthUser
from auth.security import hash_password, verify_password
from database.db import connection

logger = logging.getLogger(__name__)


def get_user_by_username(username: str) -> Optional[AuthUser]:
    """Retrieve user by case-insensitive username."""
    if not username:
        return None
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
            (username.strip(),),
        ).fetchone()
        if not row:
            return None
        return AuthUser(
            user_id=row["user_id"],
            username=row["username"],
            role=row["role"],
            student_id=row["student_id"],
            full_name=row["full_name"],
            email=row["email"],
            is_active=bool(row["is_active"]),
        )


def get_user_by_id(user_id: str) -> Optional[AuthUser]:
    """Retrieve user by user_id."""
    if not user_id:
        return None
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return AuthUser(
            user_id=row["user_id"],
            username=row["username"],
            role=row["role"],
            student_id=row["student_id"],
            full_name=row["full_name"],
            email=row["email"],
            is_active=bool(row["is_active"]),
        )


def authenticate_user(
    username: str,
    password: str,
    session_id: Optional[str] = None,
) -> Optional[AuthUser]:
    """Authenticate credentials. Logs all success and failure events to the security audit log.
    Never logs or persists the plaintext password.
    """
    clean_username = (username or "").strip()
    if not clean_username or not password:
        log_security_event(
            requester_id=clean_username or "anonymous",
            requester_role="anonymous",
            action="login_failed",
            resource="auth",
            authorization_decision="DENIED",
            execution_status="FAILED",
            failure_reason="Missing username or password",
            session_id=session_id,
        )
        return None

    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
            (clean_username,),
        ).fetchone()

    if not row or not row["is_active"]:
        log_security_event(
            requester_id=clean_username,
            requester_role="anonymous",
            action="login_failed",
            resource="auth",
            authorization_decision="DENIED",
            execution_status="FAILED",
            failure_reason="User not found or inactive account",
            session_id=session_id,
        )
        return None

    if not verify_password(password, row["password_hash"]):
        log_security_event(
            requester_id=clean_username,
            requester_role=row["role"],
            action="login_failed",
            resource="auth",
            requested_resource_id=row["student_id"],
            authorization_decision="DENIED",
            execution_status="FAILED",
            failure_reason="Invalid credentials",
            session_id=session_id,
        )
        return None

    user = AuthUser(
        user_id=row["user_id"],
        username=row["username"],
        role=row["role"],
        student_id=row["student_id"],
        full_name=row["full_name"],
        email=row["email"],
        is_active=bool(row["is_active"]),
    )

    log_security_event(
        requester_id=user.user_id,
        requester_role=user.role,
        action="login_success",
        resource="auth",
        requested_resource_id=user.student_id,
        authorization_decision="ALLOWED",
        execution_status="SUCCESS",
        details={"username": user.username, "role": user.role},
        session_id=session_id,
    )
    return user


def create_user(
    username: str,
    password: str,
    role: str,
    student_id: Optional[str] = None,
    full_name: str = "",
    email: str = "",
) -> AuthUser:
    """Create a new user with salted bcrypt password hashing."""
    user_id = f"USR-{uuid.uuid4().hex[:10].upper()}"
    hashed = hash_password(password)
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO users (
                user_id, username, password_hash, role, student_id,
                full_name, email, created_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (user_id, username.strip().lower(), hashed, role, student_id, full_name, email, created_at),
        )

    return AuthUser(
        user_id=user_id,
        username=username.strip().lower(),
        role=role,
        student_id=student_id,
        full_name=full_name,
        email=email,
        is_active=True,
    )


def list_users() -> list[AuthUser]:
    """Return all users in the system."""
    with connection() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY role, username").fetchall()
        return [
            AuthUser(
                user_id=r["user_id"],
                username=r["username"],
                role=r["role"],
                student_id=r["student_id"],
                full_name=r["full_name"],
                email=r["email"],
                is_active=bool(r["is_active"]),
            )
            for r in rows
        ]


def get_user_by_username(username: str) -> Optional[AuthUser]:
    """Retrieve user by username without password verification."""
    clean_username = (username or "").strip().lower()
    if not clean_username:
        return None
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
            (clean_username,),
        ).fetchone()
        if not row:
            return None
        return AuthUser(
            user_id=row["user_id"],
            username=row["username"],
            role=row["role"],
            student_id=row["student_id"],
            full_name=row["full_name"],
            email=row["email"],
            is_active=bool(row["is_active"]),
        )
