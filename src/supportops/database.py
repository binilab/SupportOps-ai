"""주문·상품 데이터를 PostgreSQL에 저장하고 읽는다 (SQLAlchemy).

서비스는 이 데이터를 읽기만 한다. 적재는 scripts/init_database.py로 명시적으로 실행한다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import Boolean, Date, ForeignKey, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from supportops.structured import Order, Product, StructuredStore


class Base(DeclarativeBase):
    pass


class ProductRow(Base):
    """support_products 테이블. 필드는 structured.Product와 같다."""

    __tablename__ = "support_products"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_hygiene: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_digital: Mapped[bool] = mapped_column(Boolean, nullable=False)


class OrderRow(Base):
    """support_orders 테이블. 필드는 structured.Order와 같다."""

    __tablename__ = "support_orders"

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("support_products.product_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    delivered_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False)
    seal_opened: Mapped[bool] = mapped_column(Boolean, nullable=False)
    custom_production_started: Mapped[bool] = mapped_column(Boolean, nullable=False)
    digital_redeemed: Mapped[bool] = mapped_column(Boolean, nullable=False)


def make_engine(database_url: str) -> Engine:
    """DB 엔진을 만든다. 이 시점에는 아직 연결하지 않는다.

    `postgresql://` 주소는 psycopg 3 드라이버를 쓰도록 `postgresql+psycopg://`로 바꾼다.
    """
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not database_url.startswith("postgresql+psycopg://"):
        raise ValueError("SUPPORTOPS_DATABASE_URL must use postgresql:// or postgresql+psycopg://")
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def seed_demo_data(engine: Engine, orders_path: Path, products_path: Path) -> tuple[int, int]:
    """테이블을 만들고 CSV 데이터를 넣는다. 반환값은 (주문 수, 상품 수).

    여러 번 실행해도 안전하다. 이미 있는 행은 건너뛰고, CSV와 내용이 다르면
    덮어쓰지 않고 오류를 내서 데이터가 어긋난 것을 바로 알 수 있게 한다.
    """
    source = StructuredStore(orders_path, products_path)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        for product in source.products.values():
            existing = session.get(ProductRow, product.product_id)
            if existing is None:
                session.add(ProductRow(**vars(product)))
            elif _product(existing) != product:
                raise ValueError(f"Database product differs from CSV: {product.product_id}")
        # 주문의 외래 키가 상품을 참조하므로 상품을 먼저 DB에 반영한다.
        session.flush()
        for order in source.orders.values():
            existing = session.get(OrderRow, order.order_id)
            if existing is None:
                session.add(OrderRow(**vars(order)))
            elif _order(existing) != order:
                raise ValueError(f"Database order differs from CSV: {order.order_id}")
    return len(source.orders), len(source.products)


def _order(row: OrderRow) -> Order:
    """DB 행을 규칙 판단에 쓰는 Order 객체로 바꾼다."""
    return Order(
        row.order_id, row.product_id, row.status, row.delivered_at,
        row.used, row.seal_opened, row.custom_production_started, row.digital_redeemed,
    )


def _product(row: ProductRow) -> Product:
    """DB 행을 Product 객체로 바꾼다."""
    return Product(row.product_id, row.name, row.is_custom, row.is_hygiene, row.is_digital)


class SQLAlchemyStructuredStore:
    """요청마다 열린 DB 세션으로 주문·상품을 기본 키로 조회한다 (OrderProductStore 구현)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_order(self, order_id: str) -> Order | None:
        """주문 ID로 주문을 조회한다. 없으면 None."""
        row = self.session.get(OrderRow, order_id)
        return _order(row) if row is not None else None

    def get_product(self, product_id: str) -> Product | None:
        """상품 ID로 상품을 조회한다. 없으면 None."""
        row = self.session.get(ProductRow, product_id)
        return _product(row) if row is not None else None
