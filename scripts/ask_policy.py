"""Ask one policy question with Phase 4 grounded generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.dense import DensePolicyIndex, load_embedding_model  # noqa: E402
from supportops.hybrid import HybridPolicyIndex  # noqa: E402
from supportops.lexical import BM25PolicyIndex, load_policy_chunks  # noqa: E402
from supportops.rag import OllamaAnswerModel, PolicyRAG  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    args = parser.parse_args()
    chunks = load_policy_chunks(ROOT / "data" / "raw" / "policies", ROOT)
    retriever = HybridPolicyIndex(BM25PolicyIndex(chunks), DensePolicyIndex(chunks, load_embedding_model()))
    answer = PolicyRAG(retriever, OllamaAnswerModel()).answer(args.question)
    print(json.dumps({
        "answer": answer.answer,
        "abstained": answer.abstained,
        "reason": answer.reason,
        "citations": [citation.__dict__ for citation in answer.citations],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
