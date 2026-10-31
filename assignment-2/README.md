# 🤖 Assignment 2: Multi-Agent Student Support System

**Module**: Agentic AI Engineering – Assignment 2 · PGDM (BDA / AI & DS), Batch 2025–27  
**Status**: **Prepared for Development · Pending Implementation**  
**Development Branch**: `feature/assignment-2`

---

## 1. Scope & Purpose

Assignment 2 builds upon the successful foundation established in **Assignment 1** (`assignment-1/`), transitioning from a single-agent architecture into a **Collaborative Multi-Agent Ecosystem**.

The system will feature:
* **Supervisor-Worker Hierarchy**: A lead triage orchestrator coordinating domain-specific worker agents.
* **Specialist Subagents**:
  * 📚 **Academic Advising Agent**: Curricular planning, credit transfers, elective recommendations, prerequisites.
  * 💰 **Financial Services Agent**: Complex fee structures, scholarship evaluation, payment rescheduling, hardship funds.
  * 🛠 **Administrative & Grievance Agent**: Formal complaint handling, escalations, support ticket workflows.
* **Shared Multi-Agent Blackboard State**: Distributed message passing with typed state annotations.
* **Human-in-the-Loop (HITL) Controls**: Approval gates for administrative overrides and concessions.
* **Multi-Corpus Hybrid RAG**: Integrated lexical (BM25) and dense semantic vector search across multiple university handbooks and catalogues.
* **Multi-Agent Evaluation Benchmark**: 50+ challenging multi-turn collaborative scenarios.

---

## 2. Directory Scaffolding

```
assignment-2/
├── README.md              # Assignment 2 overview & documentation (this file)
├── .env.example           # Template for environment configuration
├── .gitignore             # Git ignore rules for Assignment 2
├── requirements.txt       # Dependencies for Assignment 2
├── agents/                # Supervisor and specialist worker subagents
├── tools/                 # Domain-specific toolkits
├── memory/                # Multi-tenant and shared memory stores
├── config/                # Settings, model registries, and policies
├── data/                  # Multi-handbook corpora and student data
├── evaluation/            # Multi-agent benchmark datasets and evaluators
└── tests/                 # Unit, integration, and collaboration test suites
```

---

## 3. Development Workflow

All development for Assignment 2 must proceed on the designated feature branch:

```bash
# Check out the Assignment 2 feature branch
git checkout feature/assignment-2

# Navigate to Assignment 2 directory
cd assignment-2

# Set up dedicated virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

---

## 4. References & Documentation

* Detailed Architecture Preview: [`../docs/assignment-2/ASSIGNMENT_2_ROADMAP.md`](../docs/assignment-2/ASSIGNMENT_2_ROADMAP.md)
* Completed Assignment 1 Implementation: [`../assignment-1/README.md`](../assignment-1/README.md)
* Overall Architecture & Diagrams: [`../docs/architecture/`](../docs/architecture/)
