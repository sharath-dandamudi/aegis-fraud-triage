"""Publish the immutable synthetic Aegis golden set to LangSmith once."""
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client


ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env", override=False)
DATASET_NAME = "aegis-fraud-triage-golden-v1.3"


def main() -> None:
    client = Client()
    if client.has_dataset(dataset_name=DATASET_NAME):
        print(json.dumps({"status": "exists", "dataset_name": DATASET_NAME, "action": "no duplicate examples created"}))
        return
    rows = [json.loads(line) for line in (ROOT / "data" / "golden_dataset_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    dataset = client.create_dataset(
        DATASET_NAME,
        description="Frozen synthetic Australian banking-scam triage golden set. Contains expected route, evidence IDs, tool trajectory, gate and release behaviour; no real customer information.",
        metadata={"dataset_version": "v1.3.0", "case_count": len(rows), "synthetic": True, "contains_pii": False},
    )
    examples = [{
        "inputs": {"case_id": row["case_id"], "message": row["message"], "scenario_group": row["scenario_group"]},
        "outputs": {
            "expected_route": row["expected_route"], "expected_escalation": row["expected_escalation"], "required_chunk_ids": row["retrieval_expectations"]["required_chunk_ids"],
            "expected_tool_calls": row["expected_tool_calls"], "gate_expectations": row["gate_expectations"], "response_release_expectations": row["response_release_expectations"],
        },
    } for row in rows]
    client.create_examples(dataset_id=dataset.id, examples=examples, max_concurrency=3)
    print(json.dumps({"status": "created", "dataset_name": DATASET_NAME, "case_count": len(examples)}))


if __name__ == "__main__":
    main()
