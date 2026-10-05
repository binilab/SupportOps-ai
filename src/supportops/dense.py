"""Phase 2 dense policy retrieval over the Phase 1 policy chunks."""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from supportops.lexical import PolicyChunk, PolicyHit

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
EMBEDDING_DIM = 384


def load_embedding_model() -> SentenceTransformer:
    """Load the fixed multilingual model revision on CPU for reproducibility."""
    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu")
    if model.get_embedding_dimension() != EMBEDDING_DIM:
        raise ValueError("Unexpected embedding dimension")
    return model


class DensePolicyIndex:
    def __init__(self, chunks: list[PolicyChunk], model: SentenceTransformer) -> None:
        if not chunks:
            raise ValueError("At least one policy chunk is required")
        self.chunks = chunks
        self.model = model
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
        """Embed one query with the same normalization as documents."""
        vector = np.asarray(
            self.model.encode([query], normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float32,
        )
        if vector.shape != (1, EMBEDDING_DIM) or not np.isfinite(vector).all():
            raise ValueError("Invalid query embedding")
        return vector[0]

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        """Rank distinct policy IDs by their best chunk's cosine similarity."""
        if k < 1:
            raise ValueError("k must be positive")
        if not query.strip():
            return []
        similarities = self.vectors @ self.encode_query(query)
        best: dict[str, PolicyHit] = {}
        for chunk, similarity in zip(self.chunks, similarities, strict=True):
            candidate = PolicyHit(chunk.policy_id, chunk.chunk_id, chunk.source_path, float(similarity))
            previous = best.get(chunk.policy_id)
            if previous is None or candidate.score > previous.score:
                best[chunk.policy_id] = candidate
        return sorted(best.values(), key=lambda hit: (-hit.score, hit.policy_id))[:k]
