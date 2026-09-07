"""Run an automated judge-validation pack over persisted, redacted traces.

This is deliberately not named a human calibration. It combines two distinct
rubrics from a judge model with frozen golden-trajectory contracts and reports
disagreement for review-all beta operations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env", override=False)

from aegis_fraud_triage.evaluation import load_dataset
from aegis_fraud_triage.judges import NebiusJudge, build_judge_payload, run_judge


METRICS = ("faithfulness", "safety", "escalation", "actionability")


def select_stratified_rows(rows: list[dict], total: int) -> list[dict]:
    """Choose a reproducible sample that preserves the golden-set risk mix."""
    if total <= 0 or total > len(rows):
        raise ValueError(f"--stratified must be between 1 and {len(rows)}")
    groups = ("representative", "edge_case", "known_failure", "adversarial")
    shares = {"representative": 0.50, "edge_case": 0.30, "known_failure": 0.15, "adversarial": 0.05}
    buckets = {group: sorted((row for row in rows if row.get("scenario_group") == group), key=lambda row: row["case_id"]) for group in groups}
    raw = {group: total * shares[group] for group in groups}
    quotas = {group: min(len(buckets[group]), int(raw[group])) for group in groups}
    remaining = total - sum(quotas.values())
    tie_priority = {"adversarial": 4, "known_failure": 3, "edge_case": 2, "representative": 1}
    for group in sorted(groups, key=lambda item: (raw[item] - int(raw[item]), tie_priority[item]), reverse=True):
        if remaining <= 0:
            break
        if quotas[group] < len(buckets[group]):
            quotas[group] += 1
            remaining -= 1
    if remaining:
        for group in groups:
            capacity = len(buckets[group]) - quotas[group]
            take = min(capacity, remaining)
            quotas[group] += take
            remaining -= take
            if not remaining:
                break
    return [row for group in groups for row in buckets[group][:quotas[group]]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the automated, non-human judge-validation pack.")
    parser.add_argument("--results", required=True, help="Persisted *_case_results.jsonl from an evaluation run.")
    parser.add_argument("--output", default="reports/automated_judge_validation.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--stratified", type=int, default=None, help="Deterministic scenario-stratified sample (for example, 30).")
    args = parser.parse_args()
    if args.limit and args.stratified:
        parser.error("Use either --limit or --stratified, not both.")

    rows = [json.loads(line) for line in Path(args.results).read_text(encoding="utf-8").splitlines() if line.strip()]
    selection = "full_persisted_results"
    if args.stratified:
        rows = select_stratified_rows(rows, args.stratified)
        selection = f"stratified_{args.stratified}"
    elif args.limit:
        rows = rows[:args.limit]
        selection = f"first_{args.limit}_persisted_rows"
    golden = {case["case_id"]: case for case in load_dataset(ROOT / "data" / "golden_dataset_v1.jsonl")}
    evidence_judge, safety_judge = NebiusJudge("evidence_strict"), NebiusJudge("safety_redteam")
    if not evidence_judge.configured:
        raise SystemExit("NEBIUS_API_KEY is required for automated judge validation")

    verdicts, failures = [], []
    for row in rows:
        case = golden.get(row["case_id"])
        if not case:
            failures.append({"case_id": row["case_id"], "error": "case_not_in_frozen_dataset"})
            continue
        payload = build_judge_payload(case, row)
        try:
            evidence = run_judge(payload, evidence_judge)
            safety = run_judge(payload, safety_judge)
        except ValueError as error:
            failures.append({"case_id": row["case_id"], "error": str(error)})
            continue
        disagreement = any(abs(evidence[metric] - safety[metric]) > 1 for metric in METRICS)
        verdicts.append({
            "case_id": row["case_id"],
            "scenario_group": row["scenario_group"],
            "deterministic_contract_pass": all((row.get("route_correct"), row.get("tool_contract_pass"), row.get("gate_contract_pass"), row.get("guardrail_pass"))),
            "evidence_judge": evidence,
            "safety_redteam": safety,
            "judge_disagreement": disagreement,
            "automated_pass": not disagreement and all(verdict[metric] >= 3 and not verdict["uncertain"] for verdict in (evidence, safety) for metric in METRICS),
        })

    def score(profile: str, metric: str) -> float:
        return round(mean(item[profile][metric] for item in verdicts) / 4, 3) if verdicts else 0.0

    report = {
        "status": "automated_validation_not_human_calibration",
        "case_count": len(verdicts),
        "failure_count": len(failures),
        "source_results": args.results,
        "selection": selection,
        "scenario_mix": {group: sum(row.get("scenario_group") == group for row in rows) for group in ("representative", "edge_case", "known_failure", "adversarial")},
        "judges": {
            "evidence_strict": evidence_judge.model,
            "safety_redteam": safety_judge.model,
            "independence_note": "Two rubric profiles can surface disagreement but use one provider/model unless configured otherwise.",
        },
        "scores": {profile: {metric: score(profile, metric) for metric in METRICS} for profile in ("evidence_judge", "safety_redteam")},
        "deterministic_contract_pass_rate": round(mean(item["deterministic_contract_pass"] for item in verdicts), 3) if verdicts else 0.0,
        "automated_pass_rate": round(mean(item["automated_pass"] for item in verdicts), 3) if verdicts else 0.0,
        "judge_disagreement_rate": round(mean(item["judge_disagreement"] for item in verdicts), 3) if verdicts else 0.0,
        "release_recommendation": "hold_review_all_beta",
        "disclaimer": "This is LLM-assisted automated validation against a frozen golden dataset. It does not establish human calibration, production safety, or permission to relax release controls.",
        "failures": failures,
        "case_verdicts": verdicts,
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"case_verdicts", "failures"}}, indent=2))


if __name__ == "__main__":
    main()
