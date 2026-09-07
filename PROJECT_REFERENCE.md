# Aegis Fraud Triage — Technical Reference

## Goal and user outcome

Build a production-shaped Australian banking scam-triage copilot. It gives safe, evidence-linked next steps and creates a reviewable case package; it does **not** decide liability, move money, block accounts or promise recovery.

The customer outcome is clear, actionable advice through official channels. The operational outcome is an explainable trajectory: risk route, evidence, tool authorisation, gates, release decision, latency, cost and trace ID.

## Success criteria

| Criterion | Current control | Required behaviour |
| --- | --- | --- |
| Injection and PII | Redaction plus containment route | No normal workflow or protected-data disclosure |
| Insufficient evidence | Route-required evidence and fail-closed retrieval gate | Abstain and send to review; do not use tools |
| Tool safety | Server identity, ownership, consent, scopes, route and schema | Zero unauthorised successful calls |
| Unsafe draft | Citation, abstention and output-safety gates | Safe abstention or human review |
| Consequential response | HITL response release policy | Human review required |
| Operational accountability | JSONL, OTel, Grafana and LangSmith | Traceable reconstruction of a decision |

### Proposed beta promotion bars

These are targets, not production claims: 100% critical escalation recall, citation accuracy >=98%, zero unauthorised successful tools, zero critical safety failures after review, groundedness >=95% on independently reviewed data, and auto-send edit rate <10% before any expansion.

## AI and platform stack

| Layer | Technology | Why | Trade-off / boundary |
| --- | --- | --- | --- |
| Application | Python, Streamlit | Transparent demo and HITL console | Not a customer-facing production channel |
| Orchestration | Explicit deterministic Python graph | Auditable gates and trajectory | Less flexible than open-ended autonomy |
| Retrieval | Pinecone `policy-v1` namespace + graph requirements | Semantic search plus mandatory policy coverage | Corpus/index requires governed change control |
| Generation | Nebius Qwen3-30B | Evidence-constrained customer draft | Draft has no release authority |
| LLM judge | Nebius Llama-3.3-70B | Semantic evaluation from a different model family | Same-provider correlation; automated validation only |
| RAG evaluation | RAGAS 0.3.9 | Faithfulness/relevance/context metrics | Not a compliance proof; pin requires review before upgrade |
| LLM experiment traces | LangSmith APAC | Dataset, nested trace and prompt/model comparison | Redacted data only |
| Operations | OpenTelemetry, Alloy, Grafana, Prometheus, Loki, Tempo | Metrics, logs and trace drill-down | Local Docker stack lacks enterprise deployment controls |
| Tools | Mock transaction, payee risk, fraud case | Demonstrates least-privilege authorisation | No real banking action |

## Major architecture decisions and trade-offs

| Decision | Why | Cost / mitigation |
| --- | --- | --- |
| Triage copilot, not autonomous bank agent | High-consequence risk requires limited authority | Lower automation; visible HITL operating model |
| Deterministic gates around LLM | Cheap, auditable boundaries | They cannot prove semantic entailment; evaluate with RAGAS/judges |
| Retrieve before tool use | Avoid unnecessary account-data access | More abstentions; correct least-privilege behaviour |
| Graph-constrained vector RAG | Semantics plus route-required evidence | Needs route-to-policy mapping and corpus versioning |
| Deny-by-default tools | Separates authorisation from chat text | Production needs real entitlement service |
| Review-all consequential guidance | Defensible beta policy | Human workload; cannot relax without evidence |
| Synthetic golden data first | Repeatability without customer-data exposure | Not real-world validation; later add governed de-identified holdout cases |
| Grafana plus LangSmith | Operational and LLM-specialist views | Two systems, correlated through trace IDs |

The detailed chronological ADR is `DECISION_LOG.md`.

## Golden dataset and knowledge corpus

`data/golden_dataset_v1.jsonl` is a 100-case, de-identified, versioned set (`v1.3.0`): 50 representative cases, 30 edge cases, 15 known failures and 5 adversarial/injection cases. Every row specifies expected route/risk/escalation, source and chunk IDs, citations, tool plan and authorisation conditions, gates, release mode, prohibited claims and trajectory constraints. It measures the entire agent path, not only the final prose.

The retrieval corpus has 69 nodes: 9 internal demonstration control nodes and 60 provenance-rich, paraphrased Australian public customer-safety chunks from 15 sources. Public chunks include publisher, URL, AU jurisdiction, trust tier, review date and `not_bank_policy=true`; they are not represented as bank policy. See `data/SOURCES.md`.

