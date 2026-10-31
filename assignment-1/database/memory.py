"""Persistent, per-student long-term memory in SQLite.

Design (simple on purpose, easy to explain in a viva):
  EXTRACT : rule-based patterns pull out only durable, non-sensitive facts from a student's own
            statements (preferred name, programme, semester, stated preferences, "remember that ...").
  FILTER  : any sentence that looks sensitive (password, OTP, PIN, card number, API key...) is dropped
            before extraction. Questions and temporary statements never match the patterns.
  DEDUPE  : keyed facts (name/programme/semester) are updated in place; other facts are skipped if an
            identical or very similar memory (Jaccard >= 0.8) already exists.
  RETRIEVE: only memories relevant to the current query are returned (keyword overlap + type hints).
"""
import re
from datetime import datetime, timezone

from config import settings
from config.text_utils import tokenize
from database.db import connection

SENSITIVE_PATTERNS = [
    r"\b(password|passcode|passwd|otp|one[- ]time|pin|cvv|cvc|secret|token|api[ _-]?key|credential)s?\b",
    r"\b(?:\d[ -]?){13,19}\b",          # card-like numbers
    r"\b\d{6}\b",                       # 6-digit codes (typical OTPs)
    r"\b(gsk_|sk-)[A-Za-z0-9_-]{8,}",   # API-key-looking strings
    r"\b(card number|account number|ifsc|upi pin|net ?banking)\b",
]
_SENSITIVE_RE = re.compile("|".join(SENSITIVE_PATTERNS), re.IGNORECASE)

# words in a question that point to a memory type
TYPE_HINTS = {
    "preferred_name": {"name", "call", "address", "who"},
    "programme": {"program", "course", "study", "studying", "enrolled", "specialisation"},
    "semester": {"semester", "sem", "year"},
    "preference": {"preference", "interest", "like", "elective", "favourite", "focus", "told", "mention", "discuss"},
    "note": {"remember", "told", "mention", "note", "discuss", "earlier", "previous", "session"},
}

_NAME_RE = re.compile(r"\b(?:call me|my preferred name is|you can call me|please address me as)\s+([A-Za-z][A-Za-z'-]{1,20})", re.I)
_PREF_RE = re.compile(r"\bI\s+(?:really\s+)?(?:prefer|like|love|enjoy|am interested in|am keen on|want to focus on|would like to focus on)\s+(.{3,120})", re.I)
_PROG_RE = re.compile(r"\bI(?:'m| am)\s+(?:studying|enrolled in|pursuing)\s+(.{3,80})", re.I)
_SEM_RE = re.compile(r"\bI(?:'m| am)\s+in\s+(?:the\s+)?(\w+)\s+semester", re.I)
_NOTE_RE = re.compile(r"\b(?:remember that|please remember|keep in mind that)\s+(.{3,150})", re.I)


def is_sensitive(text: str) -> bool:
    return bool(_SENSITIVE_RE.search(text or ""))


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
    """Return candidate memories [{'mem_key','mem_type','content'}] from one user message."""
    candidates: list[dict] = []
    for sentence in re.split(r"(?<=[.!?;\n])\s+|\n", message or ""):
        sentence = sentence.strip()
        if not sentence or sentence.endswith("?") or is_sensitive(sentence):
            continue
        if m := _NAME_RE.search(sentence):
            candidates.append({"mem_key": "preferred_name", "mem_type": "preferred_name",
                               "content": f"Preferred name: {m.group(1).capitalize()}"})
        if m := _PROG_RE.search(sentence):
            candidates.append({"mem_key": "programme", "mem_type": "programme",
                               "content": f"Programme (as told by student): {_clean_value(m.group(1))}"})
        if m := _SEM_RE.search(sentence):
            candidates.append({"mem_key": "semester", "mem_type": "semester",
                               "content": f"Semester (as told by student): {m.group(1)}"})
        if m := _PREF_RE.search(sentence):
            value = _clean_value(m.group(1))
            if value:
                candidates.append({"mem_key": "", "mem_type": "preference", "content": f"Preference: {value}"})
        if m := _NOTE_RE.search(sentence):
            value = _clean_value(m.group(1))
            if value:
                candidates.append({"mem_key": "", "mem_type": "note", "content": f"Note: {value}"})
    return [c for c in candidates if not is_sensitive(c["content"])]


def save_memories(student_id: str, candidates: list[dict]) -> list[dict]:
    """Persist candidates with de-duplication. Returns [{'id','content','action'}] for what changed."""
    saved: list[dict] = []
    if not student_id:
        return saved
    with connection() as conn:
        for c in candidates:
            norm = _norm(c["content"])
            if c["mem_key"]:  # keyed fact: update in place
                row = conn.execute("SELECT id, content FROM memories WHERE student_id=? AND mem_key=?",
                                   (student_id, c["mem_key"])).fetchone()
                if row:
                    if row["content"] != c["content"]:
                        conn.execute("UPDATE memories SET content=?, norm_content=? WHERE id=?",
                                     (c["content"], norm, row["id"]))
                        saved.append({"id": row["id"], "content": c["content"], "action": "updated"})
                    continue
            else:  # free-form fact: skip duplicates / near-duplicates
                existing = conn.execute("SELECT norm_content FROM memories WHERE student_id=? AND mem_key=''",
                                        (student_id,)).fetchall()
                if any(_jaccard(norm, r["norm_content"]) >= 0.8 for r in existing):
                    continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO memories (student_id,mem_key,mem_type,content,norm_content,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (student_id, c["mem_key"], c["mem_type"], c["content"], norm, _now()))
            if cur.rowcount:
                saved.append({"id": cur.lastrowid, "content": c["content"], "action": "created"})
    return saved


def update_memory_from_message(student_id: str, message: str) -> list[dict]:
    return save_memories(student_id, extract_memories(message))


def retrieve_relevant_memories(student_id: str, query: str, limit: int | None = None) -> list[dict]:
    """Return only memories that overlap with the query (never the whole memory table)."""
    limit = limit or settings.MAX_MEMORIES
    if not student_id:
        return []
    raw_words = set(re.findall(r"[a-z0-9]+", (query or "").lower()))
    q_tokens = set(tokenize(query)) | (raw_words & {"who", "name", "prefer", "preferences", "preference"})
    with connection() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM memories WHERE student_id=?", (student_id,))]
    scored = []
    is_recall = bool(re.search(r"\b(remember|earlier|previous|tell you|told you|know about me)\b", (query or "").lower()))
    for r in rows:
        overlap = len(q_tokens & set(tokenize(r["content"])))
        hint = len(q_tokens & TYPE_HINTS.get(r["mem_type"], set()))
        base = 1 if is_recall else 0
        score = overlap * 2 + hint * 3 + base
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    top = [r for _, r in scored[:limit]]
    if top:
        with connection() as conn:
            conn.executemany("UPDATE memories SET last_used_at=? WHERE id=?", [(_now(), r["id"]) for r in top])
    return [{"id": r["id"], "type": r["mem_type"], "content": r["content"]} for r in top]


def list_memories(student_id: str) -> list[dict]:
    with connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, mem_type, content, created_at, last_used_at FROM memories WHERE student_id=? ORDER BY id",
            (student_id,))]


def delete_memory(memory_id: int, student_id: str) -> bool:
    with connection() as conn:
        return conn.execute("DELETE FROM memories WHERE id=? AND student_id=?", (memory_id, student_id)).rowcount > 0


def clear_memories(student_id: str) -> int:
    with connection() as conn:
        return conn.execute("DELETE FROM memories WHERE student_id=?", (student_id,)).rowcount
