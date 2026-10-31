# 🚀 Assignment 2: Technical Roadmap & Architecture Preview

**Project**: Agentic Student Support Agent  
**Module**: Agentic AI Engineering – Assignment 2 · PGDM (BDA / AI & DS), Batch 2025–27  
**Status**: **Planned / Pending Implementation**  
**Development Branch**: `feature/assignment-2`

---

## 1. Vision & Objectives

While **Assignment 1** established a robust single-agent architecture with dynamic tool calling, RAG, and memory persistence, **Assignment 2** expands the system into an **Autonomous Multi-Agent Collaborative System**. 

The goal of Assignment 2 is to solve complex, multi-domain student workflows that require:
1. Cross-domain specialization (Academic Advising, Financial Aid, Administration, Mental Wellbeing).
2. Autonomous task decomposition, delegation, and inter-agent communication.
3. Hierarchical supervision with debate, consensus, and self-reflection loops.
4. Human-in-the-loop approval workflows for irreversible actions (e.g., scholarship disbursements, fee concessions, course withdrawals).
5. Comprehensive end-to-end multi-agent evaluation benchmarks.

---

## 2. Multi-Agent System Architecture (Planned)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Supervisor Orchestrator Agent                   │
│          (Task Decomposition · Routing · Synthesis · Guardrails)       │
└────────┬───────────────────┬───────────────────┬───────────────────────┘
         │                   │                   │
         ▼                   ▼                   ▼
┌──────────────────┐┌──────────────────┐┌──────────────────┐
│  Academic Agent  ││  Financial Agent ││  Support Agent   │
│  - Degree audits ││  - Fee schedules ││  - Ticket triage │
│  - Prerequisites ││  - Scholarships  ││  - Grievances    │
│  - Grade appeals ││  - Refund claims ││  - Escalations   │
└────────┬─────────┘└────────┬─────────┘└────────┬─────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Shared Infrastructure & Guardrail Services               │
│  - Shared Blackboard State                                             │
│  - Multi-Document Hierarchical Vector Store (Hybrid BM25 + Dense)      │
│  - Human-in-the-Loop Approval Queue                                    │
│  - Distributed Tracing & Inter-Agent Message Telemetry                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Architectural Pillars for Assignment 2

### 3.1 Hierarchical Supervisor-Worker Pattern
- A central **Supervisor Agent** inspects incoming complex inquiries (e.g., *"I want to take a semester break, defer my tuition payment, and preserve my scholarship eligibility"*).
- The Supervisor decomposes the problem into sub-tasks and delegates to domain-specialist subagents.
- Subagents execute concurrently or sequentially, posting findings back to a shared state graph.
- The Supervisor synthesizes the final comprehensive advisory notice.

### 3.2 Human-in-the-Loop (HITL) Gateways
- High-stakes administrative actions require explicit authorization:
  - Applying emergency fee concessions.
  - Overriding prerequisite blocks.
  - De-registering courses.
- The agent halts execution, surfaces an approval card with full evidence to the human administrator, and resumes upon digital signature.

### 3.3 Enhanced RAG (Hybrid & Multi-Document)
- Scale RAG beyond a single handbook to multiple corpora:
  - Examination Regulations.
  - Placement & Internship Guidelines.
  - Code of Conduct & Disciplinary Procedures.
  - Course Catalogues & Syllabi.
- Implement **Hybrid Search (BM25 Lexical + Dense Vector Embeddings)** with Reciprocal Rank Fusion (RRF) and Re-ranking (e.g. BGE-Reranker).

### 3.4 Multi-Agent Benchmark & Evaluation Framework
- Expand evaluation dataset to 50+ multi-step, multi-agent scenarios.
- Quantify:
  - Task completion accuracy across multi-turn delegation.
  - Routing precision to specialized subagents.
  - Inter-agent communication efficiency (token overhead vs. accuracy).
  - Agreement rate between autonomous agent decisions and human-expert baselines.

---

## 4. Development Milestones & Phasing

| Phase | Milestone | Description | Target Branch |
|---|---|---|---|
| **Phase 1** | **Scaffolding & Schema** | Define multi-agent state schemas, supervisor routing graph, and communication channels | `feature/assignment-2` |
| **Phase 2** | **Specialist Subagents** | Implement Academic, Financial, and Grievance agents with custom toolsets | `feature/assignment-2` |
| **Phase 3** | **HITL & Memory v2** | Add human approval interrupts, multi-tenant memory sharing, and hybrid RAG | `feature/assignment-2` |
| **Phase 4** | **Testing & Evaluation** | Build multi-agent pytest suite, 50-case benchmark, and trace visualizer | `feature/assignment-2` |
| **Phase 5** | **Review & Merging** | Final audit, benchmark verification, PR review, and merge into `main` | `feature/assignment-2` → `main` |

---

## 5. Branching & Git Workflow

All Assignment 2 code will be developed strictly on the `feature/assignment-2` branch:

```bash
# Checkout feature branch
git checkout feature/assignment-2

# Develop in the assignment-2/ workspace
cd assignment-2

# Run development tests
pytest tests/
```
