"""Human-in-the-loop response release policy and local demonstration queue."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import GateResult, RiskTier, Route, ToolEvent


@dataclass(frozen=True)
class ReviewAssessment:
    required: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReviewTask:
    review_id: str
    trace_id: str
    case_id: str | None
    route: str
    risk_tier: str
    reasons: list[str]
    draft_response: str
    evidence_chunk_ids: list[str]
    tool_summary: list[dict]
    gate_summary: list[dict]
    created_at: str
    case_package: dict | None = None
    status: str = "pending_human_review"


def assess_response_release(
    route: Route,
    risk: RiskTier,
    confidence: float,
    gates: list[GateResult],
    tools: list[ToolEvent],
) -> ReviewAssessment:
    """Return a conservative, explainable review decision.

    Automated release is deliberately limited to general safety or out-of-scope
    guidance that has passed all gates with high router confidence and no tools.
    Injection containment remains automated to avoid attackers creating a human
    review denial-of-service queue.
    """
    reasons: list[str] = []
    if route == Route.BLOCKED:
        return ReviewAssessment(False, ("automated_safety_containment",))
    if any(not gate.passed for gate in gates):
        reasons.append("safety_or_evidence_gate_failed")
    if any(tool.success for tool in tools):
        reasons.append("tool_result_used")
    if route in {Route.URGENT_FRAUD, Route.AUTHORISED_PAYMENT_SCAM, Route.CREDENTIAL_COMPROMISE, Route.CARD_SECURITY}:
        reasons.append("financial_or_account_security_case")
    if risk in {RiskTier.HIGH, RiskTier.CRITICAL}:
        reasons.append("high_risk_case")
    if confidence < 0.85:
        reasons.append("routing_confidence_below_release_threshold")
    return ReviewAssessment(bool(reasons), tuple(dict.fromkeys(reasons)))


def create_review_task(
    trace_id: str,
    case_id: str | None,
    route: Route,
    risk: RiskTier,
    assessment: ReviewAssessment,
    draft_response: str,
    evidence_chunk_ids: list[str],
    tools: list[ToolEvent],
    gates: list[GateResult],
    case_package: dict | None = None,
) -> ReviewTask:
    return ReviewTask(
        review_id=str(uuid4()), trace_id=trace_id, case_id=case_id, route=route.value,
        risk_tier=risk.value, reasons=list(assessment.reasons), draft_response=draft_response,
        evidence_chunk_ids=evidence_chunk_ids,
        tool_summary=[{"name": tool.name, "success": tool.success, "status": tool.output.get("status")} for tool in tools],
        gate_summary=[gate.as_dict() for gate in gates],
        created_at=datetime.now(UTC).isoformat(),
        case_package=case_package,
    )


class LocalReviewQueue:
    """Append-only audit log for the local Streamlit demo; not a production queue."""

    def __init__(self, directory: str | Path):
        self.path = Path(directory) / "review_queue.jsonl"

    def enqueue(self, task: ReviewTask) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._append({"event": "created", "task": asdict(task)})

    def resolve(self, review_id: str, decision: str, reviewer_id: str, edited_response: str | None = None, note: str = "") -> None:
        if decision not in {"approved", "edited", "escalated", "rejected"}:
            raise ValueError("Unsupported review decision")
        if not reviewer_id.strip():
            raise ValueError("Reviewer ID is required")
        self._append({
            "event": "resolved", "review_id": review_id, "decision": decision,
            "reviewer_id": reviewer_id.strip(), "edited_response": edited_response if decision == "edited" else None,
            "note": note[:500], "resolved_at": datetime.now(UTC).isoformat(),
        })

    def tasks(self) -> list[dict]:
        if not self.path.exists():
            return []
        states: dict[str, dict] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") == "created":
                task = record["task"]
                states[task["review_id"]] = task
            elif record.get("event") == "resolved" and record["review_id"] in states:
                states[record["review_id"]].update({
                    "status": record["decision"], "reviewer_id": record["reviewer_id"],
                    "edited_response": record.get("edited_response"), "review_note": record.get("note"),
                    "resolved_at": record["resolved_at"],
                })
        return sorted(states.values(), key=lambda task: task["created_at"], reverse=True)

    def _append(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
