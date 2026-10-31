"""OfflinePlanner - a deterministic stand-in for the LLM.

It is used (1) when no GROQ_API_KEY is configured, (2) as a graceful fallback when the Groq API fails,
and (3) in automated tests/offline evaluation. It exposes the same `bind_tools()/invoke()` interface
as a chat model, so the LangGraph agent code path is identical. It is NOT a language model: it picks a
tool from keyword intent and writes extractive answers from the real tool output. Reported token usage
is always unavailable."""
import re
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.routing import classify_intent
from config import settings
from config.text_utils import tokenize

_CATEGORY_RULES = [("fee_payment", r"pay|fee|portal|refund"), ("scholarship", r"scholar|fellowship|grant"),
                   ("examination", r"exam|hall ticket|result"), ("academic", r"course|elective|programme|attendance|class"),
                   ("technical", r"login|portal error|website|app|password reset")]


def _category(text: str) -> str:
    for cat, pattern in _CATEGORY_RULES:
        if re.search(pattern, text.lower()):
            return cat
    return "general"


def _inr(n) -> str:
    return f"₹{int(n):,}"


class OfflinePlanner:
    model_name = "offline-planner (no LLM)"

    def bind_tools(self, tools):
        return self

    # ---- the "model" call ----
    def invoke(self, messages) -> AIMessage:
        last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        query = messages[last_human].content
        tool_msgs = [m for m in messages[last_human + 1:] if isinstance(m, ToolMessage)]
        system = messages[0].content if messages and messages[0].type == "system" else ""
        if tool_msgs:
            return AIMessage(content=self._compose(query, tool_msgs, system))
        calls = self._plan(query, system)
        if calls:
            return AIMessage(content="", tool_calls=[{"name": n, "args": a, "id": f"call_{uuid.uuid4().hex[:8]}"} for n, a in calls])
        return AIMessage(content=self._direct_answer(query, system))

    # ---- decide tools ----
    @classmethod
    def _plan(cls, query: str, system: str = ""):
        intent = classify_intent(query)
        mem = cls._memory_lines(system) if system else []
        # Memory-related or personal identity questions should never call tools
        if intent == "memory_recall" or (mem and re.search(r"\b(name|who am i|prefer|preference|preferences|told you|remember)\b", query.lower())):
            return []
        if intent == "fee":
            return [("check_fee_status", {"student_id": ""})]
        if intent == "scholarship":
            return [("check_scholarship_status", {"student_id": ""})]
        if intent == "profile":
            return [("get_student_profile", {"student_id": ""})]
        if intent == "support_ticket":
            return [("create_support_ticket", {"student_id": "", "issue": query, "category": _category(query)})]
        if intent == "policy":
            return [("search_policy", {"query": query})]
        if intent == "academic":
            return [("search_academic_information", {"query": query})]
        if intent == "unknown":
            # Guard against policy search for conversational/identity questions
            if not re.search(r"\b(who|name|me|my|i|preferences?|told you|remember|call me)\b", query.lower()):
                return [("search_policy", {"query": query})]
        return []  # general / memory_recall -> answer directly

    # ---- answers without tools ----
    @staticmethod
    def _memory_lines(system: str) -> list[str]:
        block = system.split("REMEMBERED INFORMATION (long-term", 1)[-1]
        return [l[2:].strip() for l in block.splitlines() if l.startswith("- ") and "nothing relevant" not in l]

    def _direct_answer(self, query: str, system: str) -> str:
        intent = classify_intent(query)
        mem = self._memory_lines(system)
        name = next((m.split(":", 1)[1].strip() for m in mem if m.startswith("Preferred name")), None)
        prefs = [m.split(":", 1)[1].strip() for m in mem if "Preference" in m]
        q_low = query.lower()

        if intent == "memory_recall" or (mem and "?" in query):
            if mem:
                if re.search(r"\b(name|who am i)\b", q_low) and name:
                    return f"Your preferred name is {name}."
                if re.search(r"\b(prefer|preference)\b", q_low) and prefs:
                    return f"You told me that your preference is: {', '.join(prefs)}."
                return "Here is what I remember from our earlier conversations:\n" + "\n".join(f"• {m}" for m in mem)
            return "I don't have anything saved about that yet. Tell me your preferences and I'll remember the useful, non-sensitive ones."
        if re.search(r"\b(otp|password|pin|cvv|card)\b", q_low):
            return "Please don't share passwords, OTPs or card details with me. I won't store them, and staff will never ask for them in chat."
        if re.search(r"\b(call me|i prefer|i like|i love|i am interested|i'm interested)\b", q_low):
            return "Thanks, noted! I'll remember that for future sessions."
        if re.search(r"\b(what can you|who are you)\b", q_low):
            return ("I can check your fee and scholarship status, show your profile, search the student handbook "
                    "(fees, late fees, attendance, course changes, exams) and raise support tickets.")
        greet = f"Hello {name}!" if name else "Hello!"
        return f"{greet} How can I help you with fees, scholarships, courses or support today?"

    # ---- answers from tool output ----
    def _compose(self, query: str, tool_msgs, system: str) -> str:
        import json

        parts = []
        for tm in tool_msgs:
            data = json.loads(tm.content)
            parts.append(self._compose_one(tm.name, data, query))
        return "\n\n".join(parts)

    @staticmethod
    def _best_clauses(results, query: str, n: int = 2) -> list[tuple[str, str]]:
        q = set(tokenize(query))
        scored = []
        for r in results:
            for line in r["text"].splitlines()[1:]:
                scored.append((len(q & set(tokenize(line))), line, r["section"]))
        scored.sort(key=lambda x: -x[0])
        return [(line, sec) for _, line, sec in scored[:n]]

    def _compose_one(self, tool: str, d: dict, query: str) -> str:
        status = d.get("status")
        if status == "needs_input":
            return "I need to know who you are first. Please select your student ID in the sidebar."
        if status == "not_found":
            return f"I couldn't find that record. {d.get('message', '')} Please check the student ID."
        if status == "no_evidence":
            return f"I couldn't find this in the student handbook, so I can't give a reliable answer. {d.get('recommendation', '')}"
        if status == "error":
            return f"Sorry, I couldn't complete that: {d.get('message', 'an error occurred')} Please try again, or contact {settings.CONTACT_OFFICE}."
        if tool == "check_fee_status":
            return (f"Your fee status is **{d['payment_status']}**. Total fee {_inr(d['total_fee'])}, paid {_inr(d['paid_amount'])}, "
                    f"outstanding {_inr(d['outstanding_amount'])}. Next due date: {d['due_date']}.")
        if tool == "check_scholarship_status":
            if d["scholarship_name"] == "None":
                return "You have no scholarship application on record."
            return (f"Scholarship: **{d['scholarship_name']}** - application status **{d['application_status']}**"
                    f"{(' (' + d['remarks'] + ')') if d.get('remarks') else ''}.")
        if tool == "get_student_profile":
            return (f"You are {d['name']} ({d['student_id']}), studying **{d['programme']}**, semester {d['semester']}. "
                    f"CGPA {d['cgpa']}, attendance {d['attendance_pct']}%, faculty advisor {d['advisor']}.")
        if tool == "create_support_ticket":
            return f"I've created your support ticket **{d['ticket_id']}** (category: {d['category']}). Expected response: {d['expected_response']}."
        if tool in ("search_policy", "search_academic_information"):
            clauses = self._best_clauses(d["results"], query)
            body = "\n".join(f"• {line}" for line, _ in clauses)
            sections = ", ".join(dict.fromkeys(sec for _, sec in clauses))
            return f"According to the student handbook:\n{body}\n\n(Source: {sections})"
        return "Done."