## Evaluation model

| Method | Signal | Status |
| --- | --- | --- |
| Code evaluation | Route, escalation, retrieval, citations, tools, gates, HITL, latency/cost | Active |
| Local 100-case control | Baseline against no external provider | Completed post-regression |
| Live 100-case profile | Pinecone + Nebius actual path | Completed post-fix; below beta promotion bar, with failures retained for review |
| Targeted regression | Failed cases after a control change | Active engineering practice |
| RAGAS | Faithfulness, relevancy, context precision/recall | One-case live smoke done; representative post-fix run in progress |
| Automated LLM validation | Evidence-strict and safety-red-team rubrics plus disagreement | Pre-fix full automated pack complete; post-fix representative pack in progress; not human calibration |
| Human calibration | Validate judge against domain reviewers | Deferred; unavailable for this demo |

### Evidence snapshot and its limitation

The post-fix 100-case live run reached routing macro-F1 `0.974`, escalation F1 `0.923`, evidence coverage `0.983`, citation accuracy `1.000`, critical-escalation recall `0.929`, p95 latency `12.34s` and estimated average cost `A$0.0035`. It improved guardrail compliance to `0.980` and output-safety gate pass rate to `0.979`; it did **not** meet the proposed beta promotion bars because two output-safety cases and other trajectory contracts still need failure analysis.

The retained pre-fix run remains a useful engineering artefact: literal matching incorrectly treated some correct safety advice as a sensitive-data request. That defect was fixed, covered by unit regression, and the urgent-review language was moved before response gates. The suite now has 23 tests. Neither the improved score nor the automated judge is evidence for autonomous release.

## Monitoring and operations

The local stack is verified running: Grafana Operations Command Centre, Prometheus aggregate metrics, Loki redacted logs, Tempo OpenTelemetry traces, Grafana Alloy collection and LangSmith APAC trace/experiment support. The OTLP HTTP exporter dependency is pinned so actual application spans can reach Tempo. Alerts cover unauthorised tools, sensitive-data outputs, urgent auto-release, gate failure, abstention, latency and cost. Thresholds and cadence are documented in `MONITORING_AND_EVALUATION.md`.

## Autonomy v1.1 — bounded workflow autonomy

Autonomy v1.1 adds a deterministic high-recall urgent-risk override, route-aware evidence reranking, a server-validated response contract and an internal review-case package. It makes a reviewer handoff more complete and reduces the chance of missing active compromise; it does not broaden the agent’s banking authority. The completed 100-case live Pinecone-plus-Nebius run reached critical-escalation recall `1.000`, guardrail compliance `1.000`, structured-contract compliance `1.000` and review-case-package completeness `1.000`; p95 latency was `12.55s` at estimated cost `A$0.0035` per run.

The trade-off is deliberate but not yet promotion-ready: escalation precision fell to `0.731` (seven false-positive escalations), route macro-F1 to `0.935`, evidence coverage to `0.960`, citation recall to `0.887` and tool-contract accuracy to `0.920`. The retained refund-fee routing regression (`BSTA-R-044`) was fixed and a targeted live rerun passed route, evidence/citation, tool, gate, review, contract and package checks. Keep mandatory review for consequential cases and improve the route taxonomy/retrieval coverage before considering any release-policy expansion.

See `AUTONOMY_V11.md` for the implementation, evidence and safe expansion path.

## Honest production boundary

1. Tools are mocks, not core-banking integrations.
2. Corpus content is customer-safety context, not approved bank policy.
3. Citation provenance is not full claim-by-claim semantic proof.
4. Automated judge validation does not replace human calibration or permit relaxing mandatory review for consequential cases.
5. Local Docker needs private networking, mTLS, SSO/RBAC, managed storage, retention, on-call and security/compliance controls before deployment.
6. Synthetic scores are not production accuracy; governed de-identified holdout cases are required.

## Entry points

| Need | File / command |
| --- | --- |
| Architecture | `ARCHITECTURE.md` |
| Gate specifics | `GATE_POLICY.md` |
| Evaluation commands | `OFFLINE_EVALUATION_RUNBOOK.md` |
| Operations stack | `OBSERVABILITY_STACK.md` |
| Senior interview narrative | `INTERVIEW_GUIDE.md` |
| Detailed interview Q&A | `INTERVIEW_QA.md` |
| Bounded autonomy increment | `AUTONOMY_V11.md` |
| Demo | `streamlit run app.py` |
