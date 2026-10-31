"""Intent classification and routing logic for the LangGraph StateGraph in Assignment 2."""
import re

from config import settings

_INTENT_PATTERNS: dict[str, list[tuple[str, int]]] = {
    "fee_extension": [
        (r"\b(extend|extension|defer|delay\s+payment|installment|hardship|concession|waiver)\b.*\b(fee|fees|payment|due|tuition)\b", 8),
        (r"\b(fee|fees|payment|due|tuition)\b.*\b(extend|extension|defer|delay\s+payment|installment|hardship|concession|waiver)\b", 8),
        (r"\b(fee payment extension|fee extension|extend my fee|extend fee due date)\b", 9),
    ],
    "support_ticket": [
        (r"\b(create|raise|file|open|submit|log|register)\b.*\b(ticket|support request|complaint)\b", 6),
        (r"\bsupport (ticket|request)\b", 3),
    ],
    "memory_recall": [
        (r"\b(previous session|last session|last time|earlier|did i (tell|say|mention)|i told you|do you remember|what do you remember)\b", 6),
        (r"\b(what('s| is) my name|my preferred name|who am i|what are my preferences|my preferences|what did i tell you|what do you know about me|what do you remember about me)\b", 8),
        (r"\b(what name|which name)\b", 6),
    ],
    "general": [
        (r"^\s*(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening))\b", 6),
        (r"\b(call me|i prefer|i like|i love|i am interested|i'm interested|my otp|my password|my pin)\b", 6),
        (r"\bwhat can you (do|help)\b|\bwho are you\b", 6),
    ],
    "profile": [
        (r"\b(my (programme|program|course|semester|profile|details|email|cgpa|advisor|record|student id)|what (programme|program) am i|which (programme|program) am i|student profile|get profile|profile of|profile for)\b", 4),
    ],
    "policy": [
        (r"\b(policy|policies|rules?|regulations?|handbook|requirement|allowed|permitted|penalty|late fee|refund|deadline|eligib\w*|procedure|attendance|exams?|examination|portal|working day|can i|may i|am i allowed|change my|switch|criteria|appeal|condonation)\b", 3),
    ],
    "fee": [
        (r"\b(fee|fees|outstanding|dues?|balance|paid|tuition)\b", 2),
    ],
    "scholarship": [
        (r"\bscholarships?\b|\bfellowship\b|\bgrant\b", 2),
        (r"\b(status|application)\b", 1),
    ],
    "academic": [
        (r"\b(programmes? offered|courses?|syllabus|curriculum|credits?|electives?|placements?|internships?|recruiters?|specialisation|subjects?|faculty)\b", 3),
    ],
}


def classify_intent(query: str) -> str:
    """Classify user query into operational intent buckets using weighted scoring."""
    q = query.lower()
    scores: dict[str, int] = {}
    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern, weight in patterns:
            matches = set(m.group(0) for m in re.finditer(pattern, q))
            if matches:
                # Policy terms multiply score to decisively beat a bare "fee" mention (e.g., "late fee policy")
                mult = len(matches) if intent == "policy" else 1
                scores[intent] = scores.get(intent, 0) + weight * mult

    if not scores:
        return "unknown" if "?" in q else "general"

    # Higher score wins; for tie-break, order in _INTENT_PATTERNS decides
    return max(scores, key=lambda k: (scores[k], list(_INTENT_PATTERNS).index(k) * -1))


def route_after_validate(state: dict) -> str:
    return "end" if state.get("final_status") == "empty_query" else "context"


def route_after_agent(state: dict) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "finalize"
    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", None)
    if tool_calls and state.get("steps", 0) < settings.MAX_AGENT_STEPS:
        return "tools"
    return "finalize"
