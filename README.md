# SupportOps AI

> 평가 가능한 근거 기반 한국어 커머스 고객지원 에이전트

Applied AI Engineer 신입/인턴 지원용 대표 포트폴리오 프로젝트다.
한국 이커머스 고객지원 Copilot을 직접 설계하고, 평가하고, 개선하고, 서비스 형태로 완성하는 것이 목표다.

## 현재 상태
**Phase 2 — Dense 검색과 pgvector 저장 경로 완료**

고정 Gold로 [BM25 기준선](docs/PHASE1_BASELINE.md)과 [Dense/pgvector 결과](docs/PHASE2_DENSE.md)를 같은 기준에서 측정했다. RAG와 Agent는 아직 시작하지 않았다.

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
```bash
python3 -m pip install -e '.[dev]'
python3 scripts/validate_gold_dataset.py
python3 -m pytest -q
python3 scripts/evaluate_bm25.py
python3 scripts/evaluate_dense.py --backend local
```

## 데이터 설계 원칙
핵심 MoaShop 데이터는 합성 데이터다.
정책, 상품, 주문, Tool, 평가 정답이 하나의 회사 세계 안에서 일관되게 연결되도록 하기 위해서다.

외부 공개 데이터셋은 나중에 보조적으로 추가할 수 있지만, 반드시 출처와 라이선스, 사용 목적을 기록한다.
