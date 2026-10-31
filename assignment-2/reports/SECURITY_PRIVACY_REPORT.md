# Security, Data Privacy, and Threat Modeling Report

**Course:** Agentic AI Engineering (PGDM BDA / AI & DS, Batch 2025–27)  
**Project:** Safe and Production-Aware Student Support Agent  
**Assignment:** Assignment 2  
**Branch:** `feature/assignment-2`  
**Repository:** `antalaraj/agentic-student-support-agent`  
**Date:** October 2026  
**Auditor Roles:** Application Security Engineer, Agentic AI Architect  

---

## 1. Executive Summary

This report establishes the security and privacy foundations implemented for Assignment 2. The transition from Assignment 1 to Assignment 2 transforms an informational prototype with demo identity selection into a secure, production-aware multi-tenant application with:
1. **Cryptographically Secure Authentication:** Salted `bcrypt` hashing (12 rounds) with server-side thread-safe session contexts.
2. **Deterministic Data Privacy and Tenant Ownership:** Enforced strictly in backend application and tool code, preventing LLM prompt overrides or client-side spoofing.
3. **Human-in-the-Loop Sensitive Action Workflows:** Fee payment extensions require administrator review before any protected database mutation occurs.
4. **Permanent, Immutable Security Audit Logging:** Capturing every authentication, authorization, access attempt, approval, and execution event.
5. **Sensitive Credential and Memory Protection:** Automated detection and sanitization of OTPs, passwords, PINs, card numbers, and API keys prior to persistence.

---

## 2. Threat Modeling & Risk Assessment

### 2.1 Threat Actor Profiles
- **Student User (Untrusted / Semi-Trusted):** Attempts to view peers' fee or scholarship data, access unassigned records, submit fraudulent fee extensions, or approve their own requests.
- **Malicious External Actor:** Attempts credential stuffing, SQL injection, session hijacking, or prompt injection to bypass guardrails.
- **Compromised LLM Output (Model Hallucination / Injection):** Untrusted or adversarial user input manipulates the LLM to hallucinate unauthorized actions or invent arguments.

### 2.2 STRIDE Threat Analysis & Applied Mitigations

| STRIDE Threat Category | Potential Attack Vector | Applied Engineering Mitigation | Verification Status |
|---|---|---|---|
| **Spoofing Identity** | User modifies client-side state or passes arbitrary `student_id` in chat query | Server-side `ContextVar` binds authenticated `AuthUser`; private tools pull identity directly from this trusted context and ignore untrusted LLM arguments. | Verified (`test_spoofed_student_id_argument_is_blocked_and_audited`) |
| **Tampering with Data** | Student executes fee due date modification directly or replays past approved requests | Direct tool execution is prohibited for sensitive actions; request enters `PENDING` state; review requires admin authentication; duplicate decisions are rejected atomically in SQLite transaction. | Verified (`test_tampered_or_invalid_request_rejected`) |
| **Repudiation** | User denies submitting a fee extension or administrator denies rejecting a request | Append-only `security_audit_logs` table records actor ID, role, action, target, authorization decision, approval state, and timestamp with parameterized SQL. | Verified (`test_audit_entries_contain_correct_roles_and_ids`) |
| **Information Disclosure** | Student queries peer's fee balance (`"What is MIM25002's fee?"`) or credentials enter memory | `require_student_ownership` validates `requested_student_id == user.student_id`; `sanitizer.py` strips OTPs, passwords, and tokens before SQLite persistence. | Verified (`test_student_a_cannot_read_student_b_fees`, `test_otp_never_remembered`) |
| **Denial of Service** | Flooding SQLite with unindexed or locking transactions | Parameterized queries with indexed foreign keys (`users`, `approval_requests`, `security_audit_logs`); single-transaction connection reuse prevents database deadlocks. | Verified (`test_approved_action_executes_exactly_once`) |
| **Elevation of Privilege** | Student invokes administrative approval endpoint to self-approve extensions | `require_admin` policy checks `user.role == 'admin'`; non-admins are rejected with `AdminPrivilegeRequiredError` and audited as security events. | Verified (`test_student_cannot_approve_own_request`) |

---

## 3. Defense-in-Depth Architecture

```
User Query (Chat / UI)
         │
         ▼
┌───────────────────────────────────────┐
│       Authentication Barrier          │  <- bcrypt (12 rounds), AuthUser session
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│     Context Binding (ContextVar)      │  <- Thread-safe execution context
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│        Agent Reasoning (Graph)        │  <- LangGraph state machine (LLM / Offline)
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│   Backend Tool Authorization Gate     │  <- require_student_ownership(requested_id)
└──────────────────┬────────────────────┘
                   │
      ┌────────────┴────────────┐
      │                         │
[Normal Read/Write]     [Sensitive Action]
      │                         │
      │                         ▼
      │           ┌───────────────────────────┐
      │           │  Approval Workflow Engine │  <- Creates PENDING record
      │           └─────────────┬─────────────┘
      │                         │
      │                         ▼
      │           ┌───────────────────────────┐
      │           │ Human Admin Adjudication  │  <- require_admin(user)
      │           └─────────────┬─────────────┘
      │                         │
      └────────────┬────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│       Atomic SQLite Execution         │  <- Transactional mutation
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│   Security Audit Trail & Sanitizer    │  <- scrubbed payload, credentials excluded
└───────────────────────────────────────┘
```

