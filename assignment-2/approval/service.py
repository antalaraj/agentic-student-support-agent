"""Sensitive Action Human-in-the-Loop (HITL) Approval Workflow.
Protects sensitive state mutations (such as fee payment extensions and concessions)
by enforcing a mandatory asynchronous administrator approval gate before execution.
Guarantees idempotent, exactly-once execution, strict role isolation, and tamper protection.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from audit.service import log_security_event
from auth.models import AuthUser
from authorization.exceptions import AccessDeniedError, AdminPrivilegeRequiredError
from authorization.service import require_admin, require_student_ownership
from database.db import connection
from privacy.sanitizer import redact_sensitive_text

logger = logging.getLogger(__name__)


def create_fee_extension_request(
    user: AuthUser,
    reason: str,
    requested_due_date: str,
    target_student_id: Optional[str] = None,
) -> dict[str, Any]:
    """Gather request info, validate, and create a PENDING approval request.
    CRITICAL: Does NOT modify student fee records at this stage.
    """
    authorized_sid = require_student_ownership(
        target_student_id, user, action="request_fee_extension", resource="fees"
    )

    clean_reason = redact_sensitive_text(reason.strip())
    clean_date = requested_due_date.strip()

    if not clean_reason:
        return {"status": "error", "message": "A detailed justification reason is required."}
    if not clean_date:
        return {"status": "error", "message": "A proposed extension due date is required."}

    # Verify student has an active fee record
    with connection() as conn:
        fee_row = conn.execute("SELECT * FROM fees WHERE student_id = ?", (authorized_sid,)).fetchone()
        if not fee_row:
            return {"status": "error", "message": f"No fee record found for student {authorized_sid}."}

        current_due = fee_row["due_date"]
        outstanding = fee_row["outstanding_amount"]

        request_id = f"REQ-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        requested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        payload = {
            "requested_due_date": clean_date,
            "reason": clean_reason,
            "current_due_date": current_due,
            "outstanding_amount": outstanding,
            "total_fee": fee_row["total_fee"],
            "paid_amount": fee_row["paid_amount"],
        }

        conn.execute(
            """
            INSERT INTO approval_requests (
                request_id, student_id, action_type, payload_json, status,
                requested_at, reviewed_by, reviewed_at, decision_reason, executed_at, execution_result
            ) VALUES (?, ?, 'fee_extension_request', ?, 'PENDING', ?, NULL, NULL, NULL, NULL, NULL)
            """,
            (request_id, authorized_sid, json.dumps(payload), requested_at),
        )

        # Log to Security Audit Log using the same active connection
        log_security_event(
            requester_id=user.user_id,
            requester_role=user.role,
            action="request_fee_extension",
            resource="approval_requests",
            requested_resource_id=request_id,
            authorization_decision="ALLOWED",
            approval_required=True,
            approval_status="PENDING",
            execution_status="PENDING_APPROVAL",
            details={"student_id": authorized_sid, "requested_due_date": clean_date, "request_id": request_id},
            conn=conn,
        )

    return {
        "status": "pending_approval",
        "request_id": request_id,
        "student_id": authorized_sid,
        "action_type": "fee_extension_request",
        "current_due_date": current_due,
        "requested_due_date": clean_date,
        "outstanding_amount": outstanding,
        "approval_status": "PENDING",
        "message": (
            f"Your request for a fee payment extension to {clean_date} has been submitted "
            f"under tracking ID {request_id}. It is currently PENDING review by the Financial Aid "
            f"Administrator and has NOT yet been applied to your account."
        ),
    }


def list_pending_requests(admin_user: AuthUser) -> list[dict]:
    """Fetch all pending requests requiring administrator action."""
    require_admin(admin_user, action="list_pending_approvals", resource="approval_requests")
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, s.name as student_name, s.programme
            FROM approval_requests r
            JOIN students s ON r.student_id = s.student_id
            WHERE r.status = 'PENDING'
            ORDER BY r.requested_at ASC
            """
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload_json"])
            results.append(d)
        return results


