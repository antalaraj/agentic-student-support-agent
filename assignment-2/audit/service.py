"""Persistent Security Audit Logging Service.
Logs all authentication, authorization, sensitive approvals, and administrative actions
using parameterized SQL. Automatically sanitizes all recorded details.
Supports optional reuse of caller connection to avoid nested SQLite locking.
"""
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from database.db import connection
from privacy.sanitizer import redact_dict

logger = logging.getLogger(__name__)


def log_security_event(
    requester_id: str,
    requester_role: str,
    action: str,
    resource: str,
    requested_resource_id: Optional[str] = None,
    authorization_decision: str = "ALLOWED",
    approval_required: bool = False,
    approver_id: Optional[str] = None,
    approval_status: str = "N/A",
    execution_status: str = "SUCCESS",
    details: Optional[dict[str, Any]] = None,
    failure_reason: Optional[str] = None,
    session_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> str:
    """Record an immutable, structured security audit log entry.
    All credentials and secrets in `details` are scrubbed before insertion.
    Returns the unique audit_id.
    """
    audit_id = f"AUD-{uuid.uuid4().hex[:12].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Deep sanitize any sensitive fields in details
    safe_details = redact_dict(details or {})
    details_json = json.dumps(safe_details, default=str)

    sql = """
        INSERT INTO security_audit_logs (
            audit_id, timestamp, requester_id, requester_role, action, resource,
            requested_resource_id, authorization_decision, approval_required,
            approver_id, approval_status, execution_status, details_json,
            failure_reason, session_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        audit_id,
        timestamp,
        str(requester_id or "anonymous"),
        str(requester_role or "anonymous"),
        action,
        resource,
        requested_resource_id,
        authorization_decision,
        1 if approval_required else 0,
        approver_id,
        approval_status,
        execution_status,
        details_json,
        failure_reason,
        session_id,
    )

    try:
        if conn is not None:
            conn.execute(sql, params)
        else:
            with connection() as c:
                c.execute(sql, params)
        return audit_id
    except Exception as exc:
        logger.critical("Security Audit Logging FAILURE: %s", exc)
        raise RuntimeError(f"Audit log insertion failed: {exc}") from exc


def query_audit_logs(
    limit: int = 100,
    action: Optional[str] = None,
    requester_id: Optional[str] = None,
    authorization_decision: Optional[str] = None,
    resource: Optional[str] = None,
    requested_resource_id: Optional[str] = None,
    search_term: Optional[str] = None,
    decision: Optional[str] = None,
) -> list[dict]:
    """Retrieve security audit records. Parameterized queries prevent SQL injection."""
    query = "SELECT * FROM security_audit_logs WHERE 1=1"
    params: list[Any] = []

    effective_decision = decision or authorization_decision
    if action:
        query += " AND action = ?"
        params.append(action)
    if requester_id:
        query += " AND requester_id = ?"
        params.append(requester_id)
    if effective_decision:
        query += " AND authorization_decision = ?"
        params.append(effective_decision)
    if resource:
        query += " AND resource = ?"
        params.append(resource)
    if requested_resource_id:
        query += " AND requested_resource_id = ?"
        params.append(requested_resource_id)
    if search_term:
        query += " AND (details_json LIKE ? OR failure_reason LIKE ? OR requested_resource_id LIKE ?)"
        like = f"%{search_term}%"
        params.extend([like, like, like])

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_audit_log_by_id(audit_id: str) -> Optional[dict]:
    """Fetch single audit record by audit_id."""
    with connection() as conn:
        row = conn.execute("SELECT * FROM security_audit_logs WHERE audit_id = ?", (audit_id,)).fetchone()
        return dict(row) if row else None
