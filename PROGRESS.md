# PROGRESS

## 현재 단계
**Phase 1 — 완료 (정책 정규화와 Lexical 검색 기준선)**

## 현재 상태
Phase 0의 고정 Gold를 사용해 정책 Markdown을 절 단위 청크로 정규화하고 BM25 검색 기준선을 측정했다. 37개 정책 검색 질문에서 Recall@1/3/5와 MRR을 기록했으며 Phase 1은 완료됐다. Dense 검색, RAG, Agent는 시작하지 않았다.

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
- [x] Phase 1 정책 8개를 출처가 있는 청크 35개로 정규화
- [x] `rank-bm25` 기준선 구현, 정책 ID 단위 Recall@1/3/5·MRR·latency 평가
- [x] Gold 40개 중 정책 ID가 있는 37개 평가, 없는 3개 제외
- [x] Recall@1 0.6081 / Recall@3 0.8378 / Recall@5 0.9459 / MRR 0.7883 기록
- [x] Top 5 실패 2개(`eval_0018`, `eval_0033`) 분석 및 기준선 보고서 작성
- [x] `python3 scripts/validate_gold_dataset.py` 통과, `python3 -m pytest -q` 5개 통과

## 현재 작업
Phase 1 종료. 후속 단계는 별도 지시 전까지 시작하지 않는다.

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

## Phase 1 완료 조건
- [x] 공통 정책 Document/Chunk 스키마와 원본 출처 보존
- [x] 재현 가능한 BM25 기준선 평가 결과 존재
- [x] Recall@1/3/5, MRR, latency와 실패 사례 기록
- [x] 검증기 및 pytest 통과

## 다음 작업
별도 요청이 있을 때 Phase 2를 시작한다.

## 아직 시작하지 않을 것
- Embedding / Vector DB
- RAG / LangChain
- Agent / LangGraph
- FastAPI
- Docker

## 막힌 사항
없음. 기준선의 한국어 활용형·오타 검색 실패는 `docs/PHASE1_BASELINE.md`에 기록했다.
