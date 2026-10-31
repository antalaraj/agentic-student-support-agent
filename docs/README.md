# 📚 Documentation Index: Agentic Student Support Agent

Welcome to the comprehensive documentation hub for the **Agentic Student Support Agent** repository.

---

## 📂 Documentation Directory Structure

```
docs/
├── README.md                          # Documentation index (this file)
├── architecture/                      # Architectural specifications & technical designs
│   ├── system_architecture.md         # Detailed subsystem architecture & design principles
│   └── diagrams.md                    # Visual Mermaid diagrams (StateGraph, ER model, memory, RAG)
├── assignment-1/                      # Assignment 1 verification deliverables & reports
│   ├── ASSIGNMENT_1_AUDIT_REPORT.md   # Official requirement-by-requirement audit & sign-off
│   ├── TESTING_REPORT.md              # 101-test automated suite results & bug fix log
│   ├── EVALUATION_REPORT.md           # 18-case benchmark evaluation metrics & analysis
│   └── viva_demo_guide.md             # Evaluator viva presentation & live demonstration script
└── assignment-2/                      # Assignment 2 deliverables, reports & guides
    ├── ASSIGNMENT_2_AUDIT_REPORT.md   # Official requirement-by-requirement audit & sign-off
    ├── SECURITY_PRIVACY_REPORT.md     # In-depth security architecture & threat model analysis
    ├── TESTING_REPORT.md              # 46-test automated security suite results (100% passing)
    ├── EVALUATION_REPORT.md           # 24-case benchmark evaluation metrics & privacy analysis
    ├── ASSIGNMENT_1_VS_ASSIGNMENT_2.md# Detailed architectural comparison matrix
    ├── viva_demo_guide.md             # Evaluator viva presentation & live demonstration script
    └── ASSIGNMENT_2_ROADMAP.md        # Forward-looking roadmap & technical specifications
```

---

## 📑 Core Documentation Documents

### 1. System Architecture & Design
* **[System Architecture](architecture/system_architecture.md)**: Details the LangGraph `StateGraph`, context selection budget, tool execution layer, persistent SQLite memory, ChromaDB vector store, Groq LLM integration with retry/backoff, and execution trace schema.
* **[Architectural Diagrams](architecture/diagrams.md)**: Visual Mermaid diagrams representing the agent cycle, database relational schema, memory lifecycle, and policy retrieval pipelines.

### 2. Assignment 1 Reports & Deliverables
* **[Audit Report](assignment-1/ASSIGNMENT_1_AUDIT_REPORT.md)**: Comprehensive audit confirming 100% compliance against all official requirements.
* **[Testing Report](assignment-1/TESTING_REPORT.md)**: Full report covering 101 passing pytest tests across unit, integration, memory, tool, and assignment scenario suites.
* **[Evaluation Report](assignment-1/EVALUATION_REPORT.md)**: Benchmark evaluation report covering 18 real-world cases with 100% task accuracy and 100% tool selection success.
* **[Viva & Demo Guide](assignment-1/viva_demo_guide.md)**: Recommended walkthrough and anticipated technical Q&A for viva voce evaluators.

### 3. Assignment 2 Reports & Deliverables
* **[Assignment 2 Audit Report](assignment-2/ASSIGNMENT_2_AUDIT_REPORT.md)**: Official requirement-by-requirement compliance verification and architectural audit.
* **[Security & Threat Model Report](assignment-2/SECURITY_PRIVACY_REPORT.md)**: Deep dive into bcrypt 12-round authentication, multi-tenant ownership enforcement, Human-in-the-Loop approvals, and immutable audit logging.
* **[Testing Report](assignment-2/TESTING_REPORT.md)**: Complete report covering 46 automated unit, security, integration, and regression tests (100% passing).
* **[Evaluation Report](assignment-2/EVALUATION_REPORT.md)**: Repeatable 24-case benchmark results covering task accuracy, zero-leak privacy enforcement, and credential redaction.
* **[Assignment 1 vs. Assignment 2 Matrix](assignment-2/ASSIGNMENT_1_VS_ASSIGNMENT_2.md)**: Side-by-side comparison of capabilities, schemas, threat models, and UI changes.
* **[Viva & Demo Guide](assignment-2/viva_demo_guide.md)**: Step-by-step evaluator demonstration script and technical Q&A for Assignment 2.
* **[Assignment 2 Roadmap](assignment-2/ASSIGNMENT_2_ROADMAP.md)**: Strategic roadmap outlining future multi-agent collaborative workflows and supervisor-worker orchestration.
