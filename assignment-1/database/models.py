"""SQLite schema. All tables are created with IF NOT EXISTS so initialisation is idempotent."""

SUPPORT_CATEGORIES = ["fee_payment", "scholarship", "academic", "examination", "technical", "general"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL,
    programme       TEXT NOT NULL,
    semester        INTEGER NOT NULL,
    cgpa            REAL,
    attendance_pct  REAL,
    advisor         TEXT,
    batch           TEXT,
    is_demo_data    INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS fees (
    student_id          TEXT PRIMARY KEY REFERENCES students(student_id),
    total_fee           INTEGER NOT NULL,
    paid_amount         INTEGER NOT NULL,
    outstanding_amount  INTEGER NOT NULL,
    payment_status      TEXT NOT NULL,
    due_date            TEXT,
    last_payment_date   TEXT
);
CREATE TABLE IF NOT EXISTS scholarships (
    student_id          TEXT PRIMARY KEY REFERENCES students(student_id),
    scholarship_name    TEXT NOT NULL,
    application_status  TEXT NOT NULL,
    amount              INTEGER,
    remarks             TEXT
);
CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id   TEXT PRIMARY KEY,
    student_id  TEXT NOT NULL REFERENCES students(student_id),
    category    TEXT NOT NULL,
    issue       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Open',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    mem_key        TEXT NOT NULL,
    mem_type       TEXT NOT NULL,
    content        TEXT NOT NULL,
    norm_content   TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    last_used_at   TEXT,
    UNIQUE (student_id, norm_content)
);
CREATE TABLE IF NOT EXISTS execution_traces (
    execution_id  TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    student_id    TEXT,
    session_id    TEXT,
    user_query    TEXT,
    status        TEXT,
    duration_ms   REAL,
    trace_json    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seed_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

DROP_ALL = """
DROP TABLE IF EXISTS execution_traces; DROP TABLE IF EXISTS memories; DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS scholarships; DROP TABLE IF EXISTS fees; DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS seed_meta;
"""
