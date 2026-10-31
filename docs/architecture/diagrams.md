# 📊 Architectural Diagrams: Intelligent Student Support Agent

This document provides visual architectural representations using standard Mermaid syntax.

---

## 1. LangGraph StateGraph Execution Flow

```mermaid
flowchart TD
    Start([User Query Submitted]) --> ValidateInput[validate_input]
    
    ValidateInput -- Query empty or invalid --> FinalizeDirect[finalize: Return Guidance]
    FinalizeDirect --> EndNode([Agent Response Delivered])
    
    ValidateInput -- Query valid --> ContextSel[context_selection]
    
    ContextSel <--> MemoryDB[(SQLite: memories)]
    
    ContextSel --> AgentNode[agent: LLM / Offline Planner]
    
    AgentNode -- Model requests tool calls --> ToolsNode[tools: Execute Requested Tool]
    ToolsNode <--> RelationalDB[(SQLite: students / fees / tickets)]
    ToolsNode <--> VectorDB[(ChromaDB: Policy Chunks)]
    ToolsNode --> AgentNode
    
    AgentNode -- Final answer ready OR max steps reached --> Finalize[finalize: Extract Memory]
    Finalize --> SaveTrace[(SQLite: execution_traces)]
    Finalize --> SaveMemory[(SQLite: memories)]
    Finalize --> EndNode
```

---

## 2. Relational Database Entity-Relationship Model (SQLite)

```mermaid
erDiagram
    STUDENTS ||--o{ FEES : "billed to"
    STUDENTS ||--o{ SCHOLARSHIPS : "applies for"
    STUDENTS ||--o{ SUPPORT_TICKETS : "submits"
    STUDENTS ||--o{ MEMORIES : "accumulates"
    STUDENTS ||--o{ EXECUTION_TRACES : "generates"

    STUDENTS {
        string student_id PK
        string name
        string email
        string programme
        int semester
        float cgpa
        float attendance_pct
        string academic_advisor
        string enrollment_date
    }

    FEES {
        int id PK
        string student_id FK
        float total_fee
        float paid_amount
        float outstanding_amount
        string due_date
        string payment_status
    }

    SCHOLARSHIPS {
        int id PK
        string student_id FK
        string scholarship_name
        string application_status
        float awarded_amount
        string application_date
        string remarks
    }

    SUPPORT_TICKETS {
        string ticket_id PK
        string student_id FK
        string issue_description
        string category
        string status
        string created_at
        string resolved_at
    }

    MEMORIES {
        int id PK
        string student_id FK
        string memory_type
        string key
        string content
        string created_at
        string updated_at
    }

    EXECUTION_TRACES {
        string execution_id PK
        string timestamp
        string student_id FK
        string query
        string intent
        string node_path
        string tools_used
        float duration_ms
        string model
        int input_tokens
        int output_tokens
        string status
    }
```

---

## 3. Persistent Memory Lifecycle

```mermaid
flowchart LR
    UserMsg[User Message] --> PrivacyFilter{Credential Filter}
    PrivacyFilter -- Contains OTP / Password / Card / Key --> DropMemory[Discard Sentence]
    PrivacyFilter -- Clean Sentence --> RegexMatch{Pattern Matcher}
    
    RegexMatch -- Matches 'call me', 'I prefer', etc. --> Deduplication{Jaccard Similarity Check}
    RegexMatch -- No match --> NoMemory[Do Not Store]
    
    Deduplication -- Similarity >= 80% --> UpdateOrSkip[Update Existing Key / Skip]
    Deduplication -- New Fact --> InsertDB[(Insert into SQLite: memories)]
```

---

## 4. Policy RAG Pipeline

