import json
import sqlite3
from unittest.mock import patch

from config import settings
from database.db import connection
from database.seed import reset_database, seed_students
from tools import get_tool_map
from tools.fee_tools import check_fee_status
from tools.policy_tools import search_academic_information, search_policy
from tools.scholarship_tools import check_scholarship_status
from tools.student_tools import get_student_profile
from tools.support_tools import create_support_ticket


def test_seed_has_at_least_10_varied_students():
    with connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] >= 10
        assert conn.execute("SELECT COUNT(DISTINCT programme) FROM students").fetchone()[0] >= 4
        assert conn.execute("SELECT COUNT(DISTINCT payment_status) FROM fees").fetchone()[0] >= 3
        assert conn.execute("SELECT COUNT(DISTINCT application_status) FROM scholarships").fetchone()[0] >= 4
        bad = conn.execute("SELECT COUNT(*) FROM fees WHERE total_fee - paid_amount != outstanding_amount").fetchone()[0]
        assert bad == 0


def test_seed_is_idempotent_and_does_not_overwrite_edits():
    with connection() as conn:
        conn.execute("UPDATE fees SET paid_amount=1, outstanding_amount=449999 WHERE student_id='MIM25001'")
    assert seed_students() == 0
    with connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 12
        assert conn.execute("SELECT paid_amount FROM fees WHERE student_id='MIM25001'").fetchone()[0] == 1


def test_reset_restores_seed_data():
    with connection() as conn:
        conn.execute("UPDATE fees SET paid_amount=1 WHERE student_id='MIM25001'")
    assert reset_database() == 12
    assert check_fee_status("MIM25001")["paid_amount"] == 450000


def test_profile_fee_scholarship_return_real_db_values():
    p = get_student_profile("mim25002")  # case-insensitive
    assert p["status"] == "ok" and p["name"] == "Diya Nair" and p["semester"] == 3
    f = check_fee_status("MIM25002")
    assert (f["total_fee"], f["paid_amount"], f["outstanding_amount"], f["payment_status"]) == (450000, 300000, 150000, "Partially Paid")
    s = check_scholarship_status("MIM25007")
    assert s["application_status"] == "Rejected" and "3.5" in s["remarks"]


def test_unknown_and_invalid_student_ids():
    assert check_fee_status("ZZZ99999")["status"] == "not_found"
    assert get_student_profile("")["status"] == "error"
    assert check_scholarship_status("bad id; DROP TABLE")["error_type"] == "invalid_input"
    assert check_fee_status(None)["error_type"] == "invalid_input"


def test_sql_injection_attempt_is_harmless():
    get_student_profile("MIM25001' OR '1'='1")
    with connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 12


def test_ticket_creation_unique_ids_and_stored():
    a = create_support_ticket("MIM25003", "Payment portal failed twice", "payment")
    b = create_support_ticket("MIM25003", "Payment portal failed twice", "fee_payment")
    assert a["status"] == "ok" and a["ticket_id"].startswith("TKT-") and a["ticket_id"] != b["ticket_id"]
    assert a["category"] == "fee_payment"  # alias normalised
    with connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM support_tickets WHERE student_id='MIM25003'").fetchone()[0] == 2


def test_ticket_validation_and_sensitive_redaction():
    assert create_support_ticket("MIM25003", "x", "general")["error_type"] == "invalid_input"
    assert create_support_ticket("MIM25003", "Portal problem here", "nonsense")["error_type"] == "invalid_input"
    assert create_support_ticket("NOPE0000", "Portal problem here", "general")["status"] == "not_found"
    t = create_support_ticket("MIM25003", "Portal failed, my OTP is 482913", "technical")
    with connection() as conn:
        stored = conn.execute("SELECT issue FROM support_tickets WHERE ticket_id=?", (t["ticket_id"],)).fetchone()[0]
    assert "482913" not in stored


def test_policy_and_academic_search_tools():
    r = search_policy("What is the late fee policy?")
    assert r["status"] == "ok" and r["results"][0]["chunk_id"].startswith("hb-2")
    a = search_academic_information("Which electives are offered in AI?")
    assert a["status"] == "ok" and all(x["chunk_id"].startswith("hb-9") for x in a["results"])
    assert search_policy("hostel accommodation rules")["status"] == "no_evidence"
    assert search_policy("   ")["error_type"] == "invalid_input"


def test_tool_database_failure_returns_structured_error():
    with patch("tools.fee_tools.connection", side_effect=sqlite3.OperationalError("down")):
        r = check_fee_status("MIM25001")
    assert r["status"] == "error" and r["error_type"] == "database_error"


def test_registry_exposes_six_tools_with_schemas():
    tools = get_tool_map()
    assert set(tools) == {"get_student_profile", "check_fee_status", "check_scholarship_status",
                          "create_support_ticket", "search_academic_information", "search_policy"}
    assert "student_id" in tools["check_fee_status"].args
    assert json.loads(json.dumps(tools["check_fee_status"].invoke({"student_id": "MIM25001"})))["status"] == "ok"
