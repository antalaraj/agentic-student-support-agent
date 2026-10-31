import json

import pytest
from langchain_core.messages import AIMessage

from agent.graph import build_graph, run_agent
from agent.routing import classify_intent
from config import settings
from database import memory
from tests.conftest import ScriptedLLM
from tracing.tracer import load_traces


def call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "c1"}])


# ---------- graph structure ----------
def test_graph_is_a_real_stategraph_with_expected_nodes():
    g = build_graph().get_graph()
    assert {"validate_input", "context_selection", "agent", "tools", "finalize"} <= set(g.nodes)
    edges = {(e.source, e.target) for e in g.edges}
    assert ("tools", "agent") in edges and ("agent", "finalize") in edges and ("agent", "tools") in edges


# ---------- routing / tool selection (offline planner) ----------
@pytest.mark.parametrize("query,tools", [
    ("What is my current fee status?", ["check_fee_status"]),
    ("How much outstanding fee do I have?", ["check_fee_status"]),
    ("What is my scholarship application status?", ["check_scholarship_status"]),
    ("What programme am I studying?", ["get_student_profile"]),
    ("What is the late fee policy?", ["search_policy"]),
    ("Can I change my programme?", ["search_policy"]),
    ("What is the attendance requirement?", ["search_policy"]),
    ("The payment portal failed. Can I pay on the next working day?", ["search_policy"]),
    ("Create a support ticket for a payment issue", ["create_support_ticket"]),
    ("Which electives are offered in AI & Data Science?", ["search_academic_information"]),
    ("Hello", []),
    ("Thanks!", []),
    ("Please call me Aarav and I prefer machine learning electives.", []),
])
def test_tool_routing(query, tools):
    assert run_agent(query, "MIM25001", "s", [])["tools_used"] == tools


def test_direct_answers_do_not_call_tools():
    r = run_agent("Hello", "MIM25001", "s", [])
    assert r["tools_used"] == [] and r["status"] == "success"


def test_tool_result_is_used_in_final_answer():
    r = run_agent("What is my current fee status?", "MIM25003", "s", [])
    assert "320,000" in r["response"] and "Overdue" in r["response"]


def test_intent_hint():
    assert classify_intent("What is the late fee policy?") == "policy"
    assert classify_intent("What is my fee status?") == "fee"
    assert classify_intent("blah") == "general"


# ---------- missing info & errors ----------
def test_missing_student_asks_for_selection():
    r = run_agent("What is my current fee status?", None, "s", [])
    assert "select" in r["response"].lower() and "₹" not in r["response"]
    assert r["trace"]["tool_calls"][0]["status"] == "needs_input"


def test_unknown_student_id_never_invents_data():
    r = run_agent("What is my current fee status?", "ZZZ99999", "s", [])
    assert "couldn't find" in r["response"].lower() and "₹" not in r["response"]


def test_empty_query():
    r = run_agent("   ", "MIM25001", "s", [])
    assert r["status"] == "empty_query" and r["tools_used"] == []


def test_unknown_policy_is_declined_with_referral():
    r = run_agent("Does the handbook say anything about hostel accommodation rules?", "MIM25001", "s", [])
    assert "couldn't find" in r["response"].lower() and "Student Services" in r["response"] and r["sources"] == []


# ---------- real LLM path with a scripted model ----------
def test_llm_tool_call_then_answer_with_token_usage():
    final = AIMessage(content="Your outstanding fee is ₹150,000.", usage_metadata={"input_tokens": 50, "output_tokens": 9, "total_tokens": 59})
    first = AIMessage(content="", tool_calls=[{"name": "check_fee_status", "args": {"student_id": "MIM25002"}, "id": "c1"}],
                      usage_metadata={"input_tokens": 120, "output_tokens": 15, "total_tokens": 135})
    llm = ScriptedLLM(first, final)
    r = run_agent("What do I owe?", "MIM25002", "s", [], llm=llm)
    assert r["tools_used"] == ["check_fee_status"] and "150,000" in r["response"]
    assert r["trace"]["token_usage"] == {"available": True, "input_tokens": 170, "output_tokens": 24}
    assert r["trace"]["llm_model"] == "scripted-test-llm" and llm.calls == 2


