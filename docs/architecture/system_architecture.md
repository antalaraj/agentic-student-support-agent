# 🏛 System Architecture: Intelligent Student Support Agent

This document provides a comprehensive technical overview of the architecture, data flows, and state management underpinning the **Intelligent Student Support Agent**.

---

## 1. Architectural Principles

1. **Stateful Graph Orchestration**: Built on LangGraph `StateGraph` with explicit nodes, conditional edges, typed state schemas, and safe termination criteria.
2. **Deterministic Context Budgeting**: Strict character and message quotas preventing context window overflow and token waste.
3. **Identity & Data Isolation**: Strict session-level separation between students ensuring zero cross-tenant data leakage.
4. **Resilient Dual-Engine Execution**: Seamless transition between cloud LLMs (Groq API) and local deterministic offline planning.
5. **Defense-in-Depth Observability**: Complete JSON audit trails for every agent turn, capturing timing, tools, RAG chunks, and token metrics.

---

## 2. Core Subsystems

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          Streamlit User Interface                         │
│   (Chat Assistant · Student Records · Support Requests · Traces · Eval)  │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │ Invokes run_agent()
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         LangGraph StateGraph Engine                       │
│                                                                           │
│  [START]                                                                  │
│     │                                                                     │
│     ▼                                                                     │
│  [validate_input] ────────► (If query empty/invalid) ───► [finalize] ──► [END]
│     │                                                                     │
│     ▼ (If valid)                                                          │
│  [context_selection] ◄────► [SQLite: Persistent Student Memory]           │
│     │                                                                     │
│     ▼                                                                     │
│  [agent (LLM / Planner)] ◄─► [Groq API / Offline Fallback Engine]         │
│     │                                                                     │
│     ├─── (tool_calls requested) ──► [tools node]                          │
│     │                                   │                                 │
│     │                                   ├──► [SQLite: Students/Fees/Tkts] │
│     │                                   └──► [ChromaDB: Policy Chunks]    │
│     │                                   │                                 │
│     │◄──────────────────────────────────┘ (ToolMessages injected)         │
│     │                                                                     │
│     └─── (final answer ready / step limit reached) ──► [finalize] ──► [END]
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │ Writes execution trace
                                      ▼
                        [SQLite: execution_traces]
```

---

## 3. Subsystem Breakdown

### 3.1 LangGraph StateGraph & Execution Cycle
- **State Schema (`AgentState`)**:
  - `messages`: List of LangChain base messages (`HumanMessage`, `AIMessage`, `ToolMessage`, `SystemMessage`).
  - `student_id`: Active session student identifier (e.g. `MIM25002`).
  - `query`: Raw user input query.
  - `intent`: Detected intent tag (e.g., `fee`, `policy`, `greeting`, `ticket`).
  - `tools_used`: List of invoked tool names.
  - `evidence_sources`: Retrieved handbook chunk identifiers.
  - `memories_used`: Retrieved persistent memory IDs.
  - `new_memories`: Extracted facts to persist.
  - `step_count`: Counter for agent-tool loop iterations (capped at `MAX_AGENT_STEPS = 4`).
  - `status`: Execution status (`success`, `degraded_fallback`, `needs_input`, `error`).

### 3.2 Tool Registry & Execution Layer
Six tools implemented in `assignment-1/tools/`:
1. `get_student_profile(student_id)`: Fetches student demographics, academic status, and advisor.
2. `check_fee_status(student_id)`: Retrieves fee structure, payments, balance, and due date.
3. `check_scholarship_status(student_id)`: Queries scholarship applications, awarded sums, and remarks.
4. `create_support_ticket(student_id, issue, category)`: Validates categories, redacts credentials, generates unique `TKT-YYYYMMDD-XXXXXX` identifiers, and inserts into SQLite.
5. `search_policy(query)`: Performs semantic vector retrieval across institutional policy handbook chunks.
6. `search_academic_information(query)`: Queries academic curricula, course offerings, and placement records.

### 3.3 Context Selection & Token Budgeting
To optimize latency and minimize token usage, the `context_selection` node filters what enters the prompt:
- **History Ceiling**: At most the last 6 turns (`MAX_HISTORY_MESSAGES = 6`), truncated to 600 characters each.
- **Memory Ceiling**: At most 3 memories (`MAX_MEMORIES = 3`), scored by keyword overlap with query.
- **Dynamic Retrieval**: Domain records and handbook sections are never pre-injected; they are queried dynamically via tools.

### 3.4 Persistent SQLite Memory
- Implemented in `assignment-1/database/memory.py`.
- **Extraction**: Deterministic pattern matching (`call me X`, `I prefer Y`, `remember that Z`).
- **Privacy Filter**: Regular expressions strip passwords, OTPs, credit cards, CVVs, and API keys before extraction.
- **De-duplication**: 80% Jaccard word-similarity threshold prevents repetitive memory entries.
- **Isolation**: Memory queries enforce `student_id = ?`, preventing cross-student leaks.

### 3.5 ChromaDB Retrieval-Augmented Generation (RAG)
- Implemented in `assignment-1/rag/`.
- Text chunks (grouped clauses ≤ 700 characters) ingested into ChromaDB.
- Embedder: `sentence-transformers/all-MiniLM-L6-v2` with deterministic lexical hashing fallback (`hashing-fallback-384`) when running in offline or resource-constrained environments.
- Distance threshold (`max_retrieval_distance = 0.62` for MiniLM, `0.80` for hashing) drops irrelevant chunks, prompting the agent to return `no_evidence` rather than hallucinate.

### 3.6 Observability & Trace Schema
Every turn writes an execution trace to the `execution_traces` SQLite table:
```json
{
  "execution_id": "42e2a868-...",
  "timestamp": "2026-10-31T12:15:56Z",
  "student_id": "MIM25002",
  "query": "What is my current fee status?",
  "intent": "fee",
  "node_path": ["validate_input", "context_selection", "agent", "tools", "agent", "finalize"],
  "tools_used": ["check_fee_status"],
  "evidence_sources": [],
  "memories_used": [],
  "duration_ms": 1987.4,
  "model": "openai/gpt-oss-120b",
  "token_usage": {
    "input_tokens": 1562,
    "output_tokens": 156,
    "total_tokens": 1718
  },
  "status": "success",
  "error": null
}
```
