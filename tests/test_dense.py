from __future__ import annotations

import os

import numpy as np
import psycopg
import pytest

from supportops.dense import EMBEDDING_DIM, DensePolicyIndex
from supportops.lexical import PolicyChunk
from supportops.vector_store import PgVectorPolicyStore


def vector(axis: int) -> np.ndarray:
    result = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    result[axis] = 1.0
    return result


def sample_chunks() -> list[PolicyChunk]:
    return [
        PolicyChunk("policy_a::01", "policy_a", "a.md", "A", "배송", "제주 배송비"),
        PolicyChunk("policy_a::02", "policy_a", "a.md", "A", "조회", "송장 조회"),
        PolicyChunk("policy_b::01", "policy_b", "b.md", "B", "환불", "환불 기간"),
    ]


class FakeModel:
    def encode(self, texts: list[str], **_: object) -> np.ndarray:
        if len(texts) == 3:
            return np.stack((vector(0), vector(1), vector(2)))
        return np.stack((vector(0),))


def test_dense_ranks_distinct_policies_and_validates_shape() -> None:
    index = DensePolicyIndex(sample_chunks(), FakeModel())

    assert index.vectors.shape == (3, EMBEDDING_DIM)
    assert [hit.policy_id for hit in index.search("제주 배송비", 2)] == ["policy_a", "policy_b"]
    assert index.search("  ") == []
    with pytest.raises(ValueError, match="positive"):
        index.search("배송", 0)

    class BadModel:
        def encode(self, texts: list[str], **_: object) -> np.ndarray:
            return np.zeros((len(texts), 10), dtype=np.float32)

    with pytest.raises(ValueError, match="document embeddings"):
        DensePolicyIndex(sample_chunks(), BadModel())


@pytest.mark.skipif(not os.environ.get("SUPPORTOPS_TEST_DATABASE_URL"), reason="PostgreSQL not configured")
def test_pgvector_round_trip_and_policy_filter() -> None:
    dsn = os.environ["SUPPORTOPS_TEST_DATABASE_URL"]
    chunks = sample_chunks()
    vectors = np.stack((vector(0), vector(1), vector(2)))
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
