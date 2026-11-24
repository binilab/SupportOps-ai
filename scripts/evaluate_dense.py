"""임베딩 정책 검색을 Gold 데이터로 평가한다(로컬 또는 PostgreSQL pgvector).
실행: python3 scripts/evaluate_dense.py [--backend local|pgvector] > reports/phase2_dense_local.json
pgvector 백엔드는 환경변수 SUPPORTOPS_DATABASE_URL이 필요하다."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.dense import (  # noqa: E402
    EMBEDDING_DIM,
    MODEL_ID,
    MODEL_REVISION,
    DensePolicyIndex,
    load_embedding_model,
)
from supportops.lexical import load_policy_chunks  # noqa: E402
from supportops.retrieval_eval import evaluate  # noqa: E402
from supportops.vector_store import PgVectorPolicyIndex, PgVectorPolicyStore  # noqa: E402

GOLD_PATH = ROOT / "data" / "eval" / "gold_dataset.jsonl"
POLICY_DIR = ROOT / "data" / "raw" / "policies"


def corpus_hash() -> str:
    """정책 문서 이름과 내용으로 코퍼스 SHA-256 지문을 만든다(기준선과 동일한 방식)."""
    digest = hashlib.sha256()
    for path in sorted(POLICY_DIR.glob("*.md")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    """선택한 백엔드로 임베딩 검색을 평가하고 지표와 모델/환경 메타데이터를 출력한다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("local", "pgvector"), default="local")
    args = parser.parse_args()
    dsn = os.environ.get("SUPPORTOPS_DATABASE_URL")
    if args.backend == "pgvector" and not dsn:
        parser.error("SUPPORTOPS_DATABASE_URL is required for pgvector backend")
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    model = load_embedding_model()
    dense_index = DensePolicyIndex(load_policy_chunks(POLICY_DIR, ROOT), model)

    database_info: dict = {}
    if args.backend == "local":
        result = evaluate(rows, dense_index)
    else:
        assert dsn is not None
        with psycopg.connect(dsn, connect_timeout=5) as connection:
            store = PgVectorPolicyStore(connection)
            store.setup()
            store.replace(dense_index.chunks, dense_index.vectors, MODEL_REVISION)
            # DB에 저장된 벡터 수가 청크 수와 다르면 평가 결과를 신뢰할 수 없으므로 중단한다.
            if store.count(MODEL_REVISION) != len(dense_index.chunks):
                raise RuntimeError("Stored vector count does not match policy chunks")
            result = evaluate(rows, PgVectorPolicyIndex(dense_index, store, MODEL_REVISION))
            database_info = {
                "stored_vector_count": store.count(MODEL_REVISION),
                "pgvector_extension_version": connection.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                ).fetchone()[0],
            }

    result.update(
        {
            "backend": args.backend,
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "embedding_dimension": EMBEDDING_DIM,
            "normalized_embeddings": True,
            "distance": "cosine",
            "gold_sha256": hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest(),
            "policy_corpus_sha256": corpus_hash(),
            "python_version": sys.version.split()[0],
            "sentence_transformers_version": importlib.metadata.version("sentence-transformers"),
            "transformers_version": importlib.metadata.version("transformers"),
            "torch_version": importlib.metadata.version("torch"),
            "pgvector_python_version": importlib.metadata.version("pgvector"),
            "psycopg_version": importlib.metadata.version("psycopg"),
            "numpy_version": importlib.metadata.version("numpy"),
            **database_info,
        }
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
