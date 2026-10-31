# Assignment 2 Automated Testing and Quality Assurance Report

**Course:** Agentic AI Engineering (PGDM BDA / AI & DS, Batch 2025–27)  
**Project:** Safe and Production-Aware Student Support Agent  
**Assignment:** Assignment 2  
**Branch:** `feature/assignment-2`  
**Repository:** `antalaraj/agentic-student-support-agent`  
**Test Framework:** Pytest 9.0.1 (Python 3.13.14, win32)  
**Date:** October 2026  
**QA Lead:** Application Security & QA Engineer  

---

## 1. Executive Summary

A comprehensive automated test suite of **46 tests** was created and executed for Assignment 2. The test suite validates authentication, tenant ownership, human-in-the-loop approvals, security audit logging, sensitive credential memory exclusion, end-to-end LangGraph agent integration, and Assignment 1 regression safety.

### Test Execution Summary
- **Total Tests:** 46
- **Passed:** **46 (100.0%)**
- **Failed:** 0
- **Duration:** 45.58s
- **Test Isolation:** 100% of tests run against isolated, temporary SQLite databases (`tempfile.mkdtemp`), preventing any contamination of development or demonstration state.

---

## 2. Test Suite Breakdown

### 2.1 Authentication & Session Integrity (`test_auth.py`)
| Test Name | Test Objective | Assertion | Result |
|---|---|---|---|
| `test_valid_student_login` | Verify valid student credentials authenticate successfully | User object returned, student role, correct student ID | **PASSED** |
| `test_valid_admin_login` | Verify valid administrator credentials authenticate | User object returned, admin role, student_id is None | **PASSED** |
| `test_invalid_username_rejected` | Verify non-existent username fails authentication | Returns None, failure audited as DENIED | **PASSED** |
| `test_invalid_password_rejected` | Verify incorrect password fails authentication | Returns None, failure audited as DENIED | **PASSED** |
| `test_passwords_never_stored_in_plaintext` | Verify bcrypt hashes are stored in SQLite `users` table | Password hashes start with `$2b$12$`, plaintext absent | **PASSED** |
| `test_unauthenticated_access_denied` | Verify operations without login trigger `AuthenticationRequiredError` | Exception raised, audited as DENIED | **PASSED** |
| `test_session_identity_immutability` | Verify `AuthUser` dataclass is frozen and immutable | Mutating `user.role` raises `FrozenInstanceError` | **PASSED** |

### 2.2 Privacy & Student Ownership Isolation (`test_privacy_ownership.py`)
| Test Name | Test Objective | Assertion | Result |
|---|---|---|---|
| `test_student_accesses_own_profile` | Authenticated student reads own profile | Returns student's own name, programme, CGPA | **PASSED** |
| `test_student_accesses_own_fees` | Authenticated student reads own fee balance | Returns student's fee balance, status, due date | **PASSED** |
| `test_student_accesses_own_scholarship` | Authenticated student reads own scholarship | Returns student's scholarship application status | **PASSED** |
| `test_student_accesses_own_tickets` | Authenticated student lists own support tickets | Returns only tickets associated with student ID | **PASSED** |
| `test_student_a_cannot_read_student_b_fees` | Student A requests Student B's fees | Raises `AccessDeniedError`, audited as DENIED | **PASSED** |
| `test_student_a_cannot_read_student_b_profile` | Student A requests Student B's profile | Raises `AccessDeniedError`, audited as DENIED | **PASSED** |
| `test_student_a_cannot_read_student_b_scholarship` | Student A requests Student B's scholarship | Raises `AccessDeniedError`, audited as DENIED | **PASSED** |
| `test_student_a_cannot_create_ticket_for_student_b` | Student A creates ticket for Student B | Raises `AccessDeniedError`, audited as DENIED | **PASSED** |
| `test_spoofed_student_id_argument_is_blocked_and_audited` | Injected tool argument with mismatched ID | Ownership policy overrides argument, logs DENIED | **PASSED** |
| `test_cross_student_memory_isolated` | Student A attempts to retrieve Student B's memories | Returns empty list; zero cross-tenant memory leakage | **PASSED** |
| `test_admin_can_access_student_records_with_audit` | Admin reads student record for academic operations | Allowed for admin, audited with admin actor role | **PASSED** |

### 2.3 Sensitive Action Approval Lifecycle (`test_approval_workflow.py`)
| Test Name | Test Objective | Assertion | Result |
|---|---|---|---|
| `test_sensitive_action_creates_pending_request` | Student requests fee payment extension | Request inserted with status `PENDING`, ID returned | **PASSED** |
| `test_pending_request_does_not_modify_fees` | Validate that pending requests make zero fee changes | Student fee due date remains identical in SQLite | **PASSED** |
| `test_authorized_admin_can_approve` | Administrator reviews and approves request | Status updated to `APPROVED`, due date modified | **PASSED** |
| `test_approved_action_executes_exactly_once` | Re-approving already resolved request | Second approval raises `ValueError`, no double execution | **PASSED** |
| `test_authorized_admin_can_reject` | Administrator reviews and rejects request | Status updated to `REJECTED`, fee due date unchanged | **PASSED** |
| `test_student_cannot_approve_own_request` | Student attempts to self-approve extension | Raises `AdminPrivilegeRequiredError`, audited | **PASSED** |
| `test_student_cannot_approve_other_student_request` | Student attempts to approve peer's extension | Raises `AdminPrivilegeRequiredError`, audited | **PASSED** |
| `test_tampered_or_invalid_request_rejected` | Reviewing non-existent request ID | Raises `ValueError`, tamper attempt audited | **PASSED** |

