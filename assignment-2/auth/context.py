"""Thread-safe and async-safe authenticated execution context.
Enables backend tools and services to access the verified, server-side
authenticated user session without relying on untrusted LLM arguments.
"""
from contextvars import ContextVar
from typing import Optional

from auth.models import AuthUser

_CURRENT_USER: ContextVar[Optional[AuthUser]] = ContextVar("current_user", default=None)


def set_current_user(user: Optional[AuthUser]):
    """Set the authenticated user for the current execution turn."""
    return _CURRENT_USER.set(user)


def reset_current_user(token=None) -> None:
    """Reset the authenticated user context."""
    if token is not None:
        try:
            _CURRENT_USER.reset(token)
            return
        except ValueError:
            pass
    _CURRENT_USER.set(None)


def get_current_user() -> Optional[AuthUser]:
    """Retrieve the authenticated user for the current execution turn."""
    return _CURRENT_USER.get()
