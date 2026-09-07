"""Run comparable offline evaluations against local and live Aegis configurations."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env", override=False)

from aegis_fraud_triage.agent import AegisFraudTriageAgent
from aegis_fraud_triage.baseline import BaselineTriageAgent
from aegis_fraud_triage.evaluation import evaluate
from aegis_fraud_triage.evaluation import load_dataset
from aegis_fraud_triage.judges import NebiusJudge


PROFILES = {
    "baseline": {"rag_backend": "none", "generation_mode": "none"},
    "local_control": {"rag_backend": "local", "generation_mode": "deterministic"},
    "pinecone_retrieval": {"rag_backend": "pinecone", "generation_mode": "deterministic"},
    "live": {"rag_backend": "pinecone", "generation_mode": "nebius"},
}


def stratified_case_ids(dataset: list[dict], count: int) -> set[str]:
    """Use the golden-set design mix rather than accidental file order."""
    targets = {"representative": 0.50, "edge_case": 0.30, "known_failure": 0.15, "adversarial": 0.05}
    grouped = {name: [case for case in dataset if case["scenario_group"] == name] for name in targets}
    quotas = {name: max(1, int(count * share)) for name, share in targets.items()}
    remainder = count - sum(quotas.values())
    for name in sorted(targets, key=lambda item: targets[item], reverse=True):
        if remainder <= 0:
            break
        quotas[name] += 1
        remainder -= 1
    selected = []
    for name in targets:
        selected.extend(grouped[name][:quotas[name]])
    return {case["case_id"] for case in selected}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Aegis offline evaluation profiles on the frozen golden dataset.")
    parser.add_argument("--profile", choices=PROFILES, default="live")
    parser.add_argument("--judge", choices=["none", "nebius"], default="none")
    parser.add_argument("--limit", type=int, default=None, help="Use only the first N frozen cases for a smoke run.")
    parser.add_argument("--stratified", type=int, default=None, help="Select N cases using the dataset's 50/30/15/5 scenario mix.")
    parser.add_argument("--case-id", action="append", dest="case_ids", help="Evaluate an explicit golden case ID; repeat for a targeted regression set.")
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args()

    profile = PROFILES[args.profile]
    if args.profile == "baseline":
        agent = BaselineTriageAgent()
    else:
        os.environ["RAG_BACKEND"] = profile["rag_backend"]
        os.environ["LLM_GENERATION_MODE"] = profile["generation_mode"]
        agent = AegisFraudTriageAgent(ROOT / "logs")
    judge = NebiusJudge() if args.judge == "nebius" else None
    if judge and not judge.configured:
        raise SystemExit("NEBIUS_API_KEY is required for --judge nebius")
    dataset = load_dataset(ROOT / "data" / "golden_dataset_v1.jsonl")
    if args.case_ids:
        available = {case["case_id"] for case in dataset}
        unknown = set(args.case_ids) - available
        if unknown:
            raise SystemExit(f"Unknown case IDs: {sorted(unknown)}")
        case_ids = set(args.case_ids)
        selection = "targeted_regression"
    elif args.stratified:
        case_ids = stratified_case_ids(dataset, args.stratified)
        selection = f"stratified_{args.stratified}"
    else:
        case_ids = None
        selection = f"first_{args.limit}" if args.limit else "full_golden_dataset"
    run_name = args.run_name or f"{args.profile}_{args.judge}"
    summary = evaluate(
        ROOT / "data" / "golden_dataset_v1.jsonl",
        ROOT / "reports",
        agent=agent,
        run_name=run_name,
        judge_callable=judge,
        max_cases=args.limit,
        case_ids=case_ids,
        run_metadata={"profile": args.profile, "rag_backend": profile["rag_backend"], "generation_mode": profile["generation_mode"], "judge": args.judge, "selection": selection},
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
