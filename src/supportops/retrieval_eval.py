"""Policy-ID retrieval metrics shared by lexical and dense baselines."""

from __future__ import annotations

import statistics
from time import perf_counter_ns
from typing import Protocol

from supportops.lexical import PolicyChunk, PolicyHit

KS = (1, 3, 5)


class PolicySearchIndex(Protocol):
    chunks: list[PolicyChunk]

    def search(self, query: str, k: int = 5) -> list[PolicyHit]: ...


def evaluate(rows: list[dict], index: PolicySearchIndex) -> dict:
    """Measure policy-ID recall, first-relevant MRR, and per-query search time."""
    eligible = [row for row in rows if row["expected_policy_ids"]]
    if not eligible:
        raise ValueError("No Gold rows with expected policy IDs")
    recall_sums = {k: 0.0 for k in KS}
    reciprocal_rank_sum = 0.0
    latencies_ms: list[float] = []
    failures: list[dict] = []

    for row in eligible:
        start = perf_counter_ns()
        hits = index.search(row["question"], max(KS))
        latencies_ms.append((perf_counter_ns() - start) / 1_000_000)
        ranked_ids = [hit.policy_id for hit in hits]
        expected = set(row["expected_policy_ids"])
        for k in KS:
            recall_sums[k] += len(expected.intersection(ranked_ids[:k])) / len(expected)
        first_rank = next((rank for rank, policy_id in enumerate(ranked_ids, 1) if policy_id in expected), None)
        if first_rank is not None:
            reciprocal_rank_sum += 1 / first_rank
        if not expected.issubset(ranked_ids[:5]):
            failures.append({
                "id": row["id"],
                "category": row["category"],
                "expected_policy_ids": row["expected_policy_ids"],
                "top5_policy_ids": ranked_ids,
            })

    sorted_latencies = sorted(latencies_ms)
    p95_index = max(0, (95 * len(sorted_latencies) + 99) // 100 - 1)
    return {
        "gold_count": len(rows),
        "evaluated_count": len(eligible),
        "excluded_no_policy_count": len(rows) - len(eligible),
        "chunk_count": len(index.chunks),
        "policy_count": len({chunk.policy_id for chunk in index.chunks}),
        "recall_at_1": recall_sums[1] / len(eligible),
        "recall_at_3": recall_sums[3] / len(eligible),
        "recall_at_5": recall_sums[5] / len(eligible),
        "mrr": reciprocal_rank_sum / len(eligible),
        "latency_ms_median": statistics.median(latencies_ms),
        "latency_ms_p95": sorted_latencies[p95_index],
        "failures_at_5": failures,
    }
