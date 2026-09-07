# Aegis Fraud Triage — Autonomy v1.1

## Purpose

Autonomy v1.1 increases **safe internal workflow autonomy**, not financial decision autonomy. The agent can now identify high-risk indicators more conservatively, prepare a validated response envelope and assemble a complete, reversible review package. It still cannot move money, block an account, decide liability or send consequential customer guidance without a person.

## What changed

| Control | Implementation | Authority boundary |
| --- | --- | --- |
| High-recall urgent override | Deterministic detection of active remote access, exposed credentials/OTP, coercion/further-loss signals and payment-in-progress signals | Forces `urgent_fraud`, escalation and human review; never authorises a tool or customer release |
| Hybrid reranking | Pinecone semantic candidates retain required graph nodes, then optional evidence receives deterministic lexical and route-alignment reranking | Required evidence remains mandatory; reranking cannot override the retrieval-quality gate |
| Structured response contract | Server code produces risk summary, approved action list, citations, human-review flag, prohibited-claim state and schema validity | The LLM drafts prose only; the contract is a validated envelope, not a model-selected action |
| Autonomous case package | Held cases receive a redacted summary, evidence IDs, tool/gate summaries, recommendation list, route/risk, trace ID and package completeness flag | The package is a local review artefact; `create_fraud_case` remains a separately authorised mock action |

## Current evidence

The frozen 100-case local-control run after this change reported:

| Metric | Result | Interpretation |
| --- | ---: | --- |
| Critical escalation recall | 1.000 | The desired high-recall safety result in this local control run |
| Escalation precision | 0.731 | Seven extra cases were escalated; accepted short-term cost of conservative safety routing |
| Structured response-contract compliance | 1.000 | All evaluated drafts had a valid server-built, evidence-backed envelope |
| Review-case-package completeness | 1.000 | Every applicable held case received a complete internal work package |
| Guardrail compliance | 1.000 | Local deterministic control run only; not a production claim |
| Route macro-F1 | 0.935 | Lower than the preceding local score because high-recall overrides intentionally favour false-positive review over missed critical cases |

The regression suite now has 23 tests, including a 20-case urgent-risk pack with 14 active-compromise cases and 6 non-urgent near misses.

A two-case live Pinecone-plus-Nebius smoke over retained urgent-failure cases passed route, escalation, retrieval/citation, tool, gate, review and case-package contracts. Its p95 latency was `12.90s` and estimated cost was `A$0.004` per run.

The subsequent full 100-case live run confirmed the safety outcome: critical-escalation recall, guardrail compliance, structured-contract compliance and review-case-package completeness were all `1.000`. It also surfaced the operational trade-off: escalation precision `0.731` (seven extra reviews), route macro-F1 `0.935`, evidence coverage `0.960`, citation recall `0.887`, tool-contract accuracy `0.920`, p95 `12.55s`, and estimated average cost `A$0.0035`. The one non-safety route regression was `BSTA-R-044`, a refund-fee report routed as general safety. Retain it as the next targeted routing regression.

## Operating model

1. The agent redacts input and contains injection.
2. The deterministic router classifies the report.
3. The urgent override may elevate active compromise to `urgent_fraud`.
4. Retrieval must satisfy graph-required evidence; optional context is reranked deterministically.
5. A draft passes generation, evidence, output-safety and structured-contract gates.
6. Consequential cases receive a complete internal case package and enter human review.
7. Only narrow low-risk guidance can be auto-send eligible. No autonomous financial action is available.

## Why this is a meaningful autonomy increase

The previous MVP could draft and queue a case. V1.1 can reliably package enough validated context for an operations reviewer to act with less manual assembly: the intended risk route, evidence IDs, recommended actions, tool outcomes, gate results, trace ID and escalation reason travel together. That reduces handoff friction while retaining human authority.

## Known trade-off and next decision

The override improves critical recall by intentionally increasing false-positive escalation. Before changing that threshold, measure reviewer override/edit rate on a governed dataset and set a route-specific precision floor. Do not optimise average macro-F1 at the expense of missing active compromise.

The next safe increment is to connect the package to a real, bank-owned case-management workflow using service identity, consent/entitlements, idempotency, audit events and human approval. It should still not automate payment movement, account changes, reimbursement or liability decisions.
