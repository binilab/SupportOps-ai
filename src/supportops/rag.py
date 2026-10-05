"""Phase 4 policy-only grounded answer generation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol

from ollama import Client

from supportops.lexical import PolicyChunk, PolicyHit

ORDER_ID_RE = re.compile(r"\bORD-\d+\b", re.IGNORECASE)
PERSONAL_CONTACT_RE = re.compile(r"(?:직원|타인|다른\s*사람).*?(?:개인|사적).*?(?:연락처|휴대폰|전화번호|이메일)")
PERSONAL_COUPON_AMOUNT_RE = re.compile(r"(?:내|나의).*?쿠폰.*?(?:최소.*?금액|금액.*?얼마|얼마)")
MODEL_ID = "gemma4:12b"
RETRIEVAL_K = 3
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "abstain": {"type": "boolean"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "abstain", "evidence_ids"],
}
SYSTEM_PROMPT = """당신은 MoaShop 고객지원 상담 보조입니다.
제공한 정책 근거만 사용해 질문의 핵심에 한국어로 간결하게 답하세요. 필요하면 3문장까지 작성하세요.
구체적 예외와 개별 조건은 일반 규칙보다 우선합니다. 질문의 상품 종류, 단순 변심/회사 귀책, 기간, 상태를 먼저 구분하세요.
특히 단순 변심과 회사 귀책의 배송비 규칙을 섞지 마세요. 숫자, 기한, 기본 배송비와 추가 배송비를 정확히 구별하세요.
환불/교환 가능 여부에는 신청 기간뿐 아니라 상품 상태·구성품 등의 필요한 조건도 설명하세요.
조건이 모두 확인되지 않았으면 가능 여부를 확정하지 말고 조건부로 설명하세요.
개별 주문/쿠폰의 실제 상태, 미래 사건, 정책 밖 요청은 제공한 근거만으로 확인할 수 없습니다.
근거가 없거나 질문의 핵심을 확인할 수 없으면 abstain=true, answer에 부족한 정보를 적고 evidence_ids=[]로 답하세요.
답할 때는 사용한 근거의 청크 ID만 evidence_ids에 넣으세요. 주어지지 않은 ID를 만들지 마세요. answer에는 ID나 JSON 필드명을 쓰지 마세요.
JSON 형식으로만 답하세요."""


@dataclass(frozen=True)
class Citation:
    policy_id: str
    chunk_id: str
    source_path: str


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    abstained: bool
    citations: tuple[Citation, ...]
    reason: str | None = None


class PolicyRetriever(Protocol):
    chunks: list[PolicyChunk]

    def search(self, query: str, k: int = 5) -> list[PolicyHit]: ...


class AnswerModel(Protocol):
    def generate(self, question: str, evidence: list[PolicyChunk]) -> dict: ...


class OllamaAnswerModel:
    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.environ.get("SUPPORTOPS_RAG_MODEL", MODEL_ID)
        self.client = Client(host=host or os.environ.get("OLLAMA_HOST"), timeout=120)

    def generate(self, question: str, evidence: list[PolicyChunk]) -> dict:
        """Request a short structured answer from the local Ollama model."""
        context = "\n\n".join(
            f"[청크 ID: {chunk.chunk_id}; 정책 ID: {chunk.policy_id}; {chunk.title} / {chunk.heading}]\n{chunk.text}"
            for chunk in evidence
        )
        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"정책 근거:\n{context}\n\n질문: {question}"},
            ],
            format=ANSWER_SCHEMA,
            options={"temperature": 0, "num_predict": 180},
            think=False,
        )
        try:
            return json.loads(response.message.content)
        except json.JSONDecodeError:
            return {}


class PolicyRAG:
    def __init__(self, retriever: PolicyRetriever, model: AnswerModel) -> None:
        self.retriever = retriever
        self.model = model
        self.chunks_by_policy: dict[str, list[PolicyChunk]] = {}
        for chunk in retriever.chunks:
            self.chunks_by_policy.setdefault(chunk.policy_id, []).append(chunk)

    def answer(self, question: str) -> RagAnswer:
        """Retrieve policy evidence, generate, and validate citations before returning."""
        if not question.strip():
            return RagAnswer("질문을 입력해 주세요.", True, (), "empty_question")
        if ORDER_ID_RE.search(question):
            return RagAnswer("주문 정보를 조회할 수 없어 해당 주문 상태를 확인할 수 없습니다.", True, (), "requires_order_data")
        if PERSONAL_CONTACT_RE.search(question):
            return RagAnswer("개인 연락처는 제공할 수 없습니다.", True, (), "out_of_scope_personal_contact")
        if PERSONAL_COUPON_AMOUNT_RE.search(question):
            return RagAnswer("개별 쿠폰 발급 정보를 조회할 수 없어 금액을 확인할 수 없습니다.", True, (), "requires_coupon_data")

        hits = self.retriever.search(question, RETRIEVAL_K)
        evidence = [
            chunk
            for hit in hits
            for chunk in sorted(
                self.chunks_by_policy[hit.policy_id],
                key=lambda item: (item.chunk_id != hit.chunk_id, item.chunk_id),
            )
        ]
        if not evidence:
            return RagAnswer("관련 정책 근거를 찾지 못했습니다.", True, (), "no_evidence")

        output = self.model.generate(question, evidence)
        if not isinstance(output, dict) or not isinstance(output.get("answer"), str):
            return RagAnswer("답변 형식을 확인할 수 없습니다.", True, (), "invalid_model_output")
        if not isinstance(output.get("abstain"), bool) or not isinstance(output.get("evidence_ids"), list):
            return RagAnswer("답변 형식을 확인할 수 없습니다.", True, (), "invalid_model_output")
        if output["abstain"]:
            return RagAnswer("제공된 정책 근거만으로 질문의 핵심을 확인할 수 없습니다.", True, (), "model_abstained")

        chunks_by_id = {chunk.chunk_id: chunk for chunk in evidence}
        ids = output["evidence_ids"]
        if (
            not output["answer"].strip()
            or not ids
            or any(not isinstance(item, str) or item not in chunks_by_id for item in ids)
        ):
            return RagAnswer("검증 가능한 정책 인용이 없어 답변을 보류합니다.", True, (), "invalid_citation")
        citations = tuple(
            Citation(chunks_by_id[item].policy_id, item, chunks_by_id[item].source_path)
            for item in dict.fromkeys(ids)
        )
        return RagAnswer(output["answer"].strip(), False, citations)
