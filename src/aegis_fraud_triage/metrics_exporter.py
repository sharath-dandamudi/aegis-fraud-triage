"""Read-only Prometheus metrics exporter for the local Aegis monitoring stack.

The agent remains the owner of its redacted JSONL audit trail. This lightweight
sidecar turns that trail into Prometheus gauges without requiring the agent to
expose a web server or retain sensitive request text in a metrics backend.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean
from typing import Any


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-2_000:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    return sorted(values)[max(0, int(len(values) * percentile) - 1)]


def _escaped(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _metric(name: str, value: float, labels: dict[str, str] | None = None) -> str:
    label_text = ""
    if labels:
        label_text = "{" + ",".join(f'{key}="{_escaped(value)}"' for key, value in sorted(labels.items())) + "}"
    return f"{name}{label_text} {value:.8g}"


def build_metrics_payload(trace_dir: str | Path) -> str:
    """Build Prometheus exposition text from redacted local artefacts only."""
    root = Path(trace_dir)
    traces = [item for item in _read_json_lines(root / "traces.jsonl") if not str(item.get("case_id") or "").startswith("BSTA-")]
    alerts = _read_json_lines(root / "alerts.jsonl")
    review_tasks = _read_json_lines(root / "review_queue.jsonl")
    results = [item.get("result", {}) for item in traces]
    routes = Counter(str(result.get("route", "unknown")) for result in results)
    risks = Counter(str(result.get("risk_tier", "unknown")) for result in results)
    gate_outcomes: Counter[tuple[str, str]] = Counter()
    for result in results:
        for gate in result.get("gates", []):
            gate_outcomes[(str(gate.get("name", "unknown")), "pass" if gate.get("passed") else "fail")] += 1
    window = results[-20:]
    window_gate_failures = sum(any(not gate.get("passed", True) for gate in result.get("gates", [])) for result in window)
    window_abstentions = sum(any(gate.get("name") == "abstention_gate" and not gate.get("passed", True) for gate in result.get("gates", [])) for result in window)

    lines = [
        "# HELP aegis_runtime_traces Number of interactive agent traces retained locally.",
        "# TYPE aegis_runtime_traces gauge",
        _metric("aegis_runtime_traces", len(results)),
        "# HELP aegis_escalation_rate Fraction of interactive requests requiring human escalation.",
        "# TYPE aegis_escalation_rate gauge",
        _metric("aegis_escalation_rate", (sum(bool(result.get("escalation_required")) for result in results) / len(results)) if results else 0.0),
        "# HELP aegis_review_queue_pending Number of drafts awaiting human review.",
        "# TYPE aegis_review_queue_pending gauge",
        _metric("aegis_review_queue_pending", sum(task.get("status") == "pending_human_review" for task in review_tasks)),
        "# HELP aegis_latency_ms Local observed latency percentile in milliseconds.",
        "# TYPE aegis_latency_ms gauge",
        _metric("aegis_latency_ms", _percentile([float(result.get("latency_ms", 0.0)) for result in results], 0.50), {"quantile": "0.50"}),
        _metric("aegis_latency_ms", _percentile([float(result.get("latency_ms", 0.0)) for result in results], 0.95), {"quantile": "0.95"}),
        "# HELP aegis_average_cost_aud Mean estimated cost in Australian dollars.",
        "# TYPE aegis_average_cost_aud gauge",
        _metric("aegis_average_cost_aud", mean(float(result.get("estimated_cost_aud", 0.0)) for result in results) if results else 0.0),
        "# HELP aegis_window_gate_failure_rate Gate failure rate across the latest 20 interactive traces.",
        "# TYPE aegis_window_gate_failure_rate gauge",
        _metric("aegis_window_gate_failure_rate", window_gate_failures / len(window) if window else 0.0),
        "# HELP aegis_window_abstention_rate Safe-abstention rate across the latest 20 interactive traces.",
        "# TYPE aegis_window_abstention_rate gauge",
        _metric("aegis_window_abstention_rate", window_abstentions / len(window) if window else 0.0),
        "# HELP aegis_alerts Current retained alert count by severity.",
        "# TYPE aegis_alerts gauge",
    ]
    for severity, count in sorted(Counter(str(alert.get("severity", "unknown")) for alert in alerts).items()):
        lines.append(_metric("aegis_alerts", count, {"severity": severity}))
    lines.extend(["# HELP aegis_route_traces Interactive trace count by routed scenario.", "# TYPE aegis_route_traces gauge"])
    for route, count in sorted(routes.items()):
        lines.append(_metric("aegis_route_traces", count, {"route": route}))
    lines.extend(["# HELP aegis_risk_traces Interactive trace count by assessed risk tier.", "# TYPE aegis_risk_traces gauge"])
    for risk, count in sorted(risks.items()):
        lines.append(_metric("aegis_risk_traces", count, {"risk_tier": risk}))
    lines.extend(["# HELP aegis_gate_outcomes Number of gate pass/fail outcomes in retained interactive traces.", "# TYPE aegis_gate_outcomes gauge"])
    for (gate, outcome), count in sorted(gate_outcomes.items()):
        lines.append(_metric("aegis_gate_outcomes", count, {"gate": gate, "outcome": outcome}))

    comparison_path = root.parent / "reports" / "latest_comparison.json"
    try:
        evaluation = json.loads(comparison_path.read_text(encoding="utf-8")).get("v1", {})
    except (FileNotFoundError, json.JSONDecodeError):
        evaluation = {}
    offline = {
        "routing_macro_f1": evaluation.get("routing", {}).get("macro_f1"),
        "escalation_f1": evaluation.get("escalation", {}).get("f1"),
        "citation_accuracy": evaluation.get("citation_accuracy_mean"),
        "guardrail_compliance": evaluation.get("guardrail_compliance"),
        "critical_escalation_recall": evaluation.get("critical_escalation_recall"),
    }
    lines.extend(["# HELP aegis_offline_eval Latest frozen golden-set evaluation score.", "# TYPE aegis_offline_eval gauge"])
    for metric_name, score in offline.items():
        if score is not None:
            lines.append(_metric("aegis_offline_eval", float(score), {"metric": metric_name, "dataset": "golden-v1"}))
    return "\n".join(lines) + "\n"


def run_server(trace_dir: str | Path, port: int = 8001) -> None:
    class MetricsHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler interface
            if self.path not in {"/metrics", "/metrics?"}:
                self.send_response(404)
                self.end_headers()
                return
            body = build_metrics_payload(trace_dir).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), MetricsHandler)
    print(f"Aegis metrics exporter listening on http://127.0.0.1:{port}/metrics")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Expose Aegis JSONL telemetry as Prometheus metrics.")
    parser.add_argument("--trace-dir", default="logs")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    run_server(args.trace_dir, args.port)
