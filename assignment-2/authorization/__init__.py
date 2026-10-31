# authorization package for assignment-2
from authorization.exceptions import (
    AccessDeniedError,
    AdminPrivilegeRequiredError,
    AuthenticationRequiredError,
    SecurityError,
)
from authorization.service import (
    authorize_action,
    can_access_student_record,
    require_admin,
    require_authenticated_user,
    require_student_ownership,
)

__all__ = [
    "SecurityError",
    "AuthenticationRequiredError",
    "AccessDeniedError",
    "AdminPrivilegeRequiredError",
    "require_authenticated_user",
    "require_student_ownership",
    "require_admin",
    "can_access_student_record",
    "authorize_action",
]
