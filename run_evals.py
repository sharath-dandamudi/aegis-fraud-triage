from __future__ import annotations

import json
from pathlib import Path

from aegis_fraud_triage.evaluation import compare_baseline_to_v1


if __name__ == "__main__":
    root = Path(__file__).parent
    summary = compare_baseline_to_v1(root / "data" / "golden_dataset_v1.jsonl", root / "reports")
    print(json.dumps(summary, indent=2))
