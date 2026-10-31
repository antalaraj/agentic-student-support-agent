import json

from evaluation import evaluator
from evaluation.results import to_dataframe, to_markdown


def test_dataset_has_required_coverage():
    cases = json.loads(evaluator.DATASET.read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 12
    cats = " ".join(c["category"].lower() for c in cases)
    for needed in ("fee", "scholarship", "profile", "policy", "course change", "ticket", "memory", "general", "missing", "unknown policy", "failure", "sensitive"):
        assert needed in cats


def test_summary_math_is_computed_from_results():
    base = {"category": "c", "query": "q", "expected_tools": [], "actual_tools": [], "evidence": "", "status": "success", "response": ""}
    results = [dict(base, id="a", passed=True, tool_ok=True, latency_ms=10.0, input_tokens="unavailable", output_tokens="unavailable"),
               dict(base, id="b", passed=False, tool_ok=True, latency_ms=30.0, input_tokens="unavailable", output_tokens="unavailable"),
               dict(base, id="c", passed=True, tool_ok=False, latency_ms=20.0, input_tokens="unavailable", output_tokens="unavailable"),
               dict(base, id="d", passed=True, tool_ok=True, latency_ms=40.0, input_tokens="unavailable", output_tokens="unavailable")]
    s = evaluator.summarise(results, "offline planner", "hashing")
    assert (s["accuracy_pct"], s["tool_selection_pct"], s["avg_latency_ms"], s["median_latency_ms"]) == (75.0, 75.0, 25.0, 25.0)
    assert s["total_input_tokens"] == "unavailable"


def test_token_totals_use_only_real_numbers():
    base = {"category": "c", "query": "q", "expected_tools": [], "actual_tools": [], "evidence": "", "status": "success", "response": "", "passed": True, "tool_ok": True, "latency_ms": 1.0}
    results = [dict(base, id="a", input_tokens=100, output_tokens=10), dict(base, id="b", input_tokens="unavailable", output_tokens="unavailable"),
               dict(base, id="c", input_tokens=50, output_tokens=5)]
    s = evaluator.summarise(results, "live", "minilm")
    assert (s["total_input_tokens"], s["total_output_tokens"]) == (150, 15)


def test_evaluator_can_fail_wrong_assertion_and_wrong_tool():
    case = {"id": "X", "category": "neg", "student_id": "MIM25002", "query": "What is my current fee status?", "session": "s",
            "expected_tools": ["search_policy"], "assertions": {"contains_all": ["this text is not in the answer"]}, "state_checks": {}}
    result, _ = evaluator.run_case(case, None)
    assert result["passed"] is False and result["tool_ok"] is False


def test_full_offline_evaluation_runs_and_is_internally_consistent():
    out = evaluator.run_evaluation(live=False, save=False)
    res, s = out["results"], out["summary"]
    assert len(res) >= 12 and len(out["traces"]) == len(res)
    assert s["passed"] == sum(r["passed"] for r in res) and s["accuracy_pct"] == round(100 * s["passed"] / s["total"], 1)
    assert s["total_input_tokens"] == "unavailable" and "offline" in s["mode"]
    assert all(r["checks"] for r in res)
    assert "Task accuracy" in to_markdown(to_dataframe(res), s)


def test_evaluation_does_not_touch_the_app_database():
    from database.db import connection

    with connection() as conn:
        before = conn.execute("SELECT COUNT(*) FROM execution_traces").fetchone()[0]
    evaluator.run_evaluation(live=False, save=False)
    with connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM execution_traces").fetchone()[0] == before
