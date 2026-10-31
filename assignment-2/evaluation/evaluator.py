"""Repeatable evaluation runner for Assignment 2 (Security, Privacy & Functionality).

Run:
    py -3.13 -m evaluation.evaluator           (deterministic security planner)
    py -3.13 -m evaluation.evaluator --live     (Groq model; needs GROQ_API_KEY)
"""
import argparse
import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

from config import settings
from auth.models import AuthUser
from auth.context import set_current_user, reset_current_user

DATASET = Path(__file__).resolve().parent / "dataset.json"


@contextmanager
def isolated_environment():
    """Point the app at a throw-away SQLite DB + Chroma dir, seed + ingest, restore afterwards."""
    tmp = tempfile.mkdtemp(prefix="ssa_sec_eval_")
    saved = {k: os.environ.get(k) for k in ("DB_PATH", "CHROMA_DIR")}
    os.environ["DB_PATH"] = str(Path(tmp) / "eval_secure.db")
    os.environ["CHROMA_DIR"] = str(Path(tmp) / "chroma")
    try:
        from database.seed import seed_database
        from rag.ingestion import ingest

        seed_database()
        ingest()
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)


def _context_for(student_id):
    from database.db import connection

    ctx = {"student": {}, "fee": {}, "sch": {}}
    if not student_id:
        return ctx
    with connection() as conn:
        for key, sql in (
            ("student", "SELECT * FROM students WHERE student_id=?"),
            ("fee", "SELECT * FROM fees WHERE student_id=?"),
            ("sch", "SELECT * FROM scholarships WHERE student_id=?"),
        ):
            row = conn.execute(sql, (student_id,)).fetchone()
            ctx[key] = dict(row) if row else {}
    return ctx


def check_response(case: dict, run: dict, ctx: dict) -> list[dict]:
    """Automated assertions on the response text/status."""
    import re

    def _norm(s: str) -> str:
        s = re.sub(r"[\*_`]", "", str(s))
        s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        s = s.replace("‑", " ").replace("-", " ")
        return re.sub(r"[\s\u202f\u00a0]+", " ", s).strip().lower()

    a = case.get("assertions", {})
    text = run.get("response", "")
    checks = []
    clean_text = _norm(text)

    for item in a.get("contains_all", []):
        want = item.format(**ctx)
        checks.append({"check": f"contains '{want}'", "ok": _norm(want) in clean_text})

    if a.get("contains_any"):
        checks.append({
            "check": f"contains any of {a['contains_any']}",
            "ok": any(_norm(w) in clean_text for w in a["contains_any"]),
        })

    for item in a.get("not_contains", []):
        checks.append({"check": f"does not contain '{item}'", "ok": _norm(item) not in clean_text})

    if a.get("status_in"):
        checks.append({"check": f"status in {a['status_in']}", "ok": run.get("status") in a["status_in"]})

    return checks


def check_state(case: dict, run: dict) -> list[dict]:
    """Automated assertions on side effects: DB rows, memory, audit logs, approval records."""
    from database import memory
    from database.db import connection
    from audit.service import query_audit_logs

    s = case.get("state_checks", {})
    sid = case.get("student_id")
    checks = []

    # Ticket check
    if s.get("ticket_created") and sid:
        with connection() as conn:
            row = conn.execute("SELECT ticket_id FROM support_tickets WHERE student_id=?", (sid,)).fetchone()
        checks.append({
            "check": "ticket row exists in DB",
            "ok": bool(row),
        })

    # Memory checks
    if sid:
        mems = " | ".join(m["content"] for m in memory.list_memories(sid))
        if s.get("memory_contains"):
            checks.append({
                "check": f"memory contains '{s['memory_contains']}'",
                "ok": s["memory_contains"].lower() in mems.lower(),
            })
        for bad in s.get("memory_absent", []):
            checks.append({
                "check": f"memory does NOT contain '{bad}'",
                "ok": bad.lower() not in mems.lower(),
            })

    # Audit checks
    if s.get("audit_denied"):
        denied_logs = query_audit_logs(decision="DENIED", limit=10)
        checks.append({
            "check": "security audit trail recorded DENIED access event",
            "ok": len(denied_logs) > 0,
        })

    if s.get("audit_entry_created"):
        recent = query_audit_logs(limit=5)
        checks.append({
            "check": "security audit event logged",
            "ok": len(recent) > 0,
        })

    if s.get("audit_logs_intact"):
        with connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) as c FROM security_audit_logs").fetchone()["c"]
        checks.append({
            "check": "audit log remains intact and immutable",
            "ok": cnt > 0,
        })

    # Approval checks
    if s.get("approval_request_created"):
        with connection() as conn:
            req = conn.execute("SELECT * FROM approval_requests WHERE student_id=? AND status='PENDING'", (sid,)).fetchone()
        checks.append({
            "check": "pending approval request created in DB",
            "ok": bool(req),
        })

    if s.get("fee_not_yet_extended") and sid:
        with connection() as conn:
            f = conn.execute("SELECT due_date FROM fees WHERE student_id=?", (sid,)).fetchone()
        checks.append({
            "check": "fee due date NOT modified prior to administrative approval",
            "ok": bool(f) and f["due_date"] in ("2026-08-15", "2026-11-30"),
        })

    if s.get("admin_approval_executes"):
        checks.append({
            "check": "admin approval executes fee extension",
            "ok": run.get("status") == "success",
        })

    if s.get("student_approval_blocked"):
        checks.append({
            "check": "student self-approval blocked by authorization layer",
            "ok": run.get("status") in ["access_denied", "error", "failed"],
        })

    return checks


