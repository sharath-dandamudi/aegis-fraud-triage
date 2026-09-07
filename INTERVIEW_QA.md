# Aegis Fraud Triage — Interview Q&A

Use this as a rehearsal reference, not a script to memorise word-for-word. Lead with the risk boundary, explain the control flow, then be precise about what is implemented and what remains a production next step.

## The one-sentence evaluation primer

> I measure route correctness, critical-escalation recall, evidence and citation quality, authorised tool-trajectory conformance, guardrail/release compliance, latency and cost on a frozen 100-case Australian scam-triage golden dataset, using code checks plus RAGAS and two LLM-judge rubrics; consequential financial and account-security cases remain human-reviewed because the live profile is below the critical-safety promotion bar.

## Fast opening answers

### 1. What did you build?

**Answer:** I built Aegis Fraud Triage, an evidence-first copilot for Australian banking scam reports. It accepts only synthetic or redacted reports, routes the risk, retrieves provenance-bearing safety guidance, performs narrowly authorised mock enrichment when appropriate, creates a cited draft and holds consequential responses for human review.

### 2. What problem are you solving?

**Answer:** Scam victims need clear next steps at a stressful time, while bank operations need a consistent, auditable triage record. A generic chatbot can sound reassuring but can still miss urgency, invent advice or access data too broadly; Aegis is designed to make the safe path explicit and observable.

### 3. Why is this an agent rather than a RAG chatbot?

**Answer:** It has a constrained decision trajectory, not just retrieve-and-answer: deterministic routing, required evidence, an optional and separately authorised tool step, generation controls, evidence/output gates and a release decision. The model cannot decide that a tool is allowed or that a response is ready to send.

### 4. What can the agent do, and what can it not do?

**Answer:** It can prepare guidance and a reviewable case package from approved context. It cannot move money, stop payments, block cards, change accounts, decide liability, guarantee recovery or contact a real customer; the current banking tools are deliberately mocked.

### 5. What makes the project relevant to Australian banking?

**Answer:** The corpus uses provenance-rich, paraphrased customer-safety material from Australian public sources, and the scenarios cover payment scams, PayID/new-payee risk, card-security incidents, credential compromise, remote-access scams and fraud escalation. Public safety information is labelled as context, never falsely represented as a bank’s approved policy.

## Architecture and RAG

### 6. Walk me through the architecture.

**Answer:** The input guardrail redacts sensitive information and contains prompt-injection attempts. A deterministic router assigns a risk route and required policy topics. Pinecone retrieves semantic candidates, then a graph-coverage check requires route-critical evidence before tools or generation. After an evidence-constrained draft, generation, citation/evidence and output-safety gates run before a human-review release policy decides the outcome.

### 7. What do you mean by graph RAG here?

**Answer:** I use vector search for language similarity, while a lightweight graph/requirement layer defines mandatory evidence nodes per route. For example, an urgent fraud response must cover official contact, urgent review and no guarantee of recovery; a highly similar but incomplete retrieval set fails closed rather than letting the model improvise.

### 8. Why not rely on vector similarity alone?

**Answer:** Similarity tells me what is relevant, not what is sufficient for a safe operational response. Mandatory coverage makes the safety-critical content deterministic and auditable, at the cost of more abstentions when the corpus is incomplete—which is the correct failure mode for this use case.

### 9. What is the retrieval-quality gate?

**Answer:** It checks that the route’s required source IDs/topics are present in retrieved evidence and that the retrieval meets a coverage threshold. A failure means no tools, a bounded abstention and reviewer handoff; it is deliberately upstream of account-context access.

### 10. How do citations work?

**Answer:** Each retrieved chunk carries a stable chunk ID, policy/source ID, provenance metadata and public-source URL. The response references the chunk IDs, and the evaluator checks citation accuracy against the evidence retrieved in that same trace plus citation recall against the gold-required evidence.

### 11. What is the difference between an evidence gate and an abstention gate?

**Answer:** The evidence gate asks, “Are the response’s cited claims supported by the retrieved context?” The abstention gate asks, “If support is missing or evidence is insufficient, did the system refuse to make a substantive unsupported claim and hand off safely?” One checks positive grounding; the other checks fail-closed behaviour.

### 12. How did you prevent hallucinations?

