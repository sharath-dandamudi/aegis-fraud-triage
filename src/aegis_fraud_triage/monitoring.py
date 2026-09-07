"""Local online monitoring and alert policy for the Aegis MVP.

Alerts are written as redacted JSONL events.  They are local demonstration
controls, not an incident-management integration or a production paging system.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4


ALERT_POLICY_VERSION = "v1.0.0"
ONLINE_WINDOW_SIZE = 20
MAX_WINDOW_GATE_FAILURE_RATE = 0.05
MAX_WINDOW_ABSTENTION_RATE = 0.10
MAX_WINDOW_P95_LATENCY_MS = 3_000
MAX_WINDOW_AVERAGE_COST_AUD = 0.10


@dataclass(frozen=True)
class Alert:
    alert_id: str
    created_at: str
    severity: str
    code: str
    message: str
    trace_id: str
    case_id: str | None
    policy_version: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    return sorted(values)[max(0, int(len(values) * percentile) - 1)]


class AlertEngine:
    """Evaluates a redacted trace against static and rolling-window policies."""

    def __init__(self, trace_dir: str | Path):
        self.trace_dir = Path(trace_dir)
        self.alert_path = self.trace_dir / "alerts.jsonl"
        self.trace_path = self.trace_dir / "traces.jsonl"

    def evaluate(self, result: dict[str, Any], case_id: str | None = None) -> list[Alert]:
        alerts: list[Alert] = []
        gates = {gate["name"]: gate for gate in result.get("gates", [])}
        tools = result.get("tools", [])

        def add(severity: str, code: str, message: str, **metadata: Any) -> None:
            alerts.append(Alert(str(uuid4()), datetime.now(UTC).isoformat(), severity, code, message, result["trace_id"], case_id, ALERT_POLICY_VERSION, metadata))

        if any(tool.get("success") and (tool.get("output", {}).get("status") != "mock_success" or not tool.get("output", {}).get("policy_id")) for tool in tools):
            add("critical", "unauthorised_successful_tool", "A tool reported success without a valid policy-authorisation result.")
        if re.search(r"\b(?:\d[ -]*?){13,16}\b|\b[\w.+-]+@[\w-]+\.[\w.-]+\b", result.get("response", "")):
            add("critical", "sensitive_data_in_response", "Potential sensitive data was detected in a generated response.")
        if result.get("route") == "urgent_fraud" and not result.get("review_required"):
            add("critical", "critical_case_auto_release", "An urgent-fraud case was not held for human review.")
        if not gates.get("output_safety", {"passed": True}).get("passed", True):
            add("high", "output_safety_failure", "Output-safety guardrail failed; verify human handoff.")
        for gate_name, code in {
            "retrieval_quality": "retrieval_quality_failure",
            "generation_contract": "generation_contract_failure",
            "evidence_gate": "evidence_grounding_failure",
            "abstention_gate": "safe_abstention_triggered",
        }.items():
            if not gates.get(gate_name, {"passed": True}).get("passed", True):
                severity = "high" if gate_name != "abstention_gate" else "medium"
                add(severity, code, f"{gate_name} did not pass; review trace and handoff.", reasons=gates[gate_name].get("reasons", []))
        if not gates.get("tool_authorisation", {"passed": True}).get("passed", True):
            add("medium", "tool_authorisation_denied", "A requested tool call was denied by policy.", reasons=gates["tool_authorisation"].get("reasons", []))
        if not gates.get("input_safety", {"passed": True}).get("passed", True):
            add("medium", "input_safety_containment", "Input safety containment was triggered.", reasons=gates["input_safety"].get("reasons", []))

        window = self._runtime_window() + [result]
        if len(window) >= ONLINE_WINDOW_SIZE:
            gate_failures = sum(any(not gate.get("passed", True) for gate in trace.get("gates", [])) for trace in window)
            abstentions = sum(any(gate.get("name") == "abstention_gate" and not gate.get("passed", True) for gate in trace.get("gates", [])) for trace in window)
            p95_latency = _percentile([trace.get("latency_ms", 0.0) for trace in window], 0.95)
            avg_cost = mean(trace.get("estimated_cost_aud", 0.0) for trace in window)
            if gate_failures / len(window) > MAX_WINDOW_GATE_FAILURE_RATE:
                add("high", "gate_failure_rate_breach", "Rolling gate-failure rate exceeded policy threshold.", observed=round(gate_failures / len(window), 3), threshold=MAX_WINDOW_GATE_FAILURE_RATE, window=len(window))
            if abstentions / len(window) > MAX_WINDOW_ABSTENTION_RATE:
                add("medium", "abstention_rate_breach", "Rolling abstention rate exceeded policy threshold.", observed=round(abstentions / len(window), 3), threshold=MAX_WINDOW_ABSTENTION_RATE, window=len(window))
            if p95_latency > MAX_WINDOW_P95_LATENCY_MS:
                add("medium", "latency_slo_breach", "Rolling p95 latency exceeded policy threshold.", observed_ms=round(p95_latency, 2), threshold_ms=MAX_WINDOW_P95_LATENCY_MS, window=len(window))
            if avg_cost > MAX_WINDOW_AVERAGE_COST_AUD:
                add("medium", "cost_slo_breach", "Rolling average cost exceeded policy threshold.", observed_aud=round(avg_cost, 4), threshold_aud=MAX_WINDOW_AVERAGE_COST_AUD, window=len(window))
        return alerts

    def record(self, alerts: list[Alert]) -> None:
        if not alerts:
            return
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        with self.alert_path.open("a", encoding="utf-8") as handle:
            for alert in alerts:
                handle.write(json.dumps(alert.as_dict()) + "\n")

    def _runtime_window(self) -> list[dict[str, Any]]:
        if not self.trace_path.exists():
            return []
        results = []
        for line in self.trace_path.read_text(encoding="utf-8").splitlines()[-500:]:
            try:
                trace = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(trace.get("case_id") or "").startswith("BSTA-"):
                continue
            results.append(trace.get("result", {}))
        return results[-(ONLINE_WINDOW_SIZE - 1):]


def load_alerts(trace_dir: str | Path, limit: int = 250) -> list[dict[str, Any]]:
    path = Path(trace_dir) / "alerts.jsonl"
    if not path.exists():
        return []
    alerts = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            alerts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(alerts))


def alert_policy_catalog() -> list[dict[str, Any]]:
    return [
        {"severity": "critical", "code": "unauthorised_successful_tool", "threshold": "any occurrence", "action": "disable tool path and investigate"},
        {"severity": "critical", "code": "sensitive_data_in_response", "threshold": "any occurrence", "action": "stop release and investigate"},
        {"severity": "critical", "code": "critical_case_auto_release", "threshold": "any occurrence", "action": "switch to review-all"},
        {"severity": "high", "code": "output/retrieval/generation/evidence failure", "threshold": "any occurrence", "action": "verify human handoff"},
        {"severity": "high", "code": "gate_failure_rate_breach", "threshold": f"> {MAX_WINDOW_GATE_FAILURE_RATE:.0%} of {ONLINE_WINDOW_SIZE} traces", "action": "pause auto-release"},
        {"severity": "medium", "code": "abstention_rate_breach", "threshold": f"> {MAX_WINDOW_ABSTENTION_RATE:.0%} of {ONLINE_WINDOW_SIZE} traces", "action": "review corpus/retriever"},
        {"severity": "medium", "code": "latency_slo_breach", "threshold": f"p95 > {MAX_WINDOW_P95_LATENCY_MS:,} ms over {ONLINE_WINDOW_SIZE} traces", "action": "investigate provider/tool latency"},
        {"severity": "medium", "code": "cost_slo_breach", "threshold": f"mean > A${MAX_WINDOW_AVERAGE_COST_AUD:.2f} over {ONLINE_WINDOW_SIZE} traces", "action": "investigate model/tool use"},
    ]