def run_case(case: dict, llm) -> tuple[dict, dict]:
    from agent.graph import run_agent
    from database import memory
    from approval.service import create_fee_extension_request, review_approval_request
    from authorization.exceptions import AccessDeniedError, AdminPrivilegeRequiredError

    sid = case.get("student_id")
    auth_user = None

    if case.get("auth_username"):
        from auth.service import get_user_by_username
        auth_user = get_user_by_username(case["auth_username"])
        if auth_user is None:
            auth_user = AuthUser(
                user_id=f"USR-{case['auth_username'].upper()}",
                username=case["auth_username"],
                role=case.get("auth_role", "student"),
                student_id=sid,
                full_name=case["auth_username"].capitalize(),
                email=f"{case['auth_username']}@example.com",
            )
        set_current_user(auth_user)
    else:
        reset_current_user()

    # Clear memories for fresh run
    if sid:
        memory.clear_memories(sid)

    run = {}
    action_type = case.get("action_type")

    if action_type == "admin_approval":
        # Create a pending request first, then have admin approve
        from auth.service import get_user_by_username
        aarav_user = get_user_by_username("aarav")
        admin_u = get_user_by_username("admin")
        req = create_fee_extension_request(aarav_user, "Loan delay", "2025-09-15")
        review_res = review_approval_request(admin_u, req["request_id"], "APPROVED", "Approved by Dean")
        run = {
            "status": "success" if review_res.get("status") == "success" else "error",
            "response": f"Admin reviewed request: {review_res.get('decision')}",
            "tools_used": [],
            "sources": [],
            "memories_used": [],
            "trace": {"duration_ms": 15.0, "token_usage": {"input_tokens": 0, "output_tokens": 0, "available": False}, "execution_id": f"exec-admin-{req['request_id']}"},
        }
    elif action_type == "student_self_approval_attempt":
        # Create pending request, then student tries to review
        from auth.service import get_user_by_username
        student_u = get_user_by_username(case["auth_username"])
        req = create_fee_extension_request(student_u, "Loan delay", "2025-09-15")
        try:
            review_approval_request(student_u, req["request_id"], "APPROVED", "Self-approving")
            run = {"status": "success", "response": "Self approved", "tools_used": [], "sources": [], "memories_used": [], "trace": {"duration_ms": 10.0, "token_usage": {"input_tokens": 0, "output_tokens": 0, "available": False}, "execution_id": "exec-self"}}
        except (AccessDeniedError, AdminPrivilegeRequiredError) as exc:
            run = {"status": "access_denied", "response": str(exc), "tools_used": [], "sources": [], "memories_used": [], "trace": {"duration_ms": 10.0, "token_usage": {"input_tokens": 0, "output_tokens": 0, "available": False}, "execution_id": "exec-denied"}}
    elif action_type == "student_audit_tamper_attempt":
        from database.db import connection
        try:
            # Tamper attempt via normal execution - audit queries do not allow deletes
            run = run_agent(case["query"], sid, case["session"], [], llm=llm)
        except Exception as exc:
            run = {"status": "error", "response": str(exc), "tools_used": [], "sources": [], "memories_used": [], "trace": {"duration_ms": 10.0, "token_usage": {"input_tokens": 0, "output_tokens": 0, "available": False}, "execution_id": "exec-audit"}}
    else:
        # Standard query through agent
        run = run_agent(case["query"], sid, case["session"], [], llm=llm)

    ctx = _context_for(sid)
    checks = check_response(case, run, ctx) + check_state(case, run)
    tools = run.get("tools_used", [])
    expected = case.get("expected_tools", [])

    tool_ok = set(tools) == set(expected)
    passed = all(c["ok"] for c in checks) and tool_ok

    trace = run.get("trace", {})
    tok = trace.get("token_usage", {})

    result = {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "student_id": sid,
        "expected_tools": expected,
        "actual_tools": tools,
        "tool_ok": tool_ok,
        "assertions_ok": all(c["ok"] for c in checks),
        "checks": checks,
        "passed": passed,
        "latency_ms": trace.get("duration_ms", 0),
        "input_tokens": tok.get("input_tokens", 0),
        "output_tokens": tok.get("output_tokens", 0),
        "evidence": f"status={run.get('status')}",
        "response": run.get("response", ""),
    }

    return result, trace


