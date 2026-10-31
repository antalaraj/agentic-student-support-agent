"""Privacy and sensitive credential protection utilities.
Detects, redacts, and excludes passwords, OTPs, PINs, card numbers, API keys,
and tokens from memory, traces, audit logs, and tool arguments.
"""
import re
from typing import Any

SENSITIVE_PATTERNS = [
    r"\b(password|passcode|passwd|pwd|secret|token|api[ _-]?key|credential)s?\b",
    r"\b(otp|one[- ]time[- ]password|pin|cvv|cvc)\b",
    r"\b(?:\d[ -]?){13,19}\b",                          # Payment cards
    r"\b\d{6}\b",                                       # 6-digit OTP codes
    r"\b(gsk_|sk-|eyJh|bearer\s+)[A-Za-z0-9_\-\.]{8,}", # API keys & tokens
    r"\b(card number|account number|ifsc|upi pin|net ?banking)\b",
]

_SENSITIVE_RE = re.compile("|".join(SENSITIVE_PATTERNS), re.IGNORECASE)

# Targeted regex for redaction
_REDACT_PATTERNS = [
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[REDACTED_CARD]"),
    (re.compile(r"\b(otp\s*(?:is|:|=)?\s*)\d{6}\b", re.I), r"\1[REDACTED_OTP]"),
    (re.compile(r"\b(?<!\w)\d{6}(?!\w)\b"), "[REDACTED_CODE]"),
    (re.compile(r"\b(password|passwd|pwd|passcode)\s*(?:is|:|=)?\s*\S+", re.I), r"\1: [REDACTED_PASSWORD]"),
    (re.compile(r"\b(gsk_|sk-)[A-Za-z0-9_-]{8,}", re.I), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.I), r"\1[REDACTED_TOKEN]"),
]

SENSITIVE_FIELD_NAMES = {
    "password", "password_hash", "otp", "pin", "cvv", "cvc", "secret", "token",
    "api_key", "card_number", "access_token", "refresh_token", "auth_token"
}


def is_sensitive(text: str) -> bool:
    """Return True if text contains credentials, OTPs, card numbers, or auth tokens."""
    return bool(_SENSITIVE_RE.search(str(text or "")))


def redact_sensitive_text(text: str) -> str:
    """Scrub sensitive credentials and numbers from text."""
    if not text:
        return ""
    result = str(text)
    for pattern, replacement in _REDACT_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_dict(data: Any) -> Any:
    """Recursively scrub sensitive keys and credential patterns from dictionaries."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_FIELD_NAMES:
                cleaned[k] = "[REDACTED_SECRET]"
            else:
                cleaned[k] = redact_dict(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_dict(item) for item in data]
    elif isinstance(data, str):
        return redact_sensitive_text(data)
    return data
