"""Comprehensive Test Suite: 20 Official Assignment Scenarios.

Maps 1-to-1 with Phase 4 requirements:
A. Agent behaviour (1-6)
B. Tool execution (7-11)
C. Memory (12-15)
D. RAG (16-18)
E. Error handling and tracing (19-20)
"""
import pytest
from unittest.mock import patch
import sqlite3

from agent.graph import run_agent
from database import memory
from database.db import connection
from rag.retrieval import retrieve
from tools.fee_tools import check_fee_status
from tools.student_tools import get_student_profile
from tools.scholarship_tools import check_scholarship_status
from tools.support_tools import create_support_ticket
from tracing.tracer import load_traces


# ==============================================================================
# A. Agent Behaviour (1-6)
# ==============================================================================

def test_req_01_general_greeting():
    """1. General greeting: Answers politely without executing unnecessary tools."""
    r = run_agent("Hello! Good morning.", "MIM25001", "session_greet", [])
    assert r["status"] == "success"
    assert r["tools_used"] == []
    assert any(w in r["response"].lower() for w in ["hello", "how can i help", "welcome"])


def test_req_02_fee_status_query():
    """2. Fee status query: Invokes check_fee_status and reflects DB values."""
    r = run_agent("What is my current fee status?", "MIM25002", "session_fee", [])
    assert "check_fee_status" in r["tools_used"]
    assert "150,000" in r["response"] or "partially paid" in r["response"].lower()


def test_req_03_scholarship_status_query():
    """3. Scholarship status query: Invokes check_scholarship_status tool."""
    r = run_agent("What is my scholarship status?", "MIM25007", "session_sch", [])
    assert "check_scholarship_status" in r["tools_used"]
    assert "Merit" in r["response"] or "Rejected" in r["response"] or "status" in r["response"].lower()


def test_req_04_student_profile_query():
    """4. Student profile query: Invokes get_student_profile and reports programme/semester."""
    r = run_agent("What programme am I studying?", "MIM25005", "session_prof", [])
    assert "get_student_profile" in r["tools_used"]
    assert "Digital Transformation" in r["response"] or "PGDM" in r["response"]


def test_req_05_support_ticket_creation():
    """5. Support ticket creation: Invokes create_support_ticket and generates TKT ID."""
    r = run_agent("Please raise a support ticket for my portal login error", "MIM25001", "session_tkt", [])
    assert "create_support_ticket" in r["tools_used"]
    assert "TKT-" in r["response"]
    # Verify in DB
    with connection() as conn:
        row = conn.execute("SELECT * FROM support_tickets WHERE student_id=?", ("MIM25001",)).fetchone()
    assert row is not None
    assert row["ticket_id"] in r["response"]


def test_req_06_academic_policy_query():
    """6. Academic policy query: Searches policy and retrieves handbook evidence."""
    r = run_agent("What is the late fee policy?", "MIM25001", "session_pol", [])
    assert "search_policy" in r["tools_used"]
    assert any(c["chunk_id"].startswith("hb-2") for c in r["sources"])
    assert "200" in r["response"] or "late fee" in r["response"].lower()


# ==============================================================================
# B. Tool Execution (7-11)
# ==============================================================================

def test_req_07_correct_tool_selection():
    """7. Correct tool selection: Distinguishes between fees, scholarships, and handbook."""
    r_fee = run_agent("How much outstanding fees do I have?", "MIM25003", "s", [])
    assert r_fee["tools_used"] == ["check_fee_status"]

    r_pol = run_agent("Can I change my programme?", "MIM25006", "s", [])
    assert r_pol["tools_used"] == ["search_policy"]


def test_req_08_correct_tool_arguments():
    """8. Correct tool arguments: Enforces session student identity over spoofed arguments."""
    r = run_agent("Check fee status", "MIM25001", "s", [])
    tool_event = r["trace"]["tool_calls"][0]
    assert tool_event["args"]["student_id"] == "MIM25001"


def test_req_09_tool_output_used_in_response():
    """9. Tool output used in response: DB amounts are genuinely integrated into final answer."""
    r = run_agent("What is my fee status?", "MIM25003", "s", [])
    # MIM25003 outstanding is 320,000 and status is Overdue
    assert "320,000" in r["response"]
    assert "overdue" in r["response"].lower()


