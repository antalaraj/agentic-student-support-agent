"""Intent hint + conditional edges.

`classify_intent` is only a HINT used for context selection and for the trace. The decision to call a
tool is made by the LLM through tool-calling (or by the offline planner when no LLM is available)."""
import re

from config import settings

_INTENT_PATTERNS: dict[str, list[tuple[str, int]]] = {
    "support_ticket": [(r"\b(create|raise|file|open|submit|log|register)\b.*\b(ticket|support request|complaint)\b", 6),
                       (r"\bsupport (ticket|request)\b", 3)],
    "memory_recall": [
        (r"\b(previous session|last session|last time|earlier|did i (tell|say|mention)|i told you|do you remember|what do you remember)\b", 6),
        (r"\b(what('s| is) my name|my preferred name|who am i|what are my preferences|my preferences|what did i tell you|what do you know about me|what do you remember about me)\b", 8),
        (r"\b(what name|which name)\b", 6),
    ],
    "general": [(r"^\s*(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening))\b", 6),
                (r"\b(call me|i prefer|i like|i love|i am interested|i'm interested|my otp|my password|my pin)\b", 6),
                (r"\bwhat can you (do|help)\b|\bwho are you\b", 6)],
    "profile": [(r"\b(my (programme|program|course|semester|profile|details|email|cgpa|advisor|record|student id)|what (programme|program) am i|which (programme|program) am i)\b", 4)],
    "fee": [(r"\b(fee|fees|outstanding|dues?|balance|paid|installment|instalment)\b", 2)],
    "scholarship": [(r"\bscholarships?\b|\bfellowship\b|\bgrant\b", 2), (r"\b(status|application)\b", 1)],
    "policy": [(r"\b(policy|policies|rules?|regulations?|handbook|requirement|allowed|permitted|penalty|late fee|refund|deadline|eligib\w*|procedure|attendance|exams?|examination|portal|working day|can i|may i|am i allowed|change my|switch|criteria|appeal|condonation)\b", 3)],
    "academic": [(r"\b(programmes? offered|courses?|syllabus|curriculum|credits?|electives?|placements?|internships?|recruiters?|specialisation|subjects?|faculty)\b", 3)],
}


def classify_intent(query: str) -> str:
    q = query.lower()
    scores: dict[str, int] = {}
    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern, weight in patterns:
            matches = set(m.group(0) for m in re.finditer(pattern, q))
            if matches:
                scores[intent] = scores.get(intent, 0) + weight * (1 if intent != "policy" else len(matches))
    if not scores:
        return "unknown" if "?" in q else "general"
    # policy words beat a bare "fee"/"scholarship" mention (e.g. "late fee policy")
    return max(scores, key=lambda k: (scores[k], list(_INTENT_PATTERNS).index(k) * -1))


# ---- conditional edges ----
def route_after_validate(state) -> str:
    return "end" if state.get("final_status") == "empty_query" else "context"


def route_after_agent(state) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None) and state.get("steps", 0) < settings.MAX_AGENT_STEPS:
        return "tools"
    return "finalize"
