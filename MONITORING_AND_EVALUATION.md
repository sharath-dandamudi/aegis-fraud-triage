# Monitoring and Evaluation Operating Model (MVP v1.3)

## Offline evaluation — active now

`python run_evals.py` compares the intentionally limited baseline with the v1 agent on the frozen 100-case golden dataset. It writes a summary and case-level results under `reports/`.

| Evaluation family | Active metrics | Evaluator type | Purpose |
| --- | --- | --- | --- |
| Routing and escalation | Macro-F1, per-route precision/recall, escalation F1, critical-escalation recall | Code | Detects misclassification and dangerous missed escalation. |
| Retrieval and citations | Context recall, evidence coverage, citation accuracy/recall, required chunk IDs | Code | Verifies the retrieval plan and citation provenance. |
| Agent trajectory | Tool-contract accuracy, tool-authorisation compliance, trajectory conformance | Code | Verifies permitted action sequence and tool boundaries. |
| Guardrails | Gate-contract compliance; pass rates for input, retrieval, generation, evidence, abstention, and output gates | Code | Proves controls fire as expected on each golden case. |
| HITL | Human-review routing accuracy and auto-release rate | Code | Verifies risky drafts are held for people. |
| Bounded autonomy | Urgent-override trigger rate, critical urgent-route recall, structured-contract compliance, review-case-package completeness | Code | Verifies autonomous preparation remains evidence-backed and reviewable. |
| Operational | p95 latency and average mock cost | Code | Establishes regression budgets before a provider is connected. |

## Provider-backed offline evaluations

| Evaluator | Planned metrics | Activation condition |
| --- | --- | --- |
| RAGAS | Faithfulness, answer relevancy, context precision, context recall | Post-fix two-case smoke completed; 30-case stratified diagnostic run is in progress. |
| LLM-as-judge | Faithfulness, safety, escalation, actionability | Pre-fix full pack completed and post-fix 30-case pack is in progress; neither is human calibration or a release signal. |
| Human review | Correctness, safety, usefulness, reviewer edit reasons | Future production requirement; unavailable in this local demo. |

## Online monitoring — active locally

Each interactive run writes a redacted trace and evaluates it against alert policy `v1.0.0`. Alerts are stored in `logs/alerts.jsonl` and visible in the Streamlit Operations tab. Offline cases (`BSTA-*`) are excluded from online alerting and the human queue.

| Alert | Severity | Active threshold | Operator action |
| --- | --- | --- | --- |
| Unauthorised successful tool | Critical | Any occurrence | Disable tool path; investigate immediately. |
| Sensitive data in generated response | Critical | Any occurrence | Stop release; investigate immediately. |
| Urgent-fraud auto-release | Critical | Any occurrence | Switch to review-all; investigate immediately. |
| Output, retrieval, generation, or evidence failure | High | Any occurrence | Confirm safe abstention/human handoff and inspect trace. |
| Gate failure rate | High | > 5% across 20 interactive traces | Pause auto-release; inspect release/corpus change. |
| Abstention rate | Medium | > 10% across 20 interactive traces | Review retrieval coverage, policy corpus, and drift. |
| Tool authorisation denial | Medium | Any occurrence | Review scope, ownership, consent, and route policy. |
| p95 latency | Medium | > 3,000 ms across 20 interactive traces | Investigate model, retrieval, and tool latency. |
| Mean cost | Medium | > A$0.10 across 20 interactive traces | Investigate provider/model/tool usage. |

## Production telemetry contract

Every trace should include: trace ID, case ID, route, risk tier, policy/prompt/model/retriever version, retrieved chunk IDs and scores, tool proposal and authorisation decision, gate outcomes/reasons, review decision, latency, cost, errors, and alert codes. No secrets, raw account/card data, passwords, or one-time codes may be exported.

For Autonomy v1.1, also record whether the urgent-risk override fired and why, the validated response-contract state, and case-package completeness. A rising override rate is a drift/review-capacity signal; it is not a reason to lower the escalation threshold without reviewed evidence.

LangSmith is used for evaluation runs, prompt/model comparison, and trace drill-down. OpenTelemetry exports the same bounded attributes and trajectory events to the approved operational collector.

## Beta governance cadence

- Daily: review critical/high alerts, reviewer edits/escalations, and new abstentions.
- Weekly: compare current online slices with offline baseline; review route mix, gate failures, reviewer edit rate, latency, and cost.
- Before any auto-send expansion: rerun frozen golden set, a held-out governed set, RAGAS, LLM judge, and human calibration.

The current local figures are synthetic regression results. In particular, critical-escalation recall must reach the approved release bar before autonomous scope expands. The post-fix 100-case live run is below that bar (`0.929` critical-escalation recall), so consequential financial/account-security cases remain human-reviewed.
