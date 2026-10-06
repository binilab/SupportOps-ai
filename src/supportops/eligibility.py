"""Deterministic Phase 5 refund and cancellation request rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from supportops.structured import Order, Product


@dataclass(frozen=True)
class Assessment:
    status: str  # eligible, ineligible, needs_review
    reason: str


def customer_conditions(question: str) -> tuple[bool, bool]:
    """Extract only explicit component and resale-damage statements."""
    components = bool(re.search(r"구성품.{0,12}(?:모두|있|보존)", question))
    damage = bool(re.search(r"(?:오염됐|오염되어|세탁했|스크래치가|재판매.{0,5}어려)", question))
    return components, damage


def requires_special_review(question: str) -> bool:
    """Detect a claimed company fault or an unavailable individual product condition."""
    if re.search(r"하자|불량|오배송", question):
        return True
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
    """Assess whether a simple-remorse refund may be requested, not final approval."""
    if company_fault_confirmed:
        return Assessment("eligible", "confirmed_company_fault")
    if special_review_requested:
        return Assessment("needs_review", "special_condition_unverified")
    if product.is_custom:
        return Assessment("ineligible", "custom_product")
    if product.is_hygiene and order.seal_opened:
        return Assessment("ineligible", "hygiene_seal_opened")
    if product.is_digital and order.digital_redeemed:
        return Assessment("ineligible", "digital_redeemed")
    if resale_damage_reported:
        return Assessment("ineligible", "resale_damage")
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
    """Assess a full cancellation request without executing a cancellation."""
    if special_review_requested:
        return Assessment("needs_review", "special_condition_unverified")
    if order.status in {"SHIPPED", "DELIVERED"}:
        return Assessment("ineligible", "already_shipped")
    if order.status not in {"PAID", "PREPARING"}:
        return Assessment("needs_review", "unknown_order_status")
    if order.custom_production_started:
        return Assessment("ineligible", "custom_production_started")
    if order.status == "PREPARING" and product is None:
        return Assessment("needs_review", "product_unknown")
    return Assessment("eligible", "cancel_request_allowed")
