"""pgvector에 정책 임베딩을 저장하고 PostgreSQL 안에서 코사인 검색을 한다.

메모리 검색(dense.py)과 같은 결과가 나오는지 확인하려고 만든 저장소다.
현재 API의 정책 검색은 메모리 기반 하이브리드 검색을 쓰고, 이 모듈은 평가 스크립트에서만 쓴다.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from supportops.dense import EMBEDDING_DIM, DensePolicyIndex
from supportops.lexical import PolicyChunk, PolicyHit


class PgVectorPolicyStore:
    """정책 청크 임베딩 테이블을 관리하고 검색한다."""

    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def setup(self) -> None:
        """vector 확장과 임베딩 테이블을 만든다. 이미 있으면 그대로 둔다."""
        self.connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self.connection)
        # 모델 버전(revision)별로 저장해서 모델을 바꿔도 이전 벡터와 섞이지 않게 한다.
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS phase2_policy_vectors (
                model_revision text NOT NULL,
                chunk_id text NOT NULL,
                policy_id text NOT NULL,
                source_path text NOT NULL,
                embedding vector(384) NOT NULL,
                PRIMARY KEY (model_revision, chunk_id)
            )
            """
        )
        self.connection.commit()

    def replace(self, chunks: Sequence[PolicyChunk], vectors: np.ndarray, revision: str) -> None:
        """해당 모델 버전의 벡터를 지우고 새로 넣는다. 한 트랜잭션이라 중간에 실패하면 원래 상태로 돌아간다."""
        if vectors.shape != (len(chunks), EMBEDDING_DIM) or not np.isfinite(vectors).all():
            raise ValueError("Invalid vectors for policy chunks")
        if not revision:
            raise ValueError("Model revision is required")
        with self.connection.transaction():
            self.connection.execute(
                "DELETE FROM phase2_policy_vectors WHERE model_revision = %s", (revision,)
            )
            with self.connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO phase2_policy_vectors
                        (model_revision, chunk_id, policy_id, source_path, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        (revision, chunk.chunk_id, chunk.policy_id, chunk.source_path, vector)
                        for chunk, vector in zip(chunks, vectors, strict=True)
                    ],
                )

    def count(self, revision: str) -> int:
        """해당 모델 버전으로 저장된 청크 수를 센다."""
        row = self.connection.execute(
            "SELECT count(*) FROM phase2_policy_vectors WHERE model_revision = %s", (revision,)
        ).fetchone()
        assert row is not None
        return int(row[0])

    def search(
        self,
        vector: np.ndarray,
        revision: str,
        k: int = 5,
        policy_id: str | None = None,
    ) -> list[PolicyHit]:
        """질문 벡터와 코사인 거리가 가까운 순으로 청크를 찾아 정책 단위로 묶는다.

        `<=>`는 pgvector의 코사인 거리 연산자라 유사도는 1 - 거리로 바꿔 돌려준다.
        인덱스 없이 전체를 비교하는 정확한(exact) 검색이라 메모리 검색 결과와 직접 비교할 수 있다.
        """
        if k < 1:
            raise ValueError("k must be positive")
        if vector.shape != (EMBEDDING_DIM,) or not np.isfinite(vector).all():
            raise ValueError("Invalid query vector")
        condition = "AND policy_id = %s" if policy_id is not None else ""
        parameters = (vector, revision, policy_id) if policy_id is not None else (vector, revision)
        rows = self.connection.execute(
            f"""
            SELECT policy_id, chunk_id, source_path, embedding <=> %s AS distance
            FROM phase2_policy_vectors
            WHERE model_revision = %s {condition}
            ORDER BY distance, chunk_id
            """,
            parameters,
        ).fetchall()
        hits: list[PolicyHit] = []
        seen: set[str] = set()
        # 거리순으로 정렬돼 있으므로 정책마다 처음 나온 청크가 가장 가까운 청크다.
        for found_policy_id, chunk_id, source_path, distance in rows:
            if found_policy_id in seen:
                continue
            seen.add(found_policy_id)
            hits.append(PolicyHit(found_policy_id, chunk_id, source_path, 1.0 - float(distance)))
            if len(hits) >= k:
                break
        return hits


class PgVectorPolicyIndex:
    """질문 임베딩은 메모리 모델로 만들고, 검색은 pgvector에서 하는 인덱스."""

    def __init__(self, dense_index: DensePolicyIndex, store: PgVectorPolicyStore, revision: str) -> None:
        self.dense_index = dense_index
        self.chunks = dense_index.chunks
        self.store = store
        self.revision = revision

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        """질문을 임베딩한 뒤 pgvector에서 상위 k개 정책을 찾는다."""
        if k < 1:
            raise ValueError("k must be positive")
        if not query.strip():
            return []
        return self.store.search(self.dense_index.encode_query(query), self.revision, k)
