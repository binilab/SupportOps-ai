# ROADMAP — 포트폴리오 완성 로드맵

이 프로젝트는 채용 공고에서 자주 요구되는 Applied AI 도구를 여러 개 다루되, **실제 필요가 생기는 단계에서만** 도입한다.

## v1 완료 시 핵심 기술 스택
- Python, pytest
- BM25 Lexical Retrieval
- sentence-transformers / Embedding
- PostgreSQL + pgvector
- LangChain: RAG 구성/통합
- LangGraph: Tool Calling Workflow
- FastAPI + Pydantic
- SQLAlchemy: 애플리케이션 DB 접근
- Docker / Docker Compose
- GitHub Actions CI
- 구조화 로깅 + 필요 시 추적/관측성 도구 1개

처음부터 모든 의존성을 설치하지 않는다. 실제 사용하는 Phase에서 추가한다.

## Phase 0 — 문제 정의 + 데이터 계약 + Gold 평가셋
**목표:** 프로젝트 범위를 고정하고 믿을 수 있는 시험지를 만든다.

사용 도구:
- Python 표준 라이브러리
- pytest

완료 조건:
- 프로젝트 범위 고정
- 현실적인 정책/구조화 초기 데이터 존재
- 평가 스키마 고정
- Phase 1 전에 Gold 질문 30개 이상 확보
- 이후 프로젝트 진행 중 약 80~120개까지 확장 가능
- 검증기/테스트 통과

## Phase 1 — 데이터 수집/정규화 + Lexical Baseline
**목표:** 공통 Document/Chunk 스키마와 재현 가능한 Lexical Retrieval Baseline을 만든다.

사용:
- BM25용 `rank-bm25`
- 필요하면 TF-IDF를 작은 참고 Baseline으로 유지 가능

측정:
- Recall@1/3/5
- MRR
- latency

완료 조건:
- 재현 가능한 Baseline 평가 결과가 존재한다.

## Phase 2 — Dense Retrieval + Vector Storage
**목표:** Embedding 검색과 실제 Vector 저장 경로를 구현한다.

사용:
- 로컬 Embedding 실험용 `sentence-transformers`
- Vector 저장/검색용 PostgreSQL + `pgvector`

배우고 측정할 것:
- Embedding 차원
- Cosine Similarity / Distance
- Top-K
- Metadata Filtering
- Phase 1과 동일 Gold 셋을 사용한 공정한 비교

완료 조건:
- 같은 Gold 평가셋에서 Dense Retrieval 평가 결과가 존재한다.

## Phase 3 — Retrieval Engineering
**목표:** 실패 분석을 근거로 검색 품질을 개선한다.

후보:
- BM25 + Dense Hybrid Search
- RRF 또는 이유가 명확한 Weighted Fusion
- `sentence-transformers`의 CrossEncoder Reranker

품질과 latency를 함께 비교하고 실험표를 유지한다.

완료 조건:
- 정량적 개선 1개 이상
- 품질과 속도 사이 Trade-off에 대한 명시적인 선택

## Phase 4 — Grounded RAG
**목표:** Citation과 Abstention을 포함한 근거 기반 답변 생성을 구현한다.

사용:
- 먼저 LLM Provider SDK로 **아주 작은 1회성 스파이크**를 만들어 요청/응답 구조를 이해한다. 이 코드를 별도 운영 경로로 유지하지 않는다.
- 이후 실제 RAG 파이프라인에서는 필요성이 확인될 때 **LangChain**을 구성/통합 계층에 사용한다.

원칙:
- 같은 기능을 SDK 버전과 LangChain 버전으로 이중 유지하지 않는다.
- LangChain이 복잡도를 줄이지 못하면 억지로 사용하지 않고 결정 이유를 `DECISIONS.md`에 기록한다.

측정:
- 답변 정확성
- Groundedness
- Citation 정확성
- Abstention 정확성

완료 조건:
- 단순 데모 챗이 아니라 평가 결과가 있는 Grounded RAG가 존재한다.

## Phase 5 — Tool Calling 고객지원 Agent
**목표:** Multi-Agent 없이 주문/상품 Tool을 사용하는 하나의 명확한 Workflow를 만든다.

사용:
- Provider Native Function/Tool Calling의 Tool Schema와 호출 구조를 먼저 이해한다.
- 여러 단계의 상태/분기가 실제로 필요해졌을 때만 **LangGraph**를 최종 Workflow 오케스트레이션에 사용한다.

후보 Tool:
- `search_policy()`
- `get_order()`
- `get_product()`
- `check_refund_eligibility()`
- Mock `create_support_ticket()`

측정:
- Tool 선택 정확도
- 인자 정확도
- 최종 작업 성공률

완료 조건:
- 여러 Agent를 억지로 만들지 않고 하나의 이해 가능한 Agent/Workflow가 동작한다.

## Phase 6 — 서비스화
**목표:** AI 로직을 작은 Backend 서비스로 만든다.

사용:
- **FastAPI**
- 요청/응답 모델용 **Pydantic**
- **SQLAlchemy**
- PostgreSQL/pgvector

추가:
- 적절한 Error Handling
- 필요 시 Timeout/Retry
- 구조화 로깅
- latency/token/cost 기록

완료 조건:
- API가 실행되고 통합 테스트를 통과한다.

## Phase 7 — 소프트웨어 품질 + 운영 기본기
**목표:** 다른 사람이 재현하고 리뷰할 수 있는 저장소로 만든다.

사용:
- pytest
- Docker / Docker Compose
- GitHub Actions CI
- 필요하면 관측성/추적 경로 1개
  - 자격증명이 있으면 LangSmith 같은 도구 사용 가능
  - 없으면 먼저 구조화된 로컬 trace/log를 사용

**Redis**는 실제로 캐싱/Rate Limiting 필요가 측정됐을 때만 추가한다.
Kubernetes는 기술 스택 장식을 위해 넣지 않는다.

완료 조건:
- 깨끗한 로컬 실행
- 자동 테스트
- CI
- 문서화된 실패 사례

## Phase 8 — 포트폴리오 패키징
**목표:** 기능 추가를 멈춘다.

완성할 것:
- README
- 아키텍처 다이어그램
- 실험/평가 표
- 실패 분석
- 주요 기술 결정
- 데모 GIF/영상
- 면접 질문/답변

여기까지 끝나면 지원을 시작한다.

## v1에서 의도적으로 필수가 아닌 기술
다음 기술은 채용 공고에서 보일 수 있지만 첫 포트폴리오에서는 중복되거나 과할 수 있다. 특정 지원 회사에서 반복 요구될 때만 추가한다.
- LangChain과 역할이 겹치는 LlamaIndex 추가 사용
- Dify / n8n / Langflow
- MCP / A2A
- 측정된 필요가 없는 Redis
- Kubernetes
- Cloud Deployment
- GraphRAG / Ontology
- Fine-tuning
- Multi-Agent Architecture

v1 완성 후 실제 지원 공고를 분석했을 때 반복적으로 요구되는 기술이 있다면 **확장 기능 1개만** 선택해 추가한다.
