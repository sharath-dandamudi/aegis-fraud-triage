"""Pinecone-backed, graph-constrained policy retrieval.

The vector store supplies semantic retrieval while the local graph preserves the
route-specific evidence contract. Missing required policy nodes intentionally
returns incomplete evidence so the existing retrieval gate fails closed.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .knowledge import LocalGraphRetriever, Node
from .models import Evidence, Route


PINECONE_CONTROL_URL = "https://api.pinecone.io"
PINECONE_INFERENCE_URL = "https://api.pinecone.io/embed"
PINECONE_API_VERSION = "2026-04"


def policy_documents(corpus_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return approved graph nodes and public-safety chunks as indexable records."""
    retriever = LocalGraphRetriever(corpus_path)
    documents = []
    for node in retriever.nodes.values():
        chunk_id = LocalGraphRetriever._chunk_id(node.node_id)
        documents.append({
            "id": node.node_id,
            "chunk_id": chunk_id,
            "source_id": node.node_id,
            "title": node.title,
            "text": node.text,
            "node_type": node.kind,
            "keywords": list(node.keywords),
            "edges": list(node.edges),
        })
    return documents


class PineconePolicyRetriever:
    """Semantic retrieval with mandatory graph-policy nodes fetched by ID."""

    def __init__(self, corpus_path: str | Path | None = None):
        self.graph = LocalGraphRetriever(corpus_path)
        self.api_key = os.getenv("PINECONE_API_KEY", "")
        self.index_name = os.getenv("PINECONE_INDEX_NAME", "")
        self.namespace = os.getenv("PINECONE_NAMESPACE", "policy-v1")
        self.embedding_model = os.getenv("PINECONE_EMBEDDING_MODEL", "multilingual-e5-large")
        self.index_host = os.getenv("PINECONE_INDEX_HOST", "")
        self.last_error: str | None = None
        self.last_reranker_used = False

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.index_name)

    def retrieve(self, query: str, route: Route, limit: int = 5) -> list[Evidence]:
        if not self.configured:
            self.last_error = "Pinecone credentials or index name are not configured"
            return []
        try:
            vector = self.embed(query, input_type="query")
            matches = self._query(vector, top_k=max(12, limit * 3))
            required_ids = sorted(self.graph._route_nodes(route))
            required = self._fetch(required_ids)
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as error:
            self.last_error = type(error).__name__
            return []

        evidence_by_id: dict[str, Evidence] = {}
        for node_id, payload in required.items():
            evidence = self._evidence_from_metadata(node_id, payload.get("metadata", {}), 1.0)
            if evidence:
                evidence_by_id[node_id] = evidence
        for match in matches:
            node_id = str(match.get("id", ""))
            evidence = self._evidence_from_metadata(node_id, match.get("metadata", {}), float(match.get("score", 0.0)))
            if evidence and node_id not in evidence_by_id:
                evidence_by_id[node_id] = evidence

        # Required graph nodes come first. Remaining semantic neighbours pass
        # through a deterministic lexical/route-aware reranker. It is a small,
        # explainable hybrid layer—not a replacement for Pinecone similarity.
        ordered = [evidence_by_id[item] for item in required_ids if item in evidence_by_id]
        optional = [item for node_id, item in evidence_by_id.items() if node_id not in required_ids]
        ordered.extend(self._rerank_optional(optional, query, route))
        self.last_reranker_used = bool(optional)
        return ordered[:limit]

    @staticmethod
    def _rerank_optional(evidence: list[Evidence], query: str, route: Route) -> list[Evidence]:
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        route_terms = {
            Route.URGENT_FRAUD: {"urgent", "immediate", "remote", "code", "payment"},
            Route.AUTHORISED_PAYMENT_SCAM: {"payid", "payment", "transfer", "seller"},
            Route.CREDENTIAL_COMPROMISE: {"password", "code", "remote", "access", "device"},
            Route.CARD_SECURITY: {"card", "merchant", "transaction"},
        }.get(route, {"scam", "safe", "bank"})

        def score(item: Evidence) -> tuple[float, str]:
            text_tokens = set(re.findall(r"[a-z0-9]+", f"{item.title} {item.text}".lower()))
            lexical = len(query_tokens & text_tokens) * 0.025
            route_alignment = len(route_terms & text_tokens) * 0.015
            provenance = 0.01 if item.source_id.startswith("public.au.") else 0.0
            return (item.score + lexical + route_alignment + provenance, item.source_id)

        return sorted(evidence, key=lambda item: (-score(item)[0], score(item)[1]))

    def embed(self, text: str, input_type: str) -> list[float]:
        return self.embed_many([text], input_type=input_type)[0]

    def embed_many(self, texts: list[str], input_type: str) -> list[list[float]]:
        payload = {
            "model": self.embedding_model,
            "parameters": {"input_type": input_type, "truncate": "END"},
            "inputs": [{"text": text} for text in texts],
        }
        response = self._request(PINECONE_INFERENCE_URL, payload, headers={"X-Pinecone-Api-Version": PINECONE_API_VERSION})
        vectors = [item["values"] for item in response["data"]]
        if len(vectors) != len(texts) or any(len(values) != 1024 for values in vectors):
            raise ValueError("Embedding dimensionality does not match the configured Aegis index")
        return vectors

    def upsert_documents(self, documents: list[dict[str, Any]], batch_size: int = 20) -> int:
        if not self.configured:
            raise ValueError("PINECONE_API_KEY and PINECONE_INDEX_NAME are required for ingestion")
        count = 0
        for start in range(0, len(documents), batch_size):
            batch = documents[start:start + batch_size]
            vectors = []
            embedded = self.embed_many([document["text"] for document in batch], input_type="passage")
            for document, values in zip(batch, embedded, strict=True):
                vectors.append({
                    "id": document["id"],
                    "values": values,
                    "metadata": {
                        "source_id": document["source_id"],
                        "chunk_id": document["chunk_id"],
                        "title": document["title"],
                        "text": document["text"],
                        "node_type": document["node_type"],
                        "keywords": document["keywords"],
                        "edges": document["edges"],
                        "corpus_version": "v1",
                    },
                })
            self._request(f"{self._host()}/vectors/upsert", {"namespace": self.namespace, "vectors": vectors})
            count += len(vectors)
        return count

    def _query(self, vector: list[float], top_k: int) -> list[dict[str, Any]]:
        response = self._request(
            f"{self._host()}/query",
            {"namespace": self.namespace, "vector": vector, "topK": top_k, "includeMetadata": True},
        )
        return response.get("matches", [])

    def _fetch(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        query = urlencode([("namespace", self.namespace), *[("ids", item) for item in ids]])
        response = self._request(f"{self._host()}/vectors/fetch?{query}", None, method="GET")
        return response.get("vectors", {})

    def _host(self) -> str:
        if self.index_host:
            return f"https://{self.index_host.removeprefix('https://')}"
        response = self._request(
            f"{PINECONE_CONTROL_URL}/indexes/{self.index_name}",
            None,
            method="GET",
            headers={"X-Pinecone-Api-Version": PINECONE_API_VERSION},
        )
        host = response.get("host")
        if not host:
            raise ValueError("Pinecone did not return an index host")
        self.index_host = str(host)
        return f"https://{self.index_host.removeprefix('https://')}"

    def _request(self, url: str, payload: dict[str, Any] | None, method: str = "POST", headers: dict[str, str] | None = None) -> dict[str, Any]:
        request_headers = {"Api-Key": self.api_key, "Accept": "application/json", **(headers or {})}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=request_headers, method=method)
        with urlopen(request, timeout=20) as response:  # nosec B310: URL is fixed/provider configured
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _evidence_from_metadata(node_id: str, metadata: dict[str, Any], score: float) -> Evidence | None:
        if not metadata.get("source_id") or not metadata.get("chunk_id") or not metadata.get("text"):
            return None
        return Evidence(
            source_id=str(metadata["source_id"]),
            chunk_id=str(metadata["chunk_id"]),
            title=str(metadata.get("title", node_id)),
            text=str(metadata["text"]),
            score=round(score, 4),
            node_type=str(metadata.get("node_type", "policy")),
        )