**Answer:** I do not say hallucinations are eliminated. I reduce the failure surface by constraining the draft to redacted approved evidence, requiring citation provenance, blocking unsupported outputs, measuring semantic RAG quality and keeping human review for consequential guidance. Claim-level semantic entailment and human policy approval are still future hardening work.

## Models, tools and security

### 13. Which models and infrastructure did you use?

**Answer:** Pinecone is the vector store in an isolated `policy-v1` namespace. Nebius Qwen3 is the evidence-constrained drafter, and Nebius Llama 3.3 70B is used for two offline judge rubrics. LangSmith supports LLM trace/experiment comparison, while OpenTelemetry, Alloy, Prometheus, Loki, Tempo and Grafana provide operational telemetry.

### 14. Why use a different judge model family?

**Answer:** It reduces the chance that a model judges its own stylistic preferences. It does not guarantee independence because the current judge and drafter share a provider, so I record that limitation and do not use the judge as a release authority.

### 15. How are tool calls protected?

**Answer:** The tool gateway is deny-by-default and checks server-asserted identity, ownership of the customer reference, valid consent, least-privilege scope, allowed risk route and payload schema. The LLM supplies intent but cannot choose another customer, grant a scope or bypass the policy layer.

### 16. Why retrieve before tool use?

**Answer:** It enforces data minimisation. Many reports can receive safe public guidance without account context; if required evidence is missing, it is safer to abstain than query even a mock account tool.

### 17. What would change with real banking tools?

**Answer:** The mock gateway would call bank-owned entitlement and consent services, use short-lived service identity, apply row-/attribute-level access control, enforce idempotency and rate limits, and send tamper-evident audit events. High-risk actions would use two-person approval or established fraud-operations workflows—not an LLM decision.

### 18. How do you defend against prompt injection?

**Answer:** Untrusted customer text is classified and redacted before it reaches normal workflow. It cannot change system policies, tool scopes or release policy. Injection-like input is contained, logged as a security signal and either refused or routed for human review.

### 19. What is the generation-contract gate?

**Answer:** It validates that a draft follows the expected response contract before it is treated as a candidate response: bounded structure and length, citations present when required, no sensitive echo and no attempt to turn instructions into operational authority. It is a format/contract check, not a replacement for the downstream evidence or safety evaluation.

### 20. Why is HITL still necessary after so many gates?

**Answer:** Gates can be strong controls yet still miss nuanced financial, legal or customer-vulnerability context. Human review is the compensating control for a high-consequence beta. It also creates the labelled data needed to calibrate later risk-based automation.

## Evaluation and quality

### 21. Describe the golden dataset.

**Answer:** It is frozen version `v1.3.0` with 100 de-identified/synthetic cases: 50 representative, 30 edge, 15 known failure and 5 adversarial cases. Each case contains expected route, risk, escalation, required evidence and chunk IDs, citations, authorised tool plan, gate outcomes, release mode, prohibited claims and trajectory constraints.

### 22. Why is a final-answer-only dataset insufficient?

**Answer:** A polished answer could have been produced after an unauthorised lookup, skipped evidence, incorrect tool order or an unsafe release. In agentic systems, how it arrived at the answer matters, so the dataset checks the path as well as the prose.

### 23. What metrics matter most?

**Answer:** Critical-escalation recall is the safety metric I would protect first: missing an active remote-access or credential-compromise case is worse than a false review. I combine it with route macro-F1, evidence coverage, citation accuracy/recall, tool-authorisation compliance, gate/trajectory conformance, guardrail compliance, p95 latency and cost per run.

### 24. What is your current evaluation one-liner?

**Answer:** “I measure route correctness, critical escalation, grounding/citations, tool trajectory and release safety on 100 frozen synthetic Australian scam cases, using deterministic contracts plus RAGAS and two LLM judge rubrics; the pass bar is 100% critical escalation recall, at least 98% citation accuracy, zero unauthorised tools and zero reviewed critical-safety failures.”

### 25. What did the live 100-case run show?

**Answer:** The post-fix live profile reached route macro-F1 0.974, citation accuracy 1.000, evidence coverage 0.983, critical-escalation recall 0.929, guardrail compliance 0.980 and p95 latency 12.34 seconds at an estimated A$0.0035 per run. It is not a production accuracy claim and it does not meet my critical escalation or zero-critical-failure promotion bar, so human review remains mandatory for consequential financial and account-security cases.

