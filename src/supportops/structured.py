"""Read the Phase 0 synthetic order and product records as typed data."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


def parse_bool(value: str) -> bool:
    """Reject malformed boolean cells instead of silently treating them as false."""
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


@dataclass(frozen=True)
class Order:
    order_id: str
    product_id: str
    status: str
    delivered_at: date | None
    used: bool
    seal_opened: bool
    custom_production_started: bool
    digital_redeemed: bool


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    is_custom: bool
    is_hygiene: bool
    is_digital: bool


class StructuredStore:
    def __init__(self, orders_path: Path, products_path: Path) -> None:
        self.orders: dict[str, Order] = {}
        self.products: dict[str, Product] = {}
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
        """Find one order by exact ID."""
        return self.orders.get(order_id)

    def get_product(self, product_id: str) -> Product | None:
        """Find one product by exact ID."""
        return self.products.get(product_id)
