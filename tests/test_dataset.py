import json
from collections import Counter
from pathlib import Path


def test_golden_dataset_has_required_coverage():
    root = Path(__file__).parents[1]
    records = [json.loads(line) for line in (root / "data" / "golden_dataset_v1.jsonl").read_text().splitlines()]
    assert len(records) == 100
    assert Counter(case["scenario_group"] for case in records) == {"representative": 50, "edge_case": 30, "known_failure": 15, "adversarial": 5}
    assert all(case["expected_route"] and case["required_evidence_topics"] and case["prohibited_claims"] for case in records)
    assert all(case["retrieval_expectations"]["required_chunk_ids"] for case in records)
    assert all(case["citation_expectations"] for case in records)
    assert all("trajectory_constraints" in case and "expected_tool_calls" in case for case in records)
