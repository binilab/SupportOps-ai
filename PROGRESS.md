# PROGRESS

## 현재 단계
**Phase 0 — 완료 (문제 정의, 데이터 계약, Gold 평가셋)**

## 현재 상태
사용자가 상품 가치 감소, 하자/오배송 확인, 개별 조건 우선순위를 확정했다. 정책과 Gold 정답에 반영하고 참조·검증·테스트를 통과했다. Phase 0은 완료됐으며 검색/RAG/Agent 구현은 시작하지 않았다.

## 완료한 항목
- [x] 프로젝트 범위 정의
- [x] 저장소/Codex 작업 규칙 정의
- [x] MoaShop 정책 초기 데이터 추가
- [x] 상품/주문 초기 데이터 추가
- [x] Gold 평가 예시 40개 확보 (답변 가능 34개, 답변 불가 6개; Tool 필요 11개)
- [x] Gold JSONL 검증기 및 테스트 추가
- [x] 주문 10개의 상품 참조 유효성 확인, Gold의 존재하지 않는 주문 `ORD-9999`는 의도적 거부 사례로 확인
- [x] 주문 위치 정보가 없는 사례와 단순 변심 환불 조건의 Gold 정답 정제
- [x] 사용자 확정 비즈니스 규칙을 정책·결정 기록·Gold에 반영하고 충돌 재검토
- [x] `python3 scripts/validate_gold_dataset.py` 통과 (40개)
- [x] `python3 -m pytest -q` 통과 (2개)
- [x] 초기 Git 커밋 생성 (`99ab7da`)

## 현재 작업
Phase 0 종료. 후속 단계는 별도 지시 전까지 시작하지 않는다.

## Phase 0 완료 조건
- [x] 제품 문제와 범위 문서화
- [x] 데이터 디렉터리와 이름 규칙 정의
- [x] 초기 정책 Corpus 존재
- [x] 초기 구조화 데이터 존재
- [x] Gold 평가 스키마 존재
- [x] 평가 질문 최소 20개 존재
- [x] 사용자가 비즈니스 규칙의 모순 여부를 검토하고 경계 조건을 확정함
- [x] Gold 평가셋 30개 이상이며 주요 유형이 충분히 포함됨
- [x] 최종 Phase 0 수정 후 `python3 scripts/validate_gold_dataset.py` 통과
- [x] `python3 -m pytest -q` 통과
- [x] 초기 Git 커밋 생성

## 다음 작업
별도 요청이 있을 때 Phase 1을 시작한다.

## 아직 시작하지 않을 것
- BM25 / 검색 구현
- Embedding / Vector DB
- RAG / LangChain
- Agent / LangGraph
- FastAPI
- Docker

## 막힌 사항
없음. 개별 쿠폰/상품 조건과 실제 하자 확인 결과가 없는 사례는 확정 판단을 하지 않는 것으로 Gold에 명시했다.
