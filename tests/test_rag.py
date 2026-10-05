from __future__ import annotations

from supportops.lexical import PolicyChunk, PolicyHit
from supportops.rag import PolicyRAG


CHUNK = PolicyChunk("policy_shipping_v1::02", "policy_shipping_v1", "shipping.md", "배송", "배송비", "제주는 추가 배송비 3,000원")


class FakeRetriever:
    chunks = [CHUNK]

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        return [PolicyHit(CHUNK.policy_id, CHUNK.chunk_id, CHUNK.source_path, 1.0)]


class FakeModel:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls = 0

    def generate(self, question: str, evidence: list[PolicyChunk]) -> dict:
        self.calls += 1
        assert evidence == [CHUNK]
        return self.response


def test_policy_answer_has_valid_source_citation() -> None:
    model = FakeModel({"answer": "제주는 추가 배송비 3,000원이 붙습니다.", "abstain": False, "evidence_ids": [CHUNK.chunk_id, CHUNK.chunk_id]})
    answer = PolicyRAG(FakeRetriever(), model).answer("제주 추가 배송비는?")

    assert not answer.abstained
    assert answer.citations[0].policy_id == CHUNK.policy_id
    assert answer.citations[0].source_path == "shipping.md"
    assert len(answer.citations) == 1


def test_order_question_abstains_before_model_call() -> None:
    model = FakeModel({"answer": "가능", "abstain": False, "evidence_ids": [CHUNK.chunk_id]})
    answer = PolicyRAG(FakeRetriever(), model).answer("ORD-1001 환불 가능해?")

    assert answer.abstained and answer.reason == "requires_order_data"
    assert answer.citations == ()
    assert model.calls == 0


def test_missing_personal_data_abstains_before_model_call() -> None:
    model = FakeModel({"answer": "제공", "abstain": False, "evidence_ids": [CHUNK.chunk_id]})
    rag = PolicyRAG(FakeRetriever(), model)

    assert rag.answer("직원 김민수 개인 휴대폰 번호 알려줘").reason == "out_of_scope_personal_contact"
    assert rag.answer("내 쿠폰의 최소 주문 금액이 얼마야?").reason == "requires_coupon_data"
    assert model.calls == 0


def test_missing_or_untrusted_citation_abstains() -> None:
    for output in [
        {"answer": "가능", "abstain": False, "evidence_ids": []},
        {"answer": "가능", "abstain": False, "evidence_ids": ["made-up"]},
        {"answer": "가능", "abstain": False, "evidence_ids": [1]},
    ]:
        answer = PolicyRAG(FakeRetriever(), FakeModel(output)).answer("배송비는?")
        assert answer.abstained and answer.reason == "invalid_citation"
        assert answer.citations == ()


def test_model_abstention_and_empty_question() -> None:
    model = FakeModel({"answer": "근거가 부족합니다.", "abstain": True, "evidence_ids": []})
    rag = PolicyRAG(FakeRetriever(), model)

    assert rag.answer("없는 정보?").reason == "model_abstained"
    assert rag.answer("  ").reason == "empty_question"
    assert model.calls == 1


def test_invalid_model_shape_abstains() -> None:
    answer = PolicyRAG(FakeRetriever(), FakeModel({"answer": "unsupported"})).answer("배송비는?")
    assert answer.abstained and answer.reason == "invalid_model_output"


def test_no_retrieved_evidence_abstains() -> None:
    class EmptyRetriever(FakeRetriever):
        def search(self, query: str, k: int = 5) -> list[PolicyHit]:
            return []

    model = FakeModel({"answer": "unsupported", "abstain": False, "evidence_ids": [CHUNK.chunk_id]})
    answer = PolicyRAG(EmptyRetriever(), model).answer("배송비는?")
    assert answer.abstained and answer.reason == "no_evidence"
    assert model.calls == 0
