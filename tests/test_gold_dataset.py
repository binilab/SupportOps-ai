from __future__ import annotations

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

    assert len(rows) >= 20
    assert not errors, "\n".join(errors)


def test_seed_data_ids_are_unique() -> None:
    order_ids = module.collect_csv_ids(module.ORDERS_PATH, "order_id")
    product_ids = module.collect_csv_ids(module.PRODUCTS_PATH, "product_id")

    assert len(order_ids) == 10
    assert len(product_ids) == 10
