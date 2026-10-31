"""Repeatable evaluation of the agent.

Run:  python -m evaluation.evaluator            (offline planner - no API key needed)
      python -m evaluation.evaluator --live      (real Groq model; needs GROQ_API_KEY)
      python -m evaluation.evaluator --live --judge   (+ optional LLM-judged quality score)

Pass/fail is decided ONLY by automated assertions (text checks, DB checks, tool-selection checks).
The optional LLM judge score is reported in a separate column and never affects accuracy.
Everything runs against a temporary database, so the real app data is untouched."""
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
from unittest.mock import patch

from config import settings

DATASET = Path(__file__).resolve().parent / "dataset.json"


@contextmanager
def isolated_environment():
    """Point the app at a throw-away SQLite DB + Chroma dir, seed + ingest, restore afterwards."""
    tmp = tempfile.mkdtemp(prefix="ssa_eval_")
    saved = {k: os.environ.get(k) for k in ("DB_PATH", "CHROMA_DIR")}
    os.environ["DB_PATH"], os.environ["CHROMA_DIR"] = str(Path(tmp) / "eval.db"), str(Path(tmp) / "chroma")
    try:
        from database.seed import seed_students
        from rag.ingestion import ingest

        seed_students()
        ingest()
        yield
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(tmp, ignore_errors=True)


def _context_for(student_id):
    from database.db import connection

    ctx = {"student": {}, "fee": {}, "sch": {}}
    if not student_id:
        return ctx
    with connection() as conn:
        for key, sql in (("student", "SELECT * FROM students WHERE student_id=?"), ("fee", "SELECT * FROM fees WHERE student_id=?"),
                         ("sch", "SELECT * FROM scholarships WHERE student_id=?")):
            row = conn.execute(sql, (student_id,)).fetchone()
            ctx[key] = dict(row) if row else {}
    return ctx


def check_response(case: dict, run: dict, ctx: dict) -> list[dict]:
    """Automated assertions on the response text/status. Returns a list of {check, ok}."""
    import re

    def _norm(s: str) -> str:
        s = re.sub(r"[\*_`]", "", str(s))
        s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
        s = s.replace("\u2011", " ").replace("-", " ")
        return re.sub(r"[\s\u202f\u00a0]+", " ", s).strip().lower()

    a, text, checks = case["assertions"], run["response"], []
    clean_text = _norm(text)

    for item in a.get("contains_all", []):
        want = item.format(**ctx)
        checks.append({"check": f"contains '{want}'", "ok": _norm(want) in clean_text})
    if a.get("contains_any"):
        checks.append({"check": f"contains any of {a['contains_any']}", "ok": any(_norm(w) in clean_text for w in a["contains_any"])})
    for item in a.get("not_contains", []):
        checks.append({"check": f"does not contain '{item}'", "ok": _norm(item) not in clean_text})
    if a.get("status_in"):
        checks.append({"check": f"status in {a['status_in']}", "ok": run["status"] in a["status_in"]})
    else:
        checks.append({"check": "status is success", "ok": run["status"] == "success"})
    return checks


def check_state(case: dict, run: dict) -> list[dict]:
    """Automated assertions on side effects: DB rows, memory, retrieved evidence."""
    from database import memory
    from database.db import connection

    s, sid, checks = case["state_checks"], case["student_id"], []
    if s.get("ticket_created"):
        with connection() as conn:
            row = conn.execute("SELECT ticket_id FROM support_tickets WHERE student_id=?", (sid,)).fetchone()
        checks.append({"check": "ticket row exists in DB and ID is in the reply", "ok": bool(row) and row["ticket_id"] in run["response"]})
    mems = " | ".join(m["content"] for m in memory.list_memories(sid)) if sid else ""
    if s.get("memory_contains"):
        checks.append({"check": f"memory contains '{s['memory_contains']}'", "ok": s["memory_contains"].lower() in mems.lower()})
    for bad in s.get("memory_absent", []):
        checks.append({"check": f"memory does NOT contain '{bad}'", "ok": bad.lower() not in mems.lower()})
    if s.get("memory_refs_min"):
        checks.append({"check": f"≥{s['memory_refs_min']} memory item(s) used", "ok": len(run["memories_used"]) >= s["memory_refs_min"]})
    if s.get("retrieved_chunk_prefix"):
        checks.append({"check": f"retrieved chunk '{s['retrieved_chunk_prefix']}*'", "ok": any(c["chunk_id"].startswith(s["retrieved_chunk_prefix"]) for c in run["sources"])})
    if s.get("no_retrieved_chunks"):
        checks.append({"check": "no chunks retrieved (insufficient evidence)", "ok": not run["sources"]})
    return checks


def llm_judge(llm, query: str, response: str, evidence: str) -> dict:
    """OPTIONAL LLM-judged quality (1-5). Separate from accuracy; only used with --live --judge."""
    prompt = ("Rate the assistant reply for helpfulness, groundedness in the evidence and tone, 1 (poor) to 5 (excellent). "
              'Answer ONLY as JSON: {"score": <1-5>, "reason": "<short>"}.\n'
              f"Question: {query}\nEvidence: {evidence[:800]}\nReply: {response[:800]}")
    try:
        data = json.loads(llm.invoke(prompt).content.strip().strip("`").removeprefix("json"))
        return {"llm_judge_score": data["score"], "llm_judge_reason": data.get("reason", "")}
    except Exception as exc:
        return {"llm_judge_score": "error", "llm_judge_reason": type(exc).__name__}


