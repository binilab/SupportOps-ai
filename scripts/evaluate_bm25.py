"""Run the fixed Phase 1 policy-retrieval evaluation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.lexical import BM25PolicyIndex, load_policy_chunks  # noqa: E402

GOLD_PATH = ROOT / "data" / "eval" / "gold_dataset.jsonl"
POLICY_DIR = ROOT / "data" / "raw" / "policies"
KS = (1, 3, 5)


def evaluate(rows: list[dict], index: BM25PolicyIndex) -> dict:
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


def main() -> int:
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    index = BM25PolicyIndex(load_policy_chunks(POLICY_DIR, ROOT))
    result = evaluate(rows, index)
    result["gold_sha256"] = hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest()
    policy_digest = hashlib.sha256()
    for path in sorted(POLICY_DIR.glob("*.md")):
        policy_digest.update(path.name.encode("utf-8"))
        policy_digest.update(b"\0")
        policy_digest.update(path.read_bytes())
        policy_digest.update(b"\0")
    result["policy_corpus_sha256"] = policy_digest.hexdigest()
    result["python_version"] = sys.version.split()[0]
    result["numpy_version"] = importlib.metadata.version("numpy")
    result["tokenizer"] = "lowercase regex [가-힣A-Za-z0-9]+"
    result["bm25"] = f"rank-bm25 {importlib.metadata.version('rank-bm25')} BM25Okapi default parameters"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
