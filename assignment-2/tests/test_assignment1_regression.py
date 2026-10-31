"""Regression tests: Confirming 100% backward compatibility with all Assignment 1 capabilities."""
from agent.graph import run_agent
from auth.context import reset_current_user, set_current_user
from rag.retrieval import retrieve
from tools.fee_tools import check_fee_status
from tools.policy_tools import search_academic_information, search_policy
from tools.scholarship_tools import check_scholarship_status
from tools.student_tools import get_student_profile
from tools.support_tools import create_support_ticket


def test_regression_all_six_tools_operational(student_user_a):
    token = set_current_user(student_user_a)
    try:
        sid = student_user_a.student_id

        # 1. Profile
        prof = get_student_profile(sid)
        assert prof["status"] == "ok"
        assert prof["student_id"] == sid

        # 2. Fees
        fee = check_fee_status(sid)
        assert fee["status"] == "ok"
        assert fee["total_fee"] > 0

        # 3. Scholarship
        sch = check_scholarship_status(sid)
        assert sch["status"] == "ok"

        # 4. Support ticket
        tkt = create_support_ticket("Exam conflict issue", "examination", sid)
        assert tkt["status"] == "ok"
        assert tkt["ticket_id"].startswith("TKT-")

        # 5. Policy RAG
        pol = search_policy("late fee policy")
        assert pol["status"] == "ok"
        assert len(pol["results"]) > 0

        # 6. Academic RAG
        acad = search_academic_information("Which electives are offered in AI & Data Science?")
        assert acad["status"] == "ok"
    finally:
        reset_current_user(token)


def test_regression_rag_retrieval_finds_handbook_sections():
    res = search_policy("What is the late fee policy?")
    assert res["status"] == "ok"
    sections = [r["section"] for r in res["results"]]
    assert any("Late Fee" in s for s in sections)


def test_regression_rag_returns_no_evidence_for_out_of_scope_query():
    res = search_policy("hostel accommodation rules and curfew timings")
    assert res["status"] == "no_evidence"
    assert "recommendation" in res


def test_regression_agent_execution_trace_logged(student_user_a):
    out = run_agent(
        query="What programme am I studying?",
        user=student_user_a,
    )
    trace = out["trace"]
    assert trace["execution_id"].startswith("exec")
    assert trace["requester_id"] == student_user_a.user_id
    assert trace["requester_role"] == "student"
    assert "get_student_profile" in out["tools_used"]
