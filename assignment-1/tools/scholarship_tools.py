from database.db import connection
from tools.base import err, normalise_student_id, safe_tool


@safe_tool
def check_scholarship_status(student_id: str) -> dict:
    """Return scholarship name and application status for a student."""
    sid = normalise_student_id(student_id)
    if not sid:
        return err("invalid_input", "A valid student ID is required (for example MIM25001).")
    with connection() as conn:
        row = conn.execute("SELECT * FROM scholarships WHERE student_id=?", (sid,)).fetchone()
    if row is None:
        return {"status": "not_found", "message": f"No scholarship record found for student ID {sid}."}
    return {"status": "ok", "student_id": sid, "scholarship_name": row["scholarship_name"],
            "application_status": row["application_status"], "amount": row["amount"], "remarks": row["remarks"]}
