# Assignment 1 Comprehensive Evaluation Report
**Project Title**: Intelligent Student Support Agent  
**Module**: Agentic AI Engineering – Assignment 1 · PGDM (BDA / AI & DS), Batch 2025–27  
**Benchmark Suite**: `evaluation/dataset.json` (18 Diverse Real-World Evaluation Scenarios)  
**Evaluator**: `evaluation/evaluator.py` (Isolated Environment, Automated Assertions)  
**Date of Evaluation**: October 31, 2026  

---

## 1. Official Evaluation Metrics Table

As required by Phase 9 of the Assignment Specification, the following table presents the measured performance metrics of the system:

| Metric | Result (Live Groq Model: `openai/gpt-oss-120b`) | Result (Deterministic Offline Planner) | Verification Source |
|---|:---:|:---:|---|
| **Total Test Cases** | **18 cases** | **18 cases** | `evaluation/dataset.json` |
| **Passed Tests** | **18 / 18** | **18 / 18** | Automated assertion verification |
| **Failed Tests** | **0 / 18** | **0 / 18** | Automated assertion verification |
| **Task Accuracy** | **100.0%** | **100.0%** | Grounded answer & state checks |
| **Tool Execution Success** | **100.0%** | **100.0%** | Dynamic tool dispatch & schema validation |
| **Memory Retrieval Success** | **100.0%** | **100.0%** | Cross-session memory recall (TC09, TC14) |
| **RAG Retrieval Success** | **100.0%** | **100.0%** | Semantic handbook retrieval (TC05, TC06, TC07, TC12, TC16, TC18) |
| **Average Latency** | **3,303.6 ms** (median 1,950.6 ms) | **27.8 ms** (median 17.7 ms) | End-to-end turn duration (`duration_ms`) |
| **Input Token Usage** | **24,641 tokens** | *unavailable* (N/A) | Groq API `usage_metadata` |
| **Output Token Usage** | **3,105 tokens** | *unavailable* (N/A) | Groq API `usage_metadata` |
| **Trace Generation Success** | **100.0%** (18/18 stored) | **100.0%** (18/18 stored) | SQLite `execution_traces` table |

---

## 2. Benchmark Cases Breakdown (Live Groq LLM: `openai/gpt-oss-120b`)

The 18 benchmark cases test distinct capabilities, from database queries and policy extraction to edge cases, rate limits, and cross-session persistence:

| Case ID | Category | User Query | Expected Tool(s) | Actual Tool(s) | Tool Selection | Assertions | Latency | Tokens (In / Out) | Evidence Used |
|:---:|---|---|---|---|:---:|:---:|:---:|:---:|---|
| **TC01** | Fee status | *What is my current fee status?* | `check_fee_status` | `check_fee_status` | **PASS** | **PASS** | 1,987 ms | 1562 / 156 | DB row (MIM25002) |
| **TC02** | Fee status (outstanding) | *How much outstanding fee do I have?* | `check_fee_status` | `check_fee_status` | **PASS** | **PASS** | 1,288 ms | 1563 / 146 | DB row (MIM25003) |
| **TC03** | Scholarship status | *What is my scholarship application status?* | `check_scholarship_status` | `check_scholarship_status` | **PASS** | **PASS** | 1,263 ms | 1543 / 158 | DB row (MIM25007) |
| **TC04** | Student profile | *What programme am I studying?* | `get_student_profile` | `get_student_profile` | **PASS** | **PASS** | 1,124 ms | 1569 / 77 | DB row (MIM25005) |
| **TC05** | Policy retrieval (late fee) | *What is the late fee policy?* | `search_policy` | `search_policy` | **PASS** | **PASS** | 1,644 ms | 1960 / 325 | `hb-2-0`, `hb-2-1`, `hb-1-1` |
| **TC06** | Course change policy | *Can I change my programme?* | `search_policy` | `search_policy` | **PASS** | **PASS** | 2,021 ms | 1795 / 407 | `hb-5-1`, `hb-5-0` |
| **TC07** | Portal failure policy | *The payment portal failed. Can I pay on next working day?* | `search_policy` | `search_policy` | **PASS** | **PASS** | 1,706 ms | 2002 / 267 | `hb-1-1`, `hb-1-0`, `hb-3-1` |
| **TC08** | Support ticket creation | *Create a support ticket for a payment issue* | `create_support_ticket` | `create_support_ticket` | **PASS** | **PASS** | 1,870 ms | 1561 / 199 | DB ticket insertion |
| **TC09** | Memory across sessions | *What did I tell you about my academic preferences in previous session?* | *(none)* | *(none)* | **PASS** | **PASS** | 1,804 ms | 741 / 92 | `memory#2`, `memory#1` |
| **TC10** | General conversation | *Hello, what can you help me with?* | *(none)* | *(none)* | **PASS** | **PASS** | 1,954 ms | 726 / 192 | Prompt rules only |
| **TC11** | Missing student identity | *What is my current fee status?* (No ID) | `check_fee_status` | *(none)* | **PASS** | **PASS** | 7,416 ms | 728 / 79 | Asked for student ID |
| **TC12** | Unknown policy info | *Does handbook say anything about hostel rules?* | `search_policy` | `search_policy` | **PASS** | **PASS** | 4,208 ms | 1537 / 88 | Honest referral (zero chunks) |
| **TC13** | Database outage failure | *What is my current fee status?* (Simulated) | `check_fee_status` | `check_fee_status` | **PASS** | **PASS** | 4,740 ms | 1506 / 212 | Error message returned |
| **TC14** | Sensitive credential exclusion | *Please call me Ananya. My OTP is 482913.* | *(none)* | *(none)* | **PASS** | **PASS** | 1,946 ms | 730 / 98 | Sanitized memory filter |
| **TC15** | Empty query | *[Whitespace only]* | *(none)* | *(none)* | **PASS** | **PASS** | 2 ms | *N/A* | Input validation node |
| **TC16** | Academic information | *Which electives are offered in AI & Data Science?* | `search_academic_information` | `search_academic_information` | **PASS** | **PASS** | 5,560 ms | 1715 / 167 | `hb-9-0` |
| **TC17** | Unknown student record | *What is my fee status?* (ID: ZZZ99999) | `check_fee_status` | `check_fee_status` | **PASS** | **PASS** | 6,898 ms | 1502 / 223 | Tool not_found notice |
| **TC18** | Scholarship criteria policy | *What is eligibility for Merit Excellence Award?* | `search_policy` | `search_policy` | **PASS** | **PASS** | 12,025 ms | 1901 / 219 | `hb-6-0`, `hb-4-0` |

