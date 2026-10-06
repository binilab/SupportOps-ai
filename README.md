# SupportOps AI

> 평가 가능한 근거 기반 한국어 커머스 고객지원 에이전트

Applied AI Engineer 신입/인턴 지원용 대표 포트폴리오 프로젝트다.
한국 이커머스 고객지원 Copilot을 직접 설계하고, 평가하고, 개선하고, 서비스 형태로 완성하는 것이 목표다.

## 현재 상태
**Phase 7 — 로컬 실행과 CI 완료**

고정 Gold로 [BM25 기준선](docs/PHASE1_BASELINE.md), [Dense/pgvector 결과](docs/PHASE2_DENSE.md), [Hybrid RRF 결과](docs/PHASE3_RETRIEVAL.md)를 비교했다. [정책 근거 답변](docs/PHASE4_RAG.md)은 답변 정확성 22/25, 보류 정확성 15/15였다. [주문 Tool Calling](docs/PHASE5_AGENT.md)은 Gold 11개에서 Tool 순서·인자·판정 결과 11/11을 기록했다. [Phase 6 API](docs/PHASE6_SERVICE.md)는 PostgreSQL의 합성 주문·상품과 기존 답변 흐름을 연결한다. [Phase 7 실행 안내](docs/PHASE7_OPERATIONS.md)에 Docker Compose와 CI 재현 방법이 있다.

## 포트폴리오 핵심 흐름
문제 정의
→ 고정 Gold 평가셋
→ BM25 Baseline
→ Dense Retrieval
→ Hybrid/Reranker 개선
→ Citation/Abstention이 있는 Grounded RAG
→ Tool Calling 기반 업무 흐름
→ FastAPI/PostgreSQL 서비스
→ 테스트/Docker/CI
→ 정량 결과와 실패 분석이 포함된 데모

## 저장소 구조
- `AGENTS.md` — Codex가 항상 따라야 하는 상시 작업 규칙
- `PROJECT_SCOPE.md` — 제품 범위, 제외 범위, 성공 조건
- `PROGRESS.md` — **현재 작업 상태의 단일 기준 문서**
- `DECISIONS.md` — 중요한 기술/제품 결정 기록
- `BACKLOG.md` — 지금은 구현하지 않을 아이디어 보관
- `docs/ROADMAP.md` — 단계 순서와 프레임워크/도구 도입 계획
- `docs/ENGINEERING_GUIDE.md` — 개발 흐름, 데이터, 평가, 디버깅, 리뷰 규칙
- `data/` — MoaShop 합성 데이터, Gold 평가셋, 외부 데이터 출처 기록
- `scripts/` — 검증/평가 유틸리티
- `src/` — 실제 애플리케이션 코드
- `tests/` — 자동화 테스트

## 처음 실행할 명령어

Docker Compose를 통한 가장 짧은 실행 경로는 [Phase 7 실행 안내](docs/PHASE7_OPERATIONS.md)를 따른다. 아래는 각 평가 스크립트를 직접 실행하는 경로다.
```bash
python3 -m pip install -e '.[dev]'
python3 scripts/validate_gold_dataset.py
python3 -m pytest -q
python3 scripts/evaluate_bm25.py
python3 scripts/evaluate_dense.py --backend local
python3 scripts/evaluate_hybrid.py
ollama pull gemma4:12b
python3 scripts/ask_policy.py '제주도는 배송비가 더 붙어?'
python3 scripts/evaluate_rag.py
ollama pull qwen2.5:3b
python3 scripts/ask_support.py 'ORD-1008 지금 취소 가능해?' --as-of 2026-10-05
python3 scripts/evaluate_agent.py
# PostgreSQL 준비 후 SUPPORTOPS_DATABASE_URL 설정
python3 scripts/init_database.py
PYTHONPATH=src python3 -m uvicorn supportops.api:app --host 127.0.0.1 --port 8000
```

## 데이터 설계 원칙
핵심 MoaShop 데이터는 합성 데이터다.
정책, 상품, 주문, Tool, 평가 정답이 하나의 회사 세계 안에서 일관되게 연결되도록 하기 위해서다.

외부 공개 데이터셋은 나중에 보조적으로 추가할 수 있지만, 반드시 출처와 라이선스, 사용 목적을 기록한다.
