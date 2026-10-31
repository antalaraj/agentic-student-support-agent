"""Shared helpers for tools: input validation and a decorator that turns unexpected errors into
structured error results (so the agent can explain them instead of crashing)."""
import functools
import logging
import re
import sqlite3

logger = logging.getLogger(__name__)
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")


def normalise_student_id(student_id) -> str | None:
    if not isinstance(student_id, str):
        return None
    sid = student_id.strip().upper()
    return sid if _ID_RE.match(sid) else None


def err(error_type: str, message: str) -> dict:
    return {"status": "error", "error_type": error_type, "message": message}


def safe_tool(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except sqlite3.Error as exc:
            logger.error("DB error in %s: %s", fn.__name__, exc)
            return err("database_error", "The student database is temporarily unavailable.")
        except Exception as exc:  # last line of defence: never let a tool crash the agent
            logger.exception("Tool %s failed", fn.__name__)
            return err("tool_failure", f"The tool failed unexpectedly ({type(exc).__name__}).")

    return wrapper
