# 실행·운영 가이드

## 1. Docker Compose로 실행

필요한 것: Docker Compose, 호스트에서 실행 중인 [Ollama](https://ollama.com/download)

```bash
cp .env.example .env
# .env의 SUPPORTOPS_DB_PASSWORD를 URL에 넣을 수 있는 로컬 비밀번호로 변경
ollama pull qwen2.5:3b
ollama pull gemma4:12b
docker compose up -d --build
docker compose ps --all
```

Compose는 pgvector가 포함된 PostgreSQL이 준비되면 합성 주문 10건·상품 10건을 적재하고, 적재가 끝난 뒤 API를 띄운다.

- API는 `127.0.0.1:8000`에만 열리고, DB는 외부 포트를 열지 않는다.
- API 컨테이너는 `host.docker.internal:11434`로 호스트의 Ollama에 연결한다.
- `db_data`(DB)와 `model_cache`(임베딩 모델) 볼륨은 `docker compose down` 후에도 남는다. `docker compose down -v`는 둘 다 **삭제**한다.
- 로그: `docker compose logs -f api`

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/v1/answer -H 'Content-Type: application/json' \
  -d '{"question":"ORD-1008 지금 취소 가능해?","as_of":"2026-10-05"}'
curl -sS http://127.0.0.1:8000/v1/answer -H 'Content-Type: application/json' \
  -d '{"question":"ORD-9999 취소 가능해?","as_of":"2026-10-05"}'
curl -sS http://127.0.0.1:8000/v1/answer -H 'Content-Type: application/json' \
  -d '{"question":"제주도는 배송비가 더 붙어?"}'
```

첫 정책 질문은 임베딩 모델을 내려받고 초기화하느라 느리다 (이 환경에서 약 92초).

## 2. Docker 없이 실행

Python 3.11 이상, PostgreSQL, Ollama가 필요하다. DB 주소는 환경 변수로만 넘긴다.

```bash
python3 -m pip install -e '.[dev]'
export SUPPORTOPS_DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:5432/supportops'
python3 scripts/init_database.py
PYTHONPATH=src python3 -m uvicorn supportops.api:app --host 127.0.0.1 --port 8000
```

API 없이 질문 하나만 확인하려면 스크립트를 쓴다.

```bash
python3 scripts/ask_policy.py '제주도는 배송비가 더 붙어?'
python3 scripts/ask_support.py 'ORD-1008 지금 취소 가능해?' --as-of 2026-10-05
```

| 환경 변수 | 용도 | 기본값 |
|---|---|---|
| `SUPPORTOPS_DATABASE_URL` | 주문·상품 DB 주소 | 없음 (없으면 `/health`가 503) |
| `OLLAMA_HOST` | Ollama 서버 주소 | Ollama SDK 기본값 |
| `SUPPORTOPS_AGENT_MODEL` | 주문 라우터 모델 | `qwen2.5:3b` |
| `SUPPORTOPS_RAG_MODEL` | 정책 답변 모델 | `gemma4:12b` |
| `SUPPORTOPS_TEST_DATABASE_URL` | DB 통합 테스트용 주소 | 없음 (없으면 2개 건너뜀) |

## 3. API

### `GET /health`

DB에 `SELECT 1`을 보내 성공하면 `{"status": "ok"}`. Ollama 모델 준비 상태는 확인하지 않는다.

### `POST /v1/answer`

요청

```json
{"question": "ORD-1008 지금 취소 가능해?", "as_of": "2026-10-05"}
```

- `question`: 공백을 뺀 1~2000자
- `as_of`: 환불 기간 계산 기준일 (ISO 날짜, 생략하면 오늘). 질문에 날짜가 있으면 질문의 날짜가 우선한다.

응답

| 필드 | 내용 |
|---|---|
| `answer` | 답변 문구 |
| `abstained` | 보류했으면 `true` |
| `outcome` | 처리 결과 코드 (예: `cancel_request_allowed`, `order_not_found`, `invalid_citation`) |
| `citations` | 인용한 정책 (`policy_id`, `chunk_id`, `source_path`) |
| `trace` | 실행한 도구와 결과 (`get_order`, `get_product`, `check_refund_eligibility` 등) |

모든 응답에 `X-Request-ID` 헤더가 붙는다.

| 상태 코드 | 경우 |
|---|---|
| 422 | 입력 형식 오류 |
| 503 | DB 미설정·접속 장애, Ollama 호출 장애 |
| 500 | 그 밖의 내부 오류 (예외 내용은 응답에 넣지 않음) |

### 로그

요청마다 JSON 한 줄을 남긴다: 요청 ID, 경로, 상태 코드, 결과 코드, 보류 여부, 지연 시간, Ollama 입력·출력 토큰 수. 모델을 호출하지 않았으면 토큰 값은 `null`이다. 로컬 모델이라 금전 비용은 `model_cost: null`로 둔다. 질문 원문과 주문 상세는 남기지 않는다.

## 4. 테스트와 CI

```bash
python3 scripts/validate_gold_dataset.py
python3 -m pytest -q
```

DB 통합 테스트(pgvector 저장·검색, API의 DB 경로)까지 돌리려면 테스트 전용 DB를 따로 준비한다. Compose의 DB는 호스트 포트를 열지 않으므로 쓸 수 없다.

```bash
docker run --rm --name supportops-test-db \
  -e POSTGRES_USER=supportops -e POSTGRES_DB=supportops \
  -e POSTGRES_PASSWORD="$SUPPORTOPS_DB_PASSWORD" \
  -p 127.0.0.1:55432:5432 -d pgvector/pgvector:0.8.7-pg17
SUPPORTOPS_TEST_DATABASE_URL="postgresql://supportops:$SUPPORTOPS_DB_PASSWORD@127.0.0.1:55432/supportops" \
  python3 -m pytest -q
docker stop supportops-test-db
```

GitHub Actions(`.github/workflows/ci.yml`)는 push와 pull request마다 Python 3.11, CPU용 PyTorch, pgvector PostgreSQL을 준비해 평가셋 검증과 pytest 25개를 실행하고 `docker compose config`도 확인한다. CI는 가짜 모델로 규칙·검증·DB 경로를 확인하므로 Ollama나 API 키가 필요 없다. 실제 LLM 답변 품질은 [실험 기록](EXPERIMENTS.md)을 본다.

## 5. 문제 해결

| 증상 | 원인과 해결 |
|---|---|
| `docker compose up`이 바로 실패 | `.env`에 `SUPPORTOPS_DB_PASSWORD`가 없다. |
| DB 인증 실패 | 기존 볼륨이 있는 상태에서 `.env` 비밀번호만 바꿨다. DB 안에서 비밀번호를 바꾸거나, 데이터를 버려도 되면 `docker compose down -v` 후 다시 띄운다. |
| `/health`는 200인데 답변이 503 | 호스트 Ollama가 꺼져 있거나 모델을 받지 않았다. 컨테이너에서 호스트 Ollama로 접속이 허용돼야 한다. |
| 첫 정책 질문이 매우 느림 | 임베딩 모델 다운로드. 두 번째부터는 `model_cache` 볼륨을 쓴다. |
| 적재 컨테이너가 오류로 종료 | DB의 기존 데이터가 CSV와 다르다. 적재는 덮어쓰지 않고 오류를 낸다. |
