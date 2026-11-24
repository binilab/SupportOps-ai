"""정책 질문에 근거 기반 답변을 만든다 (RAG).

흐름: 범위 밖 질문 거르기 → 정책 검색 → LLM 답변 생성 → 인용 검증.
LLM이 근거로 받은 청크 ID만 인용할 수 있고, 형식이 틀리거나 인용이 맞지 않으면
답변을 내보내지 않고 보류(abstain)한다. 틀린 답보다 "확인할 수 없다"가 낫다는 원칙이다.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol

from ollama import Client

from supportops.lexical import PolicyChunk, PolicyHit
from supportops.usage import record_usage

ORDER_ID_RE = re.compile(r"\bORD-\d+\b", re.IGNORECASE)
# 정책 문서로 답할 수 없는 질문 유형. LLM에 보내기 전에 규칙으로 먼저 거른다.
PERSONAL_CONTACT_RE = re.compile(r"(?:직원|타인|다른\s*사람).*?(?:개인|사적).*?(?:연락처|휴대폰|전화번호|이메일)")
PERSONAL_COUPON_AMOUNT_RE = re.compile(r"(?:내|나의).*?쿠폰.*?(?:최소.*?금액|금액.*?얼마|얼마)")
MODEL_ID = "gemma4:12b"
RETRIEVAL_K = 3
# Ollama의 structured output 기능으로 이 JSON 형식을 강제한다.
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
    """답변에 붙는 인용 한 건. 원문 파일과 섹션까지 추적할 수 있다."""

    policy_id: str
    chunk_id: str
    source_path: str


@dataclass(frozen=True)
class RagAnswer:
    """RAG 결과. 보류했으면 abstained=True이고 reason에 이유 코드가 들어간다."""

    answer: str
    abstained: bool
    citations: tuple[Citation, ...]
    reason: str | None = None


class PolicyRetriever(Protocol):
    """정책 검색기 인터페이스 (BM25, 임베딩, 하이브리드 모두 해당)."""

    chunks: list[PolicyChunk]

    def search(self, query: str, k: int = 5) -> list[PolicyHit]: ...


class AnswerModel(Protocol):
    """답변 생성 모델 인터페이스. 테스트에서는 가짜 모델로 바꿔 끼운다."""

    def generate(self, question: str, evidence: list[PolicyChunk]) -> dict: ...


class OllamaAnswerModel:
    """로컬 Ollama 모델로 답변을 생성한다. 모델과 주소는 환경 변수로 바꿀 수 있다."""

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.environ.get("SUPPORTOPS_RAG_MODEL", MODEL_ID)
        self.client = Client(host=host or os.environ.get("OLLAMA_HOST"), timeout=120)

    def generate(self, question: str, evidence: list[PolicyChunk]) -> dict:
        """근거 청크와 질문을 넣어 JSON 형식의 짧은 답변을 받는다.

        재현성을 위해 temperature=0으로 고정한다. JSON 파싱에 실패하면 빈 dict를 돌려주고,
        호출한 쪽(PolicyRAG)에서 형식 오류로 보고 답변을 보류한다.
        """
        # 청크마다 ID를 붙여서 넘겨야 모델이 어떤 근거를 썼는지 ID로 답할 수 있다.
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
        record_usage(response.prompt_eval_count, response.eval_count)
        try:
            return json.loads(response.message.content)
        except json.JSONDecodeError:
            return {}


class PolicyRAG:
    """정책 검색 + 답변 생성 + 인용 검증을 묶은 파이프라인."""

    def __init__(self, retriever: PolicyRetriever, model: AnswerModel) -> None:
        self.retriever = retriever
        self.model = model
        self.chunks_by_policy: dict[str, list[PolicyChunk]] = {}
        for chunk in retriever.chunks:
            self.chunks_by_policy.setdefault(chunk.policy_id, []).append(chunk)

    def answer(self, question: str) -> RagAnswer:
        """정책 질문에 답한다. 아래 경우에는 답변 대신 보류 결과를 돌려준다.

        - 주문 ID가 있거나 개인 연락처·개별 쿠폰처럼 정책 문서로 알 수 없는 질문
        - 검색된 근거가 없을 때
        - 모델 출력 형식이 틀렸거나 모델이 스스로 보류했을 때
        - 인용한 청크 ID가 실제로 넘겨준 근거에 없을 때
        """
        if not question.strip():
            return RagAnswer("질문을 입력해 주세요.", True, (), "empty_question")
        if ORDER_ID_RE.search(question):
            return RagAnswer("주문 정보를 조회할 수 없어 해당 주문 상태를 확인할 수 없습니다.", True, (), "requires_order_data")
        if PERSONAL_CONTACT_RE.search(question):
            return RagAnswer("개인 연락처는 제공할 수 없습니다.", True, (), "out_of_scope_personal_contact")
        if PERSONAL_COUPON_AMOUNT_RE.search(question):
            return RagAnswer("개별 쿠폰 발급 정보를 조회할 수 없어 금액을 확인할 수 없습니다.", True, (), "requires_coupon_data")

        hits = self.retriever.search(question, RETRIEVAL_K)
        # 검색된 정책의 청크를 모두 근거로 넘기되, 검색에서 가장 잘 맞은 청크를 맨 앞에 둔다.
        # 정책 하나의 예외 조항이 다른 섹션에 있는 경우가 많아 청크 하나만 넘기면 답이 틀리기 쉽다.
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

        # 인용 검증: 모델이 만들어 낸 ID나 넘겨주지 않은 청크를 인용하면 답변 전체를 보류한다.
        chunks_by_id = {chunk.chunk_id: chunk for chunk in evidence}
        ids = output["evidence_ids"]
        if (
            not output["answer"].strip()
            or not ids
            or any(not isinstance(item, str) or item not in chunks_by_id for item in ids)
        ):
            return RagAnswer("검증 가능한 정책 인용이 없어 답변을 보류합니다.", True, (), "invalid_citation")
        # dict.fromkeys로 순서를 유지하면서 중복 인용을 없앤다.
        citations = tuple(
            Citation(chunks_by_id[item].policy_id, item, chunks_by_id[item].source_path)
            for item in dict.fromkeys(ids)
        )
        return RagAnswer(output["answer"].strip(), False, citations)