---

## 4. OWASP Top 10 for LLM Applications Assessment

| OWASP LLM Vulnerability | Repository Defense Implementation | Evaluation Result |
|---|---|---|
| **LLM01: Prompt Injection** | System architecture isolates security policy enforcement completely outside the LLM. Database tools query trusted context, not LLM arguments. | Protected (Bypass attempts blocked in tools) |
| **LLM02: Sensitive Information Disclosure** | `privacy/sanitizer.py` scrubs passwords, OTPs, PINs, card numbers, and API keys before memory storage, traces, or audit persistence. | Protected (100% redaction rate in benchmark) |
| **LLM03: Supply Chain Vulnerabilities** | Minimal, auditable dependencies (`langgraph`, `bcrypt`, `streamlit`, `chromadb`). Offline deterministic planner available without external API dependency. | Audited and verified |
| **LLM04: Data and Model Poisoning** | Demonstration data and handbook policies are read-only and loaded from verified institutional text sources (`student_handbook.txt`). | Protected |
| **LLM05: Improper Output Handling** | Streamlit UI renders responses with markdown sanitization and structured dataframe tables. Direct code execution is disabled. | Protected |
| **LLM06: Excessive Agency** | Domain tools are limited to scoped CRUD operations. Sensitive financial mutations require explicit asynchronous human approval. | Protected (No direct state mutation for approvals) |
| **LLM07: System Prompt Leakage** | Instructions in prompts contain no credentials or private data. Identity verification is handled at the application layer. | Protected |
| **LLM08: Vector and Embedding Weaknesses** | RAG retrieval scopes chunks strictly to institutional handbook categories with fallback keyword matching. | Protected |
| **LLM09: Misinformation** | Source attribution with exact chunk IDs and section citations on all policy and academic answers. | Protected |
| **LLM10: Unbounded Consumption** | Hard recursion limit (25 steps) in LangGraph, input token truncation, and bounded SQLite query limits (`LIMIT 200`). | Protected |

---

## 5. Sample Security Audit Records

The following authentic security audit log entries illustrate the enforcement of privacy, authorization, and approval workflows:

### Entry 1: Allowed Student Self-Access
```json
{
  "audit_id": "AUD-5B418464366A",
  "timestamp": "2026-10-31T13:13:52Z",
  "requester_id": "USR-MIM25001",
  "requester_role": "student",
  "action": "fee.view",
  "resource": "fees",
  "requested_resource_id": "MIM25001",
  "authorization_decision": "ALLOWED",
  "approval_required": 0,
  "approval_status": "N/A",
  "execution_status": "SUCCESS",
  "details_json": "{\"target_student_id\": \"MIM25001\", \"status\": \"Paid\"}",
  "failure_reason": null
}
```

### Entry 2: Denied Cross-Student Access Attempt
```json
{
  "audit_id": "AUD-88F932ACD012",
  "timestamp": "2026-10-31T13:13:52Z",
  "requester_id": "USR-MIM25001",
  "requester_role": "student",
  "action": "cross_student_view_fee_status_blocked",
  "resource": "fees",
  "requested_resource_id": "MIM25002",
  "authorization_decision": "DENIED",
  "approval_required": 0,
  "approval_status": "N/A",
  "execution_status": "BLOCKED",
  "details_json": "{\"authenticated_student\": \"MIM25001\", \"attempted_student\": \"MIM25002\"}",
  "failure_reason": "Cross-tenant isolation enforced: MIM25001 cannot access MIM25002"
}
```

### Entry 3: Human-in-the-Loop Fee Extension Approval
```json
{
  "audit_id": "AUD-7C12DF56B198",
  "timestamp": "2026-10-31T13:13:53Z",
  "requester_id": "USR-ADMIN-01",
  "requester_role": "admin",
  "action": "fee_extension_adjudicated",
  "resource": "approval_requests",
  "requested_resource_id": "REQ-20261031-4FE8A1",
  "authorization_decision": "ALLOWED",
  "approval_required": 1,
  "approval_status": "APPROVED",
  "execution_status": "SUCCESS",
  "details_json": "{\"student_id\": \"MIM25001\", \"decision\": \"APPROVED\", \"previous_due_date\": \"2026-08-15\", \"new_due_date\": \"2026-12-31\", \"reviewed_by\": \"admin\"}",
  "failure_reason": null
}
```

---

## 6. Recommendations & Production Roadmap

1. **Institutional SSO Integration:** Replace local demonstration bcrypt authentication with OpenID Connect (OIDC) / SAML 2.0 institutional Single Sign-On.
2. **Encrypted Field-Level Storage:** Apply envelope encryption with AES-GCM on sensitive columns (`cgpa`, `email`, `outstanding_amount`) at rest.
3. **Hardware Security Module (HSM) Signing:** Sign security audit logs with an asymmetric private key or send audit streams to an immutable remote SIEM (e.g., Datadog, AWS CloudWatch).
