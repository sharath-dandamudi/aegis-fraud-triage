# Offline Evaluation and Judge Calibration Runbook

The golden dataset is frozen at 100 synthetic, provenance-derived Australian banking-scam cases. Do not edit it to improve a score; create a versioned successor dataset instead.

## Comparable experiment profiles

Run each profile against the identical cases and keep their reports:

```bash
python run_provider_evals.py --profile baseline --run-name baseline_v0
python run_provider_evals.py --profile local_control --run-name local_graph_v1
python run_provider_evals.py --profile pinecone_retrieval --run-name pinecone_graph_v1
python run_provider_evals.py --profile live --run-name live_nebius_v1
```

Profiles isolate the value of each change:

- `baseline`: limited keyword response; establishes the meaningful before state.
- `local_control`: deterministic graph/RAG and safety gates, without providers.
- `pinecone_retrieval`: live semantic Pinecone retrieval with deterministic drafting.
- `live`: Pinecone graph-constrained retrieval plus evidence-constrained Nebius drafting.

Each report includes routing/escalation, retrieval/citations, tool trajectory, gate contracts, review routing, guardrails, latency, and cost. The dataset includes expected tool calls, chunk IDs, gates and release decisions, so this is a whole-system evaluation rather than final-answer-only scoring.

Publish the frozen synthetic set to LangSmith once, before creating UI experiments:

```bash
python publish_golden_dataset_to_langsmith.py
```

## LLM-as-judge

Run the live profile with an independent Nebius judge model:

```bash
python run_provider_evals.py --profile live --judge nebius --run-name live_judged_v1
```

The judge scores four 0–4 dimensions:

1. Faithfulness to retrieved evidence.
2. Safety: no harmful promises or sensitive-data requests.
3. Escalation appropriateness.
4. Actionability through safe, official channels.

The judge is an offline diagnostic signal only. It cannot decide release or override deterministic gates.

## Human calibration

Create a stratified 15-case review sheet after a judged run:

```bash
python run_provider_evals.py --profile live --judge nebius --stratified 15 --run-name live_judge_calibration_v1
python prepare_human_calibration.py --results reports/live_judge_calibration_v1_case_results.jsonl
```

Two reviewers should independently fill the `human_*` score columns (0–4), reviewer ID, and a concise note. Then assess agreement:

```bash
python assess_human_calibration.py --labels reports/human_calibration_template.csv
```

The judge is not release-eligible until at least 15 independently human-reviewed cases achieve mean exact agreement of 0.80 or more. Recalibrate after a model, prompt, rubric, corpus or policy change.

## Automated alternative when reviewers are unavailable

Do **not** call this human calibration. Run the automated validation pack instead: it combines strict evidence and banking-safety red-team rubrics with the frozen deterministic trajectory contracts, and reports judge disagreement.

```bash
PYTHONPATH=src python run_automated_judge_validation.py \
  --results reports/live_nebius_v2_post_output_gate_fix_case_results.jsonl \
  --stratified 30 \
  --output reports/live_nebius_v2_automated_judge_validation_30.json
```

Use it to find failures and compare model changes. It always recommends `hold_review_all_beta`; human calibration remains optional future evidence, not a hidden prerequisite for this demo.

After a defect fix, preserve the failed cases as a named targeted-regression run before repeating a representative sample:

```bash
python run_provider_evals.py --profile live --case-id BSTA-F-002 --case-id BSTA-E-001 --case-id BSTA-E-004 --run-name live_regression_active_compromise_v1
```

## RAGAS

RAGAS is pinned to `0.3.9` because the newer 0.4.3 release has a known import incompatibility with current LangChain Community packages. Run it only on persisted, redacted evaluation outputs:

```bash
PYTHONPATH=src python run_ragas_evals.py \
  --results reports/live_nebius_v2_post_output_gate_fix_case_results.jsonl \
  --stratified 30 \
  --output reports/live_nebius_v2_ragas_stratified_30.json
```

`--stratified 30` deterministically selects 15 representative, 9 edge, 4 known-failure and 2 adversarial cases. It reports faithfulness, answer relevancy, context precision and context recall. Nebius may return one generation where Answer Relevancy requests several; in that case the runner reports that metric as **unavailable**, never as zero. Keep RAGAS separate from deterministic trajectory metrics: it provides semantic RAG signals, not compliance proof.

## Release decision

For beta, retain mandatory human review for consequential scam cases. Do not change release policy based solely on an aggregate metric. The release evidence pack should include the three comparable reports, RAGAS report, judge report, human-calibration assessment, known failure modes, and linked LangSmith traces.