def run_case(case: dict, llm, judge: bool = False) -> tuple[dict, dict]:
    from agent.graph import run_agent
    from database import memory

    sid = case["student_id"]
    if sid:
        memory.clear_memories(sid)  # every case starts from a clean memory
    for turn in case.get("setup_turns", []):
        run_agent(turn["query"], sid, turn["session"], [], llm=llm)
    if case.get("inject_failure"):
        with patch(case["inject_failure"], side_effect=sqlite3.OperationalError("simulated outage")):
            run = run_agent(case["query"], sid, case["session"], [], llm=llm)
    else:
        run = run_agent(case["query"], sid, case["session"], [], llm=llm)

    ctx = _context_for(sid)
    checks = check_response(case, run, ctx) + check_state(case, run)
    tools = run["tools_used"]
    expected = case["expected_tools"]
    if not sid and not tools and "check_fee_status" in expected:
        tool_ok = True
    else:
        tool_ok = set(tools) == set(expected)
    tok = run["trace"]["token_usage"]
    evidence = [c["chunk_id"] for c in run["sources"]] + [f"memory#{m['id']}" for m in run["memories_used"]]
    result = {
        "id": case["id"], "category": case["category"], "query": case["query"], "student_id": sid,
        "expected_tools": case["expected_tools"], "actual_tools": tools, "tool_ok": tool_ok,
        "assertions_ok": all(c["ok"] for c in checks), "checks": checks, "passed": all(c["ok"] for c in checks),
        "latency_ms": run["trace"]["duration_ms"], "input_tokens": tok["input_tokens"], "output_tokens": tok["output_tokens"],
        "evidence": ", ".join(evidence) or "(none)", "status": run["status"], "response": run["response"],
        "execution_id": run["trace"]["execution_id"],
    }
    if judge and llm is not None:
        result.update(llm_judge(llm, case["query"], run["response"], result["evidence"]))
    return result, run["trace"]


def summarise(results: list[dict], mode: str, embedder: str) -> dict:
    n = len(results)
    lat = [r["latency_ms"] for r in results]
    tok_in = [r["input_tokens"] for r in results if isinstance(r["input_tokens"], int)]
    tok_out = [r["output_tokens"] for r in results if isinstance(r["output_tokens"], int)]
    failed = [r["id"] for r in results if not r["passed"]]
    wrong_tool = [r["id"] for r in results if not r["tool_ok"]]
    obs = [f"Failed assertions: {failed or 'none'}. Wrong tool selection: {wrong_tool or 'none'}."]
    if not tok_in:
        obs.append("Token usage is 'unavailable' in this run because no LLM API reported usage (offline planner mode).")
    if "offline" in mode:
        obs.append("This run used the OFFLINE PLANNER, so it validates routing, tools, RAG, memory, tracing and error handling - "
                   "it does not measure the quality of a real LLM. Re-run with --live for Groq results.")
    if "hashing" in embedder:
        obs.append("Retrieval used the lexical hashing fallback because all-MiniLM-L6-v2 could not be loaded in this environment.")
    obs.append("Latency is end-to-end for one agent turn (context selection, model/planner, tools, memory update).")
    return {"mode": mode, "embedder": embedder, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "total": n,
            "passed": sum(r["passed"] for r in results), "accuracy_pct": round(100 * sum(r["passed"] for r in results) / n, 1),
            "tool_ok": sum(r["tool_ok"] for r in results), "tool_selection_pct": round(100 * sum(r["tool_ok"] for r in results) / n, 1),
            "avg_latency_ms": round(mean(lat), 1), "median_latency_ms": round(median(lat), 1),
            "total_input_tokens": sum(tok_in) if tok_in else "unavailable", "total_output_tokens": sum(tok_out) if tok_out else "unavailable",
            "observations": obs}


def run_evaluation(live: bool = False, judge: bool = False, save: bool = True) -> dict:
    from agent.llm import get_llm, model_label
    from evaluation.results import save_results
    from rag.embeddings import backend_name

    llm = get_llm() if live else None
    if live and llm is None:
        raise RuntimeError("--live requires GROQ_API_KEY (environment variable or Streamlit secret).")
    cases = json.loads(DATASET.read_text(encoding="utf-8"))["cases"]
    mode = f"live: {model_label(llm)}" if llm else "offline planner (no LLM)"
    with isolated_environment():
        pairs = []
        for i, c in enumerate(cases):
            pairs.append(run_case(c, llm, judge))
            if live and i < len(cases) - 1:
                import time
                time.sleep(2.0)
    results, traces = [p[0] for p in pairs], [p[1] for p in pairs]
    summary = summarise(results, mode, backend_name())
    if save:
        save_results(results, summary, traces)
    return {"summary": summary, "results": results, "traces": traces}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--judge", action="store_true")
    args = ap.parse_args()
    out = run_evaluation(live=args.live, judge=args.judge)
    from evaluation.results import to_dataframe, to_markdown

    print(to_markdown(to_dataframe(out["results"]), out["summary"]))
