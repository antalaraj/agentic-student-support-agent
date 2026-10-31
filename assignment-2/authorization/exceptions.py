"""Custom authorization and access-control exceptions."""


class SecurityError(Exception):
    """Base class for application security exceptions."""
    pass


class AuthenticationRequiredError(SecurityError):
    """Raised when an unauthenticated user attempts to access a protected resource."""
    def __init__(self, message: str = "Authentication required to access this resource."):
        super().__init__(message)


class AccessDeniedError(SecurityError):
    """Raised when an authenticated user attempts to access an unauthorized resource
    (e.g., cross-student data read/write or privilege escalation).
    """
    def __init__(self, message: str = "Access Denied: You are not authorized to perform this action."):
        super().__init__(message)


class AdminPrivilegeRequiredError(AccessDeniedError):
    """Raised when a non-admin attempts to perform an administrative operation."""
    def __init__(self, message: str = "Administrative privileges required."):
        super().__init__(message)
