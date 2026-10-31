"""Student fee records query tool with strict ownership validation."""
from audit.service import log_security_event
from auth.context import get_current_user
from authorization.service import require_student_ownership
from database.db import connection
from tools.base import err, normalise_student_id, safe_tool


@safe_tool
def check_fee_status(student_id: str = "") -> dict:
    """Return total fees, paid amount, outstanding dues, payment status and due date for the authenticated student.
    Enforces student data ownership: Student A can never view Student B's fees.
    """
    user = get_current_user()
    authorized_sid = require_student_ownership(
        student_id or (user.student_id if user else None),
        user,
        action="view_fee_status",
        resource="fees",
    )

    with connection() as conn:
        row = conn.execute("SELECT * FROM fees WHERE student_id = ?", (authorized_sid,)).fetchone()

    if row is None:
        return {"status": "not_found", "message": f"No fee record found for student ID {authorized_sid}."}

    # Log successful audit read
    if user:
        log_security_event(
            requester_id=user.user_id,
            requester_role=user.role,
            action="view_fee_status",
            resource="fees",
            requested_resource_id=authorized_sid,
            authorization_decision="ALLOWED",
            execution_status="SUCCESS",
        )

    return {
        "status": "ok",
        "student_id": authorized_sid,
        "currency": "INR",
        "total_fee": row["total_fee"],
        "paid_amount": row["paid_amount"],
        "outstanding_amount": row["outstanding_amount"],
        "payment_status": row["payment_status"],
        "due_date": row["due_date"],
        "last_payment_date": row["last_payment_date"] or None,
    }
