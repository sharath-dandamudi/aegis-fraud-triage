"""Assess exact human/LLM-judge agreement for the Aegis calibration sample."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--output", default="reports/human_calibration_assessment.json")
    args = parser.parse_args()
    metrics = ("faithfulness", "safety", "escalation", "actionability")
    rows = list(csv.DictReader(Path(args.labels).open(encoding="utf-8")))
    complete = [row for row in rows if all(row.get(f"human_{metric}", "").strip() for metric in metrics)]
    if not complete:
        raise SystemExit("No complete human labels found.")
    exact = {metric: mean(int(row[f"judge_{metric}"]) == int(row[f"human_{metric}"]) for row in complete) for metric in metrics}
    within_one = {metric: mean(abs(int(row[f"judge_{metric}"]) - int(row[f"human_{metric}"])) <= 1 for row in complete) for metric in metrics}
    report = {
        "completed_cases": len(complete),
        "exact_agreement": {key: round(value, 3) for key, value in exact.items()},
        "mean_exact_agreement": round(mean(exact.values()), 3),
        "within_one_agreement": {key: round(value, 3) for key, value in within_one.items()},
        "release_eligible": len(complete) >= 15 and mean(exact.values()) >= 0.80,
        "criterion": ">=15 independently human-reviewed cases and mean exact agreement >=0.80",
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
