"""Save / load / format Assignment 2 evaluation results (pandas / JSON / Markdown)."""
import json
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def to_dataframe(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "id": r["id"],
            "category": r["category"],
            "query": r["query"][:55],
            "expected_tools": ", ".join(r.get("expected_tools", [])) or "(none)",
            "actual_tools": ", ".join(r.get("actual_tools", [])) or "(none)",
            "tool_ok": r.get("tool_ok", True),
            "assertions_ok": r.get("assertions_ok", True),
            "passed": r.get("passed", False),
            "latency_ms": r.get("latency_ms", 0),
            "evidence": r.get("evidence", "(none)"),
        })
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame, summary: dict) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("|", "/") for c in cols) + " |")

    s = summary
    head = [
        f"### Assignment 2 Security & Functional Benchmark Results",
        f"**Run Mode:** {s['mode']} | **Embedding Backend:** {s.get('embedder', 'lexical')} | **Run At:** {s['run_at']}",
        "",
        f"- **Task Accuracy:** **{s['accuracy_pct']}%** ({s['passed']}/{s['total']})",
        f"- **Tool Selection Accuracy:** **{s.get('tool_selection_pct', 100.0)}%** ({s.get('tool_ok', s['total'])}/{s['total']})",
        f"- **Privacy & Ownership Isolation:** **{s.get('privacy_isolation_pct', 100.0)}%**",
        f"- **Approval Workflow Correctness:** **{s.get('approval_correctness_pct', 100.0)}%**",
        f"- **Credential Redaction Rate:** **{s.get('credential_redaction_pct', 100.0)}%**",
        f"- **Average Latency:** **{s.get('avg_latency_ms', 0)} ms** (median {s.get('median_latency_ms', 0)} ms)",
        f"- **Token Usage:** input **{s.get('total_input_tokens', 'unavailable')}**, output **{s.get('total_output_tokens', 'unavailable')}**",
        "",
    ]
    return "\n".join(head + lines + ["", "### Key Benchmark Observations", ""] + [f"- {o}" for o in s.get("observations", [])])


def save_results(results: list[dict], summary: dict, traces: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = to_dataframe(results)
    (RESULTS_DIR / "latest_results.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2, default=str), encoding="utf-8")
    (RESULTS_DIR / "latest_traces.json").write_text(json.dumps(traces, indent=2, default=str), encoding="utf-8")
    df.to_csv(RESULTS_DIR / "latest_results.csv", index=False)
    (RESULTS_DIR / "latest_results.md").write_text(to_markdown(df, summary), encoding="utf-8")
    return RESULTS_DIR


def load_latest() -> dict | None:
    path = RESULTS_DIR / "latest_results.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
