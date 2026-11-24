"""API 서버 없이 고객 문의 하나를 에이전트로 처리해 JSON으로 출력한다.
실행: python3 scripts/ask_support.py "ORD-1008 취소 가능해?" [--as-of 2026-10-05]"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.agent import OllamaOrderRouter, SupportAgent  # noqa: E402
from supportops.lexical import load_policy_chunks  # noqa: E402
from supportops.rag import ORDER_ID_RE, OllamaAnswerModel, PolicyRAG  # noqa: E402
from supportops.structured import StructuredStore  # noqa: E402


def main() -> int:
    """주문 ID 유무에 따라 RAG 또는 주문 도구 경로로 문의를 처리하고 답변과 추적 정보를 출력한다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--as-of", type=date.fromisoformat, help="Evaluation date YYYY-MM-DD")
    args = parser.parse_args()
    chunks = load_policy_chunks(ROOT / "data/raw/policies", ROOT)
    # 주문 ID가 있는 질문은 RAG를 쓰지 않으므로, 정책 질문일 때만 무거운 임베딩 모델을 불러온다.
    rag = None
    if ORDER_ID_RE.search(args.question) is None:
        from supportops.dense import DensePolicyIndex, load_embedding_model
        from supportops.hybrid import HybridPolicyIndex
        from supportops.lexical import BM25PolicyIndex

        rag = PolicyRAG(
            HybridPolicyIndex(BM25PolicyIndex(chunks), DensePolicyIndex(chunks, load_embedding_model())),
            OllamaAnswerModel(),
        )
    store = StructuredStore(ROOT / "data/raw/structured/orders.csv", ROOT / "data/raw/structured/products.csv")
    result = SupportAgent(store, OllamaOrderRouter(), chunks, rag).run(args.question, args.as_of)
    print(json.dumps({
        "answer": result.answer,
        "abstained": result.abstained,
        "outcome": result.outcome,
        "router_request": result.router_request.__dict__ if result.router_request else None,
        "trace": [item.__dict__ for item in result.trace],
        "citations": [item.__dict__ for item in result.citations],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
