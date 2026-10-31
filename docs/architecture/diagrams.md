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
        QueryEmbed --> VectorSearch[ChromaDB Nearest Neighbors: Top 3]
        VectorSearch --> DistanceCheck{Cosine Distance <= Cut-off?}
        DistanceCheck -- Yes --> PassToPrompt[Pass Section + Clauses to Agent]
        DistanceCheck -- No --> NoEvidence[Flag status: no_evidence]
    end
```
