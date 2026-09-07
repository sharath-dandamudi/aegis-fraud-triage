"""Index the approved Aegis policy corpus into the configured Pinecone namespace."""
from __future__ import annotations

import json
from pathlib import Path

from aegis_fraud_triage.pinecone_policy import PineconePolicyRetriever, policy_documents


if __name__ == "__main__":
    root = Path(__file__).parent
    documents = policy_documents(root / "data" / "public_safety_corpus_v1.jsonl")
    retriever = PineconePolicyRetriever(root / "data" / "public_safety_corpus_v1.jsonl")
    count = retriever.upsert_documents(documents)
    print(json.dumps({"indexed_documents": count, "namespace": retriever.namespace, "index": retriever.index_name}))
