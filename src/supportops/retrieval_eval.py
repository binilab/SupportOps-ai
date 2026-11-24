"""정책 검색 성능을 Gold 평가셋으로 측정한다.

BM25, 임베딩, 하이브리드 검색이 모두 같은 함수로 평가되므로 결과를 그대로 비교할 수 있다.
지표는 Recall@1/3/5, MRR, 질문당 검색 시간(중앙값, p95)이다.
"""

from __future__ import annotations

import statistics
from time import perf_counter_ns
from typing import Protocol

from supportops.lexical import PolicyChunk, PolicyHit

KS = (1, 3, 5)


class PolicySearchIndex(Protocol):
    """평가할 수 있는 검색 인덱스의 공통 형태."""

    chunks: list[PolicyChunk]

    def search(self, query: str, k: int = 5) -> list[PolicyHit]: ...


def evaluate(rows: list[dict], index: PolicySearchIndex) -> dict:
    """Gold 질문마다 검색을 실행해 정책 ID 기준 지표를 계산한다.

    - Recall@k: 정답 정책 중 상위 k개 안에 들어온 비율의 평균
    - MRR: 첫 번째 정답 정책 순위의 역수 평균
    - failures_at_5: 정답 정책을 상위 5개 안에 모두 찾지 못한 질문 목록 (실패 분석용)
    정답 정책이 없는 질문(답변 불가 사례)은 검색 평가에서 제외한다.
    """
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
    # p95 위치를 올림으로 계산한다 (nearest-rank 방식). 정수 연산으로 부동소수 오차를 피한다.
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
