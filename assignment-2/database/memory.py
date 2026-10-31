"""Persistent, per-student long-term memory with strict privacy protection.
Extracts durable, non-sensitive student preferences (preferred name, academic interests).
Excludes passwords, OTPs, PINs, card numbers, API keys, and session tokens.
Even in mixed messages (e.g. 'Call me Aarav and my OTP is 482913'), safe facts are
extracted while all sensitive credentials are scrubbed and permanently excluded.
"""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import settings
from config.text_utils import tokenize
from database.db import connection
from privacy.sanitizer import is_sensitive, redact_sensitive_text

logger = logging.getLogger(__name__)

# Patterns for durable student information
_NAME_RE = re.compile(
    r"\b(?:call me|my preferred name is|you can call me|please address me as)\s+([A-Za-z][A-Za-z'-]{1,20})",
    re.I,
)
_PREF_RE = re.compile(
    r"\b(?:I\s+(?:really\s+)?(?:prefer|like|love|enjoy|am interested in|am keen on|want to focus on|would like to focus on)|my\s+(?:interest|focus|preference)\s+is)\s+(.{3,120})",
    re.I,
)
_PROG_RE = re.compile(r"\bI(?:'m| am)\s+(?:studying|enrolled in|pursuing)\s+(.{3,80})", re.I)
_SEM_RE = re.compile(r"\bI(?:'m| am)\s+in\s+(?:the\s+)?(\w+)\s+semester", re.I)
_NOTE_RE = re.compile(r"\b(?:remember that|please remember|keep in mind that)\s+(.{3,150})", re.I)