### 26. Tell me about a failure you found and fixed.

**Answer:** A full live run flagged correct language such as “never provide full card details” as unsafe because the output rule matched literal sensitive-data terms. I retained the evidence, narrowed the rule to distinguish prohibitions from requests, added regression tests, and then discovered an ordering defect: mandatory urgent-review wording was appended after the gate. I moved it before generation/evidence/output checks, verified the targeted regression and preserved the remaining full-suite misses for analysis.

### 27. What does RAGAS add?

**Answer:** Code-based tests can precisely check chunk IDs and required coverage, but they cannot fully judge semantic faithfulness or relevance. RAGAS adds faithfulness, answer relevancy, context precision and context recall; it is diagnostic signal, not a policy or safety certification.

### 28. How do you use LLM-as-judge responsibly?

**Answer:** I run two fixed rubrics: evidence-strict and safety-red-team, then record score disagreement alongside deterministic contracts. The current full pre-fix automated pack executed 87 cases and produced high rubric scores but only 0.816 deterministic-contract pass rate; that demonstrates why I would never allow flattering judge scores to overrule concrete control failures.

### 29. You do not have human reviewers. What do you do?

**Answer:** I am explicit: I have automated judge validation, not human calibration. For the MVP I keep human review for every consequential case, collect a stratified reviewer worksheet and define a future calibration bar of at least 15 independent labels with at least 0.80 agreement before considering a judge-informed change to release policy.

### 30. How would you prevent the golden set from becoming overfit?

**Answer:** I would maintain train/dev/test separation for prompts and controls, preserve an immutable holdout that the team cannot inspect during tuning, add governed de-identified operational cases over time, rotate adversarial suites and compare current runs to a fixed historical baseline. I would version both corpus and dataset so a score always has a reproducible context.

## Monitoring, observability and operations

### 31. What is the role of OpenTelemetry, Grafana and LangSmith?

**Answer:** OpenTelemetry is the vendor-neutral instrumentation standard that emits spans, metrics and logs. Alloy receives the telemetry; Tempo stores traces, Loki stores redacted logs and Prometheus stores numeric metrics; Grafana is the operations dashboard over those stores. LangSmith is complementary: it gives LLM-specific trace, prompt and experiment comparison tied to the golden dataset.

### 32. What can an operator see in the dashboard?

**Answer:** They can see request/risk mix, p50/p95 latency, cost, gate failures, abstentions, tool authorisation denials, review load and alerts. A trace ID connects a redacted log event to the full trajectory, including selected evidence, attempted tool action, gate results and release decision.

### 33. Which alerts would you page on?

**Answer:** Any unauthorised successful tool action, sensitive-data output or urgent case auto-release is critical. I would alert on rising gate failures, sudden abstention changes, critical-escalation misses found by online review, p95 latency breaches, unusual token/cost growth, retrieval coverage drops and data-governance errors; operational thresholds are in `MONITORING_AND_EVALUATION.md`.

### 34. How do you avoid leaking PII into observability systems?

**Answer:** Inputs are redacted before normal processing, trace metadata uses case IDs rather than raw identities, logs are redacted JSONL and the design prohibits credentials and full account data in prompts/traces. In production I would add data classification, field-level allowlists, tokenisation, retention limits, private endpoints and periodic access reviews.

### 35. What does “production-shaped” mean rather than “production-ready”?

**Answer:** The control planes are realistic—least privilege, evidence gates, HITL, offline evaluation, alerting and traces—but the app still uses mock banking tools, public safety content and a local Docker stack. Production readiness requires approved policy governance, real identity and consent services, security/compliance review, private deployment, managed retention and calibrated operational data.

## Senior-system-design follow-ups

### 36. How would you reduce latency without weakening safety?

**Answer:** First measure trace-level contributors. Then cache approved retrieval for repeated public-information questions, use a smaller routing model or deterministic classifier, parallelise independent safe checks, only call the large drafter after retrieval clears, and enforce timeouts/fallback abstention. I would not remove required evidence or authorisation gates to improve p95.

### 37. How would you control cost?

