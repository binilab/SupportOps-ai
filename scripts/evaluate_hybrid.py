"""BM25 + 임베딩 검색의 RRF(Reciprocal Rank Fusion) 결합 성능을 Gold 데이터로 평가한다.
실행: python3 scripts/evaluate_hybrid.py > reports/phase3_hybrid_rrf.json"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.dense import MODEL_ID, MODEL_REVISION, DensePolicyIndex, load_embedding_model  # noqa: E402
from supportops.hybrid import RRF_RANK_CONSTANT, HybridPolicyIndex  # noqa: E402
from supportops.lexical import BM25PolicyIndex, load_policy_chunks  # noqa: E402
from supportops.retrieval_eval import evaluate  # noqa: E402

GOLD_PATH = ROOT / "data" / "eval" / "gold_dataset.jsonl"
POLICY_DIR = ROOT / "data" / "raw" / "policies"


def main() -> int:
    """하이브리드 인덱스로 Gold 질문을 검색해 지표와 RRF 설정, 재현용 메타데이터를 출력한다."""
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    chunks = load_policy_chunks(POLICY_DIR, ROOT)
    index = HybridPolicyIndex(BM25PolicyIndex(chunks), DensePolicyIndex(chunks, load_embedding_model()))
    result = evaluate(rows, index)
    digest = hashlib.sha256()
    for path in sorted(POLICY_DIR.glob("*.md")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    result.update({
        "method": "policy-level BM25 + dense RRF",
        "rrf_rank_constant": RRF_RANK_CONSTANT,
        "candidate_count_per_retriever": index.candidate_count,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "gold_sha256": hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest(),
        "policy_corpus_sha256": digest.hexdigest(),
        "python_version": sys.version.split()[0],
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
