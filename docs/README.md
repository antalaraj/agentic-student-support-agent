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
└── assignment-2/                      # Assignment 2 forward-looking documentation
    └── ASSIGNMENT_2_ROADMAP.md        # Multi-agent architecture, supervisor-worker design & roadmap
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

### 3. Assignment 2 Roadmap
* **[Assignment 2 Roadmap](assignment-2/ASSIGNMENT_2_ROADMAP.md)**: Strategic roadmap outlining the upcoming Multi-Agent Collaborative System, hierarchical supervisor-worker pattern, human-in-the-loop controls, and hybrid RAG.
