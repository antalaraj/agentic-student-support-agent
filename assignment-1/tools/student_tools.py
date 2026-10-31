from database.db import connection
from tools.base import err, normalise_student_id, safe_tool


@safe_tool
def get_student_profile(student_id: str) -> dict:
    """Retrieve a student's academic profile (programme, semester, CGPA, attendance, advisor)."""
    sid = normalise_student_id(student_id)
    if not sid:
        return err("invalid_input", "A valid student ID is required (for example MIM25001).")
    with connection() as conn:
        row = conn.execute("SELECT * FROM students WHERE student_id=?", (sid,)).fetchone()
    if row is None:
        return {"status": "not_found", "message": f"No student found with ID {sid}."}
    return {"status": "ok", "student_id": row["student_id"], "name": row["name"], "email": row["email"],
            "programme": row["programme"], "semester": row["semester"], "cgpa": row["cgpa"],
            "attendance_pct": row["attendance_pct"], "advisor": row["advisor"], "batch": row["batch"]}
