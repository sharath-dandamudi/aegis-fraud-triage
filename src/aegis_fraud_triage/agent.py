from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .knowledge import LocalGraphRetriever
from .pinecone_policy import PineconePolicyRetriever
from .models import Evidence, GateResult, ResponseContract, ReviewStatus, RiskTier, Route, ToolEvent, TriageRequest, TriageResult
from .observability import TelemetryBridge, traceable_if_configured
from .tool_authorisation import authorise_tool_call
from .hitl import LocalReviewQueue, assess_response_release, create_review_task
from .monitoring import AlertEngine
from .nebius_generation import NebiusEvidenceGenerator


@dataclass(frozen=True)
class Decision:
    route: Route
    risk: RiskTier
    escalate: bool
    reason: str
    confidence: float
    safety_override: bool = False
    override_reasons: tuple[str, ...] = ()


class AegisFraudTriageAgent:
    """Conservative, deterministic v1; each step is a future LangGraph node."""

    def __init__(self, trace_dir: str | Path = "logs"):
        self.retriever = PineconePolicyRetriever() if os.getenv("RAG_BACKEND", "local").lower() == "pinecone" else LocalGraphRetriever()
        self.generator = NebiusEvidenceGenerator()
        self.trace_dir = Path(trace_dir)
        self.telemetry = TelemetryBridge()
        self.review_queue = LocalReviewQueue(self.trace_dir)
        self.alert_engine = AlertEngine(self.trace_dir)

    @traceable_if_configured("aegis_fraud_triage.run")
    def run(self, request: TriageRequest) -> TriageResult:
        started = perf_counter()
        trace_id = str(uuid4())
        events, trajectory, gates, tools = [], [], [], []
        clean = self._redact(request.message)
        input_gate = self._input_gate(request.message)
        gates.append(input_gate); trajectory.append("input_safety")
        self._event(events, "input_safety", passed=input_gate.passed, reasons=input_gate.reasons)
        decision = self._route(request.message)
        trajectory.append("router")
        self._event(events, "router", route=decision.route.value, risk=decision.risk.value, escalate=decision.escalate, confidence=decision.confidence, urgent_override=decision.safety_override)
        if decision.safety_override:
            trajectory.append("urgent_risk_override")
            self._event(events, "urgent_risk_override", reasons=list(decision.override_reasons), route=decision.route.value)

        if decision.route == Route.BLOCKED:
            evidence = self.retriever.retrieve("official bank scam safety", Route.SCAM_INFORMATION)
            response = "I can’t help bypass safeguards or reveal protected information. If you may be experiencing a scam, use an official bank contact channel. [kb.v1.contact_official.001]"
            return self._finish(request, trace_id, decision, response, True, "Safety containment", evidence, tools, gates, trajectory, clean, started, events)

        if decision.route == Route.OUT_OF_SCOPE:
            evidence = self.retriever.retrieve("general scam safety", Route.SCAM_INFORMATION)
            retrieval_gate = self._retrieval_gate(evidence, Route.SCAM_INFORMATION)
            gates.append(retrieval_gate); trajectory.extend(["graph_retrieval", "retrieval_quality_gate"])
            self._event(events, "retrieval_quality_gate", passed=retrieval_gate.passed, reasons=retrieval_gate.reasons)
            response = "I can provide general scam-safety information, but not personal legal, tax, or investment advice. For a possible scam, contact your bank through an official channel. [kb.v1.general_safety.001] [kb.v1.contact_official.001]"
            generation_gate = self._generation_gate(response)
            evidence_gate = self._evidence_gate(response, evidence)
            safety_gate = self._output_gate(response, decision.route)
            abstention_gate = self._abstention_gate(retrieval_gate, generation_gate, evidence_gate)
            gates.extend([generation_gate, evidence_gate, abstention_gate, safety_gate]); trajectory.extend(["generation_contract_gate", "evidence_gate", "abstention_gate", "output_safety"])
            self._event(events, "generation_contract_gate", passed=generation_gate.passed, reasons=generation_gate.reasons)
            self._event(events, "evidence_gate", passed=evidence_gate.passed, reasons=evidence_gate.reasons)
            self._event(events, "abstention_gate", passed=abstention_gate.passed, reasons=abstention_gate.reasons)
            self._event(events, "output_safety", passed=safety_gate.passed, reasons=safety_gate.reasons)
            return self._finish(request, trace_id, decision, response, False, None, evidence, tools, gates, trajectory, clean, started, events)

        evidence = self.retriever.retrieve(clean, decision.route)
        trajectory.append("graph_retrieval")
        self._event(events, "graph_retrieval", source_ids=[item.source_id for item in evidence])
        retrieval_gate = self._retrieval_gate(evidence, decision.route)
        gates.append(retrieval_gate); trajectory.append("retrieval_quality_gate")
        self._event(events, "retrieval_quality_gate", passed=retrieval_gate.passed, reasons=retrieval_gate.reasons)
        tools, tool_gate = self._run_tools(request, decision) if retrieval_gate.passed else ([], None)
        if not retrieval_gate.passed:
            self._event(events, "tool_plan", skipped=True, reason="retrieval_quality_gate_failed")
        if tool_gate:
            gates.append(tool_gate)
            self._event(events, "tool_authorisation", passed=tool_gate.passed, reasons=tool_gate.reasons)
        if tools:
            trajectory.append("tool_authorisation")
            if any(item.success for item in tools):
                trajectory.append("policy_authorised_tools")
            self._event(events, "tool_gateway", names=[item.name for item in tools], success=[item.success for item in tools])
        response = self._response(decision, evidence)
        generation = self.generator.draft(clean, decision.route, decision.risk, evidence)
        if generation.response:
            response = generation.response
            trajectory.append("evidence_constrained_nebius_draft")
            self._event(events, "nebius_generation", model=generation.model, input_tokens=generation.input_tokens, output_tokens=generation.output_tokens, fallback=False)
        else:
            trajectory.append("deterministic_response_fallback")
            self._event(events, "nebius_generation", model=generation.model, fallback=True, reason=generation.fallback_reason)
        # The output gate must assess the response that can actually be
        # released. Add the mandatory urgent-review handoff before generation,
        # evidence and safety gates rather than after they have already run.
        if decision.route == Route.URGENT_FRAUD and not re.search(r"human\s+(?:(?:fraud\s+)?review|fraud\s+specialist)", response.lower()):
            response += " A human fraud specialist will review this report. Use an official bank contact channel for immediate support. [kb.v1.contact_official.001]"
        trajectory.append("response_builder")
        generation_gate = self._generation_gate(response)
        evidence_gate = self._evidence_gate(response, evidence)
        safety_gate = self._output_gate(response, decision.route)
        abstention_gate = self._abstention_gate(retrieval_gate, generation_gate, evidence_gate)
        if not abstention_gate.passed:
            response = self._abstention_response(evidence)
            trajectory.append("safe_abstention")
        contract_gate = self._structured_contract_gate(response, decision, evidence, safety_gate)
        gates.extend([generation_gate, evidence_gate, abstention_gate, safety_gate, contract_gate]); trajectory.extend(["generation_contract_gate", "evidence_gate", "abstention_gate", "output_safety", "structured_response_contract"])
        self._event(events, "generation_contract_gate", passed=generation_gate.passed, reasons=generation_gate.reasons)
        self._event(events, "evidence_gate", passed=evidence_gate.passed, reasons=evidence_gate.reasons)
        self._event(events, "abstention_gate", passed=abstention_gate.passed, reasons=abstention_gate.reasons)
        self._event(events, "output_safety", passed=safety_gate.passed, reasons=safety_gate.reasons)
        self._event(events, "structured_response_contract", passed=contract_gate.passed, reasons=contract_gate.reasons)
        tool_authorisation_failed = tool_gate is not None and not tool_gate.passed
        evidence_insufficient = not abstention_gate.passed
        escalate = decision.escalate or tool_authorisation_failed or evidence_insufficient or not safety_gate.passed or not contract_gate.passed or decision.confidence < 0.55
        reason = decision.reason if decision.escalate else ("Tool authorisation denied" if tool_authorisation_failed else "Insufficient approved evidence" if evidence_insufficient else None)
        if escalate:
            fraud_case, case_gate = self._fraud_case_tool(request, decision, reason or "Safety or evidence review")
            tools.append(fraud_case)
            gates.append(case_gate)
            self._event(events, "tool_authorisation", passed=case_gate.passed, reasons=case_gate.reasons)
            trajectory.append("human_escalation")
            if "human fraud specialist" not in response.lower():
                response += " A human fraud specialist will review this report. Use an official bank contact channel for immediate support. [kb.v1.contact_official.001]"
        return self._finish(request, trace_id, decision, response, escalate, reason, evidence, tools, gates, trajectory, clean, started, events)

    @staticmethod
    def _route(message: str) -> Decision:
        text = message.lower()
        if re.search(r"ignore.*(instructions|safety)|reveal (the )?(system|hidden) prompt|show .*customer.*data|another customer|transfer tool|unrestricted bank operator|bypass all checks", text):
            return Decision(Route.BLOCKED, RiskTier.LOW, False, "Prompt injection or data-exfiltration attempt", 0.99)
        if re.search(r"how can i stay safe|what signs|safe ways to contact|never share|where can i report|gift cards", text):
            return Decision(Route.SCAM_INFORMATION, RiskTier.LOW, False, "General scam-prevention request", 0.85)
        if re.search(r"should i invest|which shares|legal advice|tax advice", text):
            return Decision(Route.OUT_OF_SCOPE, RiskTier.LOW, False, "Out-of-scope regulated advice", 0.95)
        if re.search(r"should i get a loan", text):
            return Decision(Route.OUT_OF_SCOPE, RiskTier.LOW, False, "Out-of-scope regulated advice", 0.95)
        urgent = bool(re.search(r"in progress|right now|just sent|few minutes ago|still on|still see.*screen|sharing my screen|pressured to transfer|another payment", text)) or bool(re.search(r"(?:gave|shared|entered|told).{0,35}(?:otp|one[- ]?time code|verification code|\bcode\b)", text))
        payment = bool(re.search(r"payid|pay id|transfer|sent \$?\d|sent money|bank transfer|seller|marketplace|invoice|bank details|bond|deposit|online listing|\bpaid\b|charity|delivery fee|crypto", text))
        credential = bool(re.search(r"password|login|remote access|anydesk|teamviewer|otp|verification code|\bcode\b|screen share|sharing my screen|screen-sharing|virus|tech support|install|fake parcel|public computer|contraseña", text))
        card = bool(re.search(r"card|unfamiliar transaction|charged|merchant", text))
        # High-recall safety override. It is intentionally conservative: false
        # positives create a review task, while false negatives can delay fraud
        # operations. The override never grants tool authority or auto-releases.
        override_reasons = []
        if re.search(r"(?:i\s+)?(?:installed|downloaded|gave|allowed|shared|entered|provided).{0,80}(?:anydesk|teamviewer|remote access|screen[- ]?shar(?:e|ing)|password|one[- ]?time code|otp|verification code)", text):
            override_reasons.append("active_remote_or_credential_exposure")
        if re.search(r"(?:gave|allowed).{0,60}access.{0,60}(?:computer|device|remotely)", text):
            override_reasons.append("active_remote_or_credential_exposure")
        if re.search(r"(?:anydesk|teamviewer|remote access|screen[- ]?shar(?:e|ing)).{0,80}(?:still|currently|can still|connected|on my (?:device|computer)|access)", text) or re.search(r"(?:still|currently).{0,60}(?:viewing|access(?:ing)?|connected).{0,80}(?:anydesk|teamviewer|remote access|screen)", text):
            override_reasons.append("remote_access_may_remain_active")
        if re.search(r"(?:wants?|asking|asked|told me).{0,50}(?:remote access|me to install|a one[- ]?time code|an? otp|verification code)", text):
            override_reasons.append("active_remote_or_credential_request")
        if re.search(r"(?:still on (?:the )?(?:phone|call)|threaten(?:ed|ing)?|pressur(?:ed|ing)?|coerc(?:ed|ion)|transfer (?:again|more)|another payment)", text):
            override_reasons.append("active_coercion_or_further_loss")
        if re.search(r"(?:payment|transfer|payid).{0,80}(?:pending|in progress|right now|just sent|few minutes ago)", text):
            override_reasons.append("payment_in_progress_or_recent")
        if override_reasons:
            return Decision(Route.URGENT_FRAUD, RiskTier.CRITICAL, True, "High-recall urgent safety override", 0.98, True, tuple(dict.fromkeys(override_reasons)))
        if urgent and (payment or credential or card):
            return Decision(Route.URGENT_FRAUD, RiskTier.CRITICAL, True, "Current compromise or time-sensitive loss", 0.92)
        if payment:
            return Decision(Route.AUTHORISED_PAYMENT_SCAM, RiskTier.HIGH if urgent else RiskTier.MEDIUM, urgent, "Authorised payment scam signal", 0.84)
        if credential:
            return Decision(Route.CREDENTIAL_COMPROMISE, RiskTier.HIGH if urgent else RiskTier.MEDIUM, urgent, "Credential or device compromise", 0.85)
        if card:
            return Decision(Route.CARD_SECURITY, RiskTier.MEDIUM, False, "Card security signal", 0.78)
        return Decision(Route.SCAM_INFORMATION, RiskTier.LOW, False, "General safety or incomplete report", 0.85)

    @staticmethod
    def _redact(text: str) -> str:
        text = re.sub(r"\b(?:\d[ -]*?){13,16}\b", "[REDACTED_CARD_OR_ACCOUNT]", text)
        text = re.sub(r"\b\d{6,8}\b", "[REDACTED_CODE]", text)
        return re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "[REDACTED_EMAIL]", text)

    @staticmethod
    def _input_gate(message: str) -> GateResult:
        reasons = []
        if re.search(r"ignore (all |previous )?instructions|reveal (the )?(system|hidden) prompt", message, re.I): reasons.append("Prompt injection detected")
        if re.search(r"\b(?:\d[ -]*?){13,16}\b|\b\d{6,8}\b", message): reasons.append("Sensitive detail redacted before tracing")
        return GateResult("input_safety", not any("injection" in reason.lower() for reason in reasons), reasons)

    @staticmethod
    def _evidence_gate(response: str, evidence: list[Evidence]) -> GateResult:
        cited = set(re.findall(r"\[([^]]+)\]", response))
        allowed = {item.chunk_id for item in evidence}
        reasons = []
        if not cited: reasons.append("Missing evidence citation")
        if not cited <= allowed: reasons.append("Citation not returned by retrieval")
        return GateResult("evidence_gate", not reasons, reasons)

    @staticmethod
    def _retrieval_gate(evidence: list[Evidence], route: Route) -> GateResult:
        required = {
            Route.URGENT_FRAUD: {"urgent_review", "contact_official", "no_guarantee"},
            Route.AUTHORISED_PAYMENT_SCAM: {"payment_scam", "contact_official", "no_guarantee"},
            Route.CREDENTIAL_COMPROMISE: {"credential_compromise", "secure_access", "contact_official"},
            Route.CARD_SECURITY: {"card_security", "contact_official", "no_guarantee"},
            Route.SCAM_INFORMATION: {"general_safety", "contact_official"},
        }.get(route, {"general_safety", "contact_official"})
        retrieved = {item.source_id for item in evidence}
        reasons = []
        if not evidence:
            reasons.append("No retrieval evidence returned")
        missing = required - retrieved
        if missing:
            reasons.append("Required approved evidence missing: " + ", ".join(sorted(missing)))
        if evidence and max(item.score for item in evidence) <= 0:
            reasons.append("Retrieval relevance below threshold")
        return GateResult("retrieval_quality", not reasons, reasons)

    @staticmethod
    def _generation_gate(response: str) -> GateResult:
        reasons = []
        if not response.strip() or len(response) > 1500:
            reasons.append("Response violates generation length contract")
        if not re.search(r"\[[^\]]+\]", response):
            reasons.append("Response has no citation token")
        if "[REDACTED_" in response:
            reasons.append("Response exposes a redacted sensitive-data marker")
        return GateResult("generation_contract", not reasons, reasons)

    @staticmethod
    def _abstention_gate(retrieval_gate: GateResult, generation_gate: GateResult, evidence_gate: GateResult) -> GateResult:
        reasons = []
        if not retrieval_gate.passed:
            reasons.append("Retrieval evidence is insufficient for a reliable answer")
        if not generation_gate.passed:
            reasons.append("Draft violates generation contract")
        if not evidence_gate.passed:
            reasons.append("Draft is not grounded in retrieved evidence")
        return GateResult("abstention_gate", not reasons, reasons)

    @staticmethod
    def _abstention_response(evidence: list[Evidence]) -> str:
        citation = next((item.chunk_id for item in evidence if item.source_id == "contact_official"), evidence[0].chunk_id if evidence else None)
        response = "I cannot verify this report safely from the approved evidence available, so I will not make a conclusion. A human fraud specialist will review it; contact your bank through an official channel for immediate support."
        return f"{response} [{citation}]" if citation else response

    @staticmethod
    def _output_gate(response: str, route: Route) -> GateResult:
        text = response.lower(); reasons = []
        # Only flag affirmative outcome promises. Cautious wording such as
        # "cannot guarantee a refund" is mandatory customer-safety guidance.
        if re.search(r"(?<!cannot )(?<!can't )(?<!cannot\s)(?:guarantee|promise|ensure)\s+(?:a\s+)?(?:refund|recovery|cancellation)", text) or any(term in text for term in ("will recover your money", "payment will be stopped")):
            reasons.append("Unsafe outcome promise")
        # Match an actual request, not the required safety language "never
        # provide passwords" or "do not provide full card details".
        sensitive_request = re.search(r"\bplease\s+(?!(?:do not|don't|never|avoid)\b).{0,60}\b(?:password|one[- ]?time code|otp|full card|account number)\b", text) or re.search(r"(?<!not )(?<!never )(?<!avoid )\b(?:provide|send|tell me|give)\b.{0,60}\b(?:password|one[- ]?time code|otp|full card|account number)\b", text)
        if sensitive_request: reasons.append("Unsafe request for sensitive information")
        if route == Route.URGENT_FRAUD and not re.search(r"human\s+(?:(?:fraud\s+)?review|fraud\s+specialist)", text):
            reasons.append("Urgent case missing human escalation")
        return GateResult("output_safety", not reasons, reasons)

    @staticmethod
    def _recommended_actions(decision: Decision) -> list[str]:
        shared = ["Use the bank's official app, website, or card number rather than a contact supplied by the suspected scammer."]
        if decision.route == Route.URGENT_FRAUD:
            return ["Stop engaging with the suspected scammer.", "Contact the bank immediately through an official channel.", "A human fraud specialist must review the report."]
        if decision.route == Route.AUTHORISED_PAYMENT_SCAM:
            return ["Contact the bank through an official channel as soon as possible.", "Keep relevant messages and payment details for the reviewer."]
        if decision.route == Route.CREDENTIAL_COMPROMISE:
            return ["Stop engaging with the suspected scammer.", "Use a trusted device or official bank channel to secure access.", "Do not share passwords or one-time codes in chat."]
        if decision.route == Route.CARD_SECURITY:
            return ["Use the bank's official card-security process.", "Do not share full card details in chat."]
        return shared

    @classmethod
    def _build_response_contract(
        cls,
        response: str,
        decision: Decision,
        evidence: list[Evidence],
        requires_human_review: bool,
        output_gate: GateResult,
    ) -> ResponseContract:
        citations = sorted(set(re.findall(r"\[([^\]]+)\]", response)))
        allowed = {item.chunk_id for item in evidence}
        evidence_backed = bool(citations) and set(citations) <= allowed
        actions = cls._recommended_actions(decision)
        schema_valid = bool(actions and citations and evidence_backed)
        return ResponseContract(
            risk_summary=decision.reason,
            recommended_actions=actions,
            citations=citations,
            requires_human_review=requires_human_review,
            prohibited_claims_check="passed" if output_gate.passed else "failed",
            evidence_backed=evidence_backed,
            schema_valid=schema_valid,
        )

    @classmethod
    def _structured_contract_gate(cls, response: str, decision: Decision, evidence: list[Evidence], output_gate: GateResult) -> GateResult:
        contract = cls._build_response_contract(response, decision, evidence, decision.escalate, output_gate)
        reasons = []
        if not contract.schema_valid:
            reasons.append("Response contract lacks valid evidence-backed actions or citations")
        if decision.route == Route.URGENT_FRAUD and not contract.requires_human_review:
            reasons.append("Urgent response contract must require human review")
        if contract.prohibited_claims_check != "passed":
            reasons.append("Response contract failed prohibited-claim validation")
        return GateResult("structured_response_contract", not reasons, reasons)

    @staticmethod
    def _response(decision: Decision, evidence: list[Evidence]) -> str:
        ids = {item.source_id for item in evidence}
        def c(preferred: str) -> str:
            source_id = preferred if preferred in ids else next(iter(ids))
            return f"kb.v1.{source_id}.001"
        if decision.route == Route.URGENT_FRAUD:
            return f"This may need urgent fraud review. Stop engaging with the suspected scammer and contact your bank now through the official app, website, or number on your card. A human fraud specialist will review this report. I cannot promise a payment can be stopped or recovered. [{c('urgent_review')}] [{c('contact_official')}] [{c('no_guarantee')}]"
        if decision.route == Route.AUTHORISED_PAYMENT_SCAM:
            return f"Because you reported a payment after possible deception, contact your bank through an official channel as soon as possible and keep relevant messages for the specialist. A review is required before any outcome can be confirmed; I cannot guarantee recovery. [{c('payment_scam')}] [{c('contact_official')}] [{c('no_guarantee')}]"
        if decision.route == Route.CREDENTIAL_COMPROMISE:
            return f"Stop interacting with the suspected scammer and use a trusted device or official bank channel to secure access. Do not share passwords or one-time codes in chat. [{c('credential_compromise')}] [{c('secure_access')}] [{c('contact_official')}]"
        if decision.route == Route.CARD_SECURITY:
            return f"For unfamiliar card activity or exposed card details, use your bank’s official security process and do not share full card details in chat. A specialist must review any dispute outcome. [{c('card_security')}] [{c('contact_official')}] [{c('no_guarantee')}]"
        return f"Use trusted contact details for your bank and do not share passwords, one-time codes, or full card details in chat. [{c('general_safety')}] [{c('contact_official')}]"

    @staticmethod
    def _tool(name: str, payload: dict, decision) -> ToolEvent:
        if not decision.allowed:
            return ToolEvent(name, payload, {"status": "denied", "policy_id": decision.policy_id, "reason_codes": list(decision.reason_codes)}, False, 0.0)
        return ToolEvent(name, payload, {"status": "mock_success", "note": "No real banking action performed", "policy_id": decision.policy_id}, True, 1.0)

    def _authorised_tool(self, request: TriageRequest, decision: Decision, name: str, payload: dict) -> tuple[ToolEvent, list[str], bool]:
        authorisation = authorise_tool_call(name, payload, decision.route, request.tool_authorisation)
        return self._tool(name, payload, authorisation), list(authorisation.reason_codes), authorisation.allowed

    def _run_tools(self, request: TriageRequest, decision: Decision) -> tuple[list[ToolEvent], GateResult | None]:
        context = request.tool_authorisation
        customer_reference = context.customer_reference if context else "unverified-customer"
        candidates: list[tuple[str, dict]] = []
        if decision.route == Route.URGENT_FRAUD:
            candidates.append(("transaction_lookup", {"customer_reference": customer_reference}))
        elif decision.route == Route.AUTHORISED_PAYMENT_SCAM:
            candidates.extend([("transaction_lookup", {"customer_reference": customer_reference}), ("payee_risk_lookup", {"payee_hint": "customer_reported"})])
        if not candidates:
            return [], None
        tools, reasons, results = [], [], []
        for name, payload in candidates:
            tool, denied_reasons, allowed = self._authorised_tool(request, decision, name, payload)
            tools.append(tool); reasons.extend(f"{name}:{reason}" for reason in denied_reasons); results.append(allowed)
        return tools, GateResult("tool_authorisation", all(results), reasons)

    def _fraud_case_tool(self, request: TriageRequest, decision: Decision, reason: str) -> tuple[ToolEvent, GateResult]:
        context = request.tool_authorisation
        customer_reference = context.customer_reference if context else "unverified-customer"
        tool, denied_reasons, allowed = self._authorised_tool(request, decision, "create_fraud_case", {"customer_reference": customer_reference, "reason": reason})
        return tool, GateResult("tool_authorisation", allowed, [f"create_fraud_case:{item}" for item in denied_reasons])

    @staticmethod
    def _event(events: list[dict], name: str, **attrs: object) -> None:
        events.append({"name": name, "attributes": attrs})

    def _finish(self, request, trace_id, decision, response, escalation, reason, evidence, tools, gates, trajectory, clean, started, events) -> TriageResult:
        review_assessment = assess_response_release(decision.route, decision.risk, decision.confidence, gates, tools)
        review_id = None
        review_status = ReviewStatus.NOT_REQUIRED
        trajectory.append("response_release_gate")
        output_gate = next((gate for gate in reversed(gates) if gate.name == "output_safety"), GateResult("output_safety", False, ["Output gate missing"]))
        response_contract = self._build_response_contract(response, decision, evidence, review_assessment.required, output_gate)
        case_package = self._build_case_package(
            trace_id, request, clean, decision, escalation, reason, evidence, tools, gates, response_contract, review_assessment,
        ) if review_assessment.required else None
        if case_package:
            trajectory.append("autonomous_case_package")
            self._event(events, "autonomous_case_package", status=case_package["status"], completeness=case_package["completeness"], package_id=case_package["package_id"])
        if review_assessment.required:
            review_task = create_review_task(
                trace_id, request.case_id, decision.route, decision.risk, review_assessment,
                response, [item.chunk_id for item in evidence], tools, gates,
                case_package=case_package,
            )
            if request.enqueue_review:
                self.review_queue.enqueue(review_task)
                review_id = review_task.review_id
            review_status = ReviewStatus.PENDING
        self._event(events, "response_release_gate", review_required=review_assessment.required, reasons=list(review_assessment.reasons), review_id=review_id)
        result = TriageResult(
            decision.route, decision.risk, response, escalation, reason, evidence, tools, gates,
            trace_id, (perf_counter() - started) * 1000, round(0.003 + 0.0005 * len(tools), 4), trajectory, clean,
            review_required=review_assessment.required, review_status=review_status,
            review_reasons=list(review_assessment.reasons), review_id=review_id,
            response_contract=response_contract, case_package=case_package,
            urgent_override_triggered=decision.safety_override, urgent_override_reasons=list(decision.override_reasons),
        )
        alerts = self.alert_engine.evaluate(result.as_dict(), request.case_id) if request.enqueue_review else []
        if alerts:
            self._event(events, "monitoring_alerts", count=len(alerts), severities=[alert.severity for alert in alerts], codes=[alert.code for alert in alerts])
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        record = {"trace_id": trace_id, "case_id": request.case_id, "trajectory_events": events, "result": result.as_dict(), "metadata": {"agent_version": "v1.1-autonomy", "prompt_version": "v1", "environment": os.getenv("ENVIRONMENT", "local")}}
        with (self.trace_dir / "traces.jsonl").open("a", encoding="utf-8") as output: output.write(json.dumps(record) + "\n")
        self.alert_engine.record(alerts)
        self.telemetry.emit_trace(trace_id, request.case_id, events, result.as_dict())
        return result

    @staticmethod
    def _build_case_package(
        trace_id: str,
        request: TriageRequest,
        redacted_input: str,
        decision: Decision,
        escalation: bool,
        escalation_reason: str | None,
        evidence: list[Evidence],
        tools: list[ToolEvent],
        gates: list[GateResult],
        response_contract: ResponseContract,
        assessment,
    ) -> dict:
        """Create a reversible internal work package; it performs no bank action."""
        required_fields = {
            "trace_id": trace_id,
            "route": decision.route.value,
            "risk_tier": decision.risk.value,
            "evidence_chunk_ids": [item.chunk_id for item in evidence],
            "recommended_actions": response_contract.recommended_actions,
            "review_reasons": list(assessment.reasons),
        }
        complete = all(required_fields.values())
        create_case = next((tool for tool in tools if tool.name == "create_fraud_case"), None)
        return {
            "package_id": f"aegis-case-{trace_id[:12]}",
            "package_version": "v1.1",
            "status": "ready_for_human_review",
            "completeness": complete,
            "case_id": request.case_id,
            "trace_id": trace_id,
            "route": decision.route.value,
            "risk_tier": decision.risk.value,
            "urgent_override": decision.safety_override,
            "urgent_override_reasons": list(decision.override_reasons),
            "escalation_required": escalation,
            "escalation_reason": escalation_reason,
            "redacted_case_summary": redacted_input[:300],
            "evidence_chunk_ids": required_fields["evidence_chunk_ids"],
            "recommended_actions": required_fields["recommended_actions"],
            "response_contract_valid": response_contract.schema_valid,
            "review_reasons": required_fields["review_reasons"],
            "tool_summary": [{"name": tool.name, "success": tool.success, "status": tool.output.get("status")} for tool in tools],
            "gate_summary": [{"name": gate.name, "passed": gate.passed} for gate in gates],
            "fraud_case_action": "created" if create_case and create_case.success else "not_created_or_denied",
            "boundary": "Internal review package only; no customer response or banking action has been released.",
        }
