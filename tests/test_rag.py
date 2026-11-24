"""PolicyRAG의 근거 인용 검증과 보류(abstain) 경로를 가짜 검색기/모델로 테스트한다."""

from __future__ import annotations

from supportops.lexical import PolicyChunk, PolicyHit
from supportops.rag import PolicyRAG


CHUNK = PolicyChunk("policy_shipping_v1::02", "policy_shipping_v1", "shipping.md", "배송", "배송비", "제주는 추가 배송비 3,000원")


class FakeRetriever:
    """항상 같은 청크 하나를 반환하는 가짜 검색기."""
    chunks = [CHUNK]

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        """질의와 무관하게 고정 청크의 검색 결과를 반환한다."""
        return [PolicyHit(CHUNK.policy_id, CHUNK.chunk_id, CHUNK.source_path, 1.0)]


class FakeModel:
    """미리 정한 응답을 반환하고 호출 횟수를 세는 가짜 답변 모델."""
    def __init__(self, response: dict) -> None:
        """반환할 응답을 저장하고 호출 횟수를 0으로 초기화한다."""
        self.response = response
        self.calls = 0

    def generate(self, question: str, evidence: list[PolicyChunk]) -> dict:
        """근거가 검색된 청크와 같은지 확인하고 고정 응답을 반환한다."""
        self.calls += 1
        assert evidence == [CHUNK]
        return self.response


def test_policy_answer_has_valid_source_citation() -> None:
    """유효한 청크 ID를 인용한 답변은 출처가 붙고 중복 인용은 하나로 합쳐지는지 확인한다."""
    model = FakeModel({"answer": "제주는 추가 배송비 3,000원이 붙습니다.", "abstain": False, "evidence_ids": [CHUNK.chunk_id, CHUNK.chunk_id]})
    answer = PolicyRAG(FakeRetriever(), model).answer("제주 추가 배송비는?")

    assert not answer.abstained
    assert answer.citations[0].policy_id == CHUNK.policy_id
    assert answer.citations[0].source_path == "shipping.md"
    assert len(answer.citations) == 1


def test_order_question_abstains_before_model_call() -> None:
    """주문 ID가 있는 질문은 모델을 호출하지 않고 주문 데이터 필요로 보류하는지 확인한다."""
    model = FakeModel({"answer": "가능", "abstain": False, "evidence_ids": [CHUNK.chunk_id]})
    answer = PolicyRAG(FakeRetriever(), model).answer("ORD-1001 환불 가능해?")

    assert answer.abstained and answer.reason == "requires_order_data"
    assert answer.citations == ()
    assert model.calls == 0


def test_missing_personal_data_abstains_before_model_call() -> None:
    """개인 연락처나 쿠폰 정보처럼 정책 문서에 없는 질문은 모델 호출 전에 보류하는지 확인한다."""
    model = FakeModel({"answer": "제공", "abstain": False, "evidence_ids": [CHUNK.chunk_id]})
    rag = PolicyRAG(FakeRetriever(), model)

    assert rag.answer("직원 김민수 개인 휴대폰 번호 알려줘").reason == "out_of_scope_personal_contact"
    assert rag.answer("내 쿠폰의 최소 주문 금액이 얼마야?").reason == "requires_coupon_data"
    assert model.calls == 0


def test_missing_or_untrusted_citation_abstains() -> None:
    """인용이 없거나 검색되지 않은 ID, 잘못된 타입이면 답변을 버리고 보류하는지 확인한다."""
    for output in [
        {"answer": "가능", "abstain": False, "evidence_ids": []},
        {"answer": "가능", "abstain": False, "evidence_ids": ["made-up"]},
        {"answer": "가능", "abstain": False, "evidence_ids": [1]},
    ]:
        answer = PolicyRAG(FakeRetriever(), FakeModel(output)).answer("배송비는?")
        assert answer.abstained and answer.reason == "invalid_citation"
        assert answer.citations == ()


def test_model_abstention_and_empty_question() -> None:
    """모델이 스스로 보류한 경우와 빈 질문의 사유가 올바르고, 빈 질문에는 모델을 호출하지 않는지 확인한다."""
    model = FakeModel({"answer": "근거가 부족합니다.", "abstain": True, "evidence_ids": []})
    rag = PolicyRAG(FakeRetriever(), model)

    assert rag.answer("없는 정보?").reason == "model_abstained"
    assert rag.answer("  ").reason == "empty_question"
    assert model.calls == 1


def test_invalid_model_shape_abstains() -> None:
    """필수 필드가 빠진 모델 출력은 보류 처리하는지 확인한다."""
    answer = PolicyRAG(FakeRetriever(), FakeModel({"answer": "unsupported"})).answer("배송비는?")
    assert answer.abstained and answer.reason == "invalid_model_output"


def test_no_retrieved_evidence_abstains() -> None:
    """검색된 근거가 없으면 모델을 호출하지 않고 보류하는지 확인한다."""
    class EmptyRetriever(FakeRetriever):
        """검색 결과가 항상 비어 있는 가짜 검색기."""
        def search(self, query: str, k: int = 5) -> list[PolicyHit]:
            """검색 결과가 없는 상황을 흉내 내기 위해 빈 목록을 반환한다."""
            return []

    model = FakeModel({"answer": "unsupported", "abstain": False, "evidence_ids": [CHUNK.chunk_id]})
    answer = PolicyRAG(EmptyRetriever(), model).answer("배송비는?")
    assert answer.abstained and answer.reason == "no_evidence"
    assert model.calls == 0
