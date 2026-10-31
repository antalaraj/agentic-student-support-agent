"""The shared state that flows through the LangGraph StateGraph."""
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # --- inputs ---
    user_query: str
    student_id: Optional[str]          # demo identity chosen in the UI (None = nobody selected)
    session_id: str
    history: list[dict]                # previous turns of THIS session: [{"role","content"}]
    # --- produced by context selection ---
    intent: str                        # keyword-based hint: fee / policy / memory_recall / ...
    memories: list[dict]               # only the memories relevant to this question
    context_sources: list[str]
    # --- working data ---
    messages: Annotated[list[AnyMessage], add_messages]   # what the LLM sees this turn
    steps: int                         # agent<->tool loop counter
    use_fallback: bool                 # True after the real LLM failed
    llm_errors: list[str]
    tool_events: list[dict]            # trace of every tool call
    retrieved_chunks: list[dict]       # policy chunks that came back from RAG
    memory_writes: list[dict]
    usage: dict                        # token usage reported by the model API
    route_path: list[str]              # nodes visited (for the trace)
    # --- outputs ---
    final_response: str
    final_status: str                  # success / degraded_fallback / empty_query / error
    error: Optional[str]
