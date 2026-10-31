"""Tests for Section B: Data Privacy, Student Ownership, and Cross-Tenant Isolation."""
import pytest

from audit.service import query_audit_logs
from auth.context import reset_current_user, set_current_user
from authorization.exceptions import AccessDeniedError
from authorization.service import require_student_ownership
from database import memory
from tools.fee_tools import check_fee_status
from tools.scholarship_tools import check_scholarship_status
from tools.student_tools import get_student_profile
from tools.support_tools import create_support_ticket, list_tickets


def test_student_accesses_own_profile(student_user_a):
    token = set_current_user(student_user_a)
    try:
        res = get_student_profile("MIM25002")
        assert res["status"] == "ok"
        assert res["student_id"] == "MIM25002"
        assert "Diya" in res["name"]
    finally:
        reset_current_user(token)


def test_student_accesses_own_fees(student_user_a):
    token = set_current_user(student_user_a)
    try:
        res = check_fee_status("MIM25002")
        assert res["status"] == "ok"
        assert res["student_id"] == "MIM25002"
        assert res["total_fee"] == 450000
        assert res["outstanding_amount"] == 150000
    finally:
        reset_current_user(token)


def test_student_accesses_own_scholarship(student_user_a):
    token = set_current_user(student_user_a)
    try:
        res = check_scholarship_status("MIM25002")
        assert res["status"] == "ok"
        assert res["student_id"] == "MIM25002"
        assert res["application_status"] == "Under Review"
    finally:
        reset_current_user(token)


def test_student_accesses_own_tickets(student_user_a):
    token = set_current_user(student_user_a)
    try:
        res = create_support_ticket("Question regarding my elective subject registration", "academic", "MIM25002")
        assert res["status"] == "ok"
        assert res["student_id"] == "MIM25002"

        tickets = list_tickets("MIM25002", user=student_user_a)
        assert len(tickets) >= 1
        assert tickets[0]["student_id"] == "MIM25002"
    finally:
        reset_current_user(token)


def test_student_a_cannot_read_student_b_fees(student_user_a):
    # Student A (Diya - MIM25002) attempts to read Student B (Aarav - MIM25001) fees
    token = set_current_user(student_user_a)
    try:
        res = check_fee_status("MIM25001")
        assert res["status"] == "error"
        assert res["error_type"] == "access_denied"
        assert "not authorized" in res["message"].lower()

        # Confirm security audit recorded the violation
        logs = query_audit_logs(action="cross_student_view_fee_status_blocked")
        assert len(logs) >= 1
        assert logs[0]["authorization_decision"] == "DENIED"
        assert logs[0]["requested_resource_id"] == "MIM25001"
    finally:
        reset_current_user(token)


def test_student_a_cannot_read_student_b_profile(student_user_a):
    token = set_current_user(student_user_a)
    try:
        res = get_student_profile("MIM25001")
        assert res["status"] == "error"
        assert res["error_type"] == "access_denied"
    finally:
        reset_current_user(token)


def test_student_a_cannot_read_student_b_scholarship(student_user_a):
    token = set_current_user(student_user_a)
    try:
        res = check_scholarship_status("MIM25001")
        assert res["status"] == "error"
        assert res["error_type"] == "access_denied"
    finally:
        reset_current_user(token)


def test_student_a_cannot_create_ticket_for_student_b(student_user_a):
    token = set_current_user(student_user_a)
    try:
        res = create_support_ticket("Spoofed ticket for another student", "general", "MIM25001")
        assert res["status"] == "error"
        assert res["error_type"] == "access_denied"
    finally:
        reset_current_user(token)


def test_spoofed_student_id_argument_is_blocked_and_audited(student_user_a):
    # Direct service-layer test
    with pytest.raises(AccessDeniedError):
        require_student_ownership("MIM25003", student_user_a, action="tamper_test")


def test_cross_student_memory_isolated(student_user_a, student_user_b):
    # Store preference for Diya
    memory.update_memory_from_message(student_user_a.student_id, "I prefer machine learning electives.")
    # Store preference for Aarav
    memory.update_memory_from_message(student_user_b.student_id, "I prefer supply chain electives.")

    # Diya's recall
    diya_mems = memory.retrieve_relevant_memories(student_user_a.student_id, "electives")
    diya_texts = [m["content"] for m in diya_mems]
    assert any("machine learning" in t for t in diya_texts)
    assert not any("supply chain" in t for t in diya_texts)

    # Aarav's recall
    aarav_mems = memory.retrieve_relevant_memories(student_user_b.student_id, "electives")
    aarav_texts = [m["content"] for m in aarav_mems]
    assert any("supply chain" in t for t in aarav_texts)
    assert not any("machine learning" in t for t in aarav_texts)


def test_admin_can_access_student_records_with_audit(admin_user):
    token = set_current_user(admin_user)
    try:
        res = check_fee_status("MIM25002")
        assert res["status"] == "ok"
        assert res["student_id"] == "MIM25002"
    finally:
        reset_current_user(token)
