"""BM25 + 임베딩 검색의 RRF 결합(fuse_policy_hits)과 HybridPolicyIndex의 입력 검증을 테스트한다."""

from __future__ import annotations

import pytest

from supportops.hybrid import HybridPolicyIndex, fuse_policy_hits
from supportops.lexical import PolicyChunk, PolicyHit


def hit(policy: str, chunk: str) -> PolicyHit:
    """테스트용 검색 결과(PolicyHit)를 간단히 만든다."""
    return PolicyHit(policy, chunk, f"{policy}.md", 1.0)


def test_rrf_combines_ranks_and_preserves_source_chunk() -> None:
    """RRF가 순위를 결합해 정책 순서를 정하고, 대표 청크는 가장 높은 순위의 것을 유지하는지 확인한다."""
    lexical = [hit("a", "a::lex"), hit("b", "b::lex")]
    dense = [hit("b", "b::dense"), hit("a", "a::dense"), hit("c", "c::dense")]
    fused = fuse_policy_hits([lexical, dense], 3)

    assert [item.policy_id for item in fused] == ["a", "b", "c"]
    # 정책별 대표 청크는 해당 정책을 더 높은 순위로 찾은 검색기의 청크를 쓴다.
    assert [item.chunk_id for item in fused] == ["a::lex", "b::dense", "c::dense"]
    # RRF 점수는 1/(60+순위)의 합이며, a는 BM25 1위와 임베딩 2위를 받는다.
    assert fused[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert [item.policy_id for item in fuse_policy_hits([[], dense], 2)] == ["b", "a"]
    with pytest.raises(ValueError, match="positive"):
        fuse_policy_hits([lexical], 0)


def test_hybrid_uses_same_corpus_and_handles_empty_query() -> None:
    """두 검색기가 같은 청크 집합을 써야 하며, 빈 질의와 잘못된 k를 처리하는지 확인한다."""
    chunks = [PolicyChunk("a::01", "a", "a.md", "A", "section", "text")]

    class FakeIndex:
        """고정된 검색 결과를 반환하는 가짜 검색기."""
        def __init__(self, items: list[PolicyChunk], answer: list[PolicyHit]) -> None:
            """청크 목록과 반환할 검색 결과를 저장한다."""
            self.chunks = items
            self.answer = answer

        def search(self, query: str, k: int) -> list[PolicyHit]:
            """질의와 무관하게 상위 k개의 고정 결과를 반환한다."""
            return self.answer[:k]

    index = HybridPolicyIndex(FakeIndex(chunks, []), FakeIndex(chunks, [hit("a", "a::01")]))
    assert [item.policy_id for item in index.search("질문")] == ["a"]
    assert index.search("   ") == []
    with pytest.raises(ValueError, match="positive"):
        index.search("질문", 0)
    with pytest.raises(ValueError, match="same policy chunks"):
        HybridPolicyIndex(FakeIndex(chunks, []), FakeIndex([], []))