def list_student_requests(user: AuthUser, target_student_id: Optional[str] = None) -> list[dict]:
    """Fetch requests belonging strictly to the authenticated student."""
    authorized_sid = require_student_ownership(
        target_student_id, user, action="list_approval_requests", resource="approval_requests"
    )
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM approval_requests
            WHERE student_id = ?
            ORDER BY requested_at DESC
            """,
            (authorized_sid,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload_json"])
            results.append(d)
        return results


def review_approval_request(
    admin_user: AuthUser,
    request_id: str,
    decision: str,
    decision_reason: str = "",
) -> dict[str, Any]:
    """Review, decide, and atomically execute a pending approval request.
    Strictly verifies:
    1. Reviewer MUST be an authorized administrator.
    2. Request MUST be in 'PENDING' state (prevents double execution, replays, or tampering).
    3. If APPROVED: Protected mutation executes atomically.
    4. If REJECTED: No protected mutation is executed.
    """
    require_admin(admin_user, action="review_approval_request", resource="approval_requests")

    clean_decision = decision.strip().upper()
    if clean_decision not in ("APPROVED", "REJECTED"):
        raise ValueError("Decision must be either 'APPROVED' or 'REJECTED'")

    reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    clean_remarks = redact_sensitive_text(decision_reason.strip() or f"Decision {clean_decision} by Administrator")

    with connection() as conn:
        # Atomic lock and verification
        row = conn.execute(
            "SELECT * FROM approval_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()

        if not row:
            raise ValueError(f"Approval request '{request_id}' not found.")

        current_status = row["status"]
        if current_status != "PENDING":
            log_security_event(
                requester_id=admin_user.user_id,
                requester_role=admin_user.role,
                action="replay_or_tampered_approval_rejected",
                resource="approval_requests",
                requested_resource_id=request_id,
                authorization_decision="DENIED",
                execution_status="BLOCKED",
                failure_reason=f"Attempted to decide request {request_id} currently in state '{current_status}'",
                conn=conn,
            )
            raise ValueError(
                f"Request {request_id} has already been resolved with status '{current_status}'. "
                "Duplicate or replayed decisions are strictly prohibited."
            )

        payload = json.loads(row["payload_json"])
        student_id = row["student_id"]
        execution_result = None

        if clean_decision == "APPROVED":
            # Execute protected state mutation: update fee due_date
            new_due_date = payload["requested_due_date"]
            conn.execute(
                "UPDATE fees SET due_date = ? WHERE student_id = ?",
                (new_due_date, student_id),
            )
            execution_result = json.dumps(
                {
                    "action": "fee_due_date_extended",
                    "student_id": student_id,
                    "previous_due_date": payload["current_due_date"],
                    "new_due_date": new_due_date,
                    "executed_at": reviewed_at,
                }
            )

            conn.execute(
                """
                UPDATE approval_requests
                SET status = 'APPROVED', reviewed_by = ?, reviewed_at = ?,
                    decision_reason = ?, executed_at = ?, execution_result = ?
                WHERE request_id = ?
                """,
                (admin_user.user_id, reviewed_at, clean_remarks, reviewed_at, execution_result, request_id),
            )

            log_security_event(
                requester_id=admin_user.user_id,
                requester_role=admin_user.role,
                action="approve_fee_extension",
                resource="approval_requests",
                requested_resource_id=request_id,
                authorization_decision="ALLOWED",
                approval_required=True,
                approver_id=admin_user.user_id,
                approval_status="APPROVED",
                execution_status="SUCCESS",
                details={
                    "request_id": request_id,
                    "student_id": student_id,
                    "new_due_date": new_due_date,
                    "remarks": clean_remarks,
                },
                conn=conn,
            )

            return {
                "status": "success",
                "request_id": request_id,
                "decision": "APPROVED",
                "message": f"Request {request_id} APPROVED and executed. New fee due date set to {new_due_date}.",
                "executed": True,
            }

        else:  # REJECTED
            conn.execute(
                """
                UPDATE approval_requests
                SET status = 'REJECTED', reviewed_by = ?, reviewed_at = ?,
                    decision_reason = ?, executed_at = NULL, execution_result = NULL
                WHERE request_id = ?
                """,
                (admin_user.user_id, reviewed_at, clean_remarks, request_id),
            )

            log_security_event(
                requester_id=admin_user.user_id,
                requester_role=admin_user.role,
                action="reject_fee_extension",
                resource="approval_requests",
                requested_resource_id=request_id,
                authorization_decision="ALLOWED",
                approval_required=True,
                approver_id=admin_user.user_id,
                approval_status="REJECTED",
                execution_status="DENIED",
                details={"request_id": request_id, "student_id": student_id, "remarks": clean_remarks},
                conn=conn,
            )

            return {
                "status": "rejected",
                "request_id": request_id,
                "decision": "REJECTED",
                "message": f"Request {request_id} has been REJECTED. No student records were modified.",
                "executed": False,
            }


def get_approval_request(request_id: str, user: AuthUser) -> Optional[dict]:
    """Retrieve details for a single approval request."""
    with connection() as conn:
        row = conn.execute("SELECT * FROM approval_requests WHERE request_id = ?", (request_id,)).fetchone()
        if not row:
            return None
        if user.is_student() and row["student_id"] != user.student_id:
            raise AccessDeniedError("You are not authorized to view this request.")
        d = dict(row)
        d["payload"] = json.loads(d["payload_json"])
        return d
