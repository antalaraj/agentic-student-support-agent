"""Streamlit front-end for the Intelligent Student Support Agent."""
from config import sqlite_compat  # noqa: F401  (must be imported before chromadb)

import json
from pathlib import Path
import uuid

from dotenv import load_dotenv
# Ensure .env from workspace root is loaded reliably
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import pandas as pd
import streamlit as st

from config import settings

st.set_page_config(page_title="Student Support Agent", page_icon="🎓", layout="wide")

CSS = """
<style>
:root { --navy:#0B1F3A; --blue:#1F4FBF; --soft:#EAF1FB; }
.block-container { padding-top: 1.5rem; max-width: 1100px; }
h1,h2,h3 { color: var(--navy); font-family: 'Segoe UI', system-ui, sans-serif; }
.hero { background: linear-gradient(90deg,#0B1F3A,#1F4FBF); color:#fff; padding:18px 24px; border-radius:14px; margin-bottom:14px; }
.hero h2 { color:#fff; margin:0; } .hero p { margin:4px 0 0; opacity:.9; }
[data-testid="stChatMessage"] { border-radius: 14px; padding: 10px 14px; margin-bottom: 8px; background:#F7F9FC; border:1px solid #E1E8F3; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: var(--soft); border-color:#C9D9F2; }
.chip { display:inline-block; background:var(--soft); color:var(--navy); border:1px solid #C9D9F2; border-radius:999px; padding:2px 10px; margin:2px 4px 0 0; font-size:.78rem; }
.demo-banner { background:#FFF8E1; border:1px solid #F3DE9B; border-radius:8px; padding:6px 10px; font-size:.82rem; color:#5a4a00; }
section[data-testid="stSidebar"] { background:#F2F6FC; }
@media (max-width: 640px) { .block-container { padding: .8rem .6rem; } .hero { padding:12px 14px; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

SAMPLE_QUESTIONS = [
    "What is my current fee status?", "How much outstanding fee do I have?", "What is my scholarship application status?",
    "What is the late fee policy?", "Can I change my programme?", "What is the attendance requirement?",
    "The payment portal failed. Can I pay on the next working day?", "Create a support ticket for a payment issue",
    "What programme am I studying?", "What did I tell you about my academic preferences in our previous session?",
    "Please call me Aarav and I prefer machine learning electives.", "My OTP is 482913. Please remember it.",
    "Does the handbook say anything about hostel accommodation rules?",
]


# ───────────────────────── start-up (cached, idempotent) ─────────────────────────
@st.cache_resource(show_spinner="Preparing database and knowledge base…")
def initialise():
    """Create tables, insert demo data ONLY if missing, build the vector index ONLY if missing/outdated."""
    from database.seed import seed_students
    from rag.embeddings import backend_name
    from rag.ingestion import ingest

    new_students = seed_students()
    info = ingest()
    return {"new_students": new_students, "rag": info, "embedder": backend_name()}


@st.cache_resource(show_spinner=False)
def _cached_llm(api_key: str, model_name: str):
    from agent.llm import get_llm

    return get_llm()


def load_llm():
    key = settings.groq_api_key()
    if not key:
        return None
    model = settings.groq_model()
    try:
        return _cached_llm(key, model)
    except Exception:
        return None


def friendly_error(exc: Exception) -> str:
    return f"Something went wrong while starting the app ({type(exc).__name__}). Please refresh the page or try again shortly."


try:
    init_info = initialise()
except Exception as exc:  # keep the UI alive with a readable message instead of a stack trace
    st.error(friendly_error(exc))
    st.stop()

from agent.llm import model_label
from agent.graph import run_agent
from database import memory
from database.db import connection
from tools.support_tools import list_tickets
from tracing.metrics import summarise_traces
from tracing.tracer import load_traces

llm = load_llm()

# ───────────────────────── session state ─────────────────────────
ss = st.session_state
ss.setdefault("messages", [])
ss.setdefault("session_id", uuid.uuid4().hex[:8])
ss.setdefault("student_id", None)


def new_conversation():
    ss.messages, ss.session_id = [], uuid.uuid4().hex[:8]


def students() -> list[dict]:
    with connection() as conn:
        return [dict(r) for r in conn.execute("SELECT student_id, name FROM students ORDER BY student_id")]


# ───────────────────────── sidebar ─────────────────────────
with st.sidebar:
    st.markdown("### 🎓 Student Support Agent")
    st.caption("Agentic AI Engineering · Assignment 1 · PGDM 2025-27")
    page = st.radio("Navigate", ["AI Chat Assistant", "Student Information", "Support Requests",
                                 "Agent Activity / Trace", "Evaluation Dashboard", "About Project"], label_visibility="collapsed")
    st.divider()
    options = {"— Not selected —": None} | {f"{s['student_id']} · {s['name']}": s["student_id"] for s in students()}
    current = next((k for k, v in options.items() if v == ss.student_id), "— Not selected —")
    choice = st.selectbox("Demo student identity", list(options), index=list(options).index(current),
                          help="Demo identity only – this is NOT real authentication.")
    if options[choice] != ss.student_id:
        ss.student_id = options[choice]
        new_conversation()
        st.rerun()
    if st.button("➕ New conversation", width="stretch"):
        new_conversation()
        st.rerun()
    st.divider()
    st.caption(f"🤖 Model: **{model_label(llm)}**")
    if llm is None:
        st.caption("No `GROQ_API_KEY` found → running in offline planner mode.")
    st.caption(f"🔎 Embeddings: **{init_info['embedder']}**")
    st.markdown('<div class="demo-banner">All data and policies are <b>fictional demo data</b>.</div>', unsafe_allow_html=True)

st.markdown(f"""<div class="hero"><h2>{page}</h2><p>{settings.INSTITUTION}</p></div>""", unsafe_allow_html=True)


# ───────────────────────── pages ─────────────────────────
def chips(label: str, items: list[str]) -> str:
    return "".join(f'<span class="chip">{label} {i}</span>' for i in items)


def show_meta(trace: dict):
    tools = [c["tool"] for c in trace["tool_calls"]]
    html = ""
    if tools:
        html += chips("🛠", tools)
    if trace["retrieved_chunks"]:
        html += chips("📚", list(dict.fromkeys(c["section"] for c in trace["retrieved_chunks"])))
    if trace["memory_refs"]:
        html += chips("🧠 memory", [f"#{m['id']}" for m in trace["memory_refs"]])
    if trace["memory_writes"]:
        html += chips("💾 saved", [m["content"] for m in trace["memory_writes"]])
    if not tools and not trace["memory_refs"]:
        html += chips("💬", ["answered directly"])
    tok = trace["token_usage"]
    tokens = f"{tok['input_tokens']}/{tok['output_tokens']} tokens" if tok["available"] else "tokens unavailable"
    st.markdown(html, unsafe_allow_html=True)
    st.caption(f"⏱ {trace['duration_ms']:.0f} ms · {tokens} · {trace['execution_id']}")


def page_chat():
    if not ss.student_id:
        st.info("Select a demo student in the sidebar to ask about your fees, scholarship or profile. "
                "You can still ask general handbook questions.")
    with st.expander("💡 Sample questions (click to ask)"):
        cols = st.columns(2)
        for i, q in enumerate(SAMPLE_QUESTIONS):
            if cols[i % 2].button(q, key=f"sq{i}", width="stretch"):
                ss.pending = q
    for m in ss.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("trace"):
                show_meta(m["trace"])

    query = st.chat_input("Ask about fees, scholarships, policies, course changes…") or ss.pop("pending", None)
    if query is None:
        return
    history = [{"role": m["role"], "content": m["content"]} for m in ss.messages]
    ss.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
    with st.chat_message("assistant"):
        with st.spinner("Agent is working…"):
            try:
                result = run_agent(query, ss.student_id, ss.session_id, history, llm=llm)
            except Exception as exc:
                st.error(friendly_error(exc))
                return
        st.markdown(result["response"])
        show_meta(result["trace"])
    ss.messages.append({"role": "assistant", "content": result["response"], "trace": result["trace"]})


def page_student():
    if not ss.student_id:
        st.info("Select a demo student in the sidebar.")
        return
    with connection() as conn:
        s = conn.execute("SELECT * FROM students WHERE student_id=?", (ss.student_id,)).fetchone()
        f = conn.execute("SELECT * FROM fees WHERE student_id=?", (ss.student_id,)).fetchone()
        sch = conn.execute("SELECT * FROM scholarships WHERE student_id=?", (ss.student_id,)).fetchone()
    c1, c2, c3 = st.columns(3)
    c1.metric("Programme", s["programme"].replace("PGDM ", ""))
    c2.metric("Semester", s["semester"])
    c3.metric("Payment status", f["payment_status"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Total fee", f"₹{f['total_fee']:,}")
    c2.metric("Paid", f"₹{f['paid_amount']:,}")
    c3.metric("Outstanding", f"₹{f['outstanding_amount']:,}")
    st.write(f"**Scholarship:** {sch['scholarship_name']} — {sch['application_status']}  \n"
             f"**Advisor:** {s['advisor']} · **CGPA:** {s['cgpa']} · **Attendance:** {s['attendance_pct']}% · **Email:** {s['email']}")
    st.subheader("🧠 Persistent memory (stored in SQLite)")
    mems = memory.list_memories(ss.student_id)
    if not mems:
        st.caption("Nothing stored yet. Try: “Please call me Aarav and I prefer machine learning electives.”")
    for m in mems:
        col1, col2 = st.columns([6, 1])
        col1.write(f"**#{m['id']}** `{m['mem_type']}` {m['content']}  \n<small>saved {m['created_at']}</small>", unsafe_allow_html=True)
        if col2.button("Delete", key=f"del{m['id']}"):
            memory.delete_memory(m["id"], ss.student_id)
            st.rerun()
    st.caption("Passwords, OTPs, card numbers and API keys are never stored in memory.")


def page_tickets():
    if not ss.student_id:
        st.info("Select a demo student in the sidebar.")
        return
    tickets = list_tickets(ss.student_id)
    if isinstance(tickets, list) and tickets:
        st.dataframe(pd.DataFrame(tickets), width="stretch", hide_index=True)
    else:
        st.caption("No support tickets yet. Ask the assistant: “Create a support ticket for a payment issue”.")


def page_activity():
    traces = load_traces(200, ss.student_id)
    scope = f"for {ss.student_id}" if ss.student_id else "for all students"
    st.caption(f"Latest agent runs {scope}")
    if not traces:
        st.info("No traces yet – ask the assistant something first.")
        return
    summary = summarise_traces(traces)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Runs", summary["runs"]); m2.metric("Avg latency", f"{summary['avg_latency_ms']} ms")
    m3.metric("Input tokens", summary["total_input_tokens"]); m4.metric("Output tokens", summary["total_output_tokens"])
    table = pd.DataFrame([{"execution_id": t["execution_id"], "time": t["timestamp"], "student": t["student_id"], "query": t["user_query"][:60],
                           "intent": t["intent"], "tools": ", ".join(c["tool"] for c in t["tool_calls"]) or "-",
                           "status": t["final_status"], "ms": t["duration_ms"]} for t in traces])
    st.dataframe(table, width="stretch", hide_index=True)
    pick = st.selectbox("Inspect a trace", [t["execution_id"] for t in traces])
    st.json(next(t for t in traces if t["execution_id"] == pick))


def page_eval():
    from evaluation.results import load_latest, to_dataframe

    st.write("Automated assertions decide pass/fail. Optional LLM-judged quality is reported separately and never counted in accuracy.")
    if st.button("▶ Run evaluation now" + (" (live Groq)" if llm else " (offline planner)")):
        from evaluation.evaluator import run_evaluation

        with st.spinner("Running 18 test cases on a temporary database…"):
            try:
                run_evaluation(live=llm is not None)
            except Exception as exc:
                st.error(f"Evaluation could not run ({type(exc).__name__}).")
    data = load_latest()
    if not data:
        st.info("No evaluation results yet. Run `python -m evaluation.evaluator` or press the button above.")
        return
    s = data["summary"]
    st.caption(f"Mode: **{s['mode']}** · embeddings: **{s['embedder']}** · run at {s['run_at']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Task accuracy", f"{s['accuracy_pct']}%", f"{s['passed']}/{s['total']}")
    c2.metric("Tool selection", f"{s['tool_selection_pct']}%", f"{s['tool_ok']}/{s['total']}")
    c3.metric("Avg latency", f"{s['avg_latency_ms']} ms")
    c4.metric("Tokens in/out", f"{s['total_input_tokens']} / {s['total_output_tokens']}")
    st.dataframe(to_dataframe(data["results"]), width="stretch", hide_index=True)
    for o in s["observations"]:
        st.markdown(f"- {o}")


def page_about():
    st.markdown(f"""
**{settings.APP_NAME}** — a LangGraph tool-using agent for the *Agentic AI Engineering* course (PGDM 2025-27).

**Flow:** `validate input → context selection → agent (LLM) ⇄ tools → final response + memory update → trace`

| Capability | Implementation |
|---|---|
| Agent loop | LangGraph `StateGraph` with conditional routing |
| Tools | profile, fee, scholarship, support ticket, policy search, academic search (SQLite / ChromaDB) |
| Memory | SQLite, per student, de-duplicated, sensitive data filtered |
| RAG | handbook → chunks → embeddings → ChromaDB → top-k |
| Context selection | question + last turns + relevant memories only |
| Tracing | JSON trace per run in SQLite, redacted |

**Persistence on free hosting:** Streamlit Community Cloud storage is ephemeral. SQLite memory, tickets and traces can be
reset when the app restarts or redeploys. Use an external free-tier database for guaranteed persistence (see README).

All students, fees and policies are **fictional demonstration data**.
""")


{"AI Chat Assistant": page_chat, "Student Information": page_student, "Support Requests": page_tickets,
 "Agent Activity / Trace": page_activity, "Evaluation Dashboard": page_eval, "About Project": page_about}[page]()
