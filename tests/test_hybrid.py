from __future__ import annotations

import pytest

from supportops.hybrid import HybridPolicyIndex, fuse_policy_hits
from supportops.lexical import PolicyChunk, PolicyHit


def hit(policy: str, chunk: str) -> PolicyHit:
    return PolicyHit(policy, chunk, f"{policy}.md", 1.0)


def test_rrf_combines_ranks_and_preserves_source_chunk() -> None:
    lexical = [hit("a", "a::lex"), hit("b", "b::lex")]
    dense = [hit("b", "b::dense"), hit("a", "a::dense"), hit("c", "c::dense")]
    fused = fuse_policy_hits([lexical, dense], 3)

    assert [item.policy_id for item in fused] == ["a", "b", "c"]
    assert [item.chunk_id for item in fused] == ["a::lex", "b::dense", "c::dense"]
    assert fused[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert [item.policy_id for item in fuse_policy_hits([[], dense], 2)] == ["b", "a"]
    with pytest.raises(ValueError, match="positive"):
        fuse_policy_hits([lexical], 0)


def test_hybrid_uses_same_corpus_and_handles_empty_query() -> None:
    chunks = [PolicyChunk("a::01", "a", "a.md", "A", "section", "text")]

    class FakeIndex:
        def __init__(self, items: list[PolicyChunk], answer: list[PolicyHit]) -> None:
            self.chunks = items
            self.answer = answer

        def search(self, query: str, k: int) -> list[PolicyHit]:
            return self.answer[:k]

    index = HybridPolicyIndex(FakeIndex(chunks, []), FakeIndex(chunks, [hit("a", "a::01")]))
    assert [item.policy_id for item in index.search("질문")] == ["a"]
    assert index.search("   ") == []
    with pytest.raises(ValueError, match="positive"):
        index.search("질문", 0)
    with pytest.raises(ValueError, match="same policy chunks"):
        HybridPolicyIndex(FakeIndex(chunks, []), FakeIndex([], []))
