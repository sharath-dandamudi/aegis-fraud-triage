from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Route(str, Enum):
    URGENT_FRAUD = "urgent_fraud"
    AUTHORISED_PAYMENT_SCAM = "authorised_payment_scam"
    CREDENTIAL_COMPROMISE = "credential_compromise"
    CARD_SECURITY = "card_security"
    SCAM_INFORMATION = "scam_information"
    OUT_OF_SCOPE = "out_of_scope"
    BLOCKED = "blocked"


class RiskTier(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending_human_review"
    APPROVED = "approved"
    EDITED = "edited"
    ESCALATED = "escalated"
    REJECTED = "rejected"


@dataclass(frozen=True)
class TriageRequest:
    message: str
    customer_reference: str = "demo-customer"
    channel: str = "web"
    case_id: str | None = None
    tool_authorisation: Any | None = None
    enqueue_review: bool = True


@dataclass
class Evidence:
    source_id: str
    chunk_id: str
    title: str
    text: str
    score: float
    node_type: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolEvent:
    name: str
    input: dict[str, Any]
    output: dict[str, Any]
    success: bool
    duration_ms: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GateResult:
    name: str
    passed: bool
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResponseContract:
    """Server-validated envelope around a generated customer draft.

    The model can propose prose, but this contract is assembled and validated
    by application code from the route, retrieved evidence and passed gates.
    It is deliberately a review artefact, not a banking instruction.
    """

    risk_summary: str
    recommended_actions: list[str]
    citations: list[str]
    requires_human_review: bool
    prohibited_claims_check: str
    evidence_backed: bool
    schema_valid: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TriageResult:
    route: Route
    risk_tier: RiskTier
    response: str
    escalation_required: bool
    escalation_reason: str | None
    evidence: list[Evidence]
    tools: list[ToolEvent]
    gates: list[GateResult]
    trace_id: str
    latency_ms: float
    estimated_cost_aud: float
    trajectory: list[str]
    redacted_input: str
    review_required: bool = False
    review_status: ReviewStatus = ReviewStatus.NOT_REQUIRED
    review_reasons: list[str] = field(default_factory=list)
    review_id: str | None = None
    response_contract: ResponseContract | None = None
    case_package: dict[str, Any] | None = None
    urgent_override_triggered: bool = False
    urgent_override_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value, "risk_tier": self.risk_tier.value,
            "response": self.response, "escalation_required": self.escalation_required,
            "escalation_reason": self.escalation_reason,
            "evidence": [x.as_dict() for x in self.evidence], "tools": [x.as_dict() for x in self.tools],
            "gates": [x.as_dict() for x in self.gates], "trace_id": self.trace_id,
            "latency_ms": round(self.latency_ms, 2), "estimated_cost_aud": self.estimated_cost_aud,
            "trajectory": self.trajectory, "redacted_input": self.redacted_input,
            "review_required": self.review_required, "review_status": self.review_status.value,
            "review_reasons": self.review_reasons, "review_id": self.review_id,
            "response_contract": self.response_contract.as_dict() if self.response_contract else None,
            "case_package": self.case_package,
            "urgent_override_triggered": self.urgent_override_triggered,
            "urgent_override_reasons": self.urgent_override_reasons,
        }
