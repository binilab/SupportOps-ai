from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = ROOT / "data" / "eval" / "gold_dataset.jsonl"
POLICY_DIR = ROOT / "data" / "raw" / "policies"
ORDERS_PATH = ROOT / "data" / "raw" / "structured" / "orders.csv"
PRODUCTS_PATH = ROOT / "data" / "raw" / "structured" / "products.csv"

REQUIRED_KEYS = {
    "id",
    "question",
    "category",
    "expected_policy_ids",
    "expected_facts",
    "needs_tool",
    "expected_tools",
    "answerable",
    "notes",
}


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {exc}") from exc
    return rows


def collect_policy_ids(policy_dir: Path) -> set[str]:
    policy_ids: set[str] = set()
    for path in policy_dir.glob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(("Policy ID:", "정책 ID:")):
                policy_ids.add(line.split("`", 2)[1])
                break
    return policy_ids


def collect_csv_ids(path: Path, id_column: str) -> set[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row[id_column] for row in csv.DictReader(handle)}


def validate(rows: list[dict], policy_ids: set[str]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for index, row in enumerate(rows, start=1):
        missing = REQUIRED_KEYS - row.keys()
        if missing:
            errors.append(f"row {index}: missing keys {sorted(missing)}")
            continue

        item_id = row["id"]
        if item_id in seen_ids:
            errors.append(f"row {index}: duplicate id {item_id}")
        seen_ids.add(item_id)

        if not isinstance(row["question"], str) or not row["question"].strip():
            errors.append(f"{item_id}: question must be a non-empty string")

        if not isinstance(row["expected_policy_ids"], list):
            errors.append(f"{item_id}: expected_policy_ids must be a list")
        else:
            unknown = set(row["expected_policy_ids"]) - policy_ids
            if unknown:
                errors.append(f"{item_id}: unknown policy ids {sorted(unknown)}")

        if not isinstance(row["expected_facts"], list) or not row["expected_facts"]:
            errors.append(f"{item_id}: expected_facts must be a non-empty list")

        if not isinstance(row["needs_tool"], bool):
            errors.append(f"{item_id}: needs_tool must be bool")

        if not isinstance(row["expected_tools"], list):
            errors.append(f"{item_id}: expected_tools must be a list")
        elif row["needs_tool"] and not row["expected_tools"]:
            errors.append(f"{item_id}: needs_tool=true but expected_tools is empty")

        if not isinstance(row["answerable"], bool):
            errors.append(f"{item_id}: answerable must be bool")

    return errors


def main() -> int:
    rows = read_jsonl(GOLD_PATH)
    policy_ids = collect_policy_ids(POLICY_DIR)
    order_ids = collect_csv_ids(ORDERS_PATH, "order_id")
    product_ids = collect_csv_ids(PRODUCTS_PATH, "product_id")
    errors = validate(rows, policy_ids)

    print(f"Gold examples: {len(rows)}")
    print(f"Policy IDs: {len(policy_ids)}")
    print(f"Order IDs: {len(order_ids)}")
    print(f"Product IDs: {len(product_ids)}")

    if errors:
        print("\nValidation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\nValidation PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
