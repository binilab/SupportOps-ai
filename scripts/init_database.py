"""Explicitly import the versioned synthetic CSV records into PostgreSQL."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.database import make_engine, seed_demo_data  # noqa: E402


def main() -> int:
    database_url = os.environ.get("SUPPORTOPS_DATABASE_URL")
    if not database_url:
        print("Set SUPPORTOPS_DATABASE_URL to a postgresql+psycopg:// URL", file=sys.stderr)
        return 2
    engine = make_engine(database_url)
    try:
        orders, products = seed_demo_data(
            engine, ROOT / "data/raw/structured/orders.csv", ROOT / "data/raw/structured/products.csv"
        )
    finally:
        engine.dispose()
    print(f"Verified {orders} orders and {products} products in PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
