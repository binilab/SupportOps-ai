"""Gold 데이터셋 검증 스크립트(scripts/validate_gold_dataset.py)를 불러와 데이터 정합성을 테스트한다."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_gold_dataset.py"

# scripts는 패키지가 아니므로 파일 경로로 직접 모듈을 불러온다.
spec = importlib.util.spec_from_file_location("validate_gold_dataset", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_gold_dataset_schema_and_policy_references() -> None:
    """Gold 데이터가 스키마를 지키고 존재하는 정책 ID만 참조하는지 확인한다."""
    rows = module.read_jsonl(module.GOLD_PATH)
    policy_ids = module.collect_policy_ids(module.POLICY_DIR)
    errors = module.validate(rows, policy_ids)

    assert len(rows) >= 30
    assert not errors, "\n".join(errors)


def test_seed_data_ids_are_unique() -> None:
    """주문/상품 시드의 ID가 중복되지 않고 주문이 실제 상품을 참조하는지 확인한다."""
    with module.ORDERS_PATH.open(encoding="utf-8", newline="") as handle:
        orders = list(csv.DictReader(handle))
    with module.PRODUCTS_PATH.open(encoding="utf-8", newline="") as handle:
        products = list(csv.DictReader(handle))

    order_ids = {row["order_id"] for row in orders}
    product_ids = {row["product_id"] for row in products}

    assert len(order_ids) == len(orders) == 10
    assert len(product_ids) == len(products) == 10
    assert all(row["product_id"] in product_ids for row in orders)
