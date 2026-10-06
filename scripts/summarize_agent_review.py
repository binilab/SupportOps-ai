"""Verify the Phase 5 manual answer review matches its response report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports/phase5_agent_local.json"
REVIEW_PATH = ROOT / "reports/phase5_review.json"


def main() -> int:
    raw = REPORT_PATH.read_bytes()
    report = json.loads(raw)
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != review["report_sha256"]:
        raise ValueError("Review does not match the agent report")
    case_ids = {case["id"] for case in report["cases"]}
    incorrect = set(review["incorrect_answer_ids"])
    if not incorrect <= case_ids:
        raise ValueError("Review contains an unknown case ID")
    print(json.dumps({
        "reviewed_case_count": len(case_ids),
        "answer_fact_accuracy": (len(case_ids) - len(incorrect)) / len(case_ids),
        "incorrect_answer_ids": sorted(incorrect),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
