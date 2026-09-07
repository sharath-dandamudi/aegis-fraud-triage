"""Create a stratified 15-case human-label template from a judged evaluation run."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, help="Path to a *_case_results.jsonl file with llm_judge entries.")
    parser.add_argument("--output", default="reports/human_calibration_template.csv")
    parser.add_argument("--count", type=int, default=15)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.results).read_text(encoding="utf-8").splitlines() if line.strip()]
    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if "llm_judge" in row:
            by_group[row["scenario_group"]].append(row)
    selected: list[dict] = []
    while len(selected) < args.count and any(by_group.values()):
        for group in sorted(by_group):
            if by_group[group] and len(selected) < args.count:
                selected.append(by_group[group].pop(0))
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["case_id", "scenario_group", "expected_route", "expected_escalation", "response", "evidence_chunk_ids", "judge_faithfulness", "judge_safety", "judge_escalation", "judge_actionability", "human_faithfulness", "human_safety", "human_escalation", "human_actionability", "reviewer_id", "review_note"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in selected:
            verdict = row["llm_judge"]
            writer.writerow({
                "case_id": row["case_id"], "scenario_group": row["scenario_group"], "expected_route": row["expected_route"], "expected_escalation": row["expected_escalation"],
                "response": row["response"], "evidence_chunk_ids": "; ".join(item["chunk_id"] for item in row["evidence"]),
                **{f"judge_{metric}": verdict[metric] for metric in ("faithfulness", "safety", "escalation", "actionability")},
                "human_faithfulness": "", "human_safety": "", "human_escalation": "", "human_actionability": "", "reviewer_id": "", "review_note": "",
            })
    print(f"Wrote {len(selected)} stratified cases to {output}")


if __name__ == "__main__":
    main()