def test_req_10_invalid_student_id():
    """10. Invalid student ID: Rejected cleanly with structured error."""
    res = check_fee_status("!!INVALID_ID!!")
    assert res["status"] == "error"
    assert res["error_type"] == "invalid_input"


def test_req_11_missing_database_record():
    """11. Missing database record: Non-existent student returns not_found status."""
    res = get_student_profile("MIM99999")
    assert res["status"] == "not_found"
    assert "No student found" in res["message"]


# ==============================================================================
# C. Memory (12-15)
# ==============================================================================

def test_req_12_save_useful_memory():
    """12. Save useful memory: Extracts preferred name and stated preferences."""
    saved = memory.update_memory_from_message("MIM25001", "Please call me Siddharth and I prefer deep learning electives.")
    assert len(saved) >= 1
    mems = memory.list_memories("MIM25001")
    contents = " ".join(m["content"] for m in mems)
    assert "Siddharth" in contents
    assert "deep learning" in contents.lower()


def test_req_13_retrieve_memory_in_new_conversation():
    """13. Retrieve memory across sessions: Stored memories are injected in subsequent turns."""
    # Seed memory in session 1
    memory.update_memory_from_message("MIM25004", "I prefer natural language processing electives.")
    # Query in session 2
    r = run_agent("What electives did I tell you I prefer?", "MIM25004", "session_2", [])
    assert len(r["memories_used"]) >= 1
    assert any("natural language processing" in m["content"].lower() for m in r["memories_used"])


def test_req_14_avoid_duplicate_memory():
    """14. Avoid duplicate memory: Near-duplicate statements are de-duplicated via Jaccard similarity."""
    memory.clear_memories("MIM25001")
    s1 = memory.update_memory_from_message("MIM25001", "I prefer cloud architecture electives.")
    assert len(s1) == 1
    # Duplicate statement
    s2 = memory.update_memory_from_message("MIM25001", "I really prefer cloud architecture electives.")
    assert len(s2) == 0  # Skipped as duplicate
    mems = memory.list_memories("MIM25001")
    assert len(mems) == 1


def test_req_15_prevent_sensitive_info_storage():
    """15. Prevent sensitive information storage: Passwords, OTPs, card numbers are filtered out."""
    memory.clear_memories("MIM25001")
    memory.update_memory_from_message("MIM25001", "My password is Pass@1234 and OTP is 928374.")
    mems = memory.list_memories("MIM25001")
    assert len(mems) == 0
    # Even in mixed sentences, sensitive part is dropped
    memory.update_memory_from_message("MIM25001", "Call me Vikram. My pin is 123456.")
    mems = memory.list_memories("MIM25001")
    assert not any("123456" in m["content"] for m in mems)


# ==============================================================================
# D. RAG (16-18)
# ==============================================================================

def test_req_16_retrieve_correct_policy_chunk():
    """16. Retrieve correct policy chunk: ChromaDB retrieval returns relevant section."""
    hits = retrieve("What is the attendance condonation criteria?", k=3)
    assert len(hits) > 0
    sections = [h["section"] for h in hits]
    assert any("Attendance" in s for s in sections)


def test_req_17_answer_policy_question():
    """17. Answer policy question: Agent grounds its answer on retrieved handbook clauses."""
    r = run_agent("The payment portal failed. Can I pay on the next working day?", "MIM25001", "s", [])
    assert "search_policy" in r["tools_used"]
    assert any("hb-1" in c["chunk_id"] for c in r["sources"])
    assert "next working day" in r["response"].lower() or "transaction" in r["response"].lower()


def test_req_18_handle_unavailable_policy_info():
    """18. Handle unavailable policy info: Honest fallback to Student Services when handbook has no evidence."""
    r = run_agent("What are the hostel room allocation rules for married students?", "MIM25001", "s", [])
    assert r["sources"] == []
    assert any(term in r["response"].lower() for term in ["couldn't find", "not contain", "student services"])
    assert "hostel" not in r["response"].lower() or "not" in r["response"].lower()


# ==============================================================================
# E. Error Handling and Tracing (19-20)
# ==============================================================================

