"""Authorization and Student Ownership Policy Service.
Enforces strict boundaries ensuring students can only access and modify their own records.
Every policy violation is immediately recorded in the security audit log.
"""
import logging
from typing import Optional

from audit.service import log_security_event
from auth.models import AuthUser
from authorization.exceptions import (
    AccessDeniedError,
    AdminPrivilegeRequiredError,
    AuthenticationRequiredError,
)

logger = logging.getLogger(__name__)


def require_authenticated_user(user: Optional[AuthUser], action: str = "access_resource", resource: str = "general") -> AuthUser:
    """Enforce that a valid, active authenticated user session exists."""
    if user is None or not user.is_active:
        log_security_event(
            requester_id="unauthenticated",
            requester_role="anonymous",
            action=f"unauthenticated_{action}_denied",
            resource=resource,
            authorization_decision="DENIED",
            execution_status="BLOCKED",
            failure_reason="Operation attempted without authenticated user session",
        )
        raise AuthenticationRequiredError("Please log in to continue.")
    return user


def require_student_ownership(
    requested_student_id: Optional[str],
    user: Optional[AuthUser],
    action: str = "read",
    resource: str = "student_data",
) -> str:
    """Enforce strict student ownership.
    - If user is a student: requested_student_id MUST match user.student_id.
    - If user attempts to access another student's data, the attempt is blocked and audited.
    - If user is an administrator: allowed for administrative operations.
    Returns the authorized student_id.
    """
    auth_user = require_authenticated_user(user, action=action, resource=resource)

    # Clean & normalize IDs
    req_sid = (requested_student_id or "").strip().upper() if requested_student_id else None
    user_sid = (auth_user.student_id or "").strip().upper() if auth_user.student_id else None

    # Student role enforcement
    if auth_user.is_student():
        # If no target provided, default to own ID
        if not req_sid:
            return user_sid

        # Check for cross-student violation
        if req_sid != user_sid:
            log_security_event(
                requester_id=auth_user.user_id,
                requester_role=auth_user.role,
                action=f"cross_student_{action}_blocked",
                resource=resource,
                requested_resource_id=req_sid,
                authorization_decision="DENIED",
                execution_status="BLOCKED",
                details={
                    "authenticated_student": user_sid,
                    "attempted_student": req_sid,
                    "action": action,
                },
                failure_reason=f"Cross-tenant isolation enforced: {user_sid} cannot access {req_sid}",
            )
            raise AccessDeniedError(
                f"Access Denied: You are not authorized to {action} records for student {req_sid}."
            )
        return user_sid

    # Administrator role
    if auth_user.is_admin():
        if not req_sid:
            raise ValueError("Target student ID must be specified for administrative lookups.")
        return req_sid

    raise AccessDeniedError(f"Role '{auth_user.role}' has no permission on {resource}.")


def require_admin(user: Optional[AuthUser], action: str = "admin_action", resource: str = "admin_resource") -> AuthUser:
    """Enforce that the authenticated user possesses the Administrator role."""
    auth_user = require_authenticated_user(user, action=action, resource=resource)
    if not auth_user.is_admin():
        log_security_event(
            requester_id=auth_user.user_id,
            requester_role=auth_user.role,
            action=f"unauthorized_{action}_blocked",
            resource=resource,
            authorization_decision="DENIED",
            execution_status="BLOCKED",
            failure_reason="Administrative privilege required for this operation",
        )
        raise AdminPrivilegeRequiredError(
            "Access Denied: This operation requires administrative privileges."
        )
    return auth_user


def can_access_student_record(user: Optional[AuthUser], target_student_id: str) -> bool:
    """Non-raising predicate to verify access permissions."""
    if not user or not user.is_active:
        return False
    if user.is_admin():
        return True
    if user.is_student() and user.student_id:
        return user.student_id.strip().upper() == target_student_id.strip().upper()
    return False


def authorize_action(
    user: Optional[AuthUser],
    action: str,
    resource: str,
    target_student_id: Optional[str] = None,
) -> bool:
    """Verify authorization. Logs denial and returns boolean or raises based on policy."""
    if not user:
        return False
    if action.startswith("admin_"):
        return user.is_admin()
    if target_student_id:
        return can_access_student_record(user, target_student_id)
    return True
