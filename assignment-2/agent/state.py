"""The shared state that flows through the LangGraph StateGraph in Assignment 2."""
from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from auth.models import AuthUser


class AgentState(TypedDict, total=False):
    # --- Authenticated Identity & Inputs ---
    user_query: str
    user: Optional[AuthUser]           # Verified, authenticated session user
    student_id: Optional[str]          # Resolved student ID
    session_id: str
    history: list[dict]                # Previous turns in this session

    # --- Produced by Context Selection ---
    intent: str                        # Detected intent (fee, policy, fee_extension, etc.)
    memories: list[dict]               # Privacy-sanitized memories relevant to this turn
    context_sources: list[str]

    # --- Working Execution Data ---
    messages: Annotated[list[AnyMessage], add_messages]
    steps: int
    use_fallback: bool
    llm_errors: list[str]
    tool_events: list[dict]
    retrieved_chunks: list[dict]
    memory_writes: list[dict]
    usage: dict
    route_path: list[str]

    # --- Final Outputs ---
    final_response: str
    final_status: str
    error: Optional[str]
