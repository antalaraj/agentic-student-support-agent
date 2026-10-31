"""Structured execution traces stored in SQLite (table execution_traces) as JSON.
Secrets (passwords, OTPs, API keys, card numbers) are redacted before anything is stored."""
import json
import re
import uuid
from datetime import datetime, timezone

from database.db import connection

_SENSITIVE_KEYS = re.compile(r"password|passwd|otp|pin|cvv|secret|token|api[_-]?key|credential", re.I)
_REDACT_PATTERNS = [
    (re.compile(r"\b(password|passcode|otp|pin|cvv|cvc)\b(\s*(?:is|=|:)?\s*)\S+", re.I), r"\1\2[REDACTED]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[REDACTED-NUMBER]"),
    (re.compile(r"\b(gsk_|sk-)[A-Za-z0-9_-]{8,}"), "[REDACTED-KEY]"),
    (re.compile(r"\b\d{6}\b"), "[REDACTED-CODE]"),
]


def redact_text(text: str) -> str:
    for pattern, repl in _REDACT_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact_args(value):
    """Recursively redact tool arguments."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if _SENSITIVE_KEYS.search(str(k)) else redact_args(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_args(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def new_execution_id() -> str:
    return f"exec-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


def save_trace(trace: dict) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO execution_traces (execution_id,created_at,student_id,session_id,user_query,status,duration_ms,trace_json)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (trace["execution_id"], trace["timestamp"], trace.get("student_id"), trace.get("session_id"),
             trace.get("user_query"), trace.get("final_status"), trace.get("duration_ms"), json.dumps(trace, default=str)))


def load_traces(limit: int = 100, student_id: str | None = None) -> list[dict]:
    sql, params = "SELECT trace_json FROM execution_traces", []
    if student_id:
        sql, params = sql + " WHERE student_id=?", [student_id]
    with connection() as conn:
        rows = conn.execute(sql + " ORDER BY created_at DESC, rowid DESC LIMIT ?", params + [limit]).fetchall()
    return [json.loads(r["trace_json"]) for r in rows]
