"""Exact pgvector storage and cosine search for the fixed Phase 2 model."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from supportops.dense import EMBEDDING_DIM, DensePolicyIndex
from supportops.lexical import PolicyChunk, PolicyHit


class PgVectorPolicyStore:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def setup(self) -> None:
        """Create a Phase 2-only table and register the pgvector type."""
        self.connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self.connection)
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
        """Replace only this model revision's policy vectors."""
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
        """Count stored chunks for one model revision."""
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
        """Run exact cosine distance in Postgres and collapse chunks by policy."""
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
        for found_policy_id, chunk_id, source_path, distance in rows:
            if found_policy_id in seen:
                continue
            seen.add(found_policy_id)
            hits.append(PolicyHit(found_policy_id, chunk_id, source_path, 1.0 - float(distance)))
            if len(hits) >= k:
                break
        return hits


class PgVectorPolicyIndex:
    def __init__(self, dense_index: DensePolicyIndex, store: PgVectorPolicyStore, revision: str) -> None:
        self.dense_index = dense_index
        self.chunks = dense_index.chunks
        self.store = store
        self.revision = revision

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        if k < 1:
            raise ValueError("k must be positive")
        if not query.strip():
            return []
        return self.store.search(self.dense_index.encode_query(query), self.revision, k)
