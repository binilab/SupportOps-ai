# PROGRESS

## 현재 단계
**Phase 4 — 완료 (정책 근거 답변과 보류)**

## 현재 상태
기존 Hybrid 검색과 로컬 Ollama 모델로 정책 전용 RAG를 만들고 Gold 40개에서 평가했다. 정책 답변 25개 중 필수 사실을 모두 포함한 답변은 22개(88%, 수동 검토), 보류 대상 15개는 모두 보류했다. 인용 근거의 청크 ID·원본 경로를 검증한다. 전체 질문당 중앙 시간은 24.218초로 느리다. Agent와 API는 시작하지 않았다.

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
- [x] Phase 2 모델 revision 고정, 384차원 정규화 임베딩과 코사인 검색 구현
- [x] Gold 37개에서 Dense Recall@1/3/5 0.7297/0.8378/0.9189, MRR 0.8905 측정
- [x] pgvector 0.8.7에 벡터 35개 저장·조회 및 정책 ID 메타데이터 필터 확인
- [x] 동일 Gold/정책 해시에서 로컬·pgvector 검색 지표와 Top 5 실패 목록 일치 확인
- [x] 실패 5개와 BM25 대비 품질·latency 차이를 `docs/PHASE2_DENSE.md`에 기록
- [x] Gold 검증기 통과, PostgreSQL 통합 테스트 포함 pytest 7개 통과
- [x] Phase 3 BM25 + Dense 정책 ID 순위를 RRF(상수 60)로 결합하고 출처 청크 보존
- [x] 동일 Gold/정책 해시에서 BM25·Dense·Hybrid 품질과 latency 비교
- [x] Hybrid Recall@1/3/5 0.7432/0.9324/0.9730, MRR 0.9009 측정
- [x] Top 5 누락 1개(`eval_0033`)와 Dense 대비 latency 증가를 `docs/PHASE3_RETRIEVAL.md`에 기록
- [x] Gold 검증기 통과, pytest 8개 통과 (DB 미설정으로 통합 테스트 1개 건너뜀)
- [x] Phase 4 로컬 LLM SDK 단일 질문 호출로 구조화 응답 확인
- [x] Hybrid 검색 → 정책 청크 → 한국어 답변 → 인용 ID 검증·보류 경로 구현
- [x] Gold 40개에서 답변 정확성 22/25, 보류 정확성 15/15 측정
- [x] 답변한 25개에서 근거 충실도와 인용 정확성 수동 검토 및 실패 3개 기록
- [x] Gold 검증기 통과, pytest 15개 통과 (DB 미설정으로 통합 테스트 1개 건너뜀)

## 현재 작업
Phase 4 종료. 후속 단계는 별도 지시 전까지 시작하지 않는다.

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

## Phase 2 완료 조건
- [x] 같은 Gold 평가셋에서 Dense Retrieval 평가 결과 존재
- [x] Embedding 차원, 정규화, 코사인 거리, Top-K 및 메타데이터 필터 확인
- [x] PostgreSQL/pgvector 실제 저장·조회 경로 검증
- [x] 실패 사례와 latency, 재현 방법 기록

## Phase 3 완료 조건
- [x] 고정 Gold에서 BM25·Dense 대비 정량 개선 확인
- [x] 검색 품질과 latency의 절충을 명시하고 기본 검색 방법 선택
- [x] 남은 실패 사례와 재현 방법 기록

## Phase 4 완료 조건
- [x] 정책 근거를 포함한 한국어 답변과 검증된 출처 청크 인용
- [x] 근거 또는 구조화 데이터가 부족한 질문 보류
- [x] 고정 Gold에서 답변 정확성·근거 충실도·인용 정확성·보류 정확성 평가
- [x] 실패 사례, latency, 모델 및 재현 방법 기록

## 다음 작업
별도 요청이 있을 때 Phase 5를 시작한다.

## 아직 시작하지 않을 것
- Agent / LangGraph
- FastAPI
- Docker 기반 실행 구성

## 막힌 사항
없음. 답변 완전성 실패 3개와 높은 응답 latency는 `docs/PHASE4_RAG.md`에 기록했다.
