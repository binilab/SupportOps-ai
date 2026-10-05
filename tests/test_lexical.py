from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from supportops.lexical import (
    BM25PolicyIndex,
    PolicyChunk,
    PolicyHit,
    load_policy_chunks,
    load_policy_documents,
    tokenize,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_bm25.py"
spec = importlib.util.spec_from_file_location("evaluate_bm25", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_policy_chunks_preserve_source_and_search_terms(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "sample.md").write_text(
        "# 샘플 정책\n\n정책 ID: `policy_sample_v1`\n\n"
        "## 1. 배송비\n제주 지역 추가 배송비 3,000원\n\n"
        "## 2. 조회\n송장번호로 조회\n",
        encoding="utf-8",
    )
    documents = load_policy_documents(policy_dir, tmp_path)
    chunks = load_policy_chunks(policy_dir, tmp_path)

    assert len(documents) == 1
    assert documents[0].policy_id == "policy_sample_v1"
    assert documents[0].source_path == "policies/sample.md"
    assert [chunk.chunk_id for chunk in chunks] == ["policy_sample_v1::01", "policy_sample_v1::02"]
    assert all(chunk.source_path == "policies/sample.md" for chunk in chunks)
    assert chunks[0].heading == "1. 배송비"
    assert "제주 지역 추가 배송비" in chunks[0].search_text
    assert tokenize("ORD-1001 제주도?") == ["ord", "1001", "제주도"]


def test_real_corpus_search_and_empty_query() -> None:
    index = BM25PolicyIndex(load_policy_chunks(ROOT / "data/raw/policies", ROOT))

    assert index.search("제주 지역 추가 배송비", 1)[0].policy_id == "policy_shipping_v1"
    assert index.search("!!!") == []
    with pytest.raises(ValueError, match="positive"):
        index.search("배송", 0)


def test_evaluation_counts_partial_multi_policy_recall() -> None:
    class FakeIndex:
        chunks = [PolicyChunk("a::01", "a", "sample.md", "sample", "section", "text")]

        def search(self, query: str, k: int) -> list[PolicyHit]:
            ids = {"first": ["b", "c", "a"], "second": []}.get(query, [])
            return [PolicyHit(value, value, "sample.md", 1.0) for value in ids[:k]]

    rows = [
        {"id": "one", "question": "first", "category": "multi", "expected_policy_ids": ["a", "b"]},
        {"id": "two", "question": "second", "category": "missing", "expected_policy_ids": ["d"]},
        {"id": "three", "question": "excluded", "category": "none", "expected_policy_ids": []},
    ]
    result = module.evaluate(rows, FakeIndex())

    assert result["evaluated_count"] == 2
    assert result["excluded_no_policy_count"] == 1
    assert result["recall_at_1"] == pytest.approx(0.25)
    assert result["recall_at_3"] == pytest.approx(0.5)
    assert result["mrr"] == pytest.approx(0.5)
    assert [failure["id"] for failure in result["failures_at_5"]] == ["two"]
