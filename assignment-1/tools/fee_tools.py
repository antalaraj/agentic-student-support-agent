from database.db import connection
from tools.base import err, normalise_student_id, safe_tool


@safe_tool
def check_fee_status(student_id: str) -> dict:
    """Return total fees, paid amount, outstanding amount and payment status for a student."""
    sid = normalise_student_id(student_id)
    if not sid:
        return err("invalid_input", "A valid student ID is required (for example MIM25001).")
    with connection() as conn:
        row = conn.execute("SELECT * FROM fees WHERE student_id=?", (sid,)).fetchone()
    if row is None:
        return {"status": "not_found", "message": f"No fee record found for student ID {sid}."}
    return {"status": "ok", "student_id": sid, "currency": "INR", "total_fee": row["total_fee"],
            "paid_amount": row["paid_amount"], "outstanding_amount": row["outstanding_amount"],
            "payment_status": row["payment_status"], "due_date": row["due_date"],
            "last_payment_date": row["last_payment_date"] or None}
