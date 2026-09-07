# Project status and tomorrow checklist

## Completed locally

- Mermaid architecture diagram and Streamlit architecture view.
- Evidence-first MVP agent with routing, graph-aware local retrieval, policy-authorised mock tools, chunk-level citations, safety gates, and human escalation.
- Deny-by-default tool-authorisation gateway: server-asserted identity, customer ownership, consent, least-privilege scopes, route/payload policy checks, denial events, and escalation on failure. Local demo context is not production authentication.
- Human response-release gate and local review queue: financial/account-security cases, tool results, failed gates, or low-confidence routes are held for reviewer approval, edit, escalation, or rejection. The review record contains redacted input, evidence chunk IDs, tool/gate summaries, reviewer ID, decision, and trace ID.
- Guardrail chain: input safety, retrieval quality, tool authorisation, generation contract, evidence/abstention, output safety, and response release. A retrieval, generation, or evidence failure produces a safe abstention and human handoff rather than an unsupported conclusion.
- 100-case versioned golden dataset (v1.3.0): 50 representative, 30 edge, 15 known-failure, and 5 adversarial cases, including tool-authorisation and gate expectations for every case.
- 60-chunk public Australian customer-safety corpus across 15 sources, combined with 9 internal demonstration control nodes for 69 retrievable nodes. Every public chunk is a paraphrase with publisher, URL, trust tier, AU jurisdiction, review date, and a `not_bank_policy` marker.
- Expected system-level contracts in every case: route, escalation, tool plan, retrieval chunk IDs, citation targets, prohibited claims, and trajectory constraints.
- Baseline-vs-v1 offline evaluator for routing, escalation, retrieval recall, citation accuracy/recall, tool contracts, guardrails, trajectory, latency, and cost.
- Versioned local alert engine and Streamlit alert view: critical tool/PII/urgent-auto-release alerts; gate-failure, abstention, authorisation, latency, and cost alerts with explicit rolling thresholds.
- Local JSONL traces, optional OpenTelemetry spans, LangSmith APAC experiment dataset, and Streamlit monitoring/evaluation views.
- Live Pinecone graph-constrained retrieval is indexed in the isolated `policy-v1` namespace (69 provenance-bearing chunks); Nebius evidence-constrained drafting is active behind the existing deterministic gates.
- Live evaluation runner supports baseline, local-control, Pinecone-only and full live profiles, targeted regression cases, RAGAS, independent LLM-as-judge, and a stratified human-calibration sheet.
- A 15-case live, stratified judge run and a one-case RAGAS smoke run completed. The review worksheet has 8 representative, 4 edge, 2 known-failure and 1 adversarial case; human labels are still required.

## Latest local v1 evaluation

These scores are regression-test results over a synthetic set, not production performance claims.

| Metric | Result |
| --- | ---: |
| Routing macro-F1 | 0.974 |
| Escalation F1 | 0.947 |
| Retrieval context recall | 0.987 |
| Citation accuracy | 1.000 |
| Citation recall | 0.980 |
| Tool-contract accuracy | 0.970 |
| Tool-authorisation compliance | 0.980 |
| Human-review routing accuracy | 0.980 |
| Gate-contract compliance | 0.980 |
| Critical-escalation recall | 0.929 |
| Guardrail compliance | 1.000 |
| Trajectory conformance | 0.960 |
| P95 latency | 0.37 ms |
| Mean mock cost | A$0.0035 |

The latency and cost are local mock measurements. Re-baseline them once an LLM and external retrieval service are connected.

## Live evaluation evidence — not a production claim

- The live 15-case stratified run found a critical active-remote-access routing miss and an output-gate false positive. Both controls were corrected with regression tests.
- The one-case corrected live regression passed route, escalation, evidence/citation, tool contract, human-review routing and all gates; live P95 was 11.10 seconds and estimated average cost A$0.004.
- The one-case RAGAS smoke score was faithfulness 0.875, answer relevancy 0.744, context precision 1.000 and context recall 1.000. It is a connectivity and integration check, not a quality claim.
- The post-fix full 100-case live run completed: routing macro-F1 `0.974`, escalation F1 `0.923`, evidence coverage `0.983`, citation accuracy `1.000`, critical-escalation recall `0.929`, guardrail compliance `0.980`, trajectory conformance `0.980`, p95 `12.34s`, estimated average cost `A$0.0035`.
- This is not a promotion pass: the desired beta bar for critical-escalation recall is 1.000, output-safety pass rate is `0.979`, and gate-contract compliance is `0.960`. Those misses are retained as follow-up failure cases.
- Do not adjust release policy until failure analysis, post-fix semantic evaluation and human calibration are complete.

## Current completion state

- Docker Desktop observability stack is running and verified: Grafana, Prometheus, Loki, Tempo and Alloy are healthy; Prometheus scrapes Aegis metrics and Alloy has accepted and forwarded an OpenTelemetry span to Tempo.
- The pre-fix 100-case live report is retained as a failure artefact. It revealed false-positive output-safety results; the targeted regression passed after the correction and the full post-fix report is now available.
- The pre-fix full automated judge pack completed on 87 executable cases: both rubric profiles returned near-ceiling scores, while deterministic-contract pass rate was `0.816`. This mismatch is exactly why the judge remains diagnostic only; 13 failed judge executions and no human calibration make it unsuitable as a release gate. A post-fix stratified pack is queued.
- `ARCHITECTURE.md`, `PROJECT_REFERENCE.md`, `INTERVIEW_GUIDE.md`, and `INTERVIEW_QA.md` are the current reference pack for the project.
- Autonomy v1.1 is implemented and fully live-evaluated: high-recall urgent override, deterministic route-aware reranking, structured response contracts and complete internal review-case packages. The 100-case Pinecone-plus-Nebius run achieved 1.000 critical-escalation recall, 1.000 guardrail compliance, and 1.000 package/contract compliance, with p95 `12.55s` and estimated cost `A$0.0035` per run.
- This is a safety improvement, not an autonomy-promotion pass: escalation precision is `0.731` (seven false-positive escalations), routing macro-F1 `0.935`, evidence coverage `0.960`, citation recall `0.887`, and tool-contract accuracy `0.920`. The retained failure `BSTA-R-044` misrouted a refund-fee report as general safety; it should be fixed as a targeted regression before any release-policy change.

## Run tomorrow

```bash
cd "/Users/mahati/Documents/Aegis Fraud Triage"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python data/generate_golden_dataset.py
python run_evals.py
streamlit run app.py
```

## Add credentials deliberately

1. Copy `.env.example` to `.env`; never commit it.
2. Add `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` to capture native LangSmith runs.
3. Set `OTEL_EXPORTER_OTLP_ENDPOINT` only after an approved collector is available.
4. The Pinecone corpus and Nebius drafting are configured; run the four comparable profiles in `OFFLINE_EVALUATION_RUNBOOK.md` after any prompt, routing or policy change.
5. Have two reviewers independently complete `reports/human_calibration_stratified_15.csv`, then run `assess_human_calibration.py`; do not use judge scores for release decisions before agreement reaches the documented bar.

## Do not claim yet

- The mock tools do not contact a bank, retrieve transactions, block cards, stop payments, or create real cases.
- The local knowledge graph is a safe demonstration corpus, not approved banking policy.
- The LLM judge and RAGAS are diagnostic evaluation tools; neither is calibrated nor a release gate.
- Synthetic outcomes must be supplemented by governed de-identified real cases before any production or interview claim about real-world accuracy.
