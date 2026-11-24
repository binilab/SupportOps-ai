"""임베딩 검색 인덱스의 순위/입력 검증과 pgvector 저장소의 왕복 및 정책 필터를 검증한다.
pgvector 테스트는 SUPPORTOPS_TEST_DATABASE_URL이 없으면 건너뛴다."""

from __future__ import annotations

import os

import numpy as np
import psycopg
import pytest

from supportops.dense import EMBEDDING_DIM, DensePolicyIndex
from supportops.lexical import PolicyChunk
from supportops.vector_store import PgVectorPolicyStore


def vector(axis: int) -> np.ndarray:
    """지정한 축만 1인 단위 벡터를 만든다."""
    result = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    result[axis] = 1.0
    return result


def sample_chunks() -> list[PolicyChunk]:
    """두 정책(a, b)에 걸친 테스트용 청크 3개를 만든다."""
    return [
        PolicyChunk("policy_a::01", "policy_a", "a.md", "A", "배송", "제주 배송비"),
        PolicyChunk("policy_a::02", "policy_a", "a.md", "A", "조회", "송장 조회"),
        PolicyChunk("policy_b::01", "policy_b", "b.md", "B", "환불", "환불 기간"),
    ]


class FakeModel:
    """문서/질의를 미리 정한 단위 벡터로 바꾸는 가짜 임베딩 모델."""
    def encode(self, texts: list[str], **_: object) -> np.ndarray:
        """텍스트가 3개면 문서 임베딩, 그 외에는 첫 축 벡터(질의)를 반환한다."""
        if len(texts) == 3:
            return np.stack((vector(0), vector(1), vector(2)))
        return np.stack((vector(0),))


def test_dense_ranks_distinct_policies_and_validates_shape() -> None:
    """정책 단위로 중복 없이 순위를 매기고, 빈 질의와 잘못된 k, 임베딩 차원 불일치를 거절하는지 확인한다."""
    index = DensePolicyIndex(sample_chunks(), FakeModel())

    assert index.vectors.shape == (3, EMBEDDING_DIM)
    assert [hit.policy_id for hit in index.search("제주 배송비", 2)] == ["policy_a", "policy_b"]
    assert index.search("  ") == []
    with pytest.raises(ValueError, match="positive"):
        index.search("배송", 0)

    class BadModel:
        """차원이 맞지 않는 벡터를 반환하는 가짜 모델."""
        def encode(self, texts: list[str], **_: object) -> np.ndarray:
            """차원이 EMBEDDING_DIM이 아닌 10인 벡터를 반환해 검증 오류를 유도한다."""
            return np.zeros((len(texts), 10), dtype=np.float32)

    with pytest.raises(ValueError, match="document embeddings"):
        DensePolicyIndex(sample_chunks(), BadModel())


@pytest.mark.skipif(not os.environ.get("SUPPORTOPS_TEST_DATABASE_URL"), reason="PostgreSQL not configured")
def test_pgvector_round_trip_and_policy_filter() -> None:
    """pgvector 저장, 검색, 정책 ID 필터, 교체, 잘못된 질의 벡터 거절을 확인한다."""
    dsn = os.environ["SUPPORTOPS_TEST_DATABASE_URL"]
    chunks = sample_chunks()
    vectors = np.stack((vector(0), vector(1), vector(2)))
    # 테스트 전용 revision을 써서 기존 데이터와 섞이지 않게 하고, 끝에서 해당 행만 삭제한다.
    revision = "phase2-pytest"

    with psycopg.connect(dsn) as connection:
        store = PgVectorPolicyStore(connection)
        store.setup()
        try:
            store.replace(chunks, vectors, revision)
            assert store.count(revision) == 3
            assert [hit.policy_id for hit in store.search(vector(0), revision, 2)] == [
                "policy_a", "policy_b"
            ]
            assert [hit.policy_id for hit in store.search(vector(0), revision, 2, "policy_b")] == [
                "policy_b"
            ]
            store.replace(chunks[:1], vectors[:1], revision)
            assert store.count(revision) == 1
            with pytest.raises(ValueError, match="Invalid query vector"):
                store.search(np.zeros(10, dtype=np.float32), revision)
        finally:
            connection.execute(
                "DELETE FROM phase2_policy_vectors WHERE model_revision = %s", (revision,)
            )
            connection.commit()
