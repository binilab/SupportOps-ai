# PROGRESS

## 현재 단계
**Phase 0 — 문제 정의, 데이터 계약, Gold 평가셋**

## 현재 상태
최소 스타터 저장소가 만들어진 상태다. 검색/RAG/Agent 구현은 아직 시작하지 않았다.

## 완료한 항목
- [x] 프로젝트 범위 정의
- [x] 저장소/Codex 작업 규칙 정의
- [x] MoaShop 정책 초기 데이터 추가
- [x] 상품/주문 초기 데이터 추가
- [x] Gold 평가 예시 24개 추가
- [x] Gold JSONL 검증기 및 테스트 추가

## 현재 작업
검색 구현 전에 Phase 0의 비즈니스 규칙을 검토하고 Gold 평가셋을 확장/정제한다.

## Phase 0 완료 조건
- [x] 제품 문제와 범위 문서화
- [x] 데이터 디렉터리와 이름 규칙 정의
- [x] 초기 정책 Corpus 존재
- [x] 초기 구조화 데이터 존재
- [x] Gold 평가 스키마 존재
- [x] 평가 질문 최소 20개 존재
- [ ] 사용자가 비즈니스 규칙의 모순 여부를 검토함
- [ ] Gold 평가셋 30개 이상이며 주요 유형이 충분히 포함됨
- [ ] 최종 Phase 0 수정 후 `python3 scripts/validate_gold_dataset.py` 통과
- [ ] `python3 -m pytest -q` 통과
- [ ] 초기 Git 커밋 생성

## 다음 작업
초기 데이터를 검토하고 모순을 수정한 뒤 Gold 평가셋을 24개에서 30개 이상으로 늘린다. 이후 검증과 테스트를 다시 실행하고 Phase 0을 커밋한다.

## 아직 시작하지 않을 것
- BM25 / 검색 구현
- Embedding / Vector DB
- RAG / LangChain
- Agent / LangGraph
- FastAPI
- Docker

## 막힌 사항
없음.
