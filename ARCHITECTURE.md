# Aegis Fraud Triage — Architecture

## Purpose

Aegis is an evidence-first Australian banking scam-triage copilot. It gives safe guidance and prepares a reviewable triage draft; it does **not** move money, block accounts, decide liability, or guarantee recovery.

## Core decision flow

```mermaid
flowchart TB
    Customer[Customer report<br/>synthetic or redacted] --> Intake[Input guardrail<br/>PII redaction + injection containment]
    Intake --> Router{Risk router}
    Router -->|Blocked / out of scope| Contain[Safe refusal or bounded guidance]
    Router --> Override{Urgent safety override<br/>Active access · exposed credentials · coercion · pending payment}
    Override -->|High-risk signal| Urgent[Urgent fraud route + mandatory review]
    Override -->|No override| Retrieve[Graph-constrained hybrid retrieval<br/>Pinecone + route-aware reranking]
    Urgent --> Retrieve
    Retrieve --> RetrievalGate{Retrieval quality gate<br/>Required policy sources present?}
    RetrievalGate -->|No| Abstain[Safe abstention + human review]
    RetrievalGate -->|Yes| ToolNeed{Need account-context tool?}
    ToolNeed -->|No| Draft[Evidence-constrained response draft]
    ToolNeed -->|Yes| ToolGate{Tool access gate<br/>Identity · ownership · consent · scope · payload}
    ToolGate -->|Denied| Review[Human fraud specialist]
    ToolGate -->|Allowed| Tools[Authorised mock tools<br/>transaction · payee risk · fraud case]
    Tools --> Draft
    Draft --> GenGate{Generation contract<br/>Length · citations · no sensitive echo}
    GenGate -->|No| Abstain
    GenGate -->|Yes| EvidenceGate{Evidence / abstention gate<br/>Citations must be retrieved}
    EvidenceGate -->|No| Abstain
    EvidenceGate -->|Yes| OutputGate{Output safety gate<br/>No outcome promise · no sensitive-data request}
    OutputGate -->|No| Review
    OutputGate -->|Yes| Contract{Structured response contract<br/>Actions · citations · review flag}
    Contract -->|Invalid| Review
    Contract -->|Valid| Release{Response release policy}
    Release -->|Low risk + high confidence| Send[Send safe guidance]
    Release -->|Any consequential case,<br/>tool use, failure, or uncertainty| Package[Autonomous internal case package<br/>Redacted summary · evidence · gate/tool state]
    Package --> Review
    Review -->|Approve / edit| Send
    Review -->|Escalate / reject| CaseQueue[Fraud operations queue]
```

## Retrieval design

```mermaid
flowchart TB
    Message[Redacted report] --> Route[Deterministic route]
    Route --> Required[Required graph-policy nodes]
    Message --> Embed[Pinecone hosted embedding]
    Embed --> Vector[Pinecone semantic candidates]
    Required --> Select[Route-constrained evidence selection]
    Vector --> Rerank[Deterministic lexical + route rerank]
    Rerank --> Select
    Select --> Check{All required source IDs present?}
    Check -->|Yes| Evidence[Up to five provenance-bearing chunks]
    Check -->|No| FailClosed[Retrieval gate fails closed]
```

The router supplies the required core nodes. Pinecone retrieves semantic candidates, but missing graph-required evidence fails closed, preventing tools and forcing abstention/HITL.

## Telemetry and evaluation flow

```mermaid
flowchart TB
    Agent[Aegis agent] --> JSONL[Redacted local JSONL]
    Agent --> OTLP[OpenTelemetry spans]
    Agent --> LS[LangSmith traces + datasets]
    JSONL --> Alloy[Grafana Alloy]
    OTLP --> Alloy
    Alloy --> Loki[Loki logs]
    Alloy --> Tempo[Tempo traces]
    JSONL --> Exporter[Read-only metrics exporter]
    Exporter --> Prometheus[Prometheus]
    Loki --> Grafana[Grafana Operations Command Centre]
    Tempo --> Grafana
    Prometheus --> Grafana
    Golden[100-case golden set] --> Eval[Code metrics + RAGAS + LLM judges]
    Eval --> LS
```

## Control boundaries

| Boundary | Allowed | Deliberately prohibited |
| --- | --- | --- |
| Input | Redacted report and server-issued customer reference | Credentials, raw PII, system-prompt disclosure |
| Retrieval | Approved policy/public-safety chunks with provenance | Treating public content as bank policy |
| Tools | Narrow mock read/enrichment tools after authorisation | Payment movement, account changes, cross-customer lookup |
| Generation | Draft from redacted approved evidence | Invented policy, refund guarantee, sensitive-data collection |
| Release | Narrow low-risk guidance may auto-send; internal case package can be prepared | Autonomous consequential banking guidance |

## Implementation map

| Component | Implementation |
| --- | --- |
| Router, gates, trajectory | `src/aegis_fraud_triage/agent.py` |
| Tool boundary | `tool_authorisation.py` |
| HITL release policy | `hitl.py` |
| Pinecone retrieval | `pinecone_policy.py` |
| Nebius drafting | `nebius_generation.py` |
| Evaluation and judge pack | `evaluation.py`, `run_provider_evals.py`, `run_automated_judge_validation.py` |
| Telemetry and alerts | `observability.py`, `monitoring.py`, `metrics_exporter.py` |
| Local operations stack | `docker-compose.observability.yml`, `observability/` |

## Deployment posture

The Docker stack is production-shaped, not production-hosted. A real deployment still needs private networking, TLS/mTLS, managed persistence/backups, SSO/RBAC, real identity/entitlements, key rotation, retention controls, approved policy governance, security review and compliance approval.
