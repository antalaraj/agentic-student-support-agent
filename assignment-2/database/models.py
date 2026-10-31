"""SQLite schema for Assignment 2 (Safe and Production-Aware Student Support Agent).
Preserves all Assignment 1 tables and adds tables for Users & Authentication,
Approval Workflows, and Security Audit Logging.
"""

SUPPORT_CATEGORIES = ["fee_payment", "scholarship", "academic", "examination", "technical", "general"]

SCHEMA = """
-- ─────────────────────────────────────────────────────────────────────────────
-- Core Academic & Student Tables (Preserved from Assignment 1)
-- ─────────────────────────────────────────────────────────────────────────────
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
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Assignment 2 Security Extensions: Users, Roles, Approvals, & Audit
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL,           -- 'student' or 'admin'
    student_id    TEXT UNIQUE REFERENCES students(student_id),
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS approval_requests (
    request_id       TEXT PRIMARY KEY,
    student_id       TEXT NOT NULL REFERENCES students(student_id),
    action_type      TEXT NOT NULL,       -- 'fee_extension_request', 'fee_concession_request'
    payload_json     TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'PENDING',  -- 'PENDING', 'APPROVED', 'REJECTED'
    requested_at     TEXT NOT NULL,
    reviewed_by      TEXT REFERENCES users(user_id),
    reviewed_at      TEXT,
    decision_reason  TEXT,
    executed_at      TEXT,
    execution_result TEXT
);

CREATE TABLE IF NOT EXISTS security_audit_logs (
    audit_id               TEXT PRIMARY KEY,
    timestamp              TEXT NOT NULL,
    requester_id           TEXT NOT NULL,
    requester_role         TEXT NOT NULL,
    action                 TEXT NOT NULL,
    resource               TEXT NOT NULL,
    requested_resource_id  TEXT,
    authorization_decision TEXT NOT NULL,   -- 'ALLOWED' or 'DENIED'
    approval_required      INTEGER NOT NULL DEFAULT 0,
    approver_id            TEXT,
    approval_status        TEXT NOT NULL DEFAULT 'N/A', -- 'N/A', 'PENDING', 'APPROVED', 'REJECTED'
    execution_status       TEXT NOT NULL,   -- 'SUCCESS', 'DENIED', 'PENDING_APPROVAL', 'FAILED', 'BLOCKED'
    details_json           TEXT,
    failure_reason         TEXT,
    session_id             TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_approval_student ON approval_requests(student_id);
CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON security_audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON security_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_requester ON security_audit_logs(requester_id);
"""

DROP_ALL = """
DROP TABLE IF EXISTS security_audit_logs;
DROP TABLE IF EXISTS approval_requests;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS execution_traces;
DROP TABLE IF EXISTS memories;
DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS scholarships;
DROP TABLE IF EXISTS fees;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS seed_meta;
"""
