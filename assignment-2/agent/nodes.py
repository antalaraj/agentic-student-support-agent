"""LangGraph workflow nodes for Assignment 2.
Implements validated state transitions, authenticated context selection,
rate-limit resilient LLM calls, secure tool execution, and privacy memory updates.
"""
import json
import logging
import time
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage

from agent.prompts import build_system_prompt
from agent.routing import classify_intent
from auth.context import reset_current_user, set_current_user
from config import settings
from database import memory
from tracing.tracer import redact_args

logger = logging.getLogger(__name__)
FALLBACK_NOTICE = "⚠️ The AI model is temporarily unavailable, so I answered in basic mode.\n\n"


def _path(state: dict, name: str) -> list[str]:
    return list(state.get("route_path", [])) + [name]


# 1 ─────────────────────────────────────────────────────────────── validate input
def validate_input(state: dict) -> dict:
    query = (state.get("user_query") or "").strip()
    if not query:
        return {
            "route_path": _path(state, "validate_input"),
            "final_status": "empty_query",
            "final_response": "Please type a question — for example, “What is my current fee status?”",
        }
    return {
        "user_query": query[: settings.MAX_QUERY_CHARS],
        "route_path": _path(state, "validate_input"),
    }


# 2 ─────────────────────────────────────────────────────────────── context selection
def context_selection(state: dict) -> dict:
    """Select context with strict token budgeting and student data isolation."""
    query = state["user_query"]
    user = state.get("user")
    sid = user.student_id if user else state.get("student_id")
    intent = classify_intent(query)
    sources = ["current_message"]

    history: list[AnyMessage] = []
    for turn in (state.get("history") or [])[-settings.MAX_HISTORY_MESSAGES:]:
        text = str(turn.get("content", ""))[: settings.MAX_HISTORY_CHARS]
        if text:
            history.append(HumanMessage(content=text) if turn.get("role") == "user" else AIMessage(content=text))
    if history:
        sources.append(f"recent_history({len(history)} msgs)")

    memories: list[dict] = []
    if sid:
        try:
            limit = settings.MAX_MEMORIES + 2 if intent == "memory_recall" else settings.MAX_MEMORIES
            memories = memory.retrieve_relevant_memories(sid, query, limit)
        except Exception as exc:
            logger.warning("Memory retrieval failed: %s", exc)
    if memories:
        sources.append(f"memory({len(memories)} items)")

    return {
        "intent": intent,
        "student_id": sid,
        "memories": memories,
        "context_sources": sources,
        "steps": 0,
        "messages": history + [HumanMessage(content=query)],
        "route_path": _path(state, "context_selection"),
    }


# 3 ─────────────────────────────────────────────────────────────── agent reasoning
def _is_rate_limit(exc: Exception) -> bool:
    return "ratelimit" in type(exc).__name__.lower() or "429" in str(exc)


def _add_usage(usage: dict, resp) -> dict:
    usage = dict(usage or {"available": False, "input_tokens": 0, "output_tokens": 0, "llm_calls": 0})
    meta = getattr(resp, "usage_metadata", None)
    if meta:
        usage["available"] = True
        usage["input_tokens"] += int(meta.get("input_tokens", 0))
        usage["output_tokens"] += int(meta.get("output_tokens", 0))
        usage["llm_calls"] += 1
    return usage


