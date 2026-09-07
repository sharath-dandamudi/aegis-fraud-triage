# Aegis Fraud Triage — Gate and Guardrail Policy (MVP v1.3)

This document separates thresholds enforced by the local MVP from proposed beta release criteria. The local agent is deterministic and uses mock tools; it is not a production control system.

## Enforced runtime rules

| Checkpoint | Enforced rule | Failure action |
| --- | --- | --- |
| Input safety | Block prompt-injection/data-exfiltration patterns; redact 13–16 digit card/account-like strings, 6–8 digit code-like strings, and email addresses before tracing. | Blocked safety response; no normal workflow. |
| Retrieval quality | At least one chunk; **all** route-required core sources present; maximum lexical score must be `> 0.0`. Retrieval limit is 5 chunks. | Skip optional enrichment tools; safe abstention and human handoff. |
| Tool authorisation | Deny unless authenticated, verified ownership, consent, required scope, permitted route, and exact payload schema all pass. | Do not execute tool; record denial and escalate. |
| Generation contract | Non-empty draft, maximum **1,500 characters**, at least one citation token (`[chunk_id]`), and no `[REDACTED_` marker echoed. | Safe abstention and human handoff. |
| Evidence gate | At least one citation; every response citation must exactly match a chunk returned by retrieval. | Safe abstention and human handoff. |
| Abstention gate | Retrieval quality, generation contract, and evidence gate must all pass. | Replace draft with an explicit “cannot verify safely” response and route to human review. |
| Output safety | Reject affirmative outcome promises and actual requests for password, OTP/one-time code, full card, or account number; urgent route must state that a human review/specialist will review. Safe prohibitions such as “never provide a password” pass. | Human escalation. |
| Response release | Review is required if any gate fails, any tool succeeds, the route is payment/credential/card/urgent fraud, risk is high/critical, or router confidence is `< 0.85`. | Hold as pending human draft. |

## Route-required retrieval evidence

| Route | Required core sources |
| --- | --- |
| Urgent fraud | `urgent_review`, `contact_official`, `no_guarantee` |
| Authorised payment scam | `payment_scam`, `contact_official`, `no_guarantee` |
| Credential compromise | `credential_compromise`, `secure_access`, `contact_official` |
| Card security | `card_security`, `contact_official`, `no_guarantee` |
| Scam information | `general_safety`, `contact_official` |
| Out of scope | `general_safety`, `contact_official` |

## Tool policy

| Tool | Allowed routes | Required scope | Exact payload | Extra boundary |
| --- | --- | --- | --- | --- |
| `transaction_lookup` | Urgent fraud, authorised-payment scam, card security | `transactions:read` | `customer_reference` | Reference must equal the server-asserted customer reference. |
| `payee_risk_lookup` | Authorised-payment scam | `payee_risk:read` | `payee_hint` | Only `customer_reported` is accepted. |
| `create_fraud_case` | Urgent fraud, authorised-payment scam, credential compromise, card security | `fraud_case:create` | `customer_reference`, `reason` | Reason must be text of at most **160 characters**. |

Every tool is deny-by-default. Unknown tools, missing authorisation context, unauthenticated sessions, unverified customers, missing consent/scopes, route mismatches, ownership mismatches, and schema mismatches are denied. No tool can move money or alter an account in this MVP.

## Routing and escalation thresholds

- The deterministic router assigns fixed confidence values by rule: blocked `0.99`, information `0.85`, out-of-scope `0.95`, urgent fraud `0.92`, payment `0.84`, credential `0.85`, card `0.78`, and fallback information `0.85`.
- The response-release policy holds a response for human review when confidence is **below 0.85**. Exactly `0.85` passes this confidence rule, but account-security routes still require review.
- The escalation rule triggers for urgent risk, tool-authorisation denial, abstention failure, output-safety failure, or confidence **below 0.55**. Blocked prompt-injection cases use a dedicated safety-containment escalation.

## Not calibrated yet — do not describe as production thresholds

- Retrieval relevance has only a structural threshold (`max score > 0`); it has no calibrated embedding, reranker, freshness, conflict, or semantic relevance threshold yet.
- The evidence gate verifies citation provenance, not full claim-by-claim semantic entailment.
- RAGAS and LLM-as-judge are provider-backed diagnostic evaluations. The judge uses 0–4 scores for faithfulness, safety, escalation, and actionability; no judge score is a runtime release threshold.
- Automated judge validation is explicitly not human calibration. It cannot justify a change to review-all policy; future human labels remain the preferred calibration evidence.
- No production queue SLA, fraud-amount threshold, customer-vulnerability rule, model drift limit, or data-retention threshold is configured.

## Recommended beta promotion criteria (proposed, not active)

Keep review-all mode enabled until the following are demonstrated on governed held-out cases:

| Measure | Proposed beta bar |
| --- | ---: |
| Critical-risk escalation recall | 100% |
| Citation accuracy | >= 98% |
| Human-calibrated LLM groundedness | >= 95% |
| Unauthorised successful tool calls | 0 |
| Critical safety failures after review | 0 |
| LLM-judge agreement with human labels | >= 0.80 on at least 15 labels |
| Auto-send reviewer edit rate | < 10% before enabling limited auto-send |

These values require approval by fraud operations, security, privacy/compliance, and model-risk stakeholders before use.
