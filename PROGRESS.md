# PROGRESS

## 현재 단계
**Phase 0 — 문제 정의, 데이터 계약, Gold 평가셋**

## 현재 상태
정책/상품/주문 참조와 Gold 정답의 모순을 점검하고 Gold를 35개로 확장했다. 검색/RAG/Agent 구현은 아직 시작하지 않았다. Phase 0의 사용자 비즈니스 규칙 검토가 남아 있다.

## 완료한 항목
- [x] 프로젝트 범위 정의
- [x] 저장소/Codex 작업 규칙 정의
- [x] MoaShop 정책 초기 데이터 추가
- [x] 상품/주문 초기 데이터 추가
- [x] Gold 평가 예시 35개 확보 (답변 가능 29개, 답변 불가 6개; Tool 필요 11개)
- [x] Gold JSONL 검증기 및 테스트 추가
- [x] 주문 10개의 상품 참조 유효성 확인, Gold의 존재하지 않는 주문 `ORD-9999`는 의도적 거부 사례로 확인
- [x] 주문 위치 정보가 없는 사례와 단순 변심 환불 조건의 Gold 정답 정제
- [x] `python3 scripts/validate_gold_dataset.py` 통과 (35개)
- [x] `python3 -m pytest -q` 통과 (2개)
- [x] 초기 Git 커밋 생성 (`99ab7da`)

## 현재 작업
사용자가 정제된 비즈니스 규칙과 남은 모호성을 검토한다. 확인 후 Phase 0을 종료한다.

## Phase 0 완료 조건
- [x] 제품 문제와 범위 문서화
- [x] 데이터 디렉터리와 이름 규칙 정의
- [x] 초기 정책 Corpus 존재
- [x] 초기 구조화 데이터 존재
- [x] Gold 평가 스키마 존재
- [x] 평가 질문 최소 20개 존재
- [ ] 사용자가 비즈니스 규칙의 모순 여부를 검토함
- [x] Gold 평가셋 30개 이상이며 주요 유형이 충분히 포함됨
- [x] 최종 Phase 0 수정 후 `python3 scripts/validate_gold_dataset.py` 통과
- [x] `python3 -m pytest -q` 통과
- [x] 초기 Git 커밋 생성

## 다음 작업
사용자 검토에서 비즈니스 규칙의 이견이 없으면 Phase 0을 완료 처리한다. 이후에만 Phase 1 계획을 시작한다.

## 아직 시작하지 않을 것
- BM25 / 검색 구현
- Embedding / Vector DB
- RAG / LangChain
- Agent / LangGraph
- FastAPI
- Docker

## 막힌 사항
Phase 0 종료에는 사용자 비즈니스 규칙 검토가 필요하다. 특히 사용으로 인한 상품 가치 감소의 판정 기준, 하자/오배송 확인 절차, 쿠폰·한정 상품의 개별 조건은 현재 데이터만으로 확정할 수 없다.