def agent_node(state: dict, *, llm, planner, tools) -> dict:
    """Reason over the query: formulate a direct answer or request structured tool calls.
    Resilient retry with exponential backoff on Groq rate limits, falling back to OfflinePlanner.
    """
    user = state.get("user")
    full_name = user.full_name if user else None
    system = SystemMessage(
        content=build_system_prompt(state.get("student_id"), state.get("memories", []), state.get("intent", ""), full_name)
    )
    messages = [system] + list(state["messages"])
    errors = list(state.get("llm_errors", []))
    use_fallback = state.get("use_fallback", False) or llm is None
    usage = state.get("usage") or {"available": False, "input_tokens": 0, "output_tokens": 0, "llm_calls": 0}
    response = None

    if not use_fallback:
        for attempt in range(3):
            try:
                response = llm.bind_tools(tools).invoke(messages)
                if not isinstance(response, AIMessage) or (not response.content and not response.tool_calls):
                    raise ValueError("malformed or empty model response")
                usage = _add_usage(usage, response)
                break
            except Exception as exc:
                is_rl = _is_rate_limit(exc)
                is_mock = hasattr(llm, "script") or type(llm).__name__ == "ScriptedLLM"
                if is_rl and attempt < 2 and not is_mock:
                    time.sleep(2.5 * (attempt + 1))
                    continue
                kind = "rate_limit" if is_rl else type(exc).__name__
                logger.warning("LLM call failed (%s): %s", kind, str(exc)[:200])
                errors.append(f"{kind}: {str(exc)[:200]}")
                use_fallback, response = True, None
                break

    if use_fallback and response is None:
        response = planner.invoke(messages)

    return {
        "messages": [response],
        "steps": state.get("steps", 0) + 1,
        "use_fallback": use_fallback,
        "llm_errors": errors,
        "usage": usage,
        "route_path": _path(state, "agent"),
    }


# 4 ─────────────────────────────────────────────────────────────── tool execution
def tools_node(state: dict, *, tool_map: dict) -> dict:
    """Execute requested tool calls with verified authentication context.
    The tool execution layer sets the verified user in thread context,
    enforcing that tools resolve identity from trusted server-side state.
    """
    last = state["messages"][-1]
    user = state.get("user")
    events = list(state.get("tool_events", []))
    chunks = list(state.get("retrieved_chunks", []))
    out_msgs = []

    # Bind authenticated user to execution context
    token = set_current_user(user)

    try:
        for call in last.tool_calls:
            name, args = call.get("name"), call.get("args")
            started = time.perf_counter()
            tool = tool_map.get(name)

            if tool is None:
                result = {"status": "error", "error_type": "unknown_tool", "message": f"Tool '{name}' does not exist."}
            elif not isinstance(args, dict):
                result = {"status": "error", "error_type": "invalid_arguments", "message": "Tool arguments were malformed."}
            else:
                try:
                    result = tool.invoke(dict(args))
                except Exception as exc:
                    result = {"status": "error", "error_type": "invalid_arguments", "message": f"Invalid tool arguments ({type(exc).__name__})."}

            if isinstance(result, dict) and name in ("search_policy", "search_academic_information"):
                chunks += [
                    {"chunk_id": r["chunk_id"], "section": r["section"], "relevance": r["relevance"]}
                    for r in result.get("results", [])
                ]

            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            events.append({
                "tool": name,
                "args": redact_args(args if isinstance(args, dict) else {"raw": str(args)}),
                "status": result.get("status") if isinstance(result, dict) else "error",
                "duration_ms": duration_ms,
                "error_type": result.get("error_type") if isinstance(result, dict) else None,
            })
            out_msgs.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=call["id"], name=name))
    finally:
        reset_current_user(token)

    return {
        "messages": out_msgs,
        "tool_events": events,
        "retrieved_chunks": chunks,
        "route_path": _path(state, "tools"),
    }


# 5 ─────────────────────────────────────────────────────────────── finalization & memory
def finalize(state: dict) -> dict:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return {
            "final_response": f"Sorry, I couldn't complete that request within step limits. Please rephrase or contact {settings.CONTACT_OFFICE}.",
            "final_status": "error",
            "error": "max agent steps reached",
            "route_path": _path(state, "finalize"),
        }

    text = last.content if isinstance(last.content, str) else str(last.content)
    degraded = bool(state.get("llm_errors"))
    if degraded:
        text = FALLBACK_NOTICE + text

    writes: list[dict] = []
    sid = state.get("student_id")
    if sid:
        try:
            # Privacy-safe extraction: credentials, OTPs, passwords are automatically stripped
            writes = memory.update_memory_from_message(sid, state["user_query"])
        except Exception as exc:
            logger.warning("Memory update failed: %s", exc)

    return {
        "final_response": text,
        "final_status": "degraded_fallback" if degraded else "success",
        "error": "; ".join(state.get("llm_errors", [])) or None,
        "memory_writes": writes,
        "route_path": _path(state, "finalize"),
    }
