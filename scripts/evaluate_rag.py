"""Evaluate Phase 4 policy-only RAG decisions and source citations on fixed Gold."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.dense import DensePolicyIndex, load_embedding_model  # noqa: E402
from supportops.hybrid import HybridPolicyIndex  # noqa: E402
from supportops.lexical import BM25PolicyIndex, load_policy_chunks  # noqa: E402
from supportops.rag import OllamaAnswerModel, PolicyRAG, RETRIEVAL_K  # noqa: E402

GOLD_PATH = ROOT / "data" / "eval" / "gold_dataset.jsonl"
POLICY_DIR = ROOT / "data" / "raw" / "policies"


def main() -> int:
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    chunks = load_policy_chunks(POLICY_DIR, ROOT)
    model = OllamaAnswerModel()
    model_digest = next(item.digest for item in model.client.list().models if item.model == model.model)
    rag = PolicyRAG(HybridPolicyIndex(BM25PolicyIndex(chunks), DensePolicyIndex(chunks, load_embedding_model())), model)
    cases = []
    for row in rows:
        start = perf_counter_ns()
        answer = rag.answer(row["question"])
        cases.append({
            "id": row["id"],
            "category": row["category"],
            "question": row["question"],
            "expected_answer": row["answerable"] and not row["needs_tool"],
            "expected_policy_ids": row["expected_policy_ids"],
            "expected_facts": row["expected_facts"],
            "answer": answer.answer,
            "abstained": answer.abstained,
            "reason": answer.reason,
            "citations": [citation.__dict__ for citation in answer.citations],
            "latency_ms": (perf_counter_ns() - start) / 1_000_000,
        })

    positive = [case for case in cases if case["expected_answer"]]
    negative = [case for case in cases if not case["expected_answer"]]
    answered = [case for case in positive if not case["abstained"]]
    citation_scores = []
    for case in answered:
        cited = {citation["policy_id"] for citation in case["citations"]}
        expected = set(case["expected_policy_ids"])
        citation_scores.append({
            "id": case["id"],
            "precision": len(cited & expected) / len(cited),
            "recall": len(cited & expected) / len(expected),
        })
    latencies = sorted(case["latency_ms"] for case in cases)
    policy_digest = hashlib.sha256()
    for path in sorted(POLICY_DIR.glob("*.md")):
        policy_digest.update(path.name.encode("utf-8"))
        policy_digest.update(b"\0")
        policy_digest.update(path.read_bytes())
        policy_digest.update(b"\0")

    report = {
        "model": model.model,
        "model_digest": model_digest,
        "ollama_python_version": importlib.metadata.version("ollama"),
        "temperature": 0,
        "generation_max_tokens": 180,
        "retrieval_k": RETRIEVAL_K,
        "gold_sha256": hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest(),
        "policy_corpus_sha256": policy_digest.hexdigest(),
        "case_count": len(cases),
        "policy_answer_expected_count": len(positive),
        "abstain_expected_count": len(negative),
        "policy_answer_rate": len(answered) / len(positive),
        "abstention_accuracy": sum(case["abstained"] for case in negative) / len(negative),
        "decision_accuracy": sum(case["abstained"] != case["expected_answer"] for case in cases) / len(cases),
        "citation_policy_precision_on_answered": statistics.mean(item["precision"] for item in citation_scores) if citation_scores else 0,
        "citation_policy_recall_on_answered": statistics.mean(item["recall"] for item in citation_scores) if citation_scores else 0,
        "latency_ms_median": statistics.median(latencies),
        "latency_ms_p95": latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)],
        "cases": cases,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
