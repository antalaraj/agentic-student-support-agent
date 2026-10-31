"""Tests for Section D: Security Audit Logging and Non-repudiation."""
import pytest

from approval.service import create_fee_extension_request, review_approval_request
from audit.service import log_security_event, query_audit_logs
from auth.context import reset_current_user, set_current_user
from database.db import connection
from tools.fee_tools import check_fee_status


def test_allowed_read_action_logged(student_user_a):
    token = set_current_user(student_user_a)
    try:
        check_fee_status("MIM25002")
        logs = query_audit_logs(action="view_fee_status", requester_id=student_user_a.user_id)
        assert len(logs) >= 1
        assert logs[0]["authorization_decision"] == "ALLOWED"
        assert logs[0]["requested_resource_id"] == "MIM25002"
    finally:
        reset_current_user(token)


def test_denied_cross_student_action_logged(student_user_a):
    token = set_current_user(student_user_a)
    try:
        check_fee_status("MIM25001")
        logs = query_audit_logs(action="cross_student_view_fee_status_blocked")
        assert len(logs) >= 1
        assert logs[0]["authorization_decision"] == "DENIED"
        assert logs[0]["requested_resource_id"] == "MIM25001"
        assert logs[0]["execution_status"] == "BLOCKED"
    finally:
        reset_current_user(token)


def test_approval_and_rejection_audit_records(admin_user, student_user_a):
    req = create_fee_extension_request(
        user=student_user_a,
        reason="Audit tracking test",
        requested_due_date="2026-12-28",
    )
    req_id = req["request_id"]

    review_approval_request(admin_user, req_id, "APPROVED", "Approved for testing")

    logs = query_audit_logs(action="approve_fee_extension", requested_resource_id=req_id)
    assert len(logs) >= 1
    assert logs[0]["approver_id"] == admin_user.user_id
    assert logs[0]["approval_status"] == "APPROVED"
    assert logs[0]["execution_status"] == "SUCCESS"


def test_sensitive_credentials_redacted_in_audit_details():
    audit_id = log_security_event(
        requester_id="test_user",
        requester_role="student",
        action="test_action",
        resource="test_res",
        details={
            "safe_field": "public_note",
            "password": "SecretPassword123!",
            "otp": "482913",
            "api_key": "gsk_secret_key_abcdef",
            "mixed_text": "My phone OTP is 987654 and card is 4111111111111111",
        },
    )

    with connection() as conn:
        row = conn.execute("SELECT details_json FROM security_audit_logs WHERE audit_id = ?", (audit_id,)).fetchone()
        raw_json = row["details_json"]

        assert "SecretPassword123!" not in raw_json
        assert "482913" not in raw_json
        assert "gsk_secret_key" not in raw_json
        assert "4111111111111111" not in raw_json
        assert "[REDACTED_SECRET]" in raw_json or "[REDACTED" in raw_json
        assert "public_note" in raw_json


def test_audit_entries_contain_correct_roles_and_ids(student_user_a):
    token = set_current_user(student_user_a)
    try:
        check_fee_status("MIM25002")
        logs = query_audit_logs(requester_id=student_user_a.user_id)
        assert len(logs) >= 1
        assert logs[0]["requester_role"] == "student"
        assert logs[0]["requester_id"] == student_user_a.user_id
    finally:
        reset_current_user(token)
