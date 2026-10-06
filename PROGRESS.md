# PROGRESS

## 현재 단계
**Phase 8 — 완료 (포트폴리오 패키징)**

## 현재 상태
README에 실제 구현 구조, 고정 Gold 평가표, 실패 분석, 실행 절차와 한계를 한곳에 정리했다. Compose API에서 직접 받은 주문·정책·보류 응답 3건을 원본 JSON과 GIF로 남기고 면접 질문·답변을 작성했다. Gold 검증은 통과했고, 로컬 pytest는 DB 미설정으로 23개 통과·2개 건너뜀이다. Phase 7 원격 CI에서는 DB 포함 25개가 통과했다.

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
- [x] Phase 5 Ollama 네이티브 `get_order` 함수 호출과 모델 인자 검증
- [x] CSV `get_order`·`get_product`와 결정적 환불·취소 적격성 규칙 구현
- [x] Gold Tool 질문 11개에서 Tool 선택·인자·순서·최종 결과·보류 11/11 평가
- [x] 답변의 Gold 필수 사실 11/11 수동 검토, 모델·데이터 해시와 latency 기록
- [x] 미확인 하자/오배송·상품별 개별 조건, `used=true` 경계 테스트
- [x] Gold 검증기 통과, pytest 20개 통과 (DB 미설정으로 통합 테스트 1개 건너뜀)
- [x] FastAPI `/v1/answer`·`/health`, Pydantic 검증, 인용·Tool trace 응답 추가
- [x] SQLAlchemy 요청별 PostgreSQL 조회 및 버전 관리된 합성 CSV 10개 주문·10개 상품의 멱등 적재
- [x] DB/모델 장애 503, 입력 오류 422, 요청 ID와 지연 시간·Ollama 토큰 수 구조화 로그 확인
- [x] 실제 PostgreSQL/pgvector에서 API·DB 통합 테스트와 기존 테스트 통과
- [x] 실제 Ollama 주문·정책 질문과 Uvicorn HTTP 주문 요청에서 200 및 인용 확인
- [x] Phase 6 실행·한계를 `docs/PHASE6_SERVICE.md`에 기록
- [x] CPU 전용 API Docker 이미지와 PostgreSQL/pgvector Compose 실행 구성
- [x] Compose에서 DB 준비 → 합성 CSV 적재 → API 시작과 주문·정책 HTTP 200 확인
- [x] `.env.example`, 모델 캐시 볼륨, 로컬 실행·장애 문서 추가
- [x] GitHub Actions에 Gold 검증·실제 DB 통합 테스트 구성
- [x] 로컬 Gold 40개 검증과 실제 PostgreSQL/pgvector 포함 pytest 25개 통과
- [x] 원격 GitHub Actions CI 성공 (`f11584f`, 실행 37457093395)
- [x] Phase 8 README 아키텍처 다이어그램과 검색·RAG·Tool 평가표, 실패·한계 분석 정리
- [x] 실제 Compose API 응답 3건의 원본 JSON과 GIF 데모 작성
- [x] 주요 기술 결정과 면접 질문·답변 연결, 구현하지 않은 프레임워크·Reranker 표현 정정
- [x] README·데모 링크, GIF 프레임, Gold 검증기와 pytest 확인 (23개 통과·DB 통합 2개 건너뜀)

## 현재 작업
Phase 8 종료. 기능 추가를 멈추고 포트폴리오를 지원 자료로 사용할 수 있다.

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

## Phase 5 완료 조건
- [x] Multi-Agent 없이 주문/상품 Tool을 사용하는 하나의 이해 가능한 Workflow
- [x] 모델 제안 Tool 인자 검증과 결정적 환불·취소 판단
- [x] Tool 선택·인자·최종 작업 성공률을 고정 Gold에서 평가
- [x] 주문 누락·위치 정보 부족·미확인 하자·상품 상태 경계 테스트

## Phase 6 완료 조건
- [x] 기존 정책·주문 답변 경로를 제공하는 FastAPI 실행
- [x] PostgreSQL의 합성 주문·상품을 SQLAlchemy로 조회
- [x] API 입력·응답 검증과 DB/모델 장애 처리
- [x] 실제 PostgreSQL/pgvector 통합 테스트와 실제 Ollama HTTP 확인
- [x] 요청별 구조화 로그에 latency와 제공된 토큰 수 기록

## Phase 7 완료 조건
- [x] 깨끗한 Compose 로컬 실행에서 DB 적재와 주문·정책 API 확인
- [x] Gold 검증기와 DB 포함 자동 테스트 통과
- [x] 원격 GitHub Actions CI 통과
- [x] 실행 절차와 확인한 실패·경계 사례 기록

## Phase 8 완료 조건
- [x] 실제 구현 범위를 설명하는 README와 아키텍처 다이어그램
- [x] 원본 보고서와 일치하는 검색·답변·Tool 평가표
- [x] 남은 실패와 개발 Gold의 일반화 한계 명시
- [x] 주요 기술 결정, 재생 GIF와 실제 API 응답 원본, 면접 질문·답변 연결
- [x] Gold 검증기와 pytest 실행, GitHub Actions CI 경로 유지

## 다음 작업
채용 지원 시 README·데모를 사용한다. 추가 기능이나 범위 확장은 별도 요청이 있을 때 결정한다.

## 아직 시작하지 않을 것
- 별도 요청 없는 새 기능 구현

## 막힌 사항
없음. 로컬 Compose 데모에는 호스트 Ollama와 모델 다운로드가 필요하다. 현재 Gold는 개발 중 사용됐으므로 별도 held-out 일반화 성능은 측정하지 않았다.
