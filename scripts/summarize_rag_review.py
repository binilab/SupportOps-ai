"""Summarize a manually checked Phase 4 response report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "phase4_rag_local.json"
REVIEW_PATH = ROOT / "reports" / "phase4_review.json"


def main() -> int:
    raw = REPORT_PATH.read_bytes()
    report = json.loads(raw)
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != review["report_sha256"]:
        raise ValueError("Review does not match the response report")

    answered = {case["id"] for case in report["cases"] if case["expected_answer"] and not case["abstained"]}
    expected = {case["id"] for case in report["cases"] if case["expected_answer"]}
    wrong = set(review["incorrect_answer_ids"])
    ungrounded = set(review["ungrounded_ids"])
    bad_citations = set(review["incorrect_citation_ids"])
    if not wrong <= expected or not ungrounded <= answered or not bad_citations <= answered:
        raise ValueError("Review contains an ID outside its scoring population")
    if expected - answered - wrong:
        raise ValueError("Abstained positive cases must be counted as incorrect answers")
    result = {
        "policy_answer_accuracy": (len(expected) - len(wrong)) / len(expected),
        "groundedness_on_answered": (len(answered) - len(ungrounded)) / len(answered),
        "citation_accuracy_on_answered": (len(answered) - len(bad_citations)) / len(answered),
        "answer_count": len(answered),
        "incorrect_answer_ids": sorted(wrong),
        "ungrounded_ids": sorted(ungrounded),
        "incorrect_citation_ids": sorted(bad_citations),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
