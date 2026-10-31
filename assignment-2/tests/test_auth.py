"""Tests for Section A: Authentication, Hashing, Roles, and Session Identity."""
import pytest

from audit.service import query_audit_logs
from auth.models import AuthUser
from auth.security import hash_password, verify_password
from auth.service import authenticate_user, get_user_by_username
from authorization.exceptions import AuthenticationRequiredError
from authorization.service import require_authenticated_user
from database.db import connection


def test_valid_student_login(student_user_a):
    assert student_user_a.username == "diya"
    assert student_user_a.student_id == "MIM25002"
    assert student_user_a.is_student() is True
    assert student_user_a.is_admin() is False


def test_valid_admin_login(admin_user):
    assert admin_user.username == "admin"
    assert admin_user.student_id is None
    assert admin_user.is_admin() is True
    assert admin_user.is_student() is False


def test_invalid_username_rejected():
    user = authenticate_user("nonexistent_user", "SomePass123!")
    assert user is None
    # Check that failed login was logged in audit
    logs = query_audit_logs(action="login_failed", limit=5)
    assert any("nonexistent_user" in l["requester_id"] for l in logs)


def test_invalid_password_rejected():
    user = authenticate_user("diya", "WrongPassword!")
    assert user is None
    logs = query_audit_logs(action="login_failed", limit=5)
    assert any(l["requester_role"] == "student" for l in logs)


def test_passwords_never_stored_in_plaintext():
    with connection() as conn:
        rows = conn.execute("SELECT password_hash FROM users").fetchall()
        for r in rows:
            h = r["password_hash"]
            # Plaintext passwords like "Student@123" must never appear
            assert "Student@123" not in h
            assert "Admin@12345" not in h
            # Must be valid bcrypt hash starting with $2b$ or $2a$
            assert h.startswith("$2")


def test_unauthenticated_access_denied():
    with pytest.raises(AuthenticationRequiredError):
        require_authenticated_user(None, action="view_profile")


def test_session_identity_immutability(student_user_a):
    # Verify AuthUser is frozen / immutable dataclass
    with pytest.raises(Exception):
        student_user_a.student_id = "MIM25001"
    with pytest.raises(Exception):
        student_user_a.role = "admin"
