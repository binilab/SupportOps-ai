"""고객지원 에이전트: 질문을 주문 처리와 정책 답변으로 나눠 처리한다.

- 주문 ID(ORD-####)가 없으면 정책 RAG(rag.py)로 넘긴다.
- 주문 ID가 있으면 작은 LLM(라우터)이 get_order 도구 호출과 요청 종류(환불/취소/배송)를 제안한다.
  LLM의 제안은 그대로 믿지 않고 주문 ID와 요청 종류를 코드로 검증한 뒤에만 조회한다.
- 조회는 모두 읽기 전용이고, 환불·취소 가능 여부는 eligibility.py의 규칙이 정한다.
- 답변 문구와 인용 정책은 규칙 판단 결과(reason)에 따라 코드에서 고른다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from ollama import Client

from supportops.eligibility import Assessment, check_cancel_eligibility, check_refund_eligibility, customer_conditions, requires_special_review
from supportops.lexical import PolicyChunk
from supportops.rag import Citation, ORDER_ID_RE, PolicyRAG, RagAnswer
from supportops.structured import Order, OrderProductStore, Product
from supportops.usage import record_usage

MODEL_ID = "qwen2.5:3b"
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# 라우터 LLM에 제공하는 유일한 도구. 모델은 이 도구를 호출할지와 인자만 정하고, 실제 조회는 코드가 한다.
GET_ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_order",
        "description": "Look up an order for a customer-support question. Copy the exact order ID and classify the request.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Exact ORD-#### ID in the question"},
                "intent": {"type": "string", "enum": ["refund", "cancel", "shipping"]},
            },
            "required": ["order_id", "intent"],
        },
    },
}
ROUTER_PROMPT = (
    "주문 질문이면 get_order 도구를 한 번 호출하세요. 질문의 정확한 주문 ID와 "
    "환불(refund), 취소(cancel), 배송 위치(shipping) 중 요청 종류를 전달하세요. "
    "오타가 있어도 의도를 파악하세요. 직접 답하지 말고 도구를 호출하세요."
)


@dataclass(frozen=True)
class ToolRequest:
    """라우터 LLM이 제안한 도구 호출 (검증 전)."""

    name: str
    arguments: dict


@dataclass(frozen=True)
class ToolTrace:
    """실제로 실행한 도구와 결과. API 응답에 그대로 담아 판단 과정을 보여 준다."""

    name: str
    arguments: dict
    result: str


@dataclass(frozen=True)
class AgentResult:
    """에이전트 최종 결과. outcome은 어떤 경로로 끝났는지 나타내는 코드다."""

    answer: str
    abstained: bool
    outcome: str
    router_request: ToolRequest | None
    trace: tuple[ToolTrace, ...]
    citations: tuple[Citation, ...]


class OrderRouter(Protocol):
    """주문 질문의 도구 호출을 고르는 라우터 인터페이스. 테스트에서는 가짜 라우터를 쓴다."""

    def choose(self, question: str) -> ToolRequest | None: ...


class OllamaOrderRouter:
    """Ollama의 tool calling 기능으로 도구 호출을 고르는 라우터."""

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.environ.get("SUPPORTOPS_AGENT_MODEL", MODEL_ID)
        self.client = Client(host=host or os.environ.get("OLLAMA_HOST"), timeout=60)

    def choose(self, question: str) -> ToolRequest | None:
        """모델이 제안한 도구 호출 하나를 읽어 돌려준다.

        호출이 정확히 하나가 아니거나 인자 형식이 이상하면 None을 돌려준다.
        인자 값이 맞는지는 여기서 판단하지 않고 SupportAgent.run에서 검증한다.
        """
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": question}],
            tools=[GET_ORDER_TOOL],
            options={"temperature": 0, "num_predict": 120},
            think=False,
        )
        record_usage(response.prompt_eval_count, response.eval_count)
        calls = response.message.tool_calls or []
        if len(calls) != 1:
            return None
        call = calls[0]
        if not isinstance(call.function.arguments, dict):
            return None
        return ToolRequest(call.function.name, dict(call.function.arguments))


class SupportAgent:
    """질문 하나를 받아 주문 처리 또는 정책 답변으로 처리하는 에이전트."""

    def __init__(
        self,
        store: OrderProductStore,
        router: OrderRouter,
        policy_chunks: list[PolicyChunk],
        policy_rag: PolicyRAG | None = None,
    ) -> None:
        self.store = store
        self.router = router
        self.chunks = {chunk.chunk_id: chunk for chunk in policy_chunks}
        self.policy_rag = policy_rag

    def _citations(self, *chunk_ids: str) -> tuple[Citation, ...]:
        """청크 ID 목록을 인용 객체로 바꾼다. 없는 ID면 KeyError가 나서 오타를 바로 잡을 수 있다."""
        return tuple(
            Citation(self.chunks[item].policy_id, item, self.chunks[item].source_path)
            for item in chunk_ids
        )

    def _policy_result(self, answer: RagAnswer) -> AgentResult:
        """정책 RAG 결과를 에이전트 결과 형식으로 바꾼다."""
        return AgentResult(answer.answer, answer.abstained, answer.reason or "policy_answer", None, (), answer.citations)

    def run(self, question: str, as_of: date | None = None) -> AgentResult:
        """질문을 처리한다.

        주문 질문의 처리 순서
        1. 라우터 LLM이 제안한 도구 호출을 검증한다 (주문 ID가 질문과 같은지, 요청 종류가 허용 값인지).
        2. 주문을 조회하고, 필요하면 상품도 조회한다.
        3. 기준 날짜를 정한다 (질문에 날짜가 있으면 그 날짜, 없으면 as_of, 그것도 없으면 오늘).
        4. 환불·취소 규칙으로 판단하고, 판단 결과에 맞는 답변과 인용을 만든다.
        각 단계의 조회·판단 내역은 trace에 남긴다.
        """
        match = ORDER_ID_RE.search(question)
        if match is None:
            if self.policy_rag is None:
                return AgentResult("주문 ID 또는 정책 질문이 필요합니다.", True, "no_order_id", None, (), ())
            return self._policy_result(self.policy_rag.answer(question))

        requested_id = match.group().upper()
        request = self.router.choose(question)
        # LLM이 주문 ID를 잘못 옮겨 적거나 정의되지 않은 요청 종류를 내면 조회하지 않고 보류한다.
        if (
            request is None
            or request.name != "get_order"
            or request.arguments.get("order_id") != requested_id
            or request.arguments.get("intent") not in {"refund", "cancel", "shipping"}
        ):
            return AgentResult("주문 조회 요청을 검증할 수 없습니다.", True, "invalid_tool_request", request, (), ())

        trace: list[ToolTrace] = []
        order = self.store.get_order(requested_id)
        order_summary = (
            f"status={order.status};product_id={order.product_id};delivered_at={order.delivered_at};"
            f"used={order.used};seal_opened={order.seal_opened};"
            f"custom_production_started={order.custom_production_started};digital_redeemed={order.digital_redeemed}"
            if order else "not_found"
        )
        trace.append(ToolTrace("get_order", {"order_id": requested_id}, order_summary))
        if order is None:
            return AgentResult("해당 주문을 찾을 수 없어 상태를 확인할 수 없습니다.", True, "order_not_found", request, tuple(trace), ())

        intent = request.arguments["intent"]
        # 배송 위치는 송장·택배사 데이터가 없어 확인할 수 없다. 주문 상태만 알려 주고 보류한다.
        if intent == "shipping":
            return AgentResult(
                f"{order.order_id}의 주문 상태는 {order.status}입니다. 송장번호와 택배사 위치 정보가 없어 정확한 현재 위치는 확인할 수 없습니다.",
                True,
                "tracking_unavailable",
                request,
                tuple(trace),
                self._citations("policy_shipping_v1::04"),
            )

        # 상품 정보는 판단에 필요할 때만 조회한다 (환불, 준비 중 주문 취소, 주문제작 확인).
        product: Product | None = None
        if intent == "refund" or order.status == "PREPARING" or order.custom_production_started:
            product = self.store.get_product(order.product_id)
            product_summary = (
                f"is_custom={product.is_custom};is_hygiene={product.is_hygiene};is_digital={product.is_digital}"
                if product else "not_found"
            )
            trace.append(ToolTrace("get_product", {"product_id": order.product_id}, product_summary))
            if product is None:
                return AgentResult("상품 정보를 찾을 수 없어 판단을 보류합니다.", True, "product_not_found", request, tuple(trace), ())

        explicit_date = DATE_RE.search(question)
        try:
            effective_date = date.fromisoformat(explicit_date.group()) if explicit_date else (as_of or date.today())
        except ValueError:
            # 2026-02-30처럼 형식은 맞지만 존재하지 않는 날짜
            return AgentResult("질문의 기준 날짜를 확인할 수 없습니다.", True, "invalid_date", request, tuple(trace), ())
        if intent == "refund":
            assert product is not None
            components, damage = customer_conditions(question)
            special_review = requires_special_review(question)
            assessment = check_refund_eligibility(
                order, product, effective_date,
                components_confirmed=components,
                resale_damage_reported=damage,
                special_review_requested=special_review,
            )
            trace.append(ToolTrace("check_refund_eligibility", {
                "order_id": order.order_id,
                "product_id": product.product_id,
                "as_of": effective_date.isoformat(),
                "components_confirmed": components,
                "resale_damage_reported": damage,
                "special_review_requested": special_review,
            }, assessment.reason))
            return self._refund_result(order, product, assessment, request, trace, question)

        special_review = requires_special_review(question)
        assessment = check_cancel_eligibility(order, product, special_review_requested=special_review)
        trace.append(ToolTrace("check_cancel_eligibility", {"order_id": order.order_id, "special_review_requested": special_review}, assessment.reason))
        return self._cancel_result(order, product, assessment, request, trace)

    def _refund_result(
        self, order: Order, product: Product, assessment: Assessment,
        request: ToolRequest, trace: list[ToolTrace], question: str,
    ) -> AgentResult:
        """환불 판단 결과(reason)별 답변 문구와 근거 정책 청크를 고른다.

        문구를 LLM이 아니라 코드로 만들어서, 규칙 판단과 다른 내용의 답변이 나갈 수 없게 한다.
        """
        prefix = f"{order.order_id} 주문 상품 {product.name}({product.product_id}): "
        delivered = order.delivered_at.isoformat() if order.delivered_at else "미확인"
        hygiene_state = " 위생 상품의 보호 포장도 미개봉입니다." if product.is_hygiene and not order.seal_opened else ""
        components_state = "구성품과 사은품" if "사은품" in question else "구성품"
        use_state = "주문 기록에 사용 이력이 있고 " if order.used else ""
        # reason → (답변 문구, 인용할 정책 청크 ID)
        cases = {
            "refund_request_allowed": (f"배송 완료일이 {delivered}이고 기록상 미사용입니다.{hygiene_state} 질문에서 {components_state} 보존을 전제로 했으며 신청 기간 내이므로 단순 변심 환불 신청이 가능합니다. 최종 환불은 반품 검수 후 진행됩니다.", ("policy_refund_v1::01", "policy_refund_v1::02")),
            "custom_product": ("주문제작 상품이라 단순 변심 환불 신청이 불가합니다.", ("policy_refund_v1::04", "policy_product_restrictions_v1::02")),
            "hygiene_seal_opened": ("위생 상품의 보호 포장이 개봉되어 단순 변심 환불 신청이 불가합니다.", ("policy_refund_v1::04", "policy_product_restrictions_v1::03")),
            "digital_redeemed": ("디지털 코드가 사용되어 단순 변심 환불 신청이 불가합니다.", ("policy_refund_v1::04", "policy_product_restrictions_v1::04")),
            "resale_damage": (f"{use_state}질문에서 착용·오염으로 재판매가 어렵다고 했으므로 단순 변심 환불 신청이 불가합니다.", ("policy_refund_v1::04",)),
            "used_condition_unknown": ("사용 이력이 있지만 재판매 가능 상태는 확인되지 않아 환불 가능 여부를 확정할 수 없습니다.", ("policy_refund_v1::02", "policy_refund_v1::04")),
            "refund_window_expired": ("일반 상품의 7일 환불 신청 기간을 지나 단순 변심 환불 신청이 불가합니다.", ("policy_refund_v1::01",)),
            "refund_window_not_started": ("배송 완료일 다음 날부터 신청 기간이 시작되므로 지금은 환불 가능 여부를 확정할 수 없습니다.", ("policy_refund_v1::01",)),
            "delivery_unknown": ("배송 완료일이 확인되지 않아 환불 신청 기간을 판단할 수 없습니다.", ("policy_refund_v1::01",)),
            "components_unknown": ("구성품·사은품 보존 여부를 확인해야 환불 신청 가능 여부를 판단할 수 있습니다.", ("policy_refund_v1::02",)),
            "confirmed_company_fault": ("회사 귀책이 확인되어 환불 신청이 가능하며 반품 배송비는 MoaShop이 부담합니다.", ("policy_refund_v1::03",)),
            "special_condition_unverified": ("하자·오배송 확인 또는 상품별 개별 조건 검토가 필요해 현재 환불 가능 여부를 확정할 수 없습니다.", ("policy_refund_v1::03", "policy_refund_v1::06")),
        }
        text, chunk_ids = cases[assessment.reason]
        # 위생 상품이 환불 가능하면 위생 상품 제한 조항도 함께 인용한다.
        if assessment.reason == "refund_request_allowed" and product.is_hygiene:
            chunk_ids += ("policy_product_restrictions_v1::03",)
        return AgentResult(prefix + text, assessment.status == "needs_review", assessment.reason, request, tuple(trace), self._citations(*chunk_ids))

    def _cancel_result(
        self, order: Order, product: Product | None, assessment: Assessment,
        request: ToolRequest, trace: list[ToolTrace],
    ) -> AgentResult:
        """취소 판단 결과(reason)별 답변 문구와 근거 정책 청크를 고른다."""
        if assessment.reason == "custom_production_started":
            text = f"{order.order_id}은 주문제작 상품의 제작이 시작되어 일반 취소 요청이 불가합니다."
            chunks = ("policy_cancel_v1::02", "policy_product_restrictions_v1::02")
        elif assessment.reason == "cancel_request_allowed":
            detail = f"{order.order_id}: "
            if product:
                detail += f"상품은 {product.name}({product.product_id})입니다. "
                detail += "주문제작 상품이지만 제작 시작 전입니다. " if product.is_custom else "주문제작 상품이 아닙니다. "
            text = f"{detail}주문 상태는 {order.status}이며 전체 취소 요청이 가능합니다. 실제 취소는 실행하지 않았습니다."
            chunks = ("policy_cancel_v1::01",)
        elif assessment.reason == "already_shipped":
            text = f"{order.order_id}는 {order.status} 상태이므로 일반 취소 대신 반품/환불 절차를 확인해야 합니다."
            chunks = ("policy_cancel_v1::01",)
        elif assessment.reason == "special_condition_unverified":
            text = f"{order.order_id}는 하자·오배송 확인 또는 상품별 개별 조건 검토가 필요해 현재 취소 가능 여부를 확정할 수 없습니다."
            chunks = ("policy_cancel_v1::02", "policy_product_restrictions_v1::01")
        elif assessment.reason == "unknown_order_status":
            text = f"{order.order_id}의 주문 상태 {order.status}는 현재 취소 정책의 상태에 해당하지 않아 판단을 보류합니다."
            chunks = ("policy_cancel_v1::01",)
        else:
            text = f"{order.order_id}의 상품 정보를 확인하지 못해 취소 가능 여부를 판단할 수 없습니다."
            chunks = ("policy_cancel_v1::02",)
        return AgentResult(text, assessment.status == "needs_review", assessment.reason, request, tuple(trace), self._citations(*chunks))
