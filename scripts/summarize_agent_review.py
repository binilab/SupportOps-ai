"""수동 답변 검수 결과가 에이전트 보고서와 일치하는지 확인하고 사실 정확도를 요약한다.
실행: python3 scripts/summarize_agent_review.py (reports/phase5_agent_local.json, reports/phase5_review.json 사용)"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports/phase5_agent_local.json"
REVIEW_PATH = ROOT / "reports/phase5_review.json"


def main() -> int:
    """검수 파일의 보고서 해시와 케이스 ID를 검증한 뒤 답변 사실 정확도를 출력한다."""
    raw = REPORT_PATH.read_bytes()
    report = json.loads(raw)
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    # 보고서가 검수 이후 바뀌었다면 검수 결과를 그대로 쓸 수 없다.
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
