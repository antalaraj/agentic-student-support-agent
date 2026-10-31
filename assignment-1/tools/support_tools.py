import uuid
from datetime import datetime, timezone

from database.db import connection
from database.memory import is_sensitive
from database.models import SUPPORT_CATEGORIES
from tools.base import err, normalise_student_id, safe_tool
from tracing.tracer import redact_text

_CATEGORY_ALIASES = {"payment": "fee_payment", "fee": "fee_payment", "fees": "fee_payment", "fee & payment": "fee_payment",
                     "exam": "examination", "course": "academic", "technical issue": "technical", "other": "general"}


@safe_tool
def create_support_ticket(student_id: str, issue: str, category: str = "general") -> dict:
    """Create a support request for a student and return a unique ticket ID.
    category must be one of: fee_payment, scholarship, academic, examination, technical, general."""
    sid = normalise_student_id(student_id)
    if not sid:
        return err("invalid_input", "A valid student ID is required to create a ticket.")
    if not isinstance(issue, str) or len(issue.strip()) < 5:
        return err("invalid_input", "Please describe the issue (at least a few words) so the ticket is useful.")
    cat = (category or "general").strip().lower()
    cat = _CATEGORY_ALIASES.get(cat, cat)
    if cat not in SUPPORT_CATEGORIES:
        return err("invalid_input", f"Unknown category '{category}'. Use one of: {', '.join(SUPPORT_CATEGORIES)}.")
    clean_issue = redact_text(issue.strip())[:1000]  # never store OTPs/passwords in tickets
    with connection() as conn:
        if conn.execute("SELECT 1 FROM students WHERE student_id=?", (sid,)).fetchone() is None:
            return {"status": "not_found", "message": f"No student found with ID {sid}."}
        now = datetime.now(timezone.utc)
        ticket_id = f"TKT-{now:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        conn.execute("INSERT INTO support_tickets (ticket_id,student_id,category,issue,status,created_at) "
                     "VALUES (?,?,?,?, 'Open', ?)", (ticket_id, sid, cat, clean_issue, now.isoformat(timespec="seconds")))
    return {"status": "ok", "ticket_id": ticket_id, "category": cat, "ticket_status": "Open",
            "expected_response": "within 2 working days (1 working day for urgent fee/exam matters)",
            "sensitive_data_removed": clean_issue != issue.strip() or is_sensitive(issue)}


@safe_tool
def list_tickets(student_id: str) -> list[dict]:
    """Helper for the UI (not exposed to the LLM)."""
    with connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT ticket_id, category, issue, status, created_at FROM support_tickets WHERE student_id=? ORDER BY created_at DESC",
            (student_id,))]