TYPE_HINTS = {
    "preferred_name": {"name", "call", "address", "who"},
    "programme": {"program", "course", "study", "studying", "enrolled", "specialisation"},
    "semester": {"semester", "sem", "year"},
    "preference": {"preference", "interest", "like", "elective", "favourite", "focus", "told", "mention", "discuss"},
    "note": {"remember", "told", "mention", "note", "discuss", "earlier", "previous", "session"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(text: str) -> str:
    return " ".join(sorted(set(tokenize(text)))) or text.strip().lower()


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def _clean_value(text: str) -> str:
    return re.split(r"\b(?:but|because|since)\b|[.;!?]", text)[0].strip(" ,'\"")


def extract_memories(message: str) -> list[dict]:
    """Extract durable candidate memories from user message.
    Scrubs credentials and sensitive text before extraction.
    Never returns passwords, OTPs, PINs, card numbers, or API keys.
    """
    candidates: list[dict] = []
    if not message:
        return candidates

    # Split into sentences or clauses
    raw_sentences = re.split(r"(?<=[.!?;\n])\s+|\n", str(message))

    for raw_sentence in raw_sentences:
        sentence = raw_sentence.strip()
        if not sentence or sentence.endswith("?"):
            continue

        # If sentence contains a sensitive credential, check if a safe fact can be extracted independently
        # without the credential
        cleaned_sentence = sentence
        if is_sensitive(sentence):
            # Clean out sensitive clauses like "my OTP is 482913", "password is X"
            cleaned_sentence = re.sub(
                r"\b(?:and\s+)?(?:my\s+)?(?:otp|password|pin|passcode|token|key)\s*(?:is|:|=)?\s*\S+",
                "",
                sentence,
                flags=re.I,
            ).strip(" ,.")

        if not cleaned_sentence or is_sensitive(cleaned_sentence):
            continue

        # Preferred name
        m = _NAME_RE.search(cleaned_sentence)
        if m:
            name = m.group(1).strip()
            if not is_sensitive(name) and len(name) >= 2:
                candidates.append({
                    "mem_key": "preferred_name",
                    "mem_type": "preferred_name",
                    "content": f"Preferred name: {name.capitalize()}",
                })

        # Academic preference
        m = _PREF_RE.search(cleaned_sentence)
        if m:
            pref = _clean_value(m.group(1))
            if not is_sensitive(pref) and len(pref) >= 4:
                candidates.append({
                    "mem_key": "preference",
                    "mem_type": "preference",
                    "content": f"Prefers {pref}",
                })

        # Programme
        m = _PROG_RE.search(cleaned_sentence)
        if m:
            prog = _clean_value(m.group(1))
            if not is_sensitive(prog) and len(prog) >= 4:
                candidates.append({
                    "mem_key": "programme",
                    "mem_type": "programme",
                    "content": f"Studies {prog}",
                })

        # Semester
        m = _SEM_RE.search(cleaned_sentence)
        if m:
            sem = m.group(1).lower()
            if not is_sensitive(sem):
                candidates.append({
                    "mem_key": "semester",
                    "mem_type": "semester",
                    "content": f"In {sem} semester",
                })

        # General durable note
        m = _NOTE_RE.search(cleaned_sentence)
        if m:
            note = _clean_value(m.group(1))
            if not is_sensitive(note) and len(note) >= 4:
                candidates.append({
                    "mem_key": f"note_{uuid.uuid4().hex[:6]}",
                    "mem_type": "note",
                    "content": note,
                })

    return candidates


def update_memory_from_message(student_id: str, message: str) -> list[dict]:
    """Extract candidate memories, scrub credentials, deduplicate, and persist to SQLite."""
    if not student_id:
        return []
    candidates = extract_memories(message)
    if not candidates:
        return []

    saved: list[dict] = []
    with connection() as conn:
        for c in candidates:
            # Triple check that no credential accidentally entered the memory content
            if is_sensitive(c["content"]):
                continue

            norm = _norm(c["content"])
            key = c["mem_key"]

            # Keyed updates for single-value facts
            if key in ("preferred_name", "programme", "semester"):
                existing = conn.execute(
                    "SELECT id, norm_content FROM memories WHERE student_id = ? AND mem_key = ?",
                    (student_id, key),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE memories SET content = ?, norm_content = ?, created_at = ? WHERE id = ?",
                        (c["content"], norm, _now(), existing["id"]),
                    )
                    saved.append({"action": "updated", "id": existing["id"], "content": c["content"]})
                    continue

            # Deduplication for notes and preferences (Jaccard >= 0.8)
            existing_rows = conn.execute(
                "SELECT id, norm_content FROM memories WHERE student_id = ?",
                (student_id,),
            ).fetchall()
            if any(_jaccard(norm, r["norm_content"]) >= 0.80 for r in existing_rows):
                continue

            cur = conn.execute(
                """
                INSERT OR IGNORE INTO memories (
                    student_id, mem_key, mem_type, content, norm_content, created_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (student_id, key, c["mem_type"], c["content"], norm, _now()),
            )
            if cur.rowcount > 0:
                saved.append({"action": "inserted", "id": cur.lastrowid, "content": c["content"]})

    return saved


def retrieve_relevant_memories(student_id: str, query: str, limit: int = 3) -> list[dict]:
    """Retrieve memories strictly belonging to student_id, scored by relevance to query."""
    if not student_id:
        return []
    tokens = set(tokenize(query or ""))
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM memories WHERE student_id = ? ORDER BY created_at DESC",
            (student_id,),
        ).fetchall()

    scored = []
    for r in rows:
        d = dict(r)
        # Double check no sensitive data in memory output
        if is_sensitive(d["content"]):
            continue

        score = 0
        mem_tokens = set(tokenize(d["content"]))
        overlap = len(tokens & mem_tokens)
        score += overlap * 2

        # Check type hints
        hints = TYPE_HINTS.get(d["mem_type"], set())
        if tokens & hints:
            score += 3

        scored.append((score, d))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:limit]]


def list_student_memories(student_id: str) -> list[dict]:
    """List all memories for a student."""
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM memories WHERE student_id = ? ORDER BY created_at DESC",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_memory(memory_id: int, student_id: str) -> bool:
    """Delete a memory entry with student ownership validation."""
    with connection() as conn:
        cur = conn.execute(
            "DELETE FROM memories WHERE id = ? AND student_id = ?",
            (memory_id, student_id),
        )
        return cur.rowcount > 0


def clear_student_memories(student_id: str) -> int:
    """Clear all memories for a student."""
    with connection() as conn:
        cur = conn.execute("DELETE FROM memories WHERE student_id = ?", (student_id,))
        return cur.rowcount


# Aliases for compatibility
list_memories = list_student_memories
clear_memories = clear_student_memories