### 2.4 Security Audit Trail (`test_audit_logging.py`)
| Test Name | Test Objective | Assertion | Result |
|---|---|---|---|
| `test_allowed_read_action_logged` | Successful fee query records audit event | Audit log exists with `ALLOWED` decision, `SUCCESS` | **PASSED** |
| `test_denied_cross_student_action_logged` | Blocked cross-student attempt records audit | Audit log exists with `DENIED` decision, `BLOCKED` | **PASSED** |
| `test_approval_and_rejection_audit_records` | Administrative approvals and rejections logged | Distinct audit entries for approvals and rejections | **PASSED** |
| `test_sensitive_credentials_redacted_in_audit_details` | Injected password/OTP in audit payload | Sensitive values redacted to `[REDACTED_PASSWORD]` | **PASSED** |
| `test_audit_entries_contain_correct_roles_and_ids` | Requester ID, role, target resource recorded | Accurate forensic attributes in audit trail | **PASSED** |

### 2.5 Sensitive Memory & Credential Redaction (`test_memory_privacy.py`)
| Test Name | Test Objective | Assertion | Result |
|---|---|---|---|
| `test_preferred_name_and_preference_remembered` | Non-sensitive student preferences stored | Name and elective preferences persisted in SQLite | **PASSED** |
| `test_otp_never_remembered` | User message contains 6-digit OTP | OTP absent from memory table and memory retrieval | **PASSED** |
| `test_password_never_remembered` | User message contains password string | Password absent from memory table and retrieval | **PASSED** |
| `test_api_key_never_remembered` | User message contains API key / Bearer token | Token absent from memory table and retrieval | **PASSED** |
| `test_mixed_message_safely_extracts_name_and_strips_otp` | Message has both name and OTP | Name extracted and saved; OTP completely stripped | **PASSED** |
| `test_sensitive_values_scrubbed_from_text` | Regex sanitizer scrub capabilities | Credentials scrubbed to `[REDACTED_*]` placeholders | **PASSED** |

### 2.6 Agent Security Integration (`test_agent_security_integration.py`)
| Test Name | Test Objective | Assertion | Result |
|---|---|---|---|
| `test_agent_answers_own_fees_with_auth_context` | End-to-end agent turn with authenticated student | Agent answers fee status using `check_fee_status` | **PASSED** |
| `test_agent_blocks_cross_student_query` | Query targeting another student's ID | Agent returns Access Denied notice; no peer fee leaked | **PASSED** |
| `test_agent_fee_extension_creates_pending_request` | Query asking for fee payment extension | Agent creates pending approval request; informs user | **PASSED** |
| `test_agent_policy_rag_works` | General institutional handbook query | Agent answers from handbook with section citation | **PASSED** |
| `test_agent_memory_recall_without_tools` | User asks about remembered name/preferences | Agent answers from system prompt memory without tools | **PASSED** |

### 2.7 Assignment 1 Regression Safety (`test_assignment1_regression.py`)
| Test Name | Test Objective | Assertion | Result |
|---|---|---|---|
| `test_regression_all_six_tools_operational` | Validate all 6 original Assignment 1 tools | Profile, fee, scholarship, ticket, policy, academic | **PASSED** |
| `test_regression_rag_retrieval_finds_handbook_sections` | RAG finds relevant handbook chunks | Top-k chunks returned with section metadata | **PASSED** |
| `test_regression_rag_returns_no_evidence_for_out_of_scope_query` | RAG handles out-of-scope queries | Low-confidence retrieval returns `no_evidence` | **PASSED** |
| `test_regression_agent_execution_trace_logged` | Execution traces logged per turn | Record written to `execution_traces` in SQLite | **PASSED** |

---

## 3. Bug Fix and Engineering Hardening Log

During the test-driven development of Assignment 2, several critical engineering edge cases were detected and permanently resolved:

1. **SQLite Deadlock During Approvals:**
   - *Issue:* `review_approval_request` opened a transactional write connection, and inside that transaction called `log_security_event()`, which attempted to open a second write connection on the same thread, causing a SQLite database lock.
   - *Fix:* Added optional `conn: Optional[sqlite3.Connection] = None` to `log_security_event()`, allowing transactional methods to reuse their existing connection.
2. **Intent Scoring Ambiguity:**
   - *Issue:* "What is the late fee policy?" matched "fee" before "policy".
   - *Fix:* Implemented weighted intent scoring with a policy score multiplier, ensuring policy handbook queries beat bare financial keywords.
3. **Regex Word Boundary Handling for Credentials:**
   - *Issue:* Inputs with `"User password is P@ss123"` were missed by regex patterns matching only `:` or `=`.
   - *Fix:* Updated pattern to `\b(password|passwd|pwd|passcode)\s*(?:is|:|=)?\s*\S+`, reliably detecting spoken credential phrases.
4. **Mixed Credential Subclause Scrubbing:**
   - *Issue:* Mixed messages like `"Call me Aarav and my OTP is 482913"` risked either saving the OTP or dropping the entire message.
   - *Fix:* Clause-level regex splitting scrubs credential phrases independently while preserving valid name and interest extractions.
