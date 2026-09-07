"""Intentionally limited v0 baseline for meaningful before/after evaluation."""
from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from .models import GateResult, RiskTier, Route, TriageRequest, TriageResult


class BaselineTriageAgent:
    """Single-pass keyword RAG baseline: no tools, no evidence graph, no safety gates."""

    def run(self, request: TriageRequest) -> TriageResult:
        started = perf_counter(); text = request.message.lower()
        route = Route.AUTHORISED_PAYMENT_SCAM if any(term in text for term in ("payid", "transfer", "sent", "seller")) else Route.SCAM_INFORMATION
        response = "Please contact your bank if you are concerned about a scam."
        return TriageResult(route, RiskTier.LOW, response, False, None, [], [], [GateResult("baseline_no_gate", True)], str(uuid4()), (perf_counter() - started) * 1000, 0.001, ["single_pass_response"], request.message)
