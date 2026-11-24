"""BM25와 임베딩 검색 결과를 RRF(Reciprocal Rank Fusion)로 합친다.

두 검색의 점수는 범위가 달라 직접 더할 수 없으므로 순위만 쓴다.
정책마다 1 / (60 + 순위)를 검색 방식별로 더해 최종 순위를 정한다.
서비스의 정책 검색은 평가셋에서 가장 결과가 좋았던 이 방식을 쓴다.
"""

from __future__ import annotations

from supportops.dense import DensePolicyIndex
from supportops.lexical import BM25PolicyIndex, PolicyChunk, PolicyHit

# RRF 논문에서 쓰는 기본값. 클수록 상위권과 하위권의 점수 차이가 줄어든다.
RRF_RANK_CONSTANT = 60


def fuse_policy_hits(
    ranked_lists: list[list[PolicyHit]], k: int, rank_constant: int = RRF_RANK_CONSTANT
) -> list[PolicyHit]:
    """여러 검색 결과 목록을 RRF 점수로 합쳐 상위 k개 정책을 돌려준다.

    인용에 쓸 대표 청크는 그 정책이 가장 높은 순위로 나온 목록의 청크로 정한다.
    순위가 같으면 앞쪽 목록(BM25)의 청크를 쓴다.
    """
    if k < 1 or rank_constant < 1:
        raise ValueError("k and rank_constant must be positive")
    scores: dict[str, float] = {}
    sources: dict[str, tuple[int, int, PolicyHit]] = {}
    for source_number, hits in enumerate(ranked_lists):
        for rank, hit in enumerate(hits, start=1):
            scores[hit.policy_id] = scores.get(hit.policy_id, 0.0) + 1 / (rank_constant + rank)
            # (순위, 목록 번호)가 더 작은 쪽을 대표 청크로 남긴다.
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
    """BM25 인덱스와 임베딩 인덱스를 함께 검색해 RRF로 결합한다."""

    def __init__(self, lexical: BM25PolicyIndex, dense: DensePolicyIndex) -> None:
        if lexical.chunks != dense.chunks:
            raise ValueError("Lexical and dense indexes must use the same policy chunks")
        self.lexical = lexical
        self.dense = dense
        self.chunks: list[PolicyChunk] = lexical.chunks
        # 결합 전에 각 검색에서 모든 정책의 순위를 받아야 한쪽에만 나온 정책도 점수를 받는다.
        self.candidate_count = len({chunk.policy_id for chunk in self.chunks})

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        """두 검색을 실행하고 RRF로 합친 상위 k개 정책을 돌려준다."""
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
