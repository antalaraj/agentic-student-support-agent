"""Support ticket creation and inquiry tool with credential sanitization and ownership validation."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from audit.service import log_security_event
from auth.context import get_current_user
from auth.models import AuthUser
from authorization.service import require_student_ownership
from database.db import connection
from database.models import SUPPORT_CATEGORIES
from privacy.sanitizer import redact_sensitive_text
from tools.base import err, normalise_student_id, safe_tool


@safe_tool
def create_support_ticket(issue: str, category: str = "general", student_id: str = "") -> dict:
    """Create a tracked support request for the authenticated student.
    Category must be one of: fee_payment, scholarship, academic, examination, technical, general.
    Sensitive credentials (passwords, OTPs, PINs, card numbers) are automatically scrubbed.
    """
    user = get_current_user()
    authorized_sid = require_student_ownership(
        student_id or (user.student_id if user else None),
        user,
        action="create_ticket",
        resource="support_tickets",
    )

    clean_issue = redact_sensitive_text(str(issue or "").strip())
    if len(clean_issue) < 8:
        return err("invalid_input", "Please provide a more descriptive summary of the problem (at least 8 characters).")

    cat = (category or "general").strip().lower().replace(" ", "_")
    if cat not in SUPPORT_CATEGORIES:
        cat = "general"

    ticket_id = f"TKT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO support_tickets (ticket_id, student_id, category, issue, status, created_at)
            VALUES (?, ?, ?, ?, 'Open', ?)
            """,
            (ticket_id, authorized_sid, cat, clean_issue, created_at),
        )

    if user:
        log_security_event(
            requester_id=user.user_id,
            requester_role=user.role,
            action="create_support_ticket",
            resource="support_tickets",
            requested_resource_id=ticket_id,
            authorization_decision="ALLOWED",
            execution_status="SUCCESS",
            details={"student_id": authorized_sid, "category": cat},
        )

    return {
        "status": "ok",
        "ticket_id": ticket_id,
        "student_id": authorized_sid,
        "category": cat,
        "ticket_status": "Open",
        "created_at": created_at,
        "message": f"Support ticket {ticket_id} has been created under category '{cat}'. The Student Services team will reply via your student email.",
    }


def list_tickets(student_id: Optional[str] = None, user: Optional[AuthUser] = None) -> list[dict]:
    """Retrieve support tickets strictly belonging to the authorized student."""
    auth_user = user or get_current_user()
    authorized_sid = require_student_ownership(
        student_id or (auth_user.student_id if auth_user else None),
        auth_user,
        action="list_tickets",
        resource="support_tickets",
    )
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM support_tickets WHERE student_id = ? ORDER BY created_at DESC",
            (authorized_sid,),
        ).fetchall()
        return [dict(r) for r in rows]
