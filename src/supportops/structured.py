"""합성 주문·상품 CSV를 타입이 있는 데이터로 읽는다.

data/raw/structured/의 CSV는 PostgreSQL에 적재하기 전의 원본이자, 테스트에서 DB 없이 쓰는 저장소다.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol


def parse_bool(value: str) -> bool:
    """CSV의 "true"/"false" 문자열을 bool로 바꾼다.

    그 밖의 값은 조용히 False로 처리하지 않고 오류를 낸다. 잘못된 데이터가 규칙 판단에 섞이지 않게 하려는 것이다.
    """
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


@dataclass(frozen=True)
class Order:
    """주문 한 건. 환불·취소 규칙 판단에 필요한 상태만 담는다."""

    order_id: str
    product_id: str
    status: str  # PAID, PREPARING, SHIPPED, DELIVERED 등
    delivered_at: date | None
    used: bool
    seal_opened: bool  # 위생 상품 보호 포장 개봉 여부
    custom_production_started: bool  # 주문제작 상품 제작 시작 여부
    digital_redeemed: bool  # 디지털 코드 사용 여부


@dataclass(frozen=True)
class Product:
    """상품 한 건. 환불 제한 대상인 상품 종류를 나타낸다."""

    product_id: str
    name: str
    is_custom: bool
    is_hygiene: bool
    is_digital: bool


class OrderProductStore(Protocol):
    """에이전트가 쓰는 읽기 전용 저장소 인터페이스 (CSV 저장소와 DB 저장소가 모두 따른다)."""

    def get_order(self, order_id: str) -> Order | None: ...

    def get_product(self, product_id: str) -> Product | None: ...


class StructuredStore:
    """CSV 파일을 메모리에 올려 주문·상품을 조회하는 저장소."""

    def __init__(self, orders_path: Path, products_path: Path) -> None:
        self.orders: dict[str, Order] = {}
        self.products: dict[str, Product] = {}
        # 주문이 참조하는 상품 ID를 검증해야 하므로 상품을 먼저 읽는다.
        with products_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                product = Product(
                    product_id=row["product_id"],
                    name=row["name"],
                    is_custom=parse_bool(row["is_custom"]),
                    is_hygiene=parse_bool(row["is_hygiene"]),
                    is_digital=parse_bool(row["is_digital"]),
                )
                if product.product_id in self.products:
                    raise ValueError(f"Duplicate product ID: {product.product_id}")
                self.products[product.product_id] = product
        with orders_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                order = Order(
                    order_id=row["order_id"],
                    product_id=row["product_id"],
                    status=row["status"],
                    delivered_at=date.fromisoformat(row["delivered_at"]) if row["delivered_at"] else None,
                    used=parse_bool(row["used"]),
                    seal_opened=parse_bool(row["seal_opened"]),
                    custom_production_started=parse_bool(row["custom_production_started"]),
                    digital_redeemed=parse_bool(row["digital_redeemed"]),
                )
                if order.order_id in self.orders:
                    raise ValueError(f"Duplicate order ID: {order.order_id}")
                if order.product_id not in self.products:
                    raise ValueError(f"Unknown product {order.product_id} in {order.order_id}")
                self.orders[order.order_id] = order

    def get_order(self, order_id: str) -> Order | None:
        """주문 ID가 정확히 일치하는 주문을 찾는다. 없으면 None."""
        return self.orders.get(order_id)

    def get_product(self, product_id: str) -> Product | None:
        """상품 ID가 정확히 일치하는 상품을 찾는다. 없으면 None."""
        return self.products.get(product_id)