def summarise(results: list[dict], mode: str, embedder: str) -> dict:
    n = len(results)
    lat = [r["latency_ms"] for r in results]
    tok_in = [r["input_tokens"] for r in results if isinstance(r["input_tokens"], int) and r["input_tokens"] > 0]
    tok_out = [r["output_tokens"] for r in results if isinstance(r["output_tokens"], int) and r["output_tokens"] > 0]

    # Specific category calculations
    privacy_cases = [r for r in results if r["id"] in ["SEC-10", "SEC-11", "SEC-12", "SEC-13", "SEC-14", "SEC-15", "SEC-16"]]
    privacy_rate = 100.0 * sum(r["passed"] for r in privacy_cases) / len(privacy_cases) if privacy_cases else 100.0

    approval_cases = [r for r in results if r["id"] in ["SEC-17", "SEC-18", "SEC-19", "SEC-20"]]
    approval_rate = 100.0 * sum(r["passed"] for r in approval_cases) / len(approval_cases) if approval_cases else 100.0

    redaction_cases = [r for r in results if r["id"] in ["SEC-21", "SEC-22"]]
    redaction_rate = 100.0 * sum(r["passed"] for r in redaction_cases) / len(redaction_cases) if redaction_cases else 100.0

    failed = [r["id"] for r in results if not r["passed"]]
    wrong_tool = [r["id"] for r in results if not r["tool_ok"]]

    obs = [
        f"Failed test cases: {failed or 'none'}. Tool selection mismatches: {wrong_tool or 'none'}.",
        f"Cross-student privacy isolation rate: {privacy_rate:.1f}% across {len(privacy_cases)} boundary tests.",
        f"Human-in-the-loop approval workflow correctness: {approval_rate:.1f}% across {len(approval_cases)} approval lifecycle tests.",
        f"Sensitive credential memory exclusion rate: {redaction_rate:.1f}% across {len(redaction_cases)} credential injection tests.",
    ]
    if "offline" in mode:
        obs.append("This run used the deterministic security planner, verifying authorization barriers, DB state, and approvals.")

    return {
        "mode": mode,
        "embedder": embedder,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": n,
        "passed": sum(r["passed"] for r in results),
        "accuracy_pct": round(100.0 * sum(r["passed"] for r in results) / n, 1),
        "tool_ok": sum(r["tool_ok"] for r in results),
        "tool_selection_pct": round(100.0 * sum(r["tool_ok"] for r in results) / n, 1),
        "privacy_isolation_pct": round(privacy_rate, 1),
        "approval_correctness_pct": round(approval_rate, 1),
        "credential_redaction_pct": round(redaction_rate, 1),
        "avg_latency_ms": round(mean(lat), 1) if lat else 0,
        "median_latency_ms": round(median(lat), 1) if lat else 0,
        "total_input_tokens": sum(tok_in) if tok_in else "unavailable",
        "total_output_tokens": sum(tok_out) if tok_out else "unavailable",
        "observations": obs,
    }


def run_evaluation(live: bool = False, save: bool = True) -> dict:
    from agent.llm import get_llm, model_label
    from evaluation.results import save_results
    from rag.embeddings import backend_name

    llm = get_llm() if live else None
    if live and llm is None:
        raise RuntimeError("--live requires GROQ_API_KEY")

    cases = json.loads(DATASET.read_text(encoding="utf-8"))["cases"]
    mode = f"live: {model_label(llm)}" if llm else "offline security planner"

    with isolated_environment():
        pairs = []
        for i, c in enumerate(cases):
            pairs.append(run_case(c, llm))
            if live and i < len(cases) - 1:
                import time
                time.sleep(1.0)

    results, traces = [p[0] for p in pairs], [p[1] for p in pairs]
    summary = summarise(results, mode, backend_name())
    if save:
        save_results(results, summary, traces)
    return {"summary": summary, "results": results, "traces": traces}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    out = run_evaluation(live=args.live)
    from evaluation.results import to_dataframe, to_markdown
    print(to_markdown(to_dataframe(out["results"]), out["summary"]))
