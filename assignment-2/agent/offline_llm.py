"""OfflinePlanner for Assignment 2.
A deterministic stand-in for the LLM that enables offline testing and graceful degradation.
Plans tool calls based on intent and synthesizes grounded answers from tool outputs.
Includes support for sensitive action approval requests, access denial handling, and memory recall.
"""
import json
import re
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.routing import classify_intent
from config import settings
from config.text_utils import tokenize

_CATEGORY_RULES = [
    ("fee_payment", r"pay|fee|portal|refund|extension|concession"),
    ("scholarship", r"scholar|fellowship|grant"),
    ("examination", r"exam|hall ticket|result|grade"),
    ("academic", r"course|elective|programme|attendance|class"),
    ("technical", r"login|portal error|website|app|password reset"),
]


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

    def invoke(self, messages) -> AIMessage:
        last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        query = messages[last_human].content
        tool_msgs = [m for m in messages[last_human + 1:] if isinstance(m, ToolMessage)]
        system = messages[0].content if messages and messages[0].type == "system" else ""

        if tool_msgs:
            return AIMessage(content=self._compose(query, tool_msgs, system))

        calls = self._plan(query, system)
        if calls:
            return AIMessage(
                content="",
                tool_calls=[{"name": n, "args": a, "id": f"call_{uuid.uuid4().hex[:8]}"} for n, a in calls],
            )
        return AIMessage(content=self._direct_answer(query, system))

    @classmethod
    def _plan(cls, query: str, system: str = ""):
        intent = classify_intent(query)
        mem = cls._memory_lines(system) if system else []

        # Memory-related or personal identity questions should never call tools
        if intent == "memory_recall" or (
            mem and re.search(r"\b(name|who am i|prefer|preference|preferences|told you|remember)\b", query.lower())
        ):
            return []

        # Check if user query explicitly asked for another student's record (e.g. MIM25003)
        other_match = re.search(r"\b(MIM\d{5})\b", query.upper())
        explicit_sid = other_match.group(1) if other_match else ""

        if intent == "fee_extension":
            # Extract date if mentioned or default to end of next month
            date_match = re.search(r"\b(202\d-[01]\d-[0-3]\d)\b", query)
            req_date = date_match.group(1) if date_match else "2026-12-31"
            return [("request_fee_extension", {"reason": query, "requested_due_date": req_date, "student_id": explicit_sid})]

        if intent == "fee":
            return [("check_fee_status", {"student_id": explicit_sid})]

        if intent == "scholarship":
            return [("check_scholarship_status", {"student_id": explicit_sid})]

        if intent == "profile":
            return [("get_student_profile", {"student_id": explicit_sid})]

        if intent in ("ticket", "support_ticket"):
            return [("create_support_ticket", {"issue": query, "category": _category(query), "student_id": explicit_sid})]

        if intent == "policy":
            return [("search_policy", {"query": query})]

        if intent == "general":
            if not re.search(r"\b(who|name|me|my|i|preferences?|told you|remember|call me)\b", query.lower()):
                # If question seems like an institutional policy query
                if re.search(r"\b(can i|is it allowed|what is|how do i|rules?|policy)\b", query.lower()):
                    return [("search_policy", {"query": query})]

        return []

    @staticmethod
    def _memory_lines(system: str) -> list[str]:
        block = system.split("REMEMBERED STUDENT PREFERENCES", 1)[-1]
        return [l[2:].strip() for l in block.splitlines() if l.startswith("- ") and "nothing relevant" not in l]

    def _direct_answer(self, query: str, system: str) -> str:
        intent = classify_intent(query)
        mem = self._memory_lines(system)
        name = next((m.split(":", 1)[1].strip() for m in mem if "Preferred name" in m), None)
        prefs = [m.split("Prefers ", 1)[1].strip() for m in mem if "Prefers " in m]
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
            return "Please do not share sensitive credentials (passwords, OTPs, PINs, card numbers) with me. They will not be stored."

        if re.search(r"\b(call me|i prefer|i like|i love|i am interested|i'm interested)\b", q_low):
            return "Thanks, noted! I'll remember that for future sessions."

        if re.search(r"\b(what can you|who are you)\b", q_low):
            return (
                "I can check your fee and scholarship status, view your profile, request fee payment extensions (subject to administrator approval), "
                "search the student handbook (fees, late fees, attendance, course changes, exams), and raise support tickets."
            )

        greet = f"Hello {name}!" if name else "Hello!"
        return f"{greet} How can I assist you with your academics, fees, scholarships, or support requests today?"

    def _compose(self, query: str, tool_msgs, system: str) -> str:
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

        if d.get("error_type") == "access_denied":
            return f"🛡️ Access Denied: {d.get('message', 'You are not authorized to view or modify records belonging to other students.')}"

        if status == "needs_input":
            return f"I need to verify your identity. {d.get('message', 'Please log in with your student credentials.')}"

        if status == "not_found":
            return f"I couldn't find that record. {d.get('message', '')}"

        if status == "no_evidence":
            return f"I could not find relevant information in the student handbook. {d.get('recommendation', 'Please contact Student Services.')}"

        if status == "error":
            return f"Sorry, I couldn't complete that: {d.get('message', 'An error occurred')}"

        if status == "pending_approval" or tool == "request_fee_extension":
            return (
                f"Your request for a fee payment extension has been submitted under tracking ID **{d['request_id']}**.\n\n"
                f"**Current Status:** `PENDING APPROVAL`\n"
                f"**Requested Due Date:** {d.get('requested_due_date')}\n"
                f"**Note:** This request requires review by the Financial Aid Administrator. "
                f"It has **NOT** yet been applied to your fee records. You can check the approval status in the My Approval Requests page."
            )

        if tool == "check_fee_status":
            return (
                f"Your fee status is **{d['payment_status']}**. Total fee {_inr(d['total_fee'])}, paid {_inr(d['paid_amount'])}, "
                f"outstanding {_inr(d['outstanding_amount'])}. Next due date: {d['due_date']}."
            )

        if tool == "check_scholarship_status":
            if d.get("scholarship_name") in ("None", None):
                return "You have no scholarship application on record."
            return (
                f"Scholarship: **{d['scholarship_name']}** — application status: **{d['application_status']}**"
                f"{(' (' + d['remarks'] + ')') if d.get('remarks') else ''}."
            )

        if tool == "get_student_profile":
            return (
                f"You are {d['name']} ({d['student_id']}), enrolled in **{d['programme']}**, semester {d['semester']}. "
                f"CGPA: {d['cgpa']}, Attendance: {d['attendance_pct']}%, Faculty Advisor: {d['advisor']}."
            )

        if tool == "create_support_ticket":
            return f"Support ticket **{d['ticket_id']}** created under category '{d['category']}'. Status: {d['ticket_status']}."

        if tool in ("search_policy", "search_academic_information"):
            clauses = self._best_clauses(d.get("results", []), query)
            body = "\n".join(f"• {line}" for line, _ in clauses)
            sections = ", ".join(dict.fromkeys(sec for _, sec in clauses))
            return f"According to the student handbook:\n{body}\n\n(Source: {sections})"

        return "Done."
