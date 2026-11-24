"""SupportAgent의 주문 도구 호출 흐름과 환불/취소 자격 판정 규칙(결정론적 Python 규칙)을 검증한다."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from supportops.agent import SupportAgent, ToolRequest
from supportops.eligibility import check_cancel_eligibility, check_refund_eligibility, customer_conditions, requires_special_review
from supportops.lexical import load_policy_chunks
from supportops.structured import StructuredStore, parse_bool

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 5)


def store() -> StructuredStore:
    """테스트용 CSV 데이터로 StructuredStore를 만든다."""
    return StructuredStore(ROOT / "data/raw/structured/orders.csv", ROOT / "data/raw/structured/products.csv")


class FakeRouter:
    """LLM 없이 고정된 도구 요청을 돌려주는 가짜 라우터."""
    def __init__(self, request: ToolRequest | None) -> None:
        """라우터가 반환할 도구 요청을 저장한다."""
        self.request = request

    def choose(self, question: str) -> ToolRequest | None:
        """질문과 무관하게 미리 정한 도구 요청을 반환한다."""
        return self.request


def agent(order_id: str, intent: str) -> SupportAgent:
    """지정한 주문 ID와 의도로 get_order를 호출하는 가짜 라우터를 쓴 에이전트를 만든다."""
    return SupportAgent(
        store(), FakeRouter(ToolRequest("get_order", {"order_id": order_id, "intent": intent})),
        load_policy_chunks(ROOT / "data/raw/policies", ROOT),
    )


def test_structured_records_and_invalid_bool() -> None:
    """주문/상품 CSV 로딩, 없는 주문 조회, 잘못된 불리언 값 처리를 확인한다."""
    data = store()
    assert len(data.orders) == 10 and len(data.products) == 10
    assert data.get_order("ORD-1001").product_id == "P-1001"
    assert data.get_order("ORD-9999") is None
    assert data.get_product("P-1004").is_hygiene
    with pytest.raises(ValueError, match="Invalid boolean"):
        parse_bool("maybe")


def test_refund_rules_keep_unknown_condition_separate_from_damage() -> None:
    """사용 상태 미확인과 재판매 손상을 구분하고, 업체 과실 및 특수 조건 검토 감지가 동작하는지 확인한다."""
    data = store()
    order = data.get_order("ORD-1007")
    product = data.get_product("P-1001")
    assert check_refund_eligibility(order, product, AS_OF, components_confirmed=True, resale_damage_reported=False).reason == "used_condition_unknown"
    assert check_refund_eligibility(order, product, AS_OF, components_confirmed=True, resale_damage_reported=True).reason == "resale_damage"
    assert customer_conditions("구성품은 모두 있고 오염은 없어요") == (True, False)
    assert customer_conditions("착용해 오염됐고 재판매가 어려워요") == (False, True)
    assert check_refund_eligibility(order, product, AS_OF, components_confirmed=False, resale_damage_reported=True, company_fault_confirmed=True).reason == "confirmed_company_fault"
    assert check_refund_eligibility(order, product, AS_OF, components_confirmed=False, resale_damage_reported=False, special_review_requested=True).reason == "special_condition_unverified"
    assert requires_special_review("ORD-1004 불량이라고 주장하면 환불돼?")
    assert requires_special_review("상품 페이지의 별도 환불 조건이 있어요")
    assert not requires_special_review("별도 조건이 없으면 일반 정책을 따라?")


def test_refund_period_and_product_restrictions() -> None:
    """환불 기간 경계(배송 후 7일)와 위생 상품, 사용된 디지털 상품 제한을 확인한다."""
    data = store()
    base = data.get_order("ORD-1001")
    shirt = data.get_product("P-1001")
    assert check_refund_eligibility(base, shirt, AS_OF, components_confirmed=True, resale_damage_reported=False).status == "eligible"
    # ORD-1001은 10/1 배송이므로 10/8까지는 가능하고 10/9부터 기간이 만료된다.
    assert check_refund_eligibility(base, shirt, date(2026, 10, 8), components_confirmed=True, resale_damage_reported=False).status == "eligible"
    assert check_refund_eligibility(base, shirt, date(2026, 10, 9), components_confirmed=True, resale_damage_reported=False).reason == "refund_window_expired"
    assert check_refund_eligibility(base, shirt, AS_OF, components_confirmed=False, resale_damage_reported=False).reason == "components_unknown"
    assert check_refund_eligibility(data.get_order("ORD-1004"), data.get_product("P-1004"), AS_OF, components_confirmed=False, resale_damage_reported=False).reason == "hygiene_seal_opened"
    assert check_refund_eligibility(data.get_order("ORD-1005"), data.get_product("P-1005"), AS_OF, components_confirmed=False, resale_damage_reported=False).reason == "digital_redeemed"


def test_cancel_rules_and_workflow_tool_sequence() -> None:
    """취소 가능 여부 규칙과 에이전트가 호출하는 도구 순서를 확인한다."""
    data = store()
    assert check_cancel_eligibility(data.get_order("ORD-1003"), data.get_product("P-1003")).reason == "custom_production_started"
    assert check_cancel_eligibility(replace(data.get_order("ORD-1003"), custom_production_started=False), data.get_product("P-1003")).status == "eligible"
    assert check_cancel_eligibility(data.get_order("ORD-1003"), data.get_product("P-1003"), special_review_requested=True).reason == "special_condition_unverified"
    assert check_cancel_eligibility(data.get_order("ORD-1008"), None).status == "eligible"
    assert check_cancel_eligibility(replace(data.get_order("ORD-1002"), status="SHIPPED"), None).reason == "already_shipped"
    assert check_cancel_eligibility(replace(data.get_order("ORD-1002"), status="UNKNOWN"), None).reason == "unknown_order_status"

    paid = agent("ORD-1008", "cancel").run("ORD-1008 지금 취소 가능해?", AS_OF)
    preparing = agent("ORD-1009", "cancel").run("ORD-1009 주문 전체 취소 신청할 수 있어?", AS_OF)
    assert [item.name for item in paid.trace] == ["get_order", "check_cancel_eligibility"]
    assert [item.name for item in preparing.trace] == ["get_order", "get_product", "check_cancel_eligibility"]
    assert "실제 취소는 실행하지 않았습니다" in paid.answer


def test_agent_validates_model_arguments_and_missing_data() -> None:
    """모델이 낸 잘못된 인자와 누락된 데이터(없는 주문, 배송 추적, 불량 주장, 잘못된 날짜)에서 에이전트가 보류하는지 확인한다."""
    chunks = load_policy_chunks(ROOT / "data/raw/policies", ROOT)
    # 질문의 주문(ORD-1001)과 다른 주문 ID를 모델이 제안한 상황을 만든다.
    wrong = SupportAgent(store(), FakeRouter(ToolRequest("get_order", {"order_id": "ORD-1007", "intent": "refund"})), chunks)
    assert wrong.run("ORD-1001 환불 가능해?", AS_OF).outcome == "invalid_tool_request"
    assert wrong.run("ORD-1001 환불 가능해?", AS_OF).trace == ()

    missing = agent("ORD-9999", "refund").run("ORD-9999 환불돼?", AS_OF)
    assert missing.abstained and missing.outcome == "order_not_found"
    assert [item.name for item in missing.trace] == ["get_order"]

    shipping = agent("ORD-1002", "shipping").run("ORD-1002 배송 어디쯤 왔어?", AS_OF)
    assert shipping.abstained and shipping.outcome == "tracking_unavailable"
    assert "정확한 현재 위치는 확인할 수 없습니다" in shipping.answer

    defect = agent("ORD-1004", "refund").run("ORD-1004 마스크가 불량인데 환불돼?", AS_OF)
    assert defect.abstained and defect.outcome == "special_condition_unverified"

    invalid_date = agent("ORD-1001", "refund").run("2026-13-99 기준 ORD-1001 환불돼?", AS_OF)
    assert invalid_date.abstained and invalid_date.outcome == "invalid_date"
