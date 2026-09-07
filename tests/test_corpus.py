import json
from collections import Counter
from pathlib import Path

from aegis_fraud_triage.knowledge import LocalGraphRetriever
from aegis_fraud_triage.models import Route


def test_public_safety_corpus_has_provenance_and_policy_boundary():
    root = Path(__file__).parents[1]
    records = [json.loads(line) for line in (root / "data" / "public_safety_corpus_v1.jsonl").read_text().splitlines()]
    assert len(records) == 60
    assert len({item["document_id"] for item in records}) == 15
    assert all(item["jurisdiction"] == "AU" and item["not_bank_policy"] for item in records)
    assert all(item["source_url"].startswith("https://") and item["last_reviewed"] for item in records)
    assert Counter(item["trust_tier"] for item in records)["government_primary"] > 0


def test_retriever_surfaces_relevant_public_guidance():
    evidence = LocalGraphRetriever().retrieve("unexpected caller asks to install AnyDesk", Route.CREDENTIAL_COMPROMISE)
    assert any(item.chunk_id.startswith("public.au.") for item in evidence)
