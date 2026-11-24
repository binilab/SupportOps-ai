"""버전 관리되는 합성 CSV(주문, 상품)를 PostgreSQL에 명시적으로 적재하고 일치 여부를 검증한다.
실행: SUPPORTOPS_DATABASE_URL=postgresql+psycopg://... python scripts/init_database.py"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.database import make_engine, seed_demo_data  # noqa: E402


def main() -> int:
    """DB 연결 정보를 확인한 뒤 CSV 데이터를 적재하고 확인된 주문/상품 수를 출력한다."""
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