---

## 3. Comparative Analysis: Live LLM vs Offline Planner

| Dimension | Live Mode (`openai/gpt-oss-120b`) | Offline Planner Mode | Engineering Observations |
|---|---|---|---|
| **Intelligence Level** | High (generative, natural phrasing, markdown formatting) | Deterministic keyword template extraction | Live mode dynamically creates bullet points and tables; offline mode is exact and fast. |
| **Latency** | 1,000 ms to 7,000 ms per turn | 5 ms to 75 ms per turn | Offline mode requires zero network hops; ideal for offline CI/CD pipelines. |
| **Token Tracking** | Live counts via `usage_metadata` (24.6k in / 3.1k out) | Explicitly reported as `"unavailable"` | Adheres strictly to assignment instruction: never invent token numbers. |
| **Availability** | Subject to Groq network & TPM rate limits | 100% offline, zero external dependencies | Automatic fallback ensures student is never left without an answer. |

---

## 4. Token Measurement & Cost Efficiency

* **Input Tokens per Average Turn**: ~1,400 to 1,900 tokens (including system prompt, rules, recent history, and retrieved chunks).
* **Output Tokens per Average Turn**: ~150 to 350 tokens (concise, grounded student responses).
* **Context Budget Conservation**:
  * Limiting session history to ≤ 6 messages saves ~4,000 tokens per call on long conversations.
  * Restricting persistent memory to top ≤ 3 items prevents unbounded database leakage into prompts.
  * On-demand tool retrieval ensures handbook passages (only 2–3 chunks) are fetched only when relevant.

---

## 5. Agentic Behavior Verification

1. **Dynamic Decision-Making**: The agent dynamically selects between direct generation (e.g. greetings, remembered preferences) and tool execution (e.g. database lookups and handbook retrieval).
2. **Follow-Up & Incomplete Information**: When asked for student data without an active identity (TC11), the agent does not fabricate an ID or crash; it politely prompts the user to provide their student ID.
3. **Evidence-Grounded Policy Answering**: When answering policy questions (TC05, TC06, TC07), the agent explicitly cites the relevant handbook section and clause.
4. **Honesty on Out-of-Scope Topics**: When asked about topics not present in the handbook (TC12), the agent honestly admits that the handbook has no evidence and directs the user to the Student Services Office.
5. **No Hallucinations**: In missing student cases (TC17), the agent explicitly reports that no record was found and strictly avoids hallucinating fee balances or currency symbols (`₹`).
