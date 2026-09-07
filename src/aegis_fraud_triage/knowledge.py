from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .models import Evidence, Route


@dataclass(frozen=True)
class Node:
    node_id: str
    kind: str
    title: str
    text: str
    keywords: tuple[str, ...]
    edges: tuple[str, ...] = ()


NODES = {
    "payment_scam": Node("payment_scam", "scam_type", "Authorised payment scam", "A payment made after deception can require urgent review. Do not promise recovery or cancellation.", ("payid", "transfer", "sent", "payment", "seller", "marketplace", "bank transfer"), ("contact_official", "no_guarantee", "urgent_review")),
    "credential_compromise": Node("credential_compromise", "scam_type", "Credential or remote-access compromise", "Password, one-time-code or remote-access reports require account-security guidance. Current compromise requires urgent human review.", ("password", "otp", "code", "remote access", "anydesk", "teamviewer", "screen share"), ("secure_access", "contact_official", "urgent_review")),
    "card_security": Node("card_security", "scam_type", "Card security report", "Exposed card details or unfamiliar activity need the bank’s official security process. Do not predict dispute outcomes.", ("card", "charged", "unfamiliar", "merchant", "card details"), ("contact_official", "no_guarantee")),
    "contact_official": Node("contact_official", "customer_safety", "Official contact channel", "Use the official banking app, official website, or the number on the back of the card. Never use a number or link supplied by the suspected scammer.", ("contact", "official", "bank", "call")),
    "secure_access": Node("secure_access", "immediate_action", "Secure access", "Stop engaging with the suspected scammer and use a trusted device or official channel. Never share a password or one-time code in chat.", ("secure", "access", "password", "device")),
    "urgent_review": Node("urgent_review", "escalation", "Urgent human fraud review", "Escalate for a payment in progress or very recent, active remote access, newly shared credentials or codes, or immediate further-loss risk. Do not delay escalation for further data gathering.", ("urgent", "today", "now", "in progress", "remote", "code")),
    "no_guarantee": Node("no_guarantee", "policy", "No outcome guarantee", "The agent must not guarantee a refund, reimbursement, recovery, cancellation, or investigation result. A specialist can review the report.", ("refund", "recovery", "guarantee", "cancel")),
    "privacy": Node("privacy", "privacy", "Minimal data", "Do not request or log full card numbers, account numbers, passwords, one-time codes, or identity-document numbers.", ("privacy", "card", "account", "code", "password")),
    "general_safety": Node("general_safety", "customer_safety", "General scam safety", "For general safety information, provide cautious evidence-backed guidance and do not infer account status.", ("scam", "safe", "prevent", "phishing", "suspicious"), ("contact_official", "privacy")),
}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class LocalGraphRetriever:
    """Auditable lexical retrieval plus one-hop typed graph expansion."""

    def __init__(self, corpus_path: str | Path | None = None):
        self.nodes = dict(NODES)
        default_path = Path(__file__).parents[2] / "data" / "public_safety_corpus_v1.jsonl"
        path = Path(corpus_path) if corpus_path else default_path
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                self.nodes[item["node_id"]] = Node(
                    node_id=item["node_id"], kind=item["content_type"], title=item["title"],
                    text=item["summary"], keywords=tuple(item["keywords"]), edges=tuple(item["links"]),
                )

    def retrieve(self, query: str, route: Route, limit: int = 5) -> list[Evidence]:
        query_tokens = _tokens(query)
        scores: dict[str, float] = {}
        for node in self.nodes.values():
            hits = sum(term in query.lower() for term in node.keywords)
            overlap = len(query_tokens & _tokens(node.title + " " + node.text)) / 20
            bonus = 0.8 if node.node_id in self._route_nodes(route) else 0.0
            if hits or overlap or bonus:
                scores[node.node_id] = hits + overlap + bonus
        for node_id, score in list(scores.items()):
            for linked in self.nodes[node_id].edges:
                if linked in self.nodes:
                    scores[linked] = max(scores.get(linked, 0), score * 0.72)
        all_ranked = sorted(
            ((node_id, self._route_aware_score(node_id, score, query_tokens, route)) for node_id, score in scores.items()),
            key=lambda item: (-item[1], item[0]),
        )
        # Retain the workflow-controlled evidence needed for a safe response, then
        # reserve one slot for public, provenance-rich guidance. This is a hybrid
        # retrieval policy: operational controls are never displaced by a higher
        # lexical score from a background explainer.
        core_required = self._route_nodes(route)
        ranked = [item for item in all_ranked if item[0] in core_required]
        public_candidate = next((item for item in all_ranked if item[0].startswith("public.au.")), None)
        if public_candidate and all(node_id != public_candidate[0] for node_id, _ in ranked):
            ranked.append(public_candidate)
        for item in all_ranked:
            if item[0] not in {node_id for node_id, _ in ranked}:
                ranked.append(item)
            if len(ranked) >= limit:
                break
        ranked = ranked[:limit]
        return [Evidence(key, self._chunk_id(key), self.nodes[key].title, self.nodes[key].text, round(score, 3), self.nodes[key].kind) for key, score in ranked]

    def _route_aware_score(self, node_id: str, base_score: float, query_tokens: set[str], route: Route) -> float:
        """Deterministic second-stage rerank for auditable evidence diversity.

        This is intentionally not an LLM reranker: it improves lexical intent
        alignment while preserving mandatory graph evidence and predictable
        offline evaluation behaviour.
        """
        node = self.nodes[node_id]
        keyword_overlap = len(query_tokens & set(node.keywords))
        title_overlap = len(query_tokens & _tokens(node.title))
        route_bonus = 1.2 if node_id in self._route_nodes(route) else 0.0
        official_channel_bonus = 0.15 if node_id == "contact_official" and {"bank", "contact", "call", "number"} & query_tokens else 0.0
        return base_score + (keyword_overlap * 0.12) + (title_overlap * 0.08) + route_bonus + official_channel_bonus

    @staticmethod
    def _chunk_id(node_id: str) -> str:
        return f"kb.v1.{node_id}.001" if node_id in NODES else node_id

    @staticmethod
    def _route_nodes(route: Route) -> set[str]:
        return {
            Route.URGENT_FRAUD: {"urgent_review", "contact_official", "no_guarantee"},
            Route.AUTHORISED_PAYMENT_SCAM: {"payment_scam", "contact_official", "no_guarantee"},
            Route.CREDENTIAL_COMPROMISE: {"credential_compromise", "secure_access", "contact_official"},
            Route.CARD_SECURITY: {"card_security", "contact_official", "no_guarantee"},
            Route.SCAM_INFORMATION: {"general_safety", "contact_official", "privacy"},
        }.get(route, {"general_safety", "contact_official"})
