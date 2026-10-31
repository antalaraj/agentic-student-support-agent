"""Tests for Section C: Sensitive Action Human-in-the-Loop Approval Workflow."""
import pytest

from approval.service import (
    create_fee_extension_request,
    get_approval_request,
    list_pending_requests,
    list_student_requests,
    review_approval_request,
)
from audit.service import query_audit_logs
from authorization.exceptions import AccessDeniedError, AdminPrivilegeRequiredError
from database.db import connection


def test_sensitive_action_creates_pending_request(student_user_a):
    res = create_fee_extension_request(
        user=student_user_a,
        reason="Medical emergency in family causing cashflow delays",
        requested_due_date="2026-12-31",
    )
    assert res["status"] == "pending_approval"
    assert res["approval_status"] == "PENDING"
    assert "REQ-" in res["request_id"]
    assert "NOT yet been applied" in res["message"]


def test_pending_request_does_not_modify_fees(student_user_a):
    with connection() as conn:
        before = conn.execute("SELECT due_date FROM fees WHERE student_id = 'MIM25002'").fetchone()["due_date"]

    res = create_fee_extension_request(
        user=student_user_a,
        reason="Awaiting loan disbursement",
        requested_due_date="2027-01-15",
    )

    with connection() as conn:
        after = conn.execute("SELECT due_date FROM fees WHERE student_id = 'MIM25002'").fetchone()["due_date"]

    # Fee due date in database MUST NOT change when pending!
    assert before == after
    assert after != "2027-01-15"


def test_authorized_admin_can_approve(admin_user, student_user_a):
    req = create_fee_extension_request(
        user=student_user_a,
        reason="Valid scholarship credit delay",
        requested_due_date="2026-12-25",
    )
    req_id = req["request_id"]

    decision_res = review_approval_request(
        admin_user=admin_user,
        request_id=req_id,
        decision="APPROVED",
        decision_reason="Approved based on documentation submitted.",
    )
    assert decision_res["status"] == "success"
    assert decision_res["decision"] == "APPROVED"
    assert decision_res["executed"] is True

    # Confirm database fee record is now updated
    with connection() as conn:
        due_date = conn.execute("SELECT due_date FROM fees WHERE student_id = 'MIM25002'").fetchone()["due_date"]
    assert due_date == "2026-12-25"

    # Confirm request record updated
    info = get_approval_request(req_id, admin_user)
    assert info["status"] == "APPROVED"
    assert info["reviewed_by"] == admin_user.user_id


def test_approved_action_executes_exactly_once(admin_user, student_user_a):
    req = create_fee_extension_request(
        user=student_user_a,
        reason="Single execution test",
        requested_due_date="2026-12-20",
    )
    req_id = req["request_id"]

    # First approval succeeds
    review_approval_request(admin_user, req_id, "APPROVED")

    # Second approval attempt MUST fail (replays / duplicates rejected)
    with pytest.raises(ValueError, match="already been resolved"):
        review_approval_request(admin_user, req_id, "APPROVED")


def test_authorized_admin_can_reject(admin_user, student_user_a):
    req = create_fee_extension_request(
        user=student_user_a,
        reason="Unsubstantiated request",
        requested_due_date="2027-03-31",
    )
    req_id = req["request_id"]

    with connection() as conn:
        original_due = conn.execute("SELECT due_date FROM fees WHERE student_id = 'MIM25002'").fetchone()["due_date"]

    res = review_approval_request(
        admin_user=admin_user,
        request_id=req_id,
        decision="REJECTED",
        decision_reason="Extension exceeds permissible institutional semester window.",
    )
    assert res["status"] == "rejected"
    assert res["executed"] is False

    # Fee table must NOT be modified
    with connection() as conn:
        current_due = conn.execute("SELECT due_date FROM fees WHERE student_id = 'MIM25002'").fetchone()["due_date"]
    assert current_due == original_due


def test_student_cannot_approve_own_request(student_user_a):
    req = create_fee_extension_request(
        user=student_user_a,
        reason="Attempting self approval",
        requested_due_date="2026-12-30",
    )
    # Student attempting to act as administrator must be blocked
    with pytest.raises(AdminPrivilegeRequiredError):
        review_approval_request(
            admin_user=student_user_a,  # Non-admin passed
            request_id=req["request_id"],
            decision="APPROVED",
        )


def test_student_cannot_approve_other_student_request(student_user_a, student_user_b):
    req = create_fee_extension_request(
        user=student_user_b,
        reason="Aarav request",
        requested_due_date="2026-12-30",
    )
    with pytest.raises(AdminPrivilegeRequiredError):
        review_approval_request(
            admin_user=student_user_a,
            request_id=req["request_id"],
            decision="APPROVED",
        )


def test_tampered_or_invalid_request_rejected(admin_user):
    with pytest.raises(ValueError, match="not found"):
        review_approval_request(
            admin_user=admin_user,
            request_id="REQ-NONEXISTENT-999",
            decision="APPROVED",
        )
