"""Streamlit front-end for the Safe and Production-Aware Student Support Agent (Assignment 2)."""
from config import sqlite_compat  # noqa: F401  (must be imported before chromadb)

import json
from pathlib import Path
import uuid
import datetime

from dotenv import load_dotenv
# Ensure .env is loaded reliably
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

import pandas as pd
import streamlit as st

from config import settings
from auth.models import AuthUser
from auth.service import authenticate_user, get_user_by_username
from auth.context import set_current_user, reset_current_user, get_current_user
from authorization.service import require_student_ownership, require_admin
from approval.service import (
    list_pending_requests,
    list_student_requests,
    review_approval_request,
    create_fee_extension_request,
)
from audit.service import query_audit_logs, get_audit_log_by_id
from database.db import connection
from database import memory
from tools.support_tools import list_tickets
from tracing.metrics import summarise_traces
from tracing.tracer import load_traces

st.set_page_config(page_title="Safe Student Support Agent · Assignment 2", page_icon="🛡️", layout="wide")

CSS = """
<style>
:root {
    --navy: #0B1F3A;
    --blue: #1F4FBF;
    --soft: #EAF1FB;
    --success: #0E703C;
    --danger: #B81D13;
    --warning: #A16207;
}

/* Ensure clean light background and deep navy text across all containers */
html, body, [data-testid="stAppViewContainer"], .main {
    background-color: #FFFFFF !important;
    color: #0B1F3A !important;
}
.block-container {
    padding-top: 1.2rem;
    max-width: 1140px;
    background-color: #FFFFFF !important;
    color: #0B1F3A !important;
}
h1, h2, h3, h4, h5, h6 {
    color: var(--navy) !important;
    font-family: 'Segoe UI', system-ui, sans-serif;
}
p, span, label {
    color: #0B1F3A;
}

/* Sidebar styling matching Assignment 1 */
section[data-testid="stSidebar"], [data-testid="stSidebar"] > div {
    background-color: #F2F6FC !important;
    color: #0B1F3A !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] span, [data-testid="stSidebar"] p {
    color: #0B1F3A !important;
}
/* Radio buttons in sidebar */
div[data-testid="stRadio"] label, div[data-testid="stRadio"] p, div[data-testid="stRadio"] span {
    color: #0B1F3A !important;
    font-weight: 500 !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
    background-color: #EAF1FB;
    border-radius: 6px;
}

/* Hero banner matching Assignment 1 */
.hero {
    background: linear-gradient(90deg, #0B1F3A, #1F4FBF);
    color: #FFFFFF !important;
    padding: 18px 24px;
    border-radius: 14px;
    margin-bottom: 14px;
}
.hero h2 {
    color: #FFFFFF !important;
    margin: 0;
}
.hero p {
    color: #FFFFFF !important;
    margin: 4px 0 0;
    opacity: 0.92;
}

/* Chat messages matching Assignment 1 */
[data-testid="stChatMessage"] {
    border-radius: 14px;
    padding: 10px 14px;
    margin-bottom: 8px;
    background-color: #F7F9FC !important;
    border: 1px solid #E1E8F3 !important;
    color: #0B1F3A !important;
}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] span, [data-testid="stChatMessage"] li {
    color: #0B1F3A !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background-color: var(--soft) !important;
    border-color: #C9D9F2 !important;
}

/* Bottom chat input container */
[data-testid="stBottom"], [data-testid="stBottom"] > div {
    background-color: #FFFFFF !important;
}
[data-testid="stChatInput"] {
    background-color: #FFFFFF !important;
}
[data-testid="stChatInput"] textarea {
    color: #0B1F3A !important;
    background-color: #FFFFFF !important;
}

/* Badges, chips, banners, and cards matching Assignment 1 */
.chip {
    display: inline-block;
    background: var(--soft);
    color: var(--navy) !important;
    border: 1px solid #C9D9F2;
    border-radius: 999px;
    padding: 2px 10px;
    margin: 2px 4px 0 0;
    font-size: .78rem;
    font-weight: 500;
}
.chip-sec {
    display: inline-block;
    background: #EBFBF3;
    color: #0E703C !important;
    border: 1px solid #A4E2C6;
    border-radius: 999px;
    padding: 2px 10px;
    margin: 2px 4px 0 0;
    font-size: .78rem;
    font-weight: 600;
}
.chip-denied {
    display: inline-block;
    background: #FEEBEA;
    color: #B81D13 !important;
    border: 1px solid #F5B5B2;
    border-radius: 999px;
    padding: 2px 10px;
    margin: 2px 4px 0 0;
    font-size: .78rem;
    font-weight: 600;
}
.badge-role-admin {
    background: #F3E8FF;
    color: #6B21A8 !important;
    border: 1px solid #D8B4FE;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: .75rem;
    font-weight: bold;
}
.badge-role-student {
    background: #E0F2FE;
    color: #0369A1 !important;
    border: 1px solid #BAE6FD;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: .75rem;
    font-weight: bold;
}
.demo-banner {
    background: #FFF8E1;
    border: 1px solid #F3DE9B;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: .82rem;
    color: #5a4a00 !important;
    margin-bottom: 10px;
}
.demo-banner * {
    color: #5a4a00 !important;
}
.approval-card {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-left: 4px solid #F59E0B;
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 12px;
    color: #0B1F3A;
}
.approval-card-approved { border-left-color: #10B981; }
.approval-card-rejected { border-left-color: #EF4444; }
.auth-box {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    margin-top: 20px;
    color: #0B1F3A;
}
.stExpander {
    background-color: #FFFFFF !important;
}

/* Input fields (Username, Password, Search, etc.) */
div[data-baseweb="input"], div[data-baseweb="base-input"] {
    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
}
div[data-baseweb="input"] input, div[data-baseweb="base-input"] input {
    color: #0B1F3A !important;
    background-color: #FFFFFF !important;
    -webkit-text-fill-color: #0B1F3A !important;
}
div[data-baseweb="input"] input::placeholder {
    color: #94A3B8 !important;
    -webkit-text-fill-color: #94A3B8 !important;
}

/* Form submit button (Sign In, Submit) - Vibrant Royal Blue */
div[data-testid="stFormSubmitButton"] button, button[kind="primary"] {
    background-color: #1F4FBF !important;
    color: #FFFFFF !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px rgba(31, 79, 191, 0.2) !important;
}
div[data-testid="stFormSubmitButton"] button:hover, button[kind="primary"]:hover {
    background-color: #163B96 !important;
    color: #FFFFFF !important;
}
div[data-testid="stFormSubmitButton"] button p, div[data-testid="stFormSubmitButton"] button span, button[kind="primary"] p {
    color: #FFFFFF !important;
}

/* Secondary & Quick Login buttons - Clean Light Corporate Style */
div[data-testid="stButton"] button, button[kind="secondary"] {
    background-color: #F2F6FC !important;
    color: #0B1F3A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}
div[data-testid="stButton"] button:hover, button[kind="secondary"]:hover {
    background-color: #E2ECF9 !important;
    color: #1F4FBF !important;
    border-color: #1F4FBF !important;
}
div[data-testid="stButton"] button p, div[data-testid="stButton"] button span, button[kind="secondary"] p {
    color: #0B1F3A !important;
}

/* Code tags and demo credentials formatting */
code {
    background-color: #F1F5F9 !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 4px !important;
    padding: 2px 6px !important;
    font-size: 0.85em !important;
}
pre {
    background-color: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
}

@media (max-width: 640px) {
    .block-container { padding: .8rem .6rem; }
    .hero { padding: 12px 14px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

SAMPLE_QUESTIONS = [
    "What is my current fee status?",
    "Can I request a fee payment extension for 14 days due to banking delay?",
    "What is my scholarship application status?",
    "What is the late fee policy?",
    "Please call me Aarav and my OTP is 482913. Remember my preferred electives are NLP and Deep Learning.",
    "What is the fee status of student MIM25002?",  # Demonstrates cross-student privacy enforcement
    "Create a support ticket for my hostel WiFi issue",
    "What did I tell you about my academic preferences?",
]


# ───────────────────────── Initialisation ─────────────────────────
@st.cache_resource(show_spinner="Initialising secure database and knowledge base…")
def initialise():
    from database.seed import seed_database
    from rag.embeddings import backend_name
    from rag.ingestion import ingest

    stats = seed_database()
    info = ingest()
    return {"db": stats, "rag": info, "embedder": backend_name()}


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
    return f"Security or runtime error: {exc}"


try:
    init_info = initialise()
except Exception as exc:
    st.error(f"Application failed to initialise: {exc}")
    st.stop()

from agent.llm import model_label
from agent.graph import run_agent

llm = load_llm()

# ───────────────────────── Session State ─────────────────────────
ss = st.session_state
ss.setdefault("auth_user", None)
ss.setdefault("messages", [])
ss.setdefault("session_id", uuid.uuid4().hex[:8])


def new_conversation():
    ss.messages = []
    ss.session_id = uuid.uuid4().hex[:8]


def logout():
    ss.auth_user = None
    reset_current_user()
    new_conversation()
    st.rerun()


# ───────────────────────── Authentication Screen ─────────────────────────
def page_login():
    st.markdown("""
    <div class="hero">
        <h2>🛡️ Safe and Production-Aware Student Support Agent</h2>
        <p>Assignment 2 · Institutional Portal with Identity Verification, Ownership Isolation & Approvals</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="demo-banner">
        🔒 <b>Zero-Trust Identity Verification:</b> All queries and database tools require signed-in authentication. 
        Ownership checks are enforced in backend code and SQLite queries, preventing cross-student data leakage.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Sign In to Student / Admin Portal")
        with st.form("login_form"):
            username_input = st.text_input("Username / Student ID", placeholder="e.g. aarav or admin")
            password_input = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("Sign In 🔑", use_container_width=True)

            if submit:
                if not username_input or not password_input:
                    st.error("Please provide both username and password.")
                else:
                    user = authenticate_user(username_input.strip(), password_input)
                    if user:
                        ss.auth_user = user
                        set_current_user(user)
                        new_conversation()
                        st.success(f"Welcome back, {user.full_name}!")
                        st.rerun()
                    else:
                        st.error("Authentication failed. Invalid username or password. This event has been logged to the security audit trail.")

    with col2:
        st.subheader("Demo Accounts & Test Credentials")
        st.caption("All passwords are safe demo credentials hashed with **bcrypt (12 rounds)**.")

        st.markdown("""
        **Student Accounts:**
        - `aarav` (MIM25001) · Password: `Student@123`
        - `diya` (MIM25002) · Password: `Student@123`
        - `rohan` (MIM25003) · Password: `Student@123`
        - `ananya` (MIM25004) · Password: `Student@123`

        **Administrator Account:**
        - `admin` (Academic Office) · Password: `Admin@12345`
        """)

        st.divider()
        st.caption("Quick login for testing:")
        q1, q2, q3 = st.columns(3)
        if q1.button("Student (Aarav)", use_container_width=True):
            user = authenticate_user("aarav", "Student@123")
            if user:
                ss.auth_user = user
                set_current_user(user)
                new_conversation()
                st.rerun()
        if q2.button("Student (Diya)", use_container_width=True):
            user = authenticate_user("diya", "Student@123")
            if user:
                ss.auth_user = user
                set_current_user(user)
                new_conversation()
                st.rerun()
        if q3.button("Admin", use_container_width=True):
            user = authenticate_user("admin", "Admin@12345")
            if user:
                ss.auth_user = user
                set_current_user(user)
                new_conversation()
                st.rerun()


