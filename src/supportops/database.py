"""PostgreSQL storage for the synthetic read-only support records."""

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
    __tablename__ = "support_products"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_hygiene: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_digital: Mapped[bool] = mapped_column(Boolean, nullable=False)


class OrderRow(Base):
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
    """Build a PostgreSQL engine without opening a connection yet."""
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not database_url.startswith("postgresql+psycopg://"):
        raise ValueError("SUPPORTOPS_DATABASE_URL must use postgresql:// or postgresql+psycopg://")
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def seed_demo_data(engine: Engine, orders_path: Path, products_path: Path) -> tuple[int, int]:
    """Create schema and insert CSV demo rows; reject drift on repeated imports."""
    source = StructuredStore(orders_path, products_path)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        for product in source.products.values():
            existing = session.get(ProductRow, product.product_id)
            if existing is None:
                session.add(ProductRow(**vars(product)))
            elif _product(existing) != product:
                raise ValueError(f"Database product differs from CSV: {product.product_id}")
        session.flush()
        for order in source.orders.values():
            existing = session.get(OrderRow, order.order_id)
            if existing is None:
                session.add(OrderRow(**vars(order)))
            elif _order(existing) != order:
                raise ValueError(f"Database order differs from CSV: {order.order_id}")
    return len(source.orders), len(source.products)


def _order(row: OrderRow) -> Order:
    return Order(
        row.order_id, row.product_id, row.status, row.delivered_at,
        row.used, row.seal_opened, row.custom_production_started, row.digital_redeemed,
    )


def _product(row: ProductRow) -> Product:
    return Product(row.product_id, row.name, row.is_custom, row.is_hygiene, row.is_digital)


class SQLAlchemyStructuredStore:
    """Read one order or product by primary key within the request session."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_order(self, order_id: str) -> Order | None:
        row = self.session.get(OrderRow, order_id)
        return _order(row) if row is not None else None

    def get_product(self, product_id: str) -> Product | None:
        row = self.session.get(ProductRow, product_id)
        return _product(row) if row is not None else None
