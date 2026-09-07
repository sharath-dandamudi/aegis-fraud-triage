"""Run RAGAS metrics on a persisted Aegis case-results file using Nebius."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env", override=False)


def select_stratified_rows(rows: list[dict], total: int) -> list[dict]:
    """Choose a deterministic sample using the frozen golden-set mix.

    The preferred distribution is representative 50%, edge 30%, known
    failure 15%, adversarial 5%.  Largest-remainder allocation keeps the
    requested total exact (for 30 cases: 15 / 9 / 4 / 2).
    """
    if total <= 0 or total > len(rows):
        raise ValueError(f"--stratified must be between 1 and {len(rows)}")
    groups = ("representative", "edge_case", "known_failure", "adversarial")
    shares = {"representative": 0.50, "edge_case": 0.30, "known_failure": 0.15, "adversarial": 0.05}
    buckets = {group: sorted((row for row in rows if row.get("scenario_group") == group), key=lambda row: row["case_id"]) for group in groups}
    raw = {group: total * shares[group] for group in groups}
    quotas = {group: min(len(buckets[group]), int(raw[group])) for group in groups}
    remaining = total - sum(quotas.values())
    tie_priority = {"adversarial": 4, "known_failure": 3, "edge_case": 2, "representative": 1}
    for group in sorted(groups, key=lambda item: (raw[item] - int(raw[item]), tie_priority[item]), reverse=True):
        if remaining <= 0:
            break
        if quotas[group] < len(buckets[group]):
            quotas[group] += 1
            remaining -= 1
    if remaining:
        for group in groups:
            capacity = len(buckets[group]) - quotas[group]
            take = min(capacity, remaining)
            quotas[group] += take
            remaining -= take
            if not remaining:
                break
    return [row for group in groups for row in buckets[group][:quotas[group]]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAGAS faithfulness, relevance and context metrics on an Aegis eval result.")
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", default="reports/ragas_eval.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--stratified", type=int, default=None, help="Deterministic scenario-stratified sample (for example, 30).")
    args = parser.parse_args()
    if args.limit and args.stratified:
        parser.error("Use either --limit or --stratified, not both.")

    from datasets import Dataset
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

    api_key = os.environ["NEBIUS_API_KEY"]
    base_url = os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1")
    judge_model = os.getenv("NEBIUS_JUDGE_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
    embedding_model = os.getenv("NEBIUS_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B")
    rows = [json.loads(line) for line in Path(args.results).read_text(encoding="utf-8").splitlines() if line.strip()]
    selection = "full_persisted_results"
    if args.stratified:
        rows = select_stratified_rows(rows, args.stratified)
        selection = f"stratified_{args.stratified}"
    elif args.limit:
        rows = rows[:args.limit]
        selection = f"first_{args.limit}_persisted_rows"
    records = [{
        "user_input": row["redacted_input"],
        "response": row["response"],
        "retrieved_contexts": [item["text"] for item in row["evidence"]],
        "reference": "; ".join(row["required_evidence_topics"]) if "required_evidence_topics" in row else row["expected_route"],
    } for row in rows]
    # The code-based suite remains the authority for strict tool/gate contracts;
    # RAGAS adds semantic RAG-quality signals for offline analysis.
    llm = LangchainLLMWrapper(ChatOpenAI(model=judge_model, api_key=api_key, base_url=base_url, temperature=0))
    # Nebius accepts normal text input but not LangChain's optional token-array
    # embedding format, so keep client-side tokenisation disabled.
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=embedding_model, api_key=api_key, base_url=base_url, check_embedding_ctx_length=False))
    result = evaluate(
        Dataset.from_list(records),
        metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()],
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        show_progress=True,
    )
    scores = result.to_pandas().mean(numeric_only=True).to_dict()
    available_scores = {
        key: round(float(value), 3)
        for key, value in scores.items()
        if value is not None and math.isfinite(float(value))
    }
    unavailable_metrics = sorted(set(scores) - set(available_scores))
    report = {
        "case_count": len(records),
        "llm_model": judge_model,
        "embedding_model": embedding_model,
        "metrics": available_scores,
        "unavailable_metrics": unavailable_metrics,
        "notes": (
            "Answer relevancy requires multiple LLM generations. If the provider returns a single generation, "
            "it is deliberately reported as unavailable rather than treated as a score of zero."
            if "answer_relevancy" in unavailable_metrics else None
        ),
        "source_results": str(args.results),
        "selection": selection,
        "scenario_mix": {group: sum(row.get("scenario_group") == group for row in rows) for group in ("representative", "edge_case", "known_failure", "adversarial")},
        "status": "active",
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
