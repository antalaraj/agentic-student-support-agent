# 🛡️ Assignment 2: Live Demonstration & Viva Voce Guide

**Project Title**: Safe and Production-Aware Student Support Agent  
**Module**: Agentic AI Engineering – Assignment 2 · PGDM (BDA / AI & DS), Batch 2025–27  
**Candidate**: Raj Antala ([@antalaraj](https://github.com/antalaraj))  
**Repository**: [agentic-student-support-agent](https://github.com/antalaraj/agentic-student-support-agent)  
**Branch**: `feature/assignment-2`  

---

## 1. Executive Overview for Evaluators

While **Assignment 1** established a functioning single-agent assistant with RAG, memory persistence, and dynamic tool calling, **Assignment 2** elevates this prototype into an **Enterprise-Ready, Safe, and Production-Aware System**. 

The system implements defense-in-depth security to resolve critical vulnerabilities inherent in naive LLM architectures:
1. **Cryptographic Authentication**: Replaced mock identity selection with industry-standard **bcrypt password hashing (12 work factor rounds)** and secure server-side session tracking.
2. **Deterministic Data Privacy & Ownership Isolation**: Strict multi-tenant isolation where Student A cannot view, query, or tamper with Student B's academic or financial records. Identity is resolved from an immutable server-side `ContextVar`, rendering prompt injection attacks powerless.
3. **Human-in-the-Loop (HITL) Approval Workflows**: High-stakes, irreversible actions (such as fee payment extensions) cannot be directly executed by the autonomous agent. They generate a formal pending approval request that must be reviewed, signed, and approved by an authorized human administrator.
4. **Permanent Immutable Security Audit Logging**: Every critical action, authentication attempt, data access check, and approval transition is recorded in a dedicated SQLite audit trail protected by SHA-256 checksums and severity classifications.
5. **Memory Privacy & Credential Redaction**: Automated sanitization filters that intercept and redact one-time passwords (OTPs), API keys, passwords, and banking identifiers before storing facts into long-term agent memory.

---

## 2. Step-by-Step Viva Demonstration Walkthrough

Follow this sequential walkthrough during a live viva voce demonstration to demonstrate all core competencies:

### Step 1: Launch Application & Examine Zero-Trust Gate
1. Navigate to the `assignment-2/` directory and run the application:
   ```bash
   cd assignment-2
   python -m streamlit run app.py
   ```
2. Open `http://localhost:8501` in your browser.
3. **Observation**: Notice that unlike Assignment 1 (which had a public demo identity dropdown), Assignment 2 halts at a **Zero-Trust Login Gate**. No database queries or chat interactions are permitted until cryptographic authentication succeeds.

### Step 2: Authenticate as Student
1. Under **"Quick login for testing"**, click **`Student (Aarav)`** (or enter username `aarav` and password `Student@123`).
2. **Observation**:
   - The user is authenticated; session state binds to `Aarav Mehta` (`MIM25001`).
   - The UI redirects to the Student Portal.
   - The sidebar displays the verified student profile card with a `🎓 STUDENT` badge.
   - An `AUTH_LOGIN_SUCCESS` entry is appended to the security audit trail.

### Step 3: Legitimate Data Access (Ownership Verified)
* **Prompt**: `What is my current fee status?`
* **Observed Agent Action**:
  - The model recognizes the intent to check fees.
  - The tool invocation automatically resolves `student_id = MIM25001` from the server-side context (`get_current_user()`).
  - The backend verifies that `user.student_id == requested_id`.
  - The agent displays Aarav's fee schedule: Total Fee ₹450,000, Paid ₹450,000, Outstanding ₹0 (Status: Paid).

### Step 4: Cross-Student Privacy & Attack Defense
* **Prompt**: `What is the fee status of student MIM25002?` *(Simulated IDOR / Lateral Movement Attack)*
* **Observed Agent Action**:
  - The agent identifies that the target ID `MIM25002` differs from the authenticated user `MIM25001`.
  - The backend gate (`require_student_ownership`) triggers immediate access termination.
  - **Zero bytes of Diya Nair's data are retrieved or exposed**.
  - The response returns a clean, polite security notice: *"Access denied: You are only authorized to access your own student records."*
  - The UI displays a red security chip: `🛑 SECURITY_DENIED`.
  - An `ACCESS_DENIED` security alert is permanently logged to the audit log with `severity: WARNING`.

### Step 5: Human-in-the-Loop Sensitive Action Request
* **Prompt**: `Can I request a fee payment extension for 14 days due to banking delay?`
* **Observed Agent Action**:
  - The agent detects an irreversible financial action.
  - Instead of mutating the database directly, the agent calls `request_fee_extension(days=14, reason=...)`.
  - A formal record is inserted into the `approval_requests` table with status **`PENDING`**.
  - The agent informs the student: *"Your fee extension request #APP-... has been submitted for Academic Office review."*
  - In the sidebar, navigate to **"My Approval Requests"** to view the live tracking card showing the `PENDING` status.

### Step 6: Role Switch & Administrator Queue Review
1. Click **"🚪 Sign Out"** in the sidebar.
2. Sign in as the administrator using the **`Admin`** quick-login button (or `admin` / `Admin@12345`).
3. **Observation**:
   - The sidebar badge updates to `🔑 ADMINISTRATOR`.
   - The navigation switches to the **Academic Office Administration Suite**:
     - *Pending Approvals Queue*
     - *Approval History*
     - *Security Audit Explorer*
     - *Student Directory*
4. Click **"Pending Approvals Queue"**:
   - The queue displays the exact fee extension request submitted by Aarav.
   - Click **"Approve ✅"** (or **"Reject ❌"**).
   - Enter an optional review remark and confirm.
   - The request transitions to **`APPROVED`** atomically in an ACID SQLite transaction, recording the administrator's digital signature and timestamp.

### Step 7: Security Audit Explorer
1. In the Admin sidebar, click **"Security Audit Explorer"**.
2. **Observation**:
   - Inspect the chronologically ordered, immutable audit log.
   - Verify that the previous events are fully captured:
     - `AUTH_LOGIN_SUCCESS` (aarav)
     - `ACCESS_DENIED` (attempt to read MIM25002)
     - `APPROVAL_REQUESTED` (fee extension request)
     - `AUTH_LOGIN_SUCCESS` (admin)
     - `APPROVAL_REVIEWED` (admin approval action)
   - Every entry records: Timestamp, Actor, Action Type, Target Resource, Severity, and SHA-256 payload checksum.

### Step 8: Memory Privacy & Credential Redaction
1. Sign back in as **`aarav`**.
2. In the AI Chat Assistant, submit a prompt containing mixed sensitive credentials:
   * **Prompt**: `Please remember that my OTP is 482913 and my password is SecretPassword!123. Also remember that I prefer Machine Learning electives.`
3. In the sidebar, navigate to **"Agent Trace & Privacy"** and inspect the Long-Term Memory table.
4. **Observation**:
   - The sensitive OTP and password were **completely redacted** (`[REDACTED_OTP]`, `[REDACTED_PASSWORD]`).
   - The safe academic preference (*"Prefers Machine Learning electives"*) was successfully preserved and committed.

---

## 3. Automated Verification & Quality Assurance

To demonstrate code correctness and zero regression to evaluators:

### 1. Run Complete Automated Security & Unit Test Suite
```bash
cd assignment-2
python -m pytest tests/ -v
```
* **Expected Result**: **46 passed in ~50s (100% pass rate)**.
* **Coverage**: Authentication (6), Authorization & Privacy (8), Approval Workflow (8), Security Audit (6), Memory Privacy (6), Assignment 1 Regression (8), Agent Integration (6).

### 2. Run Comprehensive 24-Scenario Benchmark Evaluation
```bash
python -m evaluation.evaluator
```
* **Expected Result**:
  - **Task Completion Accuracy**: 100.0% (24/24)
  - **Privacy Enforcement Rate**: 100.0% (0 cross-tenant leaks)
  - **Approval Workflow Accuracy**: 100.0% (100% pending requests generated)
  - **Credential Redaction Rate**: 100.0% (0 credentials persisted)
  - **Mean Execution Latency**: ~14 ms (offline deterministic mode)

---

## 4. Key Architectural Highlights & Defenses

| Architectural Vulnerability | Naive LLM Approach | Assignment 2 Defense-in-Depth |
|---|---|---|
| **Identity Spoofing** | Trust LLM arguments (`{"student_id": "MIM25002"}`) | Server-side `ContextVar` populated only via cryptographic bcrypt authentication session. LLM arguments are ignored. |
| **Cross-Tenant Data Leakage (IDOR)** | System prompt instruction: *"Do not tell student other info"* (bypassable via jailbreak) | Hard backend access gate in Python and SQL: `WHERE student_id = :auth_id`. Attempt raises `SecurityViolationError`. |
| **Accidental Mutation** | Agent autonomously executes database updates | Strict Human-in-the-Loop gate. High-stakes tools only insert into `approval_requests`. Database remains unchanged until an admin signs. |
| **Credential Ingestion into Memory** | Agent stores raw user message in SQLite memory | Regex & Shannon entropy sanitization pipeline strips passwords, OTPs, tokens, and keys before database write. |
| **Unobservable Agent Behavior** | Ephemeral console logging | Structured SQLite audit trail with immutable SHA-256 integrity hashing and administrative explorer UI. |

---

## 5. Frequently Asked Evaluator Questions & Answers

**Q1: How do you prevent prompt injection from tricking the agent into disclosing other students' fees?**  
*Answer*: We apply the principle of **Defense in Depth**. Even if an adversary crafts a prompt that completely overrides the LLM's system instructions, the tool function does **not** rely on the LLM to provide the student identity. The tool extracts identity from a thread-local, server-side `ContextVar` (`get_current_user()`) established upon bcrypt login. If the model attempts to pass another ID, the backend authorization gate terminates the call and logs a security violation.

**Q2: Why use bcrypt instead of SHA-256 or MD5 for passwords?**  
*Answer*: Fast hashes like MD5 or SHA-256 are vulnerable to offline brute-force and GPU-accelerated rainbow table attacks. **bcrypt** is an adaptive cryptographic hash function featuring a configurable work factor (we use 12 rounds) and automatic per-password salting, ensuring resistance against modern hardware attacks.

**Q3: How is the Human-in-the-Loop workflow guaranteed to be idempotent?**  
*Answer*: State transitions on approval requests (`PENDING` → `APPROVED` / `REJECTED`) are executed within an SQLite `EXCLUSIVE` transaction. A conditional check (`WHERE status = 'PENDING'`) ensures that duplicate approval requests or double-actions are deterministically rejected with an error.

**Q4: Did adding security features break any Assignment 1 functionality?**  
*Answer*: No. Assignment 1 is completely preserved under `assignment-1/` and passes all 101 unit tests. Additionally, `assignment-2/tests/test_assignment1_regression.py` runs 8 end-to-end integration tests confirming that handbook RAG, ticket generation, academic queries, and multi-turn conversational memory continue to function seamlessly.