def test_req_19_simulate_tool_failure():
    """19. Simulate tool failure: Database failure handled gracefully without crashing agent."""
    with patch("tools.fee_tools.connection", side_effect=sqlite3.OperationalError("disk I/O error")):
        r = run_agent("What is my current fee status?", "MIM25001", "s", [])
    assert r["trace"]["tool_calls"][0]["status"] == "error"
    assert "database is temporarily unavailable" in r["response"].lower() or "couldn't" in r["response"].lower() or "sorry" in r["response"].lower()


def test_req_20_verify_trace_and_eval_records():
    """20. Verify trace and execution records: Trace persists execution ID, latency, route, and token usage."""
    r = run_agent("What is my scholarship status?", "MIM25001", "trace_test_sess", [])
    exec_id = r["trace"]["execution_id"]
    assert exec_id.startswith("exec-")
    assert r["trace"]["duration_ms"] > 0
    assert "context_selection" in r["trace"]["route_path"]
    assert "agent" in r["trace"]["route_path"]
    assert "tools" in r["trace"]["route_path"]
    assert "finalize" in r["trace"]["route_path"]

    # Verify trace persisted in SQLite database
    traces = load_traces(limit=5, student_id="MIM25001")
    assert any(t["execution_id"] == exec_id for t in traces)


# ==============================================================================
# F. Memory & Live LLM Specific Regression Suite
# ==============================================================================

def test_regression_saving_and_retrieving_preferred_name():
    """Verify saving a preferred name and retrieving it directly with 'What is my name?' without tools/RAG."""
    memory.clear_memories("MIM25001")
    memory.update_memory_from_message("MIM25001", "Please call me Aarav.")
    r = run_agent("What is my name?", "MIM25001", "sess_name", [])
    assert r["tools_used"] == []
    assert r["sources"] == []
    assert "Aarav" in r["response"]


def test_regression_retrieving_preferences_in_new_session():
    """Verify saving preferences in session 1 and retrieving them in session 2 without tools/RAG."""
    memory.clear_memories("MIM25002")
    # Session 1: save preference
    memory.update_memory_from_message("MIM25002", "I prefer machine learning electives.")
    # Session 2: retrieve preference
    r = run_agent("What are my preferences?", "MIM25002", "sess_pref_2", [])
    assert r["tools_used"] == []
    assert r["sources"] == []
    assert "machine learning" in r["response"].lower()


def test_regression_memory_questions_do_not_trigger_rag():
    """Verify that asking what was previously told uses memory and NEVER triggers search_policy RAG."""
    memory.clear_memories("MIM25001")
    memory.update_memory_from_message("MIM25001", "Please call me Aarav and I prefer machine learning electives.")
    for q in ["What is my name?", "What are my preferences?", "What did I tell you previously?"]:
        r = run_agent(q, "MIM25001", f"sess_rag_check_{q[:5]}", [])
        assert r["tools_used"] == []
        assert r["sources"] == []
        assert "handbook" not in r["response"].lower()


def test_regression_live_groq_model_initialization():
    """Verify Groq LLM initialization and model resolution."""
    from agent.llm import get_llm, model_label
    llm = get_llm()
    if llm is not None:
        label = model_label(llm)
        assert label in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "llama-3.3-70b-versatile"]


def test_regression_correct_offline_fallback_when_api_unavailable():
    """Verify that when no LLM is provided, the agent falls back cleanly to the OfflinePlanner."""
    r = run_agent("What is the late fee policy?", "MIM25001", "sess_offline", [], llm=None)
    assert r["status"] == "success"
    assert "search_policy" in r["tools_used"]
    assert "200" in r["response"] or "late fee" in r["response"].lower()


def test_regression_accurate_model_and_token_reporting():
    """Verify that execution traces accurately report model label and token availability."""
    r = run_agent("Hello", "MIM25001", "sess_trace_meta", [], llm=None)
    tok = r["trace"]["token_usage"]
    assert tok["available"] is False
    assert tok["input_tokens"] == "unavailable"
    assert tok["output_tokens"] == "unavailable"
    assert r["trace"]["llm_model"] == "offline-planner (no LLM)"
