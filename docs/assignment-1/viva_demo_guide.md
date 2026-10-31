# 🎓 Assignment 1: Live Demonstration & Viva Voce Guide

**Project Title**: Intelligent Student Support Agent  
**Module**: Agentic AI Engineering – Assignment 1 · PGDM (BDA / AI & DS), Batch 2025–27  
**Candidate**: Raj Antala ([@antalaraj](https://github.com/antalaraj))  
**Repository**: [agentic-student-support-agent](https://github.com/antalaraj/agentic-student-support-agent)

---

## 1. Executive Overview for Evaluators

The **Intelligent Student Support Agent** is a production-grade, stateful, tool-using AI agent designed to resolve realistic student queries across academic policies, financial records, scholarship tracking, and technical support requests. 

Unlike naive LLM wrappers or simple prompt-chains, the system implements:
1. **LangGraph StateGraph** cyclic orchestration with validated state transitions and safety recursion ceilings.
2. **Context Selection Logic** that strictly restricts prompt injection to a tight character and message budget, retrieving domain knowledge strictly on demand.
3. **Persistent SQLite Long-Term Memory** with heuristic statement extraction, automated PII / credential redaction, and semantic de-duplication.
4. **Deterministic Retrieval-Augmented Generation (RAG)** over institutional regulations with semantic vector distance cut-offs.
5. **Dual Runtime Modes**: Seamless execution under live high-capacity Groq LLMs with automatic exponential backoff rate-limit handling, plus an offline deterministic planner that enables full verification with zero external API dependency.
6. **Defense-in-Depth Observability**: SQLite-backed structured JSON execution traces capturing end-to-end latency, tool parameters, retrieved chunks, and live API token counts.

---

## 2. Recommended Viva Demonstration Script

To systematically demonstrate all core competencies during a live viva or evaluation, follow this sequential walkthrough:

### Step 1: Launch Application & Select Identity
1. Navigate to the `assignment-1/` directory:
   ```bash
   cd assignment-1
   streamlit run app.py
   ```
2. Open the web browser at `http://localhost:8501`.
3. In the sidebar, inspect the student selector and choose:
   **`MIM25002 · Diya Nair`** (Programme: *MBA Business Analytics*, Semester: *2*, Status: *Partially Paid*).

### Step 2: Structured Tool Execution (Database Integration)
* **Prompt**: `What is my current fee status?`
* **Observed Agent Action**:
  - The agent identifies student context `MIM25002`.
  - The model issues a structured tool call to `check_fee_status(student_id='MIM25002')`.
  - The UI renders an active tool chip: `🛠 check_fee_status`.
  - The agent formulates a grounded answer: Total Fee ₹450,000, Paid ₹300,000, Outstanding ₹150,000, Due Date: Nov 15, 2026.

### Step 3: Handbook RAG Semantic Search & Grounded Citation
* **Prompt**: `What is the late fee policy?`
* **Observed Agent Action**:
  - The agent calls `search_policy(query='late fee policy')`.
  - Top relevant chunk retrieved: `hb-2-0` (Section 2: Late Fee Policy).
  - The agent cites the penalty: ₹200 per calendar day of delay, max ₹5,000 cap before semester de-registration.
  - Source chip displayed: `📄 Section 2: Late Fee Policy`.

### Step 4: Complex Policy Scenario (Edge Case)
* **Prompt**: `The payment portal failed on the due date. Can I pay on the next working day without penalty?`
* **Observed Agent Action**:
  - The agent calls `search_policy` with the scenario details.
  - Retrieves Clause 1.5 (`hb-1-1`).
  - Correctly confirms that payment on the subsequent banking day is accepted without late fees upon submitting portal outage proof.

### Step 5: Support Ticket Generation & Data Mutation
* **Prompt**: `Please create a support ticket for my payment portal issue.`
* **Observed Agent Action**:
  - The agent invokes `create_support_ticket(student_id='MIM25002', issue='Payment portal failure...', category='Fee Issue')`.
  - Generates a unique tracking token `TKT-YYYYMMDD-XXXXXX`.
  - In the sidebar, navigate to the **Support Requests** page: confirm the ticket is persisted in SQLite with timestamp and status `Open`.

### Step 6: Long-Term Memory Persistence & Privacy Redaction
* **Prompt**: `Please call me Diya. I am interested in machine learning electives, and my bank OTP is 482913.`
* **Observed Agent Action**:
  - The agent acknowledges the student's name and elective interest.
  - Sensitive credential filter detects `OTP 482913` and scrubs it completely.
  - Click **New Conversation** (clearing local session history).
  - **Follow-up Prompt**: `What did I tell you about my academic preferences in our previous session?`
  - The agent recalls from long-term memory: *Interested in machine learning electives*.
  - Navigate to **Student Information**: verify the memory row exists, and confirm no OTP was ever recorded.

### Step 7: Honest Fallback on Unavailable Information
* **Prompt**: `Does the handbook say anything about hostel accommodation rules?`
* **Observed Agent Action**:
  - The agent executes `search_policy`.
  - ChromaDB returns chunks above the maximum cosine distance cut-off.
  - Status is flagged as `no_evidence`.
  - The agent states honestly that hostel guidelines are not covered in the handbook and directs the student to the Student Services Office.

### Step 8: Observability, Trace Inspection & Metrics
1. Navigate to **Agent Activity / Trace** in the sidebar.
2. Select the most recent execution trace.
3. Show the evaluators:
   - Unique `execution_id` (UUID4).
   - Execution duration (`duration_ms`).
   - Token accounting: prompt input tokens and completion output tokens.
   - Exact LangGraph node traversal: `validate_input → context_selection → agent → tools → finalize`.
   - Tool arguments, returned payload, and RAG chunk metadata.

---

## 3. Anticipated Viva Voce Technical Questions & Model Answers

### Q1: Why use LangGraph instead of standard LangChain chains or AgentExecutor?
> **Answer**: `AgentExecutor` in legacy LangChain was an inflexible black box that obscured state transitions and lacked deterministic control. LangGraph models the agent as a formal directed cyclical state graph (`StateGraph`). This enables explicit validation nodes (`validate_input`), budget-enforced context selection (`context_selection`), controlled reflection cycles between `agent` and `tools`, safe loop ceilings (`MAX_AGENT_STEPS = 4`), and custom finalization hooks (`finalize`) for memory extraction.

### Q2: How does the agent prevent hallucination of student fees or records?
> **Answer**: The agent prompt strictly mandates that student-specific facts must come from tool outputs. Furthermore, the tool execution layer enforces student identity isolation: regardless of any spoofed `student_id` passed in arguments, the tool node enforces the authenticated session student ID (`session_student_id`). If the tool returns `not_found`, the agent informs the student rather than guessing.

### Q3: How is context selection budgeted to keep latency and token costs minimal?
> **Answer**: Instead of sending full chat history and all database tables, `context_selection` enforces strict ceilings:
> - Maximum 6 recent conversation messages (truncated to 600 characters each).
> - Maximum 3 relevant memories fetched using keyword and type-hint scoring.
> - Zero full-database dumps: structured facts are pulled strictly on demand via tool calling.
> - Vector search retrieves only top-3 chunks (≤ 700 chars each) subject to a cosine distance threshold.

### Q4: How is sensitive student information protected from leaking into long-term memory?
> **Answer**: Memory extraction uses a deterministic filtering pipeline. Before any text is parsed for memory extraction, regular expressions scan for passwords, 6-digit OTPs, payment card numbers, CVVs, and API keys. Any sentence containing sensitive patterns is dropped immediately. Furthermore, memory deduplication uses Jaccard similarity (≥ 80% threshold) to prevent unbounded memory growth.

### Q5: How does the system handle Groq API rate limits (TPM / RPM) and outages?
> **Answer**: The agent implements an exponential backoff loop with 2.5-second replenishment waits matching Groq's `x-ratelimit-reset-tokens` header, retrying up to 3 times. If the API is completely unreachable or rate-limited, the system falls back gracefully to a deterministic rule-based `OfflinePlanner`, flagging the response with a degraded fallback banner while maintaining 100% functional uptime.
