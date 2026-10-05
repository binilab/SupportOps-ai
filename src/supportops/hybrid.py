"""Phase 3 policy-level reciprocal rank fusion of lexical and dense search."""

from __future__ import annotations

from supportops.dense import DensePolicyIndex
from supportops.lexical import BM25PolicyIndex, PolicyChunk, PolicyHit

RRF_RANK_CONSTANT = 60


def fuse_policy_hits(
    ranked_lists: list[list[PolicyHit]], k: int, rank_constant: int = RRF_RANK_CONSTANT
) -> list[PolicyHit]:
    """Fuse policy ranks while retaining the highest-ranked source chunk per policy."""
    if k < 1 or rank_constant < 1:
        raise ValueError("k and rank_constant must be positive")
    scores: dict[str, float] = {}
    sources: dict[str, tuple[int, int, PolicyHit]] = {}
    for source_number, hits in enumerate(ranked_lists):
        for rank, hit in enumerate(hits, start=1):
            scores[hit.policy_id] = scores.get(hit.policy_id, 0.0) + 1 / (rank_constant + rank)
            candidate = (rank, source_number, hit)
            previous = sources.get(hit.policy_id)
            if previous is None or candidate[:2] < previous[:2]:
                sources[hit.policy_id] = candidate
    policy_ids = sorted(scores, key=lambda policy_id: (-scores[policy_id], policy_id))[:k]
    return [
        PolicyHit(policy_id, sources[policy_id][2].chunk_id, sources[policy_id][2].source_path, scores[policy_id])
        for policy_id in policy_ids
    ]


class HybridPolicyIndex:
    def __init__(self, lexical: BM25PolicyIndex, dense: DensePolicyIndex) -> None:
        if lexical.chunks != dense.chunks:
            raise ValueError("Lexical and dense indexes must use the same policy chunks")
        self.lexical = lexical
        self.dense = dense
        self.chunks: list[PolicyChunk] = lexical.chunks
        self.candidate_count = len({chunk.policy_id for chunk in self.chunks})

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        """Search both indexes and fuse their distinct policy rankings."""
        if k < 1:
            raise ValueError("k must be positive")
        if not query.strip():
            return []
        return fuse_policy_hits(
            [
                self.lexical.search(query, self.candidate_count),
                self.dense.search(query, self.candidate_count),
            ],
            k,
        )
