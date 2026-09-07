# Data sources and governance

## Core version 1 dataset

The committed `golden_dataset_v1.jsonl` is a synthetic 100-case evaluation set. It is safe to commit because no record contains customer data, transaction IDs, real names, contact details, credentials, or account numbers.

Its scenario taxonomy is informed by the Australian Competition and Consumer Commission National Anti-Scam Centre’s public Scamwatch reporting material: https://www.scamwatch.gov.au/research-and-resources/scam-statistics

This source is used for category coverage only. It is not a knowledge source for making account decisions, and it must be periodically reviewed because scam taxonomies and public reports change.

## Public safety retrieval corpus

`build_public_safety_corpus.py` generates `public_safety_corpus_v1.jsonl`: 60 short, paraphrased chunks across 15 public Australian consumer-safety pages from Scamwatch, the Australian Cyber Security Centre, Commonwealth Bank, and Westpac. Every chunk records its publisher, source URL, trust tier, AU jurisdiction, review date, and a clear `not_bank_policy` marker.

This is an interview-quality demonstration corpus, not a substitute for an approved policy corpus. The generator makes source review and replacement straightforward; do not ingest whole public webpages or treat bank-specific guidance as universal rules.

## Controlled expansion plan

1. Add approved, versioned bank policy and customer-safety documents to the RAG corpus, retaining source owner, effective date, jurisdiction, document version, and retention metadata.
2. Use a public scam-conversation source such as a Hugging Face corpus only after checking its licence, provenance, regional relevance, and safety risks. Do not use it as the golden-answer source.
3. Add de-identified and manually adjudicated internal cases only through the bank's governed data process. Split by incident/time period to prevent template leakage between train, development, and held-out evaluation data.
4. Feed reviewed production failures back as new, versioned test cases. Never alter an existing evaluation version when comparing baseline and post-improvement results.

## Dataset quality gates

- Every case has explicit expected route, risk tier, escalation decision, allowed tools, evidence topics, prohibited claims, and expected gate behaviour.
- Scenario distribution: 50% representative happy path, 30% edge case, 15% known failure hypothesis, and 5% adversarial. This matches the course framework exactly.
- A human reviewer must check all urgent, known-failure, and adversarial cases, and calibrate the LLM judge on at least 15 cases before its results are used for release decisions.
