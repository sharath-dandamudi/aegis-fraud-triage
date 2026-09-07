# Aegis Fraud Triage — Senior AI Builder Interview Guide

## Positioning

> “Aegis Fraud Triage is an evidence-first copilot for Australian banking scam reports. It is designed as triage and guidance, not an autonomous banking agent: it cannot move money, decide liability or promise recovery. Its value is safe routing, grounded guidance, controlled enrichment, human review and observable evidence.”

## 30-second version

“I built a production-shaped scam-triage copilot for an Australian banking context. The agent routes a redacted report, retrieves route-constrained evidence, can use only deny-by-default mock tools, drafts a cited response, and passes it through retrieval, generation, evidence, output-safety and release gates. Consequential cases are held for human review. I evaluate the complete trajectory with a 100-case golden set, RAGAS, LLM judging and Grafana/LangSmith observability—not just answer quality.”

## Two-minute walkthrough

1. **Risk boundary:** “I avoided an autonomous banking agent. The system prepares safe guidance and a reviewable triage package.”
2. **Flow:** “Input guardrails redact sensitive data and contain injection. A deterministic router selects risk and required evidence. Pinecone retrieves semantically, while graph constraints require the correct core policy nodes. Missing evidence fails closed.”
3. **Tool control:** “A tool call must prove server-asserted identity, customer ownership, consent, least-privilege scope, allowed route and schema. Chat text cannot select another customer or elevate scopes.”
4. **Model authority:** “Nebius only drafts from redacted approved evidence. Gates and release policy, not the model, decide whether the draft can progress.”
5. **HITL:** “Payment, credential, card and urgent cases; tool use; low confidence; and failed gates all hold for human review. Only narrow general-safety guidance can auto-send.”
6. **Evaluation:** “The golden set includes tools, chunk IDs, citations and gates, so I test the path. A live evaluation revealed a real control defect; I preserved the run, added a regression test, fixed the control and scheduled the rerun.”

## Five-minute whiteboard sequence

Use the first diagram in `ARCHITECTURE.md`, then explain:

1. **Minimise authority:** the LLM is a drafter, never a bank decision-maker.
2. **Ground before action:** retrieval coverage is checked before tools.
3. **Least privilege:** identity, ownership, consent, scopes and payload checks gate tools.
4. **Fail closed:** missing evidence, invalid citations or unsafe output becomes abstention plus review.
5. **Measure the trajectory:** evidence, tools, gates, release, latency and cost are all logged and evaluated.

## Demo sequence

1. In Streamlit, submit a synthetic PayID scam report.
2. Show route, review status, evidence chunk IDs, gates and authorised mock tools.
3. In Grafana, show trace volume, p95 latency, route/risk mix, review load and alerts.
4. Drill from a redacted log trace ID into Tempo or LangSmith.
5. Show the golden-set report and the failure-analysis/regression loop.

Never enter real customer information in the demo.

## Questions a senior interviewer may ask

### Why not just use a stronger model and a better prompt?

“Prompting is useful but insufficient for banking controls. I separated model generation from runtime authority: retrieval coverage, deterministic gates, tool authorisation and response release decide what can happen. That gives us auditable, fail-closed behaviour.”

### How do you prevent hallucinations?

“I do not claim hallucination is solved. I constrain generation to approved evidence, require citation provenance, fail closed on missing evidence, measure faithfulness with RAGAS and strict LLM critics, and retain HITL for consequential cases. Claim-level entailment remains a known limitation and monitoring target.”

### Why combine graph RAG with Pinecone?

“Semantic retrieval handles language variation. Graph constraints encode which policy coverage is non-negotiable for each risk route. For urgent fraud, high similarity alone is not enough: the response must have urgent-review, official-channel and no-guarantee evidence.”

### How are tool calls secure?

“The model has no permission to grant itself access. A separate policy layer checks server-issued identity, ownership of the reference, consent, scopes, route and exact payload. The current tools are mocks because demonstrating a secure boundary is safer than simulating real bank action.”

### How do you evaluate an agent rather than a chatbot?

“I store final-output expectations, plus retrieved chunks, citations, expected tools, authorisation, gates, release mode and trajectory constraints. That catches a polished answer that reached the right wording through an unsafe path.”

### Is LLM-as-judge enough without reviewers?

“No. I call it automated judge validation, not human calibration. I use evidence-strict and safety-red-team rubrics, deterministic contracts and disagreement reporting. It is valuable for regression detection but does not justify relaxing mandatory human review for consequential cases.”

### What did the evaluation teach you?

“The full live run found false-positive output-safety failures from lexical matching of correct phrases such as ‘never provide full card details’ and equivalent human-review wording. I retained the run, made the gate semantically specific, added regression tests and will rerun. That is the reliability loop I would apply in production.”

### How would you harden this for production?

“Approved and versioned bank policy, real identity/consent/entitlement services, private deployment with mTLS and SSO/RBAC, retention and key controls, governed de-identified held-out data, domain-expert calibration, red-team testing, drift monitoring and an explicit auto-send expansion plan.”

## Metric language: what to say

Say: “On the synthetic, versioned golden set, the retained pre-final-fix live profile reached routing macro-F1 0.974 and citation accuracy 1.0, while exposing an output-gate false-positive issue.”

Do not say: “The system is 97.4% accurate in production,” “the model is safe,” or “LLM-as-judge replaces fraud experts.”

## Closing statement

> “This project demonstrates how I build agents for high-consequence workflows: reduce authority, put deterministic boundaries around model behaviour, preserve evidence, evaluate the full trajectory, observe the system in operation, and turn every measured failure into a regression test and safer release decision.”
