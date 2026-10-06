# Phase 7 — 로컬 실행과 CI

## Docker Compose로 시작

필요한 것은 Docker Compose와 호스트에서 실행되는 Ollama다. 모델은 `qwen2.5:3b`, `gemma4:12b`를 사용한다. API 컨테이너는 `host.docker.internal:11434`로 Ollama에 연결한다. 처음 정책 질문을 할 때는 고정된 다국어 임베딩 모델을 내려받으므로 인터넷 연결과 추가 시간이 필요하다.

```bash
cp .env.example .env
# .env의 SUPPORTOPS_DB_PASSWORD를 URL에서 안전한 로컬 비밀번호로 변경
ollama pull qwen2.5:3b
ollama pull gemma4:12b
docker compose up -d --build
docker compose ps --all
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/v1/answer \
  -H 'Content-Type: application/json' \
  -d '{"question":"ORD-1008 지금 취소 가능해?","as_of":"2026-10-05"}'
curl -sS http://127.0.0.1:8000/v1/answer \
  -H 'Content-Type: application/json' \
  -d '{"question":"제주도는 배송비가 더 붙어?"}'
```

Compose는 pgvector 포함 PostgreSQL의 준비 확인 후 합성 CSV 10개 주문·10개 상품을 적재하고 API를 시작한다. DB는 외부 포트를 열지 않고 API는 `127.0.0.1:8000`에만 공개한다. `db_data`와 임베딩 `model_cache` 볼륨은 `docker compose down` 후에도 유지된다. 로그는 `docker compose logs -f api`로 볼 수 있다. 종료는 `docker compose down`이다.

## 로컬 테스트와 CI

CI는 push와 pull request에서 Python 3.11, CPU 전용 PyTorch, pgvector PostgreSQL 서비스를 준비한다. Gold 데이터 검증기와 `pytest -q`를 실행한다. DB를 요구하는 두 통합 테스트도 실행되므로 CI에는 Ollama 모델이나 API 키가 필요 없다. `docker compose config --quiet`로 구성도 확인한다.

로컬에서 같은 검증을 하려면 별도의 테스트 PostgreSQL URL을 `SUPPORTOPS_TEST_DATABASE_URL`로 지정한다. Docker Compose DB는 호스트 포트를 열지 않으므로 별도의 테스트 DB가 필요하다. 값은 `postgresql://` 형식을 사용한다.

```bash
python3 -m pip install -e '.[dev]'
python3 scripts/validate_gold_dataset.py
SUPPORTOPS_TEST_DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:5432/TEST_DB' python3 -m pytest -q
```

## 확인한 실패와 경계

- `.env`의 비밀번호가 없으면 Compose가 구성 단계에서 중단된다. 비밀번호는 Git에 커밋하지 않는다. URL에 넣을 수 있는 문자로 설정한다.
- PostgreSQL 준비 전에는 적재 컨테이너가 실행되지 않으며, 적재가 실패하면 API도 시작하지 않는다. 기존 볼륨의 DB 비밀번호만 `.env`에서 바꾸면 기존 DB 계정과 불일치할 수 있다. 기존 DB를 유지하려면 계정 비밀번호를 DB에서 변경한다. `docker compose down -v`는 합성 DB와 모델 캐시를 **삭제**한다.
- `/health`는 DB 연결만 확인한다. 호스트 Ollama가 꺼져 있거나 모델이 없으면 답변 요청은 503이 될 수 있다. 호스트 Ollama가 외부 컨테이너 연결을 허용해야 한다.
- 첫 정책 요청의 임베딩 모델 다운로드·초기화는 느릴 수 있다. 이 환경의 첫 Compose 요청은 약 92초였고 200과 정책 인용을 반환했다. 이는 품질이나 일반적인 응답 시간 보장이 아니다.
- CI는 결정적 코드와 가짜 모델을 쓰는 API 통합 테스트를 실행한다. 실제 Ollama 답변 품질은 기존 Phase 4·5 평가 결과를 참고해야 한다.

로컬 검증 기록: `docker compose config --quiet`, CPU 전용 API 이미지 빌드, Compose DB 적재 완료, `/health` 200, 주문·정책 HTTP 200 및 인용, Gold 40개 검증 통과, 실제 PostgreSQL/pgvector 포함 pytest 25개 통과.
