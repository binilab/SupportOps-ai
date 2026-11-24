"""환불·취소 신청 가능 여부를 판단하는 확정적 규칙.

LLM에 맡기지 않고 Python 규칙으로만 판단해서, 같은 주문·같은 날짜에는 항상 같은 결과가 나온다.
결과는 "신청 가능 여부"까지만 말하며, 실제 환불·취소를 승인하거나 실행하지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from supportops.structured import Order, Product


@dataclass(frozen=True)
class Assessment:
    """규칙 판단 결과. reason은 답변 문구와 인용 정책을 고르는 키로 쓰인다."""

    status: str  # eligible(가능), ineligible(불가), needs_review(확인 필요) 중 하나
    reason: str


def customer_conditions(question: str) -> tuple[bool, bool]:
    """질문에서 고객이 직접 밝힌 상품 상태를 뽑는다.

    반환값은 (구성품 보존을 밝혔는지, 오염·훼손으로 재판매가 어렵다고 밝혔는지)이다.
    명시적인 표현이 있을 때만 True로 보고, 애매하면 False로 둔다.
    """
    components = bool(re.search(r"구성품.{0,12}(?:모두|있|보존)", question))
    damage = bool(re.search(r"(?:오염됐|오염되어|세탁했|스크래치가|재판매.{0,5}어려)", question))
    return components, damage


def requires_special_review(question: str) -> bool:
    """하자·오배송 주장이나 상품별 개별 조건 언급이 있어 사람이 확인해야 하는지 판단한다."""
    if re.search(r"하자|불량|오배송", question):
        return True
    # "개별 조건이 없다"처럼 조건이 없다고 밝힌 경우는 검토 대상에서 뺀다.
    if re.search(r"(?:개별|별도).{0,8}조건.{0,5}(?:없|미기재)", question):
        return False
    return bool(re.search(r"(?:상품\s*페이지|개별|별도).{0,12}조건", question))


def check_refund_eligibility(
    order: Order,
    product: Product,
    as_of: date,
    *,
    components_confirmed: bool,
    resale_damage_reported: bool,
    company_fault_confirmed: bool = False,
    special_review_requested: bool = False,
) -> Assessment:
    """단순 변심 환불을 신청할 수 있는지 판단한다 (최종 환불 승인이 아님).

    위에서부터 먼저 걸리는 조건이 결과가 된다. 회사 귀책 → 개별 검토 → 상품 종류별 제한
    → 상품 상태 → 신청 기간(배송 완료 다음 날부터 7일) → 구성품 확인 순서다.
    """
    if company_fault_confirmed:
        return Assessment("eligible", "confirmed_company_fault")
    if special_review_requested:
        return Assessment("needs_review", "special_condition_unverified")
    # 주문제작·위생·디지털 상품은 상품 종류만으로 단순 변심 환불이 제한된다.
    if product.is_custom:
        return Assessment("ineligible", "custom_product")
    if product.is_hygiene and order.seal_opened:
        return Assessment("ineligible", "hygiene_seal_opened")
    if product.is_digital and order.digital_redeemed:
        return Assessment("ineligible", "digital_redeemed")
    if resale_damage_reported:
        return Assessment("ineligible", "resale_damage")
    # 사용 이력만으로는 재판매 가능 여부를 알 수 없어 불가가 아니라 확인 필요로 둔다.
    if order.used:
        return Assessment("needs_review", "used_condition_unknown")
    if order.status != "DELIVERED" or order.delivered_at is None:
        return Assessment("needs_review", "delivery_unknown")
    days = (as_of - order.delivered_at).days
    if days > 7:
        return Assessment("ineligible", "refund_window_expired")
    if days < 1:
        return Assessment("needs_review", "refund_window_not_started")
    if not components_confirmed:
        return Assessment("needs_review", "components_unknown")
    return Assessment("eligible", "refund_request_allowed")


def check_cancel_eligibility(
    order: Order, product: Product | None, *, special_review_requested: bool = False
) -> Assessment:
    """전체 주문 취소를 요청할 수 있는지 판단한다. 취소를 실행하지는 않는다.

    결제 완료(PAID)·상품 준비 중(PREPARING) 상태만 취소 대상이고,
    이미 발송된 주문은 취소 대신 반품 절차로 안내한다.
    """
    if special_review_requested:
        return Assessment("needs_review", "special_condition_unverified")
    if order.status in {"SHIPPED", "DELIVERED"}:
        return Assessment("ineligible", "already_shipped")
    if order.status not in {"PAID", "PREPARING"}:
        return Assessment("needs_review", "unknown_order_status")
    if order.custom_production_started:
        return Assessment("ineligible", "custom_production_started")
    # 준비 중인 주문은 주문제작 여부를 상품 정보로 확인해야 해서 상품이 없으면 판단을 보류한다.
    if order.status == "PREPARING" and product is None:
        return Assessment("needs_review", "product_unknown")
    return Assessment("eligible", "cancel_request_allowed")
