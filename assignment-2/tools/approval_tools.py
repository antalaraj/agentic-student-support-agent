"""Sensitive action approval tool: Requesting fee payment extensions and concessions.
Requires human-in-the-loop review by an authorized administrator before any protected
student record mutation is permitted.
"""
from approval.service import create_fee_extension_request
from auth.context import get_current_user
from tools.base import err, safe_tool


@safe_tool
def request_fee_extension(reason: str, requested_due_date: str, student_id: str = "") -> dict:
    """Submit an official formal request for an extension of the student's tuition fee payment due date.
    This is a sensitive financial action that CANNOT execute immediately.
    The agent creates a PENDING approval request for review by the Financial Aid Administrator.
    """
    user = get_current_user()
    if not user:
        return {"status": "needs_input", "message": "You must be logged in as a student to request a fee extension."}

    target_sid = student_id or user.student_id
    res = create_fee_extension_request(
        user=user,
        reason=reason,
        requested_due_date=requested_due_date,
        target_student_id=target_sid,
    )
    return res
