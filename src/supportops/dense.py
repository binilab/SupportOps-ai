"""임베딩(dense) 기반 정책 검색.

BM25가 놓치는 바꿔 말한 질문(paraphrase)을 잡기 위해 다국어 문장 임베딩 모델을 쓴다.
청크는 lexical.py와 같은 것을 써서 두 검색 결과를 공정하게 비교하고 결합할 수 있게 한다.
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from supportops.lexical import PolicyChunk, PolicyHit

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# 모델이 업데이트돼도 평가 결과가 바뀌지 않도록 특정 커밋(revision)으로 고정한다.
MODEL_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
EMBEDDING_DIM = 384


def load_embedding_model() -> SentenceTransformer:
    """고정한 버전의 임베딩 모델을 CPU에서 불러온다. 차원이 다르면 오류를 낸다."""
    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu")
    if model.get_embedding_dimension() != EMBEDDING_DIM:
        raise ValueError("Unexpected embedding dimension")
    return model


class DensePolicyIndex:
    """모든 청크를 미리 임베딩해 메모리에 두고 코사인 유사도로 검색한다."""

    def __init__(self, chunks: list[PolicyChunk], model: SentenceTransformer) -> None:
        if not chunks:
            raise ValueError("At least one policy chunk is required")
        self.chunks = chunks
        self.model = model
        # 길이를 1로 정규화해 두면 내적이 곧 코사인 유사도가 된다.
        self.vectors = np.asarray(
            model.encode(
                [chunk.search_text for chunk in chunks],
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )
        if self.vectors.shape != (len(chunks), EMBEDDING_DIM) or not np.isfinite(self.vectors).all():
            raise ValueError("Invalid document embeddings")

    def encode_query(self, query: str) -> np.ndarray:
        """질문 하나를 문서와 같은 방식(정규화)으로 임베딩한다."""
        vector = np.asarray(
            self.model.encode([query], normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float32,
        )
        if vector.shape != (1, EMBEDDING_DIM) or not np.isfinite(vector).all():
            raise ValueError("Invalid query embedding")
        return vector[0]

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        """정책마다 가장 비슷한 청크의 유사도로 순위를 매겨 상위 k개 정책을 돌려준다."""
        if k < 1:
            raise ValueError("k must be positive")
        if not query.strip():
            return []
        # (청크 수, 384) @ (384,) → 청크별 코사인 유사도
        similarities = self.vectors @ self.encode_query(query)
        best: dict[str, PolicyHit] = {}
        for chunk, similarity in zip(self.chunks, similarities, strict=True):
            candidate = PolicyHit(chunk.policy_id, chunk.chunk_id, chunk.source_path, float(similarity))
            previous = best.get(chunk.policy_id)
            if previous is None or candidate.score > previous.score:
                best[chunk.policy_id] = candidate
        return sorted(best.values(), key=lambda hit: (-hit.score, hit.policy_id))[:k]
