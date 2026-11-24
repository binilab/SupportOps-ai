"""Gold 데이터의 도구 사용 문항으로 에이전트의 도구 라우팅과 결정론적 판정 결과를 평가한다.
실행: python3 scripts/evaluate_agent.py > reports/phase5_agent_local.json (로컬 Ollama 필요)"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import statistics
import sys
from datetime import date
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.agent import OllamaOrderRouter, SupportAgent  # noqa: E402
from supportops.lexical import load_policy_chunks  # noqa: E402
from supportops.rag import ORDER_ID_RE  # noqa: E402
from supportops.structured import StructuredStore  # noqa: E402

GOLD_PATH = ROOT / "data" / "eval" / "gold_dataset.jsonl"
EXPECTATIONS_PATH = ROOT / "data" / "eval" / "agent_expectations.json"
ORDERS_PATH = ROOT / "data" / "raw" / "structured" / "orders.csv"
PRODUCTS_PATH = ROOT / "data" / "raw" / "structured" / "products.csv"
EVAL_DATE = date(2026, 10, 5)


def main() -> int:
    """도구가 필요한 Gold 문항을 에이전트로 실행하고 정확도와 지연 시간을 담은 보고서를 출력한다."""
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    # 주문 도구가 필요한 문항만 평가 대상으로 삼는다.
    selected = [row for row in rows if row["needs_tool"]]
    expectations = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))
    if {row["id"] for row in selected} != set(expectations):
        raise ValueError("Agent expectations must cover every tool Gold case exactly")
    store = StructuredStore(ORDERS_PATH, PRODUCTS_PATH)
    router = OllamaOrderRouter()
    model_digest = next(item.digest for item in router.client.list().models if item.model == router.model)
    agent = SupportAgent(store, router, load_policy_chunks(ROOT / "data" / "raw" / "policies", ROOT))

    cases = []
    for row in selected:
        started = perf_counter_ns()
        result = agent.run(row["question"], EVAL_DATE)
        expected = expectations[row["id"]]
        match = ORDER_ID_RE.search(row["question"])
        if match is None:
            raise ValueError(f"Missing order ID in {row['id']}")
        order_id = match.group().upper()
        tool_names = [item.name for item in result.trace]
        request = result.router_request
        # 라우터의 첫 호출이 get_order여야 정답으로 본다.
        initial_correct = request is not None and request.name == "get_order"
        # 첫 요청과 이후 도구 호출 인자가 모두 기대한 주문/상품을 가리키는지 검사한다.
        arguments_correct = (
            initial_correct
            and request.arguments.get("order_id") == order_id
            and request.arguments.get("intent") == expected["intent"]
            and all(
                item.arguments.get("order_id") == order_id
                for item in result.trace if item.name in {"get_order", "check_refund_eligibility", "check_cancel_eligibility"}
            )
            and all(
                item.arguments.get("product_id") == store.get_order(order_id).product_id
                for item in result.trace if item.name == "get_product"
            )
        )
        case = {
            "id": row["id"],
            "question": row["question"],
            "expected_tools": row["expected_tools"],
            "expected_intent": expected["intent"],
            "expected_outcome": expected["outcome"],
            "expected_answerable": row["answerable"],
            "expected_facts": row["expected_facts"],
            "router_request": request.__dict__ if request else None,
            "trace": [item.__dict__ for item in result.trace],
            "answer": result.answer,
            "abstained": result.abstained,
            "outcome": result.outcome,
            "citations": [item.__dict__ for item in result.citations],
            "initial_tool_correct": initial_correct,
            "arguments_correct": arguments_correct,
            "tool_sequence_correct": tool_names == row["expected_tools"],
            "outcome_correct": result.outcome == expected["outcome"],
            "abstention_correct": result.abstained == (not row["answerable"]),
            "latency_ms": (perf_counter_ns() - started) / 1_000_000,
        }
        case["workflow_success"] = all(
            case[key]
            for key in ("initial_tool_correct", "arguments_correct", "tool_sequence_correct", "outcome_correct", "abstention_correct")
        )
        cases.append(case)
    # p95는 정렬된 지연 시간에서 nearest-rank 방식으로 고른다.
    latencies = sorted(case["latency_ms"] for case in cases)
    # 정책 문서 내용이 바뀌면 보고서와 대조할 수 있도록 코퍼스 해시를 남긴다.
    policy_digest = hashlib.sha256()
    for path in sorted((ROOT / "data/raw/policies").glob("*.md")):
        policy_digest.update(path.name.encode("utf-8"))
        policy_digest.update(b"\0")
        policy_digest.update(path.read_bytes())
        policy_digest.update(b"\0")
    report = {
        "model": router.model,
        "model_digest": model_digest,
        "ollama_python_version": importlib.metadata.version("ollama"),
        "evaluation_date": EVAL_DATE.isoformat(),
        "gold_sha256": hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest(),
        "policy_corpus_sha256": policy_digest.hexdigest(),
        "agent_expectations_sha256": hashlib.sha256(EXPECTATIONS_PATH.read_bytes()).hexdigest(),
        "orders_sha256": hashlib.sha256(ORDERS_PATH.read_bytes()).hexdigest(),
        "products_sha256": hashlib.sha256(PRODUCTS_PATH.read_bytes()).hexdigest(),
        "case_count": len(cases),
        "initial_tool_accuracy": sum(case["initial_tool_correct"] for case in cases) / len(cases),
        "argument_accuracy": sum(case["arguments_correct"] for case in cases) / len(cases),
        "tool_sequence_accuracy": sum(case["tool_sequence_correct"] for case in cases) / len(cases),
        "outcome_accuracy": sum(case["outcome_correct"] for case in cases) / len(cases),
        "abstention_accuracy": sum(case["abstention_correct"] for case in cases) / len(cases),
        "workflow_success_rate": sum(case["workflow_success"] for case in cases) / len(cases),
        "latency_ms_median": statistics.median(latencies),
        "latency_ms_p95": latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)],
        "cases": cases,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
