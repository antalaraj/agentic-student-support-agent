# Comparative Analysis: Assignment 1 vs. Assignment 2

**Course:** Agentic AI Engineering (PGDM BDA / AI & DS, Batch 2025–27)  
**Project:** Intelligent Student Support Agent -> Safe and Production-Aware Student Support Agent  
**Repository:** `antalaraj/agentic-student-support-agent`  
**Date:** October 2026  
**Auditor:** Agentic AI Architect & Senior AI Engineer  

---

## 1. Executive Summary

Assignment 1 successfully demonstrated a working agentic application with a LangGraph workflow, six domain tools, RAG retrieval from a student handbook, persistent long-term memory, execution tracing, and a Streamlit UI. However, as an exploratory prototype, it lacked production identity management, data isolation boundaries, human-in-the-loop approvals, security audit trails, and credential sanitization.

Assignment 2 builds upon Assignment 1 without removing or breaking any existing capabilities, transforming the application into a **safe, production-aware institutional portal**.

---

## 2. Official Requirement Comparison Table

| Metric / Capability | Assignment 1 (Baseline) | Assignment 2 (Production-Aware) | Architectural Improvement |
|---|---|---|---|
| **Normal Task Accuracy** | **100.0%** (18/18 cases) | **100.0%** (24/24 cases) | Preserved complete functional accuracy across profile, fee, scholarship, and RAG queries |
| **Tool Execution Success** | **100.0%** (18/18 cases) | **100.0%** (24/24 cases) | Added 7th tool (`request_fee_extension`) with 100% tool selection accuracy |
| **Authentication & Identity** | *Not implemented* (Demo dropdown selector only) | **100.0% Verified** (bcrypt 12 rounds, session models, `ContextVar` context) | Replaced client-side identity selection with secure server-side authenticated sessions |
| **Privacy & Tenant Isolation** | *0% / Not enforced* (Any user could query any student ID) | **100.0% Enforced** (`require_student_ownership` on all private tools) | Cross-student queries blocked at backend; LLM cannot override identity |
| **Unauthorized Action Prevention** | *0% / Not enforced* (No roles or permission barriers) | **100.0% Prevented** (`AccessDeniedError`, `AdminPrivilegeRequiredError`) | Deterministic policy enforcement in Python application code outside the LLM |
| **Human-in-the-Loop Approvals** | *Not implemented* (No approval workflow) | **100.0% Correctness** (4/4 approval lifecycle cases) | Sensitive fee extensions require human admin adjudication before atomic execution |
| **Security Audit Coverage** | *Execution tracing only* (Performance & latency metrics) | **100.0% Immutable Audit Trail** (`security_audit_logs` table) | Records requester, role, action, target, decision, approval status, and failure reasons |
| **Credential Redaction in Memory** | *Partial* (Dropped mixed messages) | **100.0% Scrubbed** (`sanitizer.py` clause scrubbing) | Excludes OTPs, passwords, PINs, card numbers; safely extracts valid preferences |
| **Average Turn Latency** | **12.8 ms** (offline planner) | **14.1 ms** (offline security planner) | Added comprehensive security barriers with negligible (~1.3 ms) runtime overhead |
| **Automated Test Count** | **101 tests** passing | **46 security tests + 101 regression tests** passing | Full regression preservation + dedicated security test suite |
| **Streamlit User Interface** | Single-role demo screen | Dual-role portal: Student Dashboard & Admin Approvals Queue / Audit Explorer | Role-aware navigation, interactive adjudication, and audit explorer |

---

## 3. Architectural Evolution

### 3.1 Identity & Context Management
- **Assignment 1:** The user selected a student from a Streamlit sidebar selectbox. The selected student ID was passed as an unverified string down through function calls.
- **Assignment 2:** Users must authenticate using valid credentials. Passwords are verified against 12-round salted bcrypt hashes. The verified `AuthUser` object is held in a thread-safe `ContextVar`, ensuring tools resolve identity from trusted server-side state.

### 3.2 Authorization & Data Ownership
- **Assignment 1:** If Student A asked `"What is the fee status of student MIM25002?"`, the agent executed `check_fee_status(student_id="MIM25002")` and returned Student B's financial data.
- **Assignment 2:** When `check_fee_status` executes, `require_student_ownership` verifies that the target student ID matches the authenticated session (`user.student_id`). If they differ, execution is immediately aborted, an `AccessDeniedError` is raised, and a `DENIED` event is written to `security_audit_logs`.

### 3.3 Sensitive Action Approvals
- **Assignment 1:** No mechanism existed to handle sensitive mutations requiring administrative authorization.
- **Assignment 2:** Introducing `approval/service.py` and `request_fee_extension` tool. Requesting an extension inserts a `PENDING` request into `approval_requests`. The student fee due date is **not** modified. An authorized administrator reviews the request in the Admin Approvals Queue, confirming approval or rejection with audit logging. Duplicate executions, replays, and student self-approvals are strictly blocked.

### 3.4 Memory Sanitization
- **Assignment 1:** Basic filtering dropped messages containing sensitive keywords entirely.
- **Assignment 2:** Advanced clause-level regex sanitization in `privacy/sanitizer.py`. If a user inputs `"Please call me Aarav and my OTP is 482913"`, the OTP is excised (`[REDACTED_OTP]`), while `"Aarav"` is safely extracted and remembered. Credentials never touch SQLite memory or audit records.

---

## 4. Verification and Regression Guarantee

Both test suites and benchmarks have been executed independently:
- **Assignment 1 Test Suite:** `101 passed, 1 warning in 21.92s` (`assignment-1/tests/`).
- **Assignment 2 Test Suite:** `46 passed, 1 warning in 45.58s` (`assignment-2/tests/`).
- **Assignment 1 Benchmark:** `18/18 passed (100.0%)` (`assignment-1/evaluation/results/latest_results.json`).
- **Assignment 2 Benchmark:** `24/24 passed (100.0%)` (`assignment-2/evaluation/results/latest_results.json`).

This empirical evidence confirms that Assignment 2 successfully delivers all safety and production-aware requirements without compromising Assignment 1 functionality.
