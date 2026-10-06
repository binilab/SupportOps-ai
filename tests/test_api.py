from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from supportops.agent import ToolRequest
from supportops.api import create_app
from supportops.database import OrderRow, ProductRow, SQLAlchemyStructuredStore, make_engine, seed_demo_data
from supportops.rag import Citation, RagAnswer
from supportops.usage import get_usage, record_usage, reset_usage

ROOT = Path(__file__).resolve().parents[1]


class FixedRouter:
    def choose(self, question: str) -> ToolRequest:
        order_id = question.split()[0]
        return ToolRequest("get_order", {"order_id": order_id, "intent": "cancel"})


class FailedRouter:
    def choose(self, question: str) -> ToolRequest:
        raise httpx.ConnectError("local model is down")


class FixedRAG:
    def answer(self, question: str) -> RagAnswer:
        return RagAnswer("제주 배송비는 별도입니다.", False, (
            Citation("policy_shipping_v1", "policy_shipping_v1::02", "data/raw/policies/shipping.md"),
        ))


def test_request_validation_and_missing_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPPORTOPS_DATABASE_URL", raising=False)
    with TestClient(create_app(router=FixedRouter(), policy_rag=FixedRAG())) as client:
        assert client.get("/health").status_code == 503
        assert client.post("/v1/answer", json={"question": "ORD-1008 취소 가능해?"}).status_code == 503
    with TestClient(create_app("postgresql://postgres:unused@127.0.0.1:1/supportops", router=FixedRouter(), policy_rag=FixedRAG())) as client:
        for payload in ({"question": "  "}, {"question": "x" * 2001}, {"question": "정책?", "unknown": 1}):
            assert client.post("/v1/answer", json=payload).status_code == 422
        unavailable = client.get("/health")
        assert unavailable.status_code == 503
        assert unavailable.json() == {"detail": "database unavailable"}


@pytest.mark.skipif(not os.environ.get("SUPPORTOPS_TEST_DATABASE_URL"), reason="PostgreSQL not configured")
def test_postgres_seed_and_api_round_trip(tmp_path: Path) -> None:
    url = os.environ["SUPPORTOPS_TEST_DATABASE_URL"]
    engine = make_engine(url)
    paths = (ROOT / "data/raw/structured/orders.csv", ROOT / "data/raw/structured/products.csv")
    try:
        assert seed_demo_data(engine, *paths) == (10, 10)
        assert seed_demo_data(engine, *paths) == (10, 10)
        changed_products = tmp_path / "products.csv"
        changed_products.write_text(
            paths[1].read_text(encoding="utf-8").replace("베이직 코튼 셔츠", "다른 이름", 1),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="differs from CSV"):
            seed_demo_data(engine, paths[0], changed_products)
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(OrderRow)) == 10
            assert session.scalar(select(func.count()).select_from(ProductRow)) == 10
            store = SQLAlchemyStructuredStore(session)
            assert store.get_order("ORD-1001").delivered_at == date(2026, 10, 1)
            assert store.get_order("ORD-9999") is None
            assert store.get_product("P-1004").is_hygiene

        with TestClient(create_app(url, router=FixedRouter(), policy_rag=FixedRAG())) as client:
            assert client.get("/health").json() == {"status": "ok"}
            response = client.post("/v1/answer", json={"question": "ORD-1008 지금 취소 가능해?", "as_of": "2026-10-05"})
            assert response.status_code == 200, response.text
            assert response.headers["X-Request-ID"]
            body = response.json()
            assert body["outcome"] == "cancel_request_allowed"
            assert [step["name"] for step in body["trace"]] == ["get_order", "check_cancel_eligibility"]
            assert body["citations"][0]["chunk_id"] == "policy_cancel_v1::01"

            missing = client.post("/v1/answer", json={"question": "ORD-9999 취소 가능해?"})
            assert missing.status_code == 200
            assert missing.json()["abstained"] and missing.json()["outcome"] == "order_not_found"

            policy = client.post("/v1/answer", json={"question": "제주 배송비는?"})
            assert policy.status_code == 200
            assert policy.json()["citations"][0]["policy_id"] == "policy_shipping_v1"

        with TestClient(create_app(url, router=FailedRouter(), policy_rag=FixedRAG())) as client:
            failed = client.post("/v1/answer", json={"question": "ORD-1008 취소 가능해?"})
            assert failed.status_code == 503
            assert failed.json() == {"detail": "model unavailable"}
    finally:
        engine.dispose()


def test_database_url_requires_psycopg_driver() -> None:
    with pytest.raises(ValueError, match="postgresql\\+psycopg"):
        make_engine("sqlite:///:memory:")


def test_usage_counts_multiple_model_calls_without_guessing_missing_counts() -> None:
    reset_usage()
    assert get_usage() is None
    record_usage(None, 4)
    assert get_usage() is None
    record_usage(12, 3)
    record_usage(8, 2)
    assert get_usage() == (20, 5)
    reset_usage()
    assert get_usage() is None
