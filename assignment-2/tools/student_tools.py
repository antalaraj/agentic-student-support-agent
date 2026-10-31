"""Student profile query tool with strict ownership validation."""
from audit.service import log_security_event
from auth.context import get_current_user
from authorization.service import require_student_ownership
from database.db import connection
from tools.base import err, normalise_student_id, safe_tool


@safe_tool
def get_student_profile(student_id: str = "") -> dict:
    """Return academic profile (programme, semester, CGPA, attendance %, advisor) for the authenticated student.
    Enforces student data ownership: students can only access their own profile.
    """
    user = get_current_user()
    authorized_sid = require_student_ownership(
        student_id or (user.student_id if user else None),
        user,
        action="view_profile",
        resource="students",
    )

    with connection() as conn:
        row = conn.execute("SELECT * FROM students WHERE student_id = ?", (authorized_sid,)).fetchone()

    if row is None:
        return {"status": "not_found", "message": f"No student record found for ID {authorized_sid}."}

    # Log successful audit read
    if user:
        log_security_event(
            requester_id=user.user_id,
            requester_role=user.role,
            action="view_student_profile",
            resource="students",
            requested_resource_id=authorized_sid,
            authorization_decision="ALLOWED",
            execution_status="SUCCESS",
        )

    return {
        "status": "ok",
        "student_id": authorized_sid,
        "name": row["name"],
        "email": row["email"],
        "programme": row["programme"],
        "semester": row["semester"],
        "cgpa": row["cgpa"],
        "attendance_pct": row["attendance_pct"],
        "advisor": row["advisor"],
        "batch": row["batch"],
    }