```mermaid
flowchart TD
    subgraph Ingestion Pipeline
        RawText[student_handbook.txt / PDF] --> Parser[PyMuPDF / Text Parser]
        Parser --> HeadingSplitter[Heading-based Chunking: ≤ 700 chars]
        HeadingSplitter --> Embedder[MiniLM / Lexical Hashing]
        Embedder --> ChromaStore[(ChromaDB: handbook_chunks)]
    end

    subgraph Query-Time Retrieval
        Query[Search Query] --> QueryEmbed[Embed Query]
        VectorSearch[ChromaDB Nearest Neighbors: Top 3]
        QueryEmbed --> VectorSearch
        VectorSearch --> DistanceCheck{Cosine Distance <= Cut-off?}
        DistanceCheck -- Yes --> PassToPrompt[Pass Section + Clauses to Agent]
        DistanceCheck -- No --> NoEvidence[Flag status: no_evidence]
    end
```

---

## 5. Assignment 2: Security & Sensitive Action Human-in-the-Loop (HITL) Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Student as Authenticated Student (Aarav)
    participant Portal as Streamlit Web Portal
    participant AuthContext as Thread Context (ContextVar)
    participant Agent as LangGraph Orchestrator
    participant Tool as Approval Tool (request_fee_extension)
    participant DB as SQLite DB
    actor Admin as Authorized Administrator (Academic Office)

    Student->>Portal: "Can I request a fee payment extension for 14 days?"
    Portal->>AuthContext: set_current_user(AuthUser: Aarav)
    Portal->>Agent: run_agent(query, user=Aarav)
    Agent->>Tool: request_fee_extension(reason, due_date)
    Tool->>AuthContext: get_current_user()
    Note over Tool: Verify Student Ownership & Active Record
    Tool->>DB: INSERT INTO approval_requests (status='PENDING')
    Note over DB: fees.due_date remains UNMODIFIED (No execution)
    Tool->>DB: INSERT INTO security_audit_logs (status='PENDING_APPROVAL')
    Tool-->>Agent: {status: 'pending_approval', request_id: 'REQ-DEMO-001'}
    Agent-->>Portal: "Request submitted under tracking ID REQ-DEMO-001. Awaiting Administrator Review."
    
    rect rgb(240, 248, 255)
    Note over Admin,DB: Human-in-the-Loop Administrative Adjudication
    Admin->>Portal: Log in as Administrator & Open Approval Queue
    Portal->>DB: SELECT * FROM approval_requests WHERE status='PENDING'
    Admin->>Portal: Review request details & Click "Approve"
    Portal->>DB: BEGIN IMMEDIATE TRANSACTION
    Portal->>DB: Verify status == 'PENDING' (Prevent Replays & Race Conditions)
    Portal->>DB: UPDATE fees SET due_date = new_date WHERE student_id = 'MIM25001'
    Portal->>DB: UPDATE approval_requests SET status = 'APPROVED'
    Portal->>DB: INSERT INTO security_audit_logs (decision='ALLOWED', approval_status='APPROVED')
    Portal->>DB: COMMIT TRANSACTION
    Portal-->>Admin: "Request Approved and Fee Due Date Extended."
    end
```

---

## 6. Extended Relational Entity-Relationship Model (Assignment 2)

```mermaid
erDiagram
    USERS ||--o| STUDENTS : "authenticates"
    STUDENTS ||--o{ FEES : "billed to"
    STUDENTS ||--o{ SCHOLARSHIPS : "applies for"
    STUDENTS ||--o{ SUPPORT_TICKETS : "submits"
    STUDENTS ||--o{ MEMORIES : "accumulates"
    STUDENTS ||--o{ APPROVAL_REQUESTS : "requests"
    USERS ||--o{ APPROVAL_REQUESTS : "adjudicates"
    USERS ||--o{ SECURITY_AUDIT_LOGS : "acts in"

    USERS {
        string user_id PK
        string username UK
        string password_hash
        string role
        string student_id FK
        string full_name
        string email
        int is_active
    }

    APPROVAL_REQUESTS {
        string request_id PK
        string student_id FK
        string action_type
        string payload_json
        string status
        string requested_at
        string reviewed_by FK
        string reviewed_at
        string decision_reason
        string executed_at
    }

    SECURITY_AUDIT_LOGS {
        string audit_id PK
        string timestamp
        string requester_id
        string requester_role
        string action
        string resource
        string requested_resource_id
        string authorization_decision
        int approval_required
        string approval_status
        string execution_status
        string details_json
        string failure_reason
    }
```