def test_token_usage_marked_unavailable_when_api_gives_none():
    r = run_agent("Hello", "MIM25001", "s", [], llm=ScriptedLLM(AIMessage(content="Hi there!")))
    assert r["trace"]["token_usage"] == {"available": False, "input_tokens": "unavailable", "output_tokens": "unavailable"}


def test_student_id_from_model_is_replaced_by_session_identity():
    llm = ScriptedLLM(call("check_fee_status", student_id="MIM25007"), AIMessage(content="ok"))
    r = run_agent("fee?", "MIM25001", "s", [], llm=llm)
    ev = r["trace"]["tool_calls"][0]
    assert ev["args"]["student_id"] == "MIM25001" and "replaced" in ev["note"]


def test_invalid_tool_arguments_and_unknown_tool_are_handled():
    llm = ScriptedLLM(call("create_support_ticket", student_id="x"), call("delete_everything"), AIMessage(content="Sorry, I could not do that."))
    r = run_agent("make ticket", "MIM25001", "s", [], llm=llm)
    statuses = [(c["tool"], c["status"]) for c in r["trace"]["tool_calls"]]
    assert statuses == [("create_support_ticket", "error"), ("delete_everything", "error")] and r["status"] == "success"


def test_rate_limit_falls_back_to_offline_mode():
    class RateLimitError(Exception):
        pass

    llm = ScriptedLLM(RateLimitError("429 Too Many Requests"))
    r = run_agent("What is my current fee status?", "MIM25002", "s", [], llm=llm)
    assert r["status"] == "degraded_fallback" and "temporarily unavailable" in r["response"] and "150,000" in r["response"]
    assert "rate_limit" in r["trace"]["error"]


@pytest.mark.parametrize("bad", [AIMessage(content=""), "not a message", ValueError("tool_use_failed")])
def test_malformed_or_failed_llm_response_falls_back(bad):
    r = run_agent("What is my scholarship application status?", "MIM25007", "s", [], llm=ScriptedLLM(bad))
    assert r["status"] == "degraded_fallback" and "Rejected" in r["response"]


def test_step_limit_prevents_infinite_tool_loops():
    llm = ScriptedLLM(*[call("search_policy", query="late fee") for _ in range(10)])
    r = run_agent("loop", "MIM25001", "s", [], llm=llm)
    assert r["status"] == "error" and len(r["trace"]["tool_calls"]) <= settings.MAX_AGENT_STEPS


# ---------- context selection ----------
def test_context_selection_limits_history_and_memories():
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i} " + "x" * 2000} for i in range(20)]
    memory.update_memory_from_message("MIM25001", "Call me Aarav. I prefer finance electives. Remember that I commute by train.")
    seen = {}

    class Spy(ScriptedLLM):
        def invoke(self, messages):
            seen["messages"] = messages
            return AIMessage(content="ok")

    run_agent("What are my academic preferences?", "MIM25001", "s", history, llm=Spy())
    msgs = seen["messages"]
    assert len(msgs) == 1 + settings.MAX_HISTORY_MESSAGES + 1          # system + recent history + current question
    assert all(len(m.content) <= settings.MAX_HISTORY_CHARS or m is msgs[0] for m in msgs)
    assert "finance electives" in msgs[0].content and "commute by train" not in msgs[0].content
    assert "Late Fee Policy" not in msgs[0].content and "MIM25002" not in msgs[0].content   # no policy / other students preloaded


# ---------- tracing ----------
def test_trace_contains_required_fields_and_is_stored():
    r = run_agent("The payment portal failed. Can I pay on the next working day?", "MIM25002", "sess-1", [])
    t = r["trace"]
    for key in ("execution_id", "timestamp", "user_query", "intent", "context_sources", "tool_calls", "retrieved_chunks", "memory_refs",
                "duration_ms", "llm_model", "token_usage", "final_status", "error", "route_path"):
        assert key in t
    assert t["tool_calls"][0]["tool"] == "search_policy" and t["tool_calls"][0]["status"] == "ok"
    assert t["retrieved_chunks"] and t["route_path"] == ["validate_input", "context_selection", "agent", "tools", "agent", "finalize"]
    stored = load_traces(5)
    assert stored[0]["execution_id"] == t["execution_id"]


def test_traces_never_contain_secrets():
    run_agent("My OTP is 482913 and password is hunter2. Create a support ticket for login problem", "MIM25001", "s", [])
    blob = json.dumps(load_traces(5))
    assert "482913" not in blob and "hunter2" not in blob
