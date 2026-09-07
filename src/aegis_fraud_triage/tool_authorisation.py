"""Server-side tool policy checks for the local MVP.

The LLM may suggest a tool, but it never supplies identity, scopes, or an
account identifier.  A production API must create ``ToolAuthorisationContext``
from its verified session and entitlement service before invoking the agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Route


@dataclass(frozen=True)
class ToolAuthorisationContext:
    """Verified, server-asserted attributes only; never populate from chat text."""

    subject_id: str
    customer_reference: str
    authenticated: bool
    customer_verified: bool
    consent_granted: bool
    scopes: frozenset[str]
    session_id: str


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    allowed_routes: frozenset[Route]
    required_scopes: frozenset[str]
    required_payload_keys: frozenset[str]
    requires_consent: bool = True


@dataclass(frozen=True)
class AuthorisationDecision:
    allowed: bool
    policy_id: str
    reason_codes: tuple[str, ...]


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "transaction_lookup": ToolPolicy(
        name="transaction_lookup",
        allowed_routes=frozenset({Route.URGENT_FRAUD, Route.AUTHORISED_PAYMENT_SCAM, Route.CARD_SECURITY}),
        required_scopes=frozenset({"transactions:read"}),
        required_payload_keys=frozenset({"customer_reference"}),
    ),
    "payee_risk_lookup": ToolPolicy(
        name="payee_risk_lookup",
        allowed_routes=frozenset({Route.AUTHORISED_PAYMENT_SCAM}),
        required_scopes=frozenset({"payee_risk:read"}),
        required_payload_keys=frozenset({"payee_hint"}),
    ),
    "create_fraud_case": ToolPolicy(
        name="create_fraud_case",
        allowed_routes=frozenset({Route.URGENT_FRAUD, Route.AUTHORISED_PAYMENT_SCAM, Route.CREDENTIAL_COMPROMISE, Route.CARD_SECURITY}),
        required_scopes=frozenset({"fraud_case:create"}),
        required_payload_keys=frozenset({"customer_reference", "reason"}),
    ),
}


def authorise_tool_call(
    tool_name: str,
    payload: dict[str, Any],
    route: Route,
    context: ToolAuthorisationContext | None,
) -> AuthorisationDecision:
    """Fail closed unless route, session, scope, ownership, and payload all pass."""
    policy = TOOL_POLICIES.get(tool_name)
    policy_id = f"tool-policy/{tool_name}/v1"
    reasons: list[str] = []
    if policy is None:
        return AuthorisationDecision(False, policy_id, ("unknown_tool",))
    if context is None:
        reasons.append("missing_server_authorisation_context")
    else:
        if not context.authenticated:
            reasons.append("unauthenticated_session")
        if not context.customer_verified:
            reasons.append("customer_identity_not_verified")
        if policy.requires_consent and not context.consent_granted:
            reasons.append("customer_consent_missing")
        missing_scopes = policy.required_scopes - context.scopes
        if missing_scopes:
            reasons.append("missing_scope:" + ",".join(sorted(missing_scopes)))
        if "customer_reference" in payload and payload["customer_reference"] != context.customer_reference:
            reasons.append("customer_ownership_mismatch")
    if route not in policy.allowed_routes:
        reasons.append("route_not_permitted")
    if set(payload) != policy.required_payload_keys:
        reasons.append("payload_schema_rejected")
    if tool_name == "payee_risk_lookup" and payload.get("payee_hint") != "customer_reported":
        reasons.append("untrusted_payee_parameter")
    if tool_name == "create_fraud_case" and (not isinstance(payload.get("reason"), str) or len(payload["reason"]) > 160):
        reasons.append("invalid_case_reason")
    return AuthorisationDecision(not reasons, policy_id, tuple(reasons))


def local_demo_context(customer_reference: str, session_id: str) -> ToolAuthorisationContext:
    """Explicit local-only fixture. Replace with verified API/session middleware."""
    return ToolAuthorisationContext(
        subject_id="local-demo-subject",
        customer_reference=customer_reference,
        authenticated=True,
        customer_verified=True,
        consent_granted=True,
        scopes=frozenset({"transactions:read", "payee_risk:read", "fraud_case:create"}),
        session_id=session_id,
    )
