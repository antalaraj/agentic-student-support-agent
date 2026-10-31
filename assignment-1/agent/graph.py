"""Builds the LangGraph StateGraph and exposes run_agent()."""
import functools
import logging
import time
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from agent import nodes
from agent.llm import model_label
from agent.offline_llm import OfflinePlanner
from agent.routing import route_after_agent, route_after_validate
from agent.state import AgentState
from config import settings
from tools import get_tool_map, get_tools
from tracing.tracer import new_execution_id, redact_text, save_trace

logger = logging.getLogger(__name__)


def build_graph(llm=None):
    """START -> validate_input -> context_selection -> agent <-> tools -> finalize -> END"""
    tools = get_tools()
    tool_map = {t.name: t for t in tools}
    g = StateGraph(AgentState)
    g.add_node("validate_input", nodes.validate_input)
    g.add_node("context_selection", nodes.context_selection)
    g.add_node("agent", functools.partial(nodes.agent_node, llm=llm, planner=OfflinePlanner(), tools=tools))
    g.add_node("tools", functools.partial(nodes.tools_node, tool_map=tool_map))
    g.add_node("finalize", nodes.finalize)

    g.add_edge(START, "validate_input")
    g.add_conditional_edges("validate_input", route_after_validate, {"context": "context_selection", "end": END})
    g.add_edge("context_selection", "agent")
    g.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()


_GRAPH_CACHE: dict[int, object] = {}


def _graph_for(llm):
    key = id(llm)
    if key not in _GRAPH_CACHE:
        _GRAPH_CACHE[key] = build_graph(llm)
    return _GRAPH_CACHE[key]


def run_agent(query: str, student_id: str | None, session_id: str = "default", history: list[dict] | None = None,
              llm=None, persist_trace: bool = True) -> dict:
    """Run one agent turn and return the response plus a full structured trace."""
    execution_id, started = new_execution_id(), time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state_in = {"user_query": query or "", "student_id": student_id, "session_id": session_id, "history": history or []}
    try:
        out = _graph_for(llm).invoke(state_in, config={"recursion_limit": 25})
    except Exception as exc:  # last resort: the graph itself failed
        logger.exception("Agent graph failed")
        out = {"final_response": f"Sorry, something went wrong on our side. Please try again or contact the {settings.CONTACT_OFFICE}.",
               "final_status": "error", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    duration_ms = round((time.perf_counter() - started) * 1000, 2)

    usage = out.get("usage") or {}
    token_usage = {"available": bool(usage.get("available")),
                   "input_tokens": usage.get("input_tokens") if usage.get("available") else "unavailable",
                   "output_tokens": usage.get("output_tokens") if usage.get("available") else "unavailable"}
    mode_label = OfflinePlanner.model_name if (llm is None or out.get("use_fallback")) else model_label(llm)
    trace = {
        "execution_id": execution_id, "timestamp": timestamp, "session_id": session_id, "student_id": student_id,
        "user_query": redact_text(query or ""), "intent": out.get("intent"), "route_path": out.get("route_path", []),
        "context_sources": out.get("context_sources", []),
        "tool_calls": out.get("tool_events", []), "retrieved_chunks": out.get("retrieved_chunks", []),
        "memory_refs": [{"id": m["id"], "content": m["content"]} for m in out.get("memories", [])],
        "memory_writes": out.get("memory_writes", []), "duration_ms": duration_ms, "llm_model": mode_label,
        "llm_calls": usage.get("llm_calls", 0), "token_usage": token_usage,
        "final_status": out.get("final_status", "error"), "error": out.get("error"),
        "response_preview": redact_text(out.get("final_response", ""))[:500],
    }
    if persist_trace:
        try:
            save_trace(trace)
        except Exception as exc:
            logger.warning("Could not save trace: %s", exc)
    return {"response": out.get("final_response", ""), "trace": trace, "status": trace["final_status"],
            "tools_used": [c["tool"] for c in trace["tool_calls"]], "sources": trace["retrieved_chunks"],
            "memories_used": trace["memory_refs"]}
