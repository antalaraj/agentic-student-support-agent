"""Student scholarship records query tool with strict ownership validation."""
from audit.service import log_security_event
from auth.context import get_current_user
from authorization.service import require_student_ownership
from database.db import connection
from tools.base import err, normalise_student_id, safe_tool


@safe_tool
def check_scholarship_status(student_id: str = "") -> dict:
    """Return scholarship application status, awarded amount, and committee remarks for the authenticated student.
    Enforces student data ownership: Student A can never view Student B's scholarship record.
    """
    user = get_current_user()
    authorized_sid = require_student_ownership(
        student_id or (user.student_id if user else None),
        user,
        action="view_scholarship_status",
        resource="scholarships",
    )

    with connection() as conn:
        row = conn.execute("SELECT * FROM scholarships WHERE student_id = ?", (authorized_sid,)).fetchone()

    if row is None:
        return {"status": "not_found", "message": f"No scholarship record found for student ID {authorized_sid}."}

    if user:
        log_security_event(
            requester_id=user.user_id,
            requester_role=user.role,
            action="view_scholarship_status",
            resource="scholarships",
            requested_resource_id=authorized_sid,
            authorization_decision="ALLOWED",
            execution_status="SUCCESS",
        )

    return {
        "status": "ok",
        "student_id": authorized_sid,
        "scholarship_name": row["scholarship_name"],
        "application_status": row["application_status"],
        "awarded_amount": row["amount"],
        "currency": "INR",
        "remarks": row["remarks"],
    }
