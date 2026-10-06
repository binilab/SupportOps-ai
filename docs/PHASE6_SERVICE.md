# Phase 6 — 읽기 전용 API 서비스

## 범위와 경로

`POST /v1/answer`는 질문과 선택적 `as_of` 날짜를 검증한 뒤 기존 단일 Agent를 실행한다. 주문 ID가 있으면 Ollama `qwen2.5:3b`가 Tool 인자를 제안하고, 검증 후 SQLAlchemy가 PostgreSQL의 합성 주문·상품을 읽는다. 환불·취소 판단은 Python 규칙을 그대로 쓴다. 주문 ID가 없으면 기존 BM25 + 로컬 Dense Hybrid 정책 검색과 Ollama `gemma4:12b` RAG를 사용한다. 정책 청크의 출처와 검증된 인용을 응답에 포함한다. 환불·취소를 실제 실행하지 않는다.

PostgreSQL은 주문·상품의 서비스 저장소다. pgvector는 Phase 2에서 저장·조회가 검증됐고 통합 테스트를 유지한다. 이 단계의 API 정책 검색은 Phase 3에서 평가한 로컬 Hybrid 경로를 재사용한다. 작은 정책 Corpus의 검색 구현을 서비스화 때문에 변경하지 않았다.

## 실행

Python 3.11 이상, PostgreSQL 및 로컬 Ollama가 필요하다. 데이터베이스 URL은 환경 변수로만 전달한다. 아래는 로컬 예시이며 비밀번호는 사용자 환경에 맞게 바꾼다.

```bash
python3 -m pip install -e '.[dev]'
export SUPPORTOPS_DATABASE_URL='postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/supportops'
python3 scripts/init_database.py
ollama pull qwen2.5:3b
ollama pull gemma4:12b
PYTHONPATH=src python3 -m uvicorn supportops.api:app --host 127.0.0.1 --port 8000
```

별도 터미널에서 확인한다.

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/v1/answer \
  -H 'Content-Type: application/json' \
  -d '{"question":"ORD-1008 지금 취소 가능해?","as_of":"2026-10-05"}'
```

PostgreSQL/pgvector 통합 테스트까지 실행하려면 전용 테스트 DB URL을 지정한다. 이 URL은 `psycopg`가 직접 읽는 `postgresql://` 형식으로 쓴다.

```bash
export SUPPORTOPS_TEST_DATABASE_URL="$SUPPORTOPS_DATABASE_URL"
python3 scripts/validate_gold_dataset.py
python3 -m pytest -q
```

초기화 명령은 버전 관리된 `data/raw/structured/` CSV 10개 주문·10개 상품을 적재한다. 다시 실행해도 중복 삽입하지 않고, 같은 ID의 DB 값이 CSV와 다르면 오류를 낸다. API 요청은 이 데이터를 수정하지 않는다.

## 계약과 오류

- `GET /health`: DB `SELECT 1` 성공 시 `{"status":"ok"}`. 모델 준비 상태는 확인하지 않는다.
- `POST /v1/answer`: `question`은 공백 제외 1~2000자, `as_of`는 ISO 날짜다. 응답은 `answer`, `abstained`, `outcome`, `citations`, `trace`를 포함한다. `X-Request-ID` 헤더가 붙는다.
- 입력 오류 422, DB 미설정·접속 장애와 Ollama 호출 장애 503, 기타 내부 오류 500이다. 원본 예외 메시지는 API 응답에 담지 않는다.
- JSON 로그는 경로, 상태, 요청 ID, 지연 시간, 결과, 보류 여부, Ollama 입력·출력 토큰 수를 기록한다. 모델 호출이 없거나 공급자가 수치를 주지 않으면 토큰 값은 `null`이다. 로컬 Ollama의 금전 비용은 산정하지 않아 `model_cost: null`로 기록한다. 질문 원문이나 주문 상세는 로그에 넣지 않는다.

## 검증과 한계

실제 PostgreSQL/pgvector 컨테이너에서 Gold 검증기와 pytest를 실행했고, API 통합 테스트는 중복 적재, 타입 변환, 주문 판정과 인용, 누락 주문 보류, 정책 답변, 입력 오류, DB·모델 장애를 확인했다. 로컬 Ollama 두 모델을 붙인 API 경로에서 주문 질문과 정책 질문이 각각 200과 인용 포함 답변을 반환했다. Gold 성능 수치는 Phase 4·5 평가를 유지하며 이 API 테스트를 새 품질 개선으로 해석하지 않는다.

정책 질문의 첫 요청은 임베딩 모델 로드 때문에 느릴 수 있다. 기존 모델 호출 제한 시간은 주문 라우터 60초, 정책 생성 120초다. 인증과 공개 서비스 배포는 v1 범위 밖이며, 이 서비스는 로컬 내부 데모를 전제로 한다. Docker 실행 구성과 CI는 Phase 7에서 다룬다.