# If not logged in, show login page and stop
if not ss.auth_user:
    page_login()
    st.stop()

# Ensure current user is bound to contextvar in this execution thread
user: AuthUser = ss.auth_user
set_current_user(user)

# ───────────────────────── Authenticated Navigation Sidebar ─────────────────────────
with st.sidebar:
    st.markdown("### 🛡️ Secure Student Portal")
    st.caption("Assignment 2 · Production-Aware Architecture")

    # User Profile Badge
    role_badge = (
        '<span class="badge-role-admin">🔑 ADMINISTRATOR</span>'
        if user.is_admin()
        else '<span class="badge-role-student">🎓 STUDENT</span>'
    )
    st.markdown(f"""
    <div style="background:#FFFFFF; border:1px solid #CBD5E1; border-radius:10px; padding:10px; margin-bottom:12px;">
        <div style="font-weight:bold; color:#0B1F3A;">{user.full_name}</div>
        <div style="font-size:0.8rem; color:#64748B;">@{user.username} {f'· {user.student_id}' if user.student_id else ''}</div>
        <div style="margin-top:6px;">{role_badge}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Sign Out", use_container_width=True):
        logout()

    st.divider()

    # Dynamic Navigation depending on Role
    if user.is_admin():
        pages = [
            "Pending Approvals Queue",
            "Approval History",
            "Security Audit Explorer",
            "AI Assistant (Admin Mode)",
            "Student Directory",
            "Evaluation Dashboard",
            "About Assignment 2",
        ]
    else:
        pages = [
            "AI Chat Assistant",
            "My Student Profile & Fees",
            "My Approval Requests",
            "My Support Requests",
            "Agent Trace & Privacy",
            "Evaluation Dashboard",
            "About Assignment 2",
        ]

    page = st.radio("Navigation", pages, label_visibility="collapsed")

    st.divider()
    if st.button("➕ New Conversation", use_container_width=True):
        new_conversation()
        st.rerun()

    st.divider()
    st.caption(f"🤖 Model: **{model_label(llm)}**")
    if llm is None:
        st.caption("Offline mode active (deterministic security planner).")
    st.caption(f"🔎 Embeddings: **{init_info['embedder']}**")
    st.caption("🛡️ Security: **Ownership Enforced**")

st.markdown(f"""<div class="hero"><h2>{page}</h2><p>{settings.INSTITUTION} · Authenticated as {user.full_name}</p></div>""", unsafe_allow_html=True)


# ───────────────────────── Meta Display Helpers ─────────────────────────
def chips(label: str, items: list[str]) -> str:
    return "".join(f'<span class="chip">{label} {i}</span>' for i in items)


def show_meta(trace: dict):
    tools = [c["tool"] for c in trace.get("tool_calls", [])]
    html = ""
    if tools:
        html += chips("🛠", tools)
    if trace.get("retrieved_chunks"):
        html += chips("📚", list(dict.fromkeys(c["section"] for c in trace["retrieved_chunks"])))
    if trace.get("memory_refs"):
        html += chips("🧠 memory", [f"#{m['id']}" for m in trace["memory_refs"]])
    if trace.get("memory_writes"):
        html += chips("💾 saved", [m["content"] for m in trace["memory_writes"]])
    if not tools and not trace.get("memory_refs"):
        html += chips("💬", ["answered directly"])

    # Security indicator
    html += '<span class="chip-sec">🔒 Verified Identity</span>'

    tok = trace.get("token_usage", {})
    tokens = f"{tok.get('input_tokens', 0)}/{tok.get('output_tokens', 0)} tokens" if tok.get("available") else "tokens unavailable"
    st.markdown(html, unsafe_allow_html=True)
    st.caption(f"⏱ {trace.get('duration_ms', 0):.0f} ms · {tokens} · Trace: `{trace.get('execution_id', 'n/a')}`")


# ───────────────────────── Student Pages ─────────────────────────
def page_student_chat():
    st.markdown("""
    <div class="demo-banner">
        💡 <b>Try it:</b> Ask about your fees or submit a payment extension. Try asking for another student's fees (e.g. MIM25002) to see security isolation in action!
    </div>
    """, unsafe_allow_html=True)

    with st.expander("💡 Clickable Sample Questions"):
        cols = st.columns(2)
        for i, q in enumerate(SAMPLE_QUESTIONS):
            if cols[i % 2].button(q, key=f"sq_{i}", use_container_width=True):
                ss.pending = q

    for m in ss.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("trace"):
                show_meta(m["trace"])

    query = st.chat_input("Ask about your fees, policies, scholarships, or fee extensions…") or ss.pop("pending", None)
    if query is None:
        return

    history = [{"role": m["role"], "content": m["content"]} for m in ss.messages]
    ss.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Processing securely…"):
            try:
                # Ensure contextvar is set in this scope
                set_current_user(user)
                result = run_agent(query, user.student_id, ss.session_id, history, llm=llm)
            except Exception as exc:
                st.error(friendly_error(exc))
                return
        st.markdown(result["response"])
        show_meta(result["trace"])

    ss.messages.append({"role": "assistant", "content": result["response"], "trace": result["trace"]})


def page_student_profile():
    if not user.student_id:
        st.info("Administrator account does not have a personal student record.")
        return

    with connection() as conn:
        s = conn.execute("SELECT * FROM students WHERE student_id=?", (user.student_id,)).fetchone()
        f = conn.execute("SELECT * FROM fees WHERE student_id=?", (user.student_id,)).fetchone()
        sch = conn.execute("SELECT * FROM scholarships WHERE student_id=?", (user.student_id,)).fetchone()

    if not s or not f:
        st.error("No student record found for authenticated user.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Programme", s["programme"].replace("PGDM ", ""))
    c2.metric("Semester", s["semester"])
    c3.metric("Payment Status", f["payment_status"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Fee", f"₹{f['total_fee']:,}")
    c2.metric("Paid Amount", f"₹{f['paid_amount']:,}")
    c3.metric("Outstanding Balance", f"₹{f['outstanding_amount']:,}")

    st.markdown(f"""
    - **Academic Advisor:** {s['advisor']}
    - **CGPA:** {s['cgpa']} · **Attendance:** {s['attendance_pct']}%
    - **Official Email:** `{s['email']}`
    - **Fee Due Date:** `{f['due_date']}`
    - **Scholarship:** {sch['scholarship_name'] if sch else 'None'} ({sch['application_status'] if sch else 'N/A'})
    """)

    st.divider()
    st.subheader("🧠 Persistent Long-Term Memory")
    st.caption("Only safe academic preferences are saved. Passwords, OTPs, PINs, and API keys are automatically stripped.")
    mems = memory.list_memories(user.student_id)
    if not mems:
        st.info("No preferences saved yet. You can ask the assistant: “Please call me Aarav and I prefer Machine Learning electives.”")
    else:
        for m in mems:
            col1, col2 = st.columns([6, 1])
            col1.write(f"**#{m['id']}** `{m['mem_type']}` {m['content']}  \n<small style='color:#64748B;'>Saved {m['created_at']}</small>", unsafe_allow_html=True)
            if col2.button("Delete", key=f"del_mem_{m['id']}"):
                memory.delete_memory(m["id"], user.student_id)
                st.rerun()


def page_student_approvals():
    st.subheader("⏳ Sensitive Action Approval Requests")
    st.markdown("""
    Under Assignment 2's security policy, **fee payment extensions** require human administrative approval before taking effect. 
    Creating a request will NOT modify your fees until an authorized academic administrator reviews and approves it.
    """)

    # List current requests
    reqs = list_student_requests(user)
    if reqs:
        st.markdown(f"#### My Submission History ({len(reqs)})")
        for r in reqs:
            status = r["status"]
            border_cls = "approval-card-approved" if status == "APPROVED" else ("approval-card-rejected" if status == "REJECTED" else "")
            badge = "🟢 **APPROVED**" if status == "APPROVED" else ("🔴 **REJECTED**" if status == "REJECTED" else "🟠 **PENDING REVIEW**")

            payload = r.get("payload", {})
            with st.container():
                st.markdown(f"""
                <div class="approval-card {border_cls}">
                    <div style="display:flex; justify-content:space-between;">
                        <b>Request ID: <code>{r['request_id']}</code></b>
                        <span>{badge}</span>
                    </div>
                    <div style="margin-top:6px; font-size:0.9rem;">
                        <b>Action:</b> {r['action_type']} · <b>Requested Due Date:</b> {payload.get('requested_due_date', 'N/A')} · <b>Requested:</b> {r['requested_at']}
                    </div>
                    <div style="margin-top:4px; font-size:0.9rem;">
                        <b>Reason:</b> {payload.get('reason', 'N/A')}
                    </div>
                    {f"<div style='margin-top:6px; font-size:0.85rem; color:#475569;'><b>Admin Remarks:</b> {r['decision_reason']} (Decided by {r['decided_by']} at {r['decided_at']})</div>" if r.get('decided_by') else ""}
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("You have no pending or past approval requests.")

    st.divider()
    st.markdown("#### Submit New Fee Extension Request")
    with st.form("new_extension_form"):
        extension_days = st.slider("Requested Extension (Days)", min_value=1, max_value=30, value=14)
        target_date = (datetime.date.today() + datetime.timedelta(days=extension_days)).isoformat()
        st.caption(f"Proposed new due date: **{target_date}**")
        reason = st.text_area("Reason for Extension", placeholder="e.g. Awaiting bank education loan disbursement...")
        submitted = st.form_submit_button("Submit Request for Administrator Review 📝")

        if submitted:
            if not reason.strip():
                st.error("Please provide a valid reason for the extension request.")
            else:
                req = create_fee_extension_request(
                    user=user,
                    reason=reason.strip(),
                    requested_due_date=target_date,
                )
                if req.get("status") == "pending_approval":
                    st.success(f"Request `{req['request_id']}` submitted successfully! It is now pending administrative review.")
                    st.rerun()
                else:
                    st.error(f"Error submitting request: {req.get('message')}")


def page_student_tickets():
    st.subheader("🎫 My Support Requests")
    tickets = list_tickets(user.student_id)
    if isinstance(tickets, list) and tickets:
        st.dataframe(pd.DataFrame(tickets), use_container_width=True, hide_index=True)
    else:
        st.info("No support tickets found for your account. You can create one through the AI Chat Assistant.")


# ───────────────────────── Administrator Pages ─────────────────────────
def page_admin_pending_queue():
    st.subheader("📋 Pending Sensitive Action Approvals")
    st.markdown("""
    Review and adjudicate student requests for fee payment extensions. 
    **Execution is atomic:** Approving executes the fee due date modification in SQLite and logs a permanent audit record.
    """)

    pending = list_pending_requests(user)
    if not pending:
        st.success("🎉 No pending requests in the queue! All requests have been adjudicated.")
        return

    st.write(f"**{len(pending)} Pending Request(s)** awaiting decision:")

    for req in pending:
        req_id = req["request_id"]
        payload = req.get("payload", {})
        req_due = payload.get("requested_due_date", "N/A")

        with st.container():
            st.markdown(f"""
            <div class="approval-card">
                <div style="display:flex; justify-content:space-between;">
                    <b>Request ID: <code>{req_id}</code></b>
                    <span style="color:#D97706; font-weight:bold;">PENDING REVIEW</span>
                </div>
                <div style="margin-top:6px;">
                    <b>Student ID:</b> <code>{req['student_id']}</code> · <b>Student:</b> {req.get('student_name', 'Unknown')}
                </div>
                <div style="margin-top:4px;">
                    <b>Programme:</b> {req.get('programme', 'PGDM')} · <b>Outstanding Fee:</b> ₹{payload.get('outstanding_amount', 0):,}
                </div>
                <div style="margin-top:4px;">
                    <b>Current Due Date:</b> {payload.get('current_due_date', 'N/A')} · <b>Proposed Due Date:</b> <b>{req_due}</b> · <b>Submitted:</b> {req['requested_at']}
                </div>
                <div style="margin-top:6px; background:#F8FAFC; padding:8px; border-radius:6px; font-size:0.9rem;">
                    <b>Student Reason:</b> “{payload.get('reason', 'N/A')}”
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_notes, col_act = st.columns([3, 2])
            with col_notes:
                notes = st.text_input(f"Admin Decision Notes ({req_id})", key=f"notes_{req_id}", placeholder="e.g. Approved per education loan proof")
            with col_act:
                st.write("")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✅ Approve", key=f"app_{req_id}", use_container_width=True):
                        try:
                            res = review_approval_request(
                                admin_user=user,
                                request_id=req_id,
                                decision="APPROVED",
                                decision_reason=notes or "Approved by academic administrator",
                            )
                            st.success(f"Request {req_id} APPROVED and executed! Fee extended to {req_due}")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Approval failed: {exc}")
                with b2:
                    if st.button("❌ Reject", key=f"rej_{req_id}", use_container_width=True):
                        try:
                            res = review_approval_request(
                                admin_user=user,
                                request_id=req_id,
                                decision="REJECTED",
                                decision_reason=notes or "Rejected per institution policy",
                            )
                            st.warning(f"Request {req_id} REJECTED. No fees were modified.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Rejection failed: {exc}")
            st.divider()
            st.divider()


def page_admin_approval_history():
    st.subheader("📜 Approval Decision History")
    with connection() as conn:
        rows = conn.execute("""
            SELECT request_id, student_id, action_type, status, reason, 
                   reviewed_by, reviewed_at, admin_notes, created_at
            FROM approval_requests
            ORDER BY created_at DESC
        """).fetchall()

    if not rows:
        st.info("No approval requests found.")
        return

    data = [dict(r) for r in rows]
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_admin_audit_logs():
    st.subheader("🛡️ Security Audit Log Explorer")
    st.caption("Immutable, append-only security audit trail recording all authentication, authorization, access control, and approval events.")

    c1, c2, c3 = st.columns(3)
    action_filter = c1.selectbox("Filter by Action", ["ALL", "auth.login", "auth.failed", "fee.view", "fee.request_extension", "approval.decision", "access.denied"])
    decision_filter = c2.selectbox("Filter by Decision", ["ALL", "ALLOWED", "DENIED"])
    student_search = c3.text_input("Filter by Student / Resource ID", placeholder="e.g. MIM25001")

    logs = query_audit_logs(
        action=None if action_filter == "ALL" else action_filter,
        decision=None if decision_filter == "ALL" else decision_filter,
        requested_resource_id=student_search.strip() or None,
        limit=200,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Events Displayed", len(logs))
    m2.metric("Allowed Actions", sum(1 for l in logs if l.get("authorization_decision") == "ALLOWED"))
    m3.metric("Denied Actions", sum(1 for l in logs if l.get("authorization_decision") == "DENIED"))
    m4.metric("Approval Events", sum(1 for l in logs if l.get("approval_status") is not None))

    if not logs:
        st.info("No audit logs matched the specified filters.")
        return

    display_data = []
    for l in logs:
        display_data.append({
            "Audit ID": l["audit_id"][:12] + "…",
            "Timestamp": l["timestamp"],
            "Requester": f"{l['requester_id']} ({l['requester_role']})",
            "Action": l["action_type"],
            "Target": l["requested_resource_id"] or "-",
            "Decision": l["authorization_decision"],
            "Approval": l["approval_status"] or "-",
            "Execution": l["execution_status"],
        })

    st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)

    pick_id = st.selectbox("Inspect Full Raw Security Record", [l["audit_id"] for l in logs])
    full_event = next(l for l in logs if l["audit_id"] == pick_id)
    st.json(full_event)


def page_admin_student_directory():
    st.subheader("👥 Student Directory (Admin View)")
    with connection() as conn:
        students = conn.execute("""
            SELECT s.student_id, s.name, s.programme, s.semester, s.cgpa, s.attendance_pct,
                   f.total_fee, f.paid_amount, f.outstanding_amount, f.payment_status, f.due_date
            FROM students s
            LEFT JOIN fees f ON s.student_id = f.student_id
            ORDER BY s.student_id
        """).fetchall()

    st.dataframe(pd.DataFrame([dict(r) for r in students]), use_container_width=True, hide_index=True)


# ───────────────────────── Shared Trace & Evaluation Pages ─────────────────────────
def page_activity_traces():
    st.subheader("🔍 Execution Traces & Privacy Verification")
    traces = load_traces(200, user.student_id if not user.is_admin() else None)
    scope = f"for {user.student_id}" if user.student_id else "for all sessions (Admin)"
    st.caption(f"Showing recent agent executions {scope}")

    if not traces:
        st.info("No execution traces found yet. Ask a question in the AI Chat Assistant.")
        return

    summary = summarise_traces(traces)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Runs", summary["runs"])
    m2.metric("Avg Latency", f"{summary['avg_latency_ms']} ms")
    m3.metric("Input Tokens", summary["total_input_tokens"])
    m4.metric("Output Tokens", summary["total_output_tokens"])

    table = pd.DataFrame([{
        "Execution ID": t["execution_id"],
        "Time": t["timestamp"],
        "Student": t["student_id"],
        "Query": t["user_query"][:60],
        "Intent": t["intent"],
        "Tools": ", ".join(c["tool"] for c in t.get("tool_calls", [])) or "-",
        "Status": t["final_status"],
        "ms": f"{t['duration_ms']:.0f}"
    } for t in traces])
    st.dataframe(table, use_container_width=True, hide_index=True)

    pick = st.selectbox("Inspect Trace Details", [t["execution_id"] for t in traces])
    st.json(next(t for t in traces if t["execution_id"] == pick))


def page_eval():
    st.subheader("📊 Evaluation & Security Verification Dashboard")
    st.markdown("""
    Run the automated benchmark covering normal task accuracy, authentication enforcement, cross-student privacy isolation, 
    unauthorized write prevention, human-in-the-loop approvals, and sensitive credential memory exclusion.
    """)

    from evaluation.results import load_latest, to_dataframe

    if st.button("▶ Run Full Assignment 2 Benchmark" + (" (live Groq)" if llm else " (offline security planner)")):
        from evaluation.evaluator import run_evaluation
        with st.spinner("Running 24 comprehensive evaluation test cases…"):
            try:
                run_evaluation(live=llm is not None)
                st.success("Evaluation completed successfully!")
            except Exception as exc:
                st.error(f"Evaluation error: {exc}")

    data = load_latest()
    if not data:
        st.info("No evaluation runs recorded yet. Press the button above to run the benchmark.")
        return

    s = data["summary"]
    st.caption(f"Mode: **{s['mode']}** · Run timestamp: `{s['run_at']}` · Embedder: **{s.get('embedder', 'lexical')}**")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Benchmark Accuracy", f"{s['accuracy_pct']}%", f"{s['passed']}/{s['total']}")
    c2.metric("Privacy & Ownership Isolation", f"{s.get('privacy_isolation_pct', 100.0)}%")
    c3.metric("Approval Workflow Correctness", f"{s.get('approval_correctness_pct', 100.0)}%")
    c4.metric("Credential Redaction Rate", f"{s.get('credential_redaction_pct', 100.0)}%")

    st.dataframe(to_dataframe(data["results"]), use_container_width=True, hide_index=True)

    if s.get("observations"):
        st.markdown("#### Key Benchmark Observations")
        for o in s["observations"]:
            st.markdown(f"- {o}")


def page_about():
    st.markdown(f"""
    ### 🛡️ {settings.APP_NAME} — Assignment 2
    **Program:** PGDM (BDA / AI & DS), Batch 2025–27  
    **Course:** Agentic AI Engineering  
    **Architecture:** Safe & Production-Aware LangGraph + Streamlit + SQLite + bcrypt + Groq

    ---

    #### Key Security Capabilities in Assignment 2:
    1. **Strict Identity & Authentication:** bcrypt password hashing (12 rounds), session tokens, thread-safe context.
    2. **Student Ownership Isolation:** Backend-enforced ownership checks on all private student records (fees, profile, scholarships, tickets, memory). Manipulating IDs in chat or UI is blocked and audited.
    3. **Human-in-the-Loop Approvals:** Sensitive actions (e.g. fee payment extensions) create pending requests that require authorized administrator adjudication before atomic execution.
    4. **Tamper-Resistant Security Audit Logging:** Complete, immutable audit log of every authentication, access control, and approval event.
    5. **Sensitive Credential Protection:** Automated regex detection and sanitization of passwords, OTPs, PINs, card numbers, and API keys from long-term memory, traces, and audit records.
    6. **Preserved Capabilities:** Retains 100% of Assignment 1 features including RAG, Groq LLM integration, offline fallback, and structured tracing.
    """)


# ───────────────────────── Page Dispatcher ─────────────────────────
page_map = {
    # Student Views
    "AI Chat Assistant": page_student_chat,
    "My Student Profile & Fees": page_student_profile,
    "My Approval Requests": page_student_approvals,
    "My Support Requests": page_student_tickets,
    "Agent Trace & Privacy": page_activity_traces,
    # Administrator Views
    "Pending Approvals Queue": page_admin_pending_queue,
    "Approval History": page_admin_approval_history,
    "Security Audit Explorer": page_admin_audit_logs,
    "AI Assistant (Admin Mode)": page_student_chat,
    "Student Directory": page_admin_student_directory,
    # Shared Views
    "Evaluation Dashboard": page_eval,
    "About Assignment 2": page_about,
}

if page in page_map:
    page_map[page]()
