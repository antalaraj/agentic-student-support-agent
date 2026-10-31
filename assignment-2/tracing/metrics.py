"""Aggregate metrics from trace dicts. Token usage is reported only when the API supplied it."""
from statistics import mean


def summarise_traces(traces: list[dict]) -> dict:
    if not traces:
        return {"runs": 0}
    durations = [t["duration_ms"] for t in traces if t.get("duration_ms") is not None]
    with_tokens = [t for t in traces if t.get("token_usage", {}).get("available")]
    tool_counts: dict[str, int] = {}
    for t in traces:
        for call in t.get("tool_calls", []):
            tool_counts[call["tool"]] = tool_counts.get(call["tool"], 0) + 1
    return {
        "runs": len(traces),
        "success_rate_pct": round(100 * sum(t.get("final_status") in ("success", "degraded_fallback") for t in traces) / len(traces), 1),
        "avg_latency_ms": round(mean(durations), 1) if durations else None,
        "tool_call_counts": tool_counts,
        "runs_with_token_data": len(with_tokens),
        "total_input_tokens": sum(t["token_usage"]["input_tokens"] for t in with_tokens) if with_tokens else "unavailable",
        "total_output_tokens": sum(t["token_usage"]["output_tokens"] for t in with_tokens) if with_tokens else "unavailable",
    }