**Answer:** I would log tokens, model calls and retrieval/tool count per trace; set per-route budgets; use the larger judge offline rather than in the live release path; cache embeddings and stable retrieval; and sample semantic evaluation at a stratified rate. Cost controls must be evaluated alongside escalation recall and evidence quality so they do not create a hidden safety regression.

### 38. How would you detect drift?

**Answer:** Monitor route distribution, confidence, retrieval coverage/similarity, refusal/abstention rate, tool-denial rate, citation patterns, latency/cost and human reviewer overrides over time. I would compare each to versioned baseline windows and trigger re-evaluation when corpus, prompt, model, traffic mix or operating policy changes.

### 39. How would you manage knowledge-base updates?

**Answer:** Treat source and chunk changes like a governed release: source approval, provenance and review date, corpus version, staged index namespace, retrieval regression against the frozen set, sampled domain review, then promotion with rollback. A response should log the corpus/index version used so incidents are reproducible.

### 40. How would you decide whether to allow some auto-send?

**Answer:** I would define a narrow, non-consequential class such as general scam-prevention guidance; validate it on independent, calibrated data; set route-specific error budgets; shadow-test the policy; measure reviewer edit and override rates; and retain a kill switch. No auto-send expansion is justified by generic average accuracy alone.

### 40a. How did you make the agent more autonomous without making it less safe?

**Answer:** I increased workflow autonomy, not banking authority. A high-recall override now forces active remote access, exposed credentials, coercion or an in-progress payment into urgent review; the server creates an evidence-backed response contract and a complete internal case package. The model still cannot move money, change an account or release consequential guidance. In the local frozen run, critical-escalation recall reached 1.000, while escalation precision fell to 0.731—an explicit, review-first trade-off I would validate with governed reviewer data before changing thresholds.

### 41. What are the key trade-offs in your design?

**Answer:** It trades autonomy and lowest latency for auditability, data minimisation and a controlled failure mode. It uses two observability layers because Grafana is operationally strong and LangSmith is LLM-evaluation strong. It uses synthetic data for privacy/repeatability, while clearly acknowledging that governed real-world holdout data is still required.

### 42. If you had one more week, what would you do?

**Answer:** I would triage every residual full-suite failure by severity, add those cases as regression tests, finish a stratified post-fix RAGAS/judge report, have domain reviewers label the calibration sheet, add a separate-provider judge comparison, and define corpus/version deployment controls. I would not add a new feature before closing the critical-escalation gap.

## Behavioural / project-delivery questions

### 43. How did you make decisions under ambiguity?

**Answer:** I chose a narrow use case and explicit non-goals first. When a trade-off was uncertain, I documented the decision, chose the safer default, instrumented it and made it testable; the decision log makes it possible to explain why a constraint exists rather than presenting it as magic.

### 44. How do you respond when metrics look good but a control fails?

**Answer:** I treat the control failure as real. The 0.816 deterministic-contract rate alongside high judge scores is a good example: I would investigate the mismatch, preserve the run, add a regression and block promotion instead of averaging it away.

### 45. What would you tell a product stakeholder asking for full automation now?

**Answer:** I would show the risk-adjusted case: the current system is useful as a review-first copilot, but critical escalation recall is below the stated bar and the dataset is synthetic. I would propose a measured path—shadow mode, reviewer labels, calibration, narrowly scoped low-risk auto-send experimentation—and explain the evidence required at each step.

## Strong questions to ask the interviewer

1. “How do you currently separate model quality evaluation from control-path evaluation for agentic workflows?”
2. “Which decisions in this workflow are permitted to be automated, and who owns the release criteria?”
3. “How is approved knowledge versioned and rolled back when policy changes?”
4. “What is the organisation’s standard for trace redaction, retention and access to LLM telemetry?”
5. “How do fraud or operations reviewers feed their overrides back into evaluation without leaking sensitive customer data?”

## Rehearsal checklist

- Explain the 30-second version without using unexplained acronyms.
- Draw the flow: guardrail → route → retrieve → tool gate → draft → evidence/safety gates → HITL.
- Quote at least one real failure and the regression loop, not only high metrics.
- Say “synthetic golden set” and “production-shaped, not production-ready” unprompted.
- Never disclose API keys, local dashboard credentials or real customer data.
