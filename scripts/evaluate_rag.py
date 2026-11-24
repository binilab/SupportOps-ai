"""정책 RAG의 답변/보류 판단과 출처 인용을 Gold 데이터로 평가한다.
실행: python3 scripts/evaluate_rag.py > reports/phase4_rag_local.json (로컬 Ollama 필요)"""

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
    """Gold 전체 문항에 RAG를 실행하고 답변율, 보류 정확도, 인용 정밀도/재현율을 담은 보고서를 출력한다."""
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
            # 주문 도구가 필요한 문항은 정책 RAG가 답하면 안 되므로 보류가 정답이다.
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
    # 인용 지표는 답변이 기대되고 실제로 답한 문항에서만 계산한다.
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
        # 보류 여부가 기대와 반대인 경우를 정답으로 센다(답해야 하면 보류 아님, 답하면 안 되면 보류).
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
