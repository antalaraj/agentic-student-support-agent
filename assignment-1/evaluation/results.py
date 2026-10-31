"""Save / load / format evaluation results (pandas)."""
import json
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def to_dataframe(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "id": r["id"], "category": r["category"], "query": r["query"][:60],
            "expected_tools": ", ".join(r["expected_tools"]) or "(none)", "actual_tools": ", ".join(r["actual_tools"]) or "(none)",
            "tool_ok": r["tool_ok"], "assertions_ok": r["assertions_ok"], "passed": r["passed"],
            "latency_ms": r["latency_ms"], "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
            "evidence": r["evidence"], "llm_judge_score": r.get("llm_judge_score", "not run"),
        })
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame, summary: dict) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("|", "/") for c in cols) + " |")
    s = summary
    head = [f"**Run mode:** {s['mode']}  |  **Embedding backend:** {s['embedder']}  |  **Run at:** {s['run_at']}", "",
            f"- Task accuracy (automated assertions): **{s['accuracy_pct']}%** ({s['passed']}/{s['total']})",
            f"- Appropriate tool selection: **{s['tool_selection_pct']}%** ({s['tool_ok']}/{s['total']})",
            f"- Average latency: **{s['avg_latency_ms']} ms** (median {s['median_latency_ms']} ms)",
            f"- Token usage: input **{s['total_input_tokens']}**, output **{s['total_output_tokens']}**", ""]
    return "\n".join(head + lines + ["", "**Observations**", ""] + [f"- {o}" for o in s["observations"]])


def save_results(results: list[dict], summary: dict, traces: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = to_dataframe(results)
    (RESULTS_DIR / "latest_results.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1, default=str), encoding="utf-8")
    (RESULTS_DIR / "latest_traces.json").write_text(json.dumps(traces, indent=1, default=str), encoding="utf-8")
    df.to_csv(RESULTS_DIR / "latest_results.csv", index=False)
    (RESULTS_DIR / "latest_results.md").write_text(to_markdown(df, summary), encoding="utf-8")
    return RESULTS_DIR


def load_latest() -> dict | None:
    path = RESULTS_DIR / "latest_results.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
