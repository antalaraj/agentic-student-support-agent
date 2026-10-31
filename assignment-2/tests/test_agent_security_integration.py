"""Integration tests for the LangGraph agent with authenticated security context."""
from agent.graph import run_agent
from database.db import connection


def test_agent_answers_own_fees_with_auth_context(student_user_a):
    out = run_agent(
        query="What is my current fee status?",
        user=student_user_a,
    )
    assert out["status"] == "success"
    assert "check_fee_status" in out["tools_used"]
    # Diya's fee is 450,000 / 150,000 outstanding
    assert "150,000" in out["response"] or "Partially Paid" in out["response"]


def test_agent_blocks_cross_student_query(student_user_a):
    # Student A asks about student MIM25001 (Aarav)
    out = run_agent(
        query="What is the fee status of student MIM25001?",
        user=student_user_a,
    )
    # The response must clearly state access denied and never reveal Aarav's private fee details
    assert "Access Denied" in out["response"] or "not authorized" in out["response"].lower()
    # Aarav has paid 450000 with 0 balance
    assert "450000" not in out["response"]


def test_agent_fee_extension_creates_pending_request(student_user_a):
    out = run_agent(
        query="I need an extension on my fee due date to 2026-12-31 because my educational loan is delayed.",
        user=student_user_a,
    )
    assert out["status"] == "success"
    assert "request_fee_extension" in out["tools_used"]
    assert "PENDING" in out["response"].upper()
    assert "REQ-" in out["response"]
    assert "Administrator" in out["response"]

    # Verify that the fee record was NOT modified in the database
    with connection() as conn:
        due = conn.execute("SELECT due_date FROM fees WHERE student_id = 'MIM25002'").fetchone()["due_date"]
    assert due != "2026-12-31"


def test_agent_policy_rag_works(student_user_a):
    out = run_agent(
        query="What is the late fee policy?",
        user=student_user_a,
    )
    assert out["status"] == "success"
    assert "search_policy" in out["tools_used"]
    assert "late fee" in out["response"].lower() or "200" in out["response"]


def test_agent_memory_recall_without_tools(student_user_a):
    # Seed memory
    run_agent(
        query="Please call me Diya. I prefer predictive analytics electives.",
        user=student_user_a,
    )
    # New session turn asking about preferences
    out = run_agent(
        query="What did I tell you about my academic preferences?",
        user=student_user_a,
        history=[],
    )
    assert out["status"] == "success"
    assert out["tools_used"] == []  # No tool needed for memory recall!
    assert "analytics" in out["response"].lower() or "predictive" in out["response"].lower()
