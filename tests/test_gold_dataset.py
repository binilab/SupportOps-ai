from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_gold_dataset.py"

spec = importlib.util.spec_from_file_location("validate_gold_dataset", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_gold_dataset_schema_and_policy_references() -> None:
    rows = module.read_jsonl(module.GOLD_PATH)
    policy_ids = module.collect_policy_ids(module.POLICY_DIR)
    errors = module.validate(rows, policy_ids)

    assert len(rows) >= 30
    assert not errors, "\n".join(errors)


def test_seed_data_ids_are_unique() -> None:
    with module.ORDERS_PATH.open(encoding="utf-8", newline="") as handle:
        orders = list(csv.DictReader(handle))
    with module.PRODUCTS_PATH.open(encoding="utf-8", newline="") as handle:
        products = list(csv.DictReader(handle))

    order_ids = {row["order_id"] for row in orders}
    product_ids = {row["product_id"] for row in products}

    assert len(order_ids) == len(orders) == 10
    assert len(product_ids) == len(products) == 10
    assert all(row["product_id"] in product_ids for row in orders)
