# Phase 2 — Dense 검색과 pgvector 저장 경로

## 재현 방법

```bash
python3 -m pip install -e '.[dev]'
python3 scripts/validate_gold_dataset.py
python3 -m pytest -q
python3 scripts/evaluate_dense.py --backend local > reports/phase2_dense_local.json
```

첫 실행에는 [모델 파일](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)을 다운로드할 수 있는 네트워크가 필요하다. 코드에서 모델 revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`와 CPU 실행을 고정한다. 모델은 384차원 벡터를 출력한다.

PostgreSQL/pgvector 경로를 재현할 때는 Docker Desktop을 실행하고 로컬 테스트용 비밀번호를 환경 변수에 설정한다. 비밀번호는 저장소에 기록하지 않는다.

```bash
docker run --rm --name supportops-phase2-db \
  -e POSTGRES_USER=supportops -e POSTGRES_DB=supportops \
  -e POSTGRES_PASSWORD="$SUPPORTOPS_DB_PASSWORD" \
  -p 127.0.0.1:55432:5432 -d pgvector/pgvector:0.8.7-pg17
export PGPASSWORD="$SUPPORTOPS_DB_PASSWORD"
export SUPPORTOPS_DATABASE_URL='postgresql://supportops@127.0.0.1:55432/supportops'
python3 scripts/evaluate_dense.py --backend pgvector > reports/phase2_dense_pgvector.json
SUPPORTOPS_TEST_DATABASE_URL="$SUPPORTOPS_DATABASE_URL" python3 -m pytest -q
```

`SUPPORTOPS_DB_PASSWORD`는 명령 실행 전에 본인이 정한 로컬 비밀번호로 설정해야 한다. 작업이 끝나면 `docker stop supportops-phase2-db`로 임시 DB를 종료할 수 있다.

## 설계와 평가 조건

- Phase 1과 동일한 정책 8개·청크 35개, Gold 40개를 사용한다. 정책 ID가 없는 3개를 제외한 37개를 동일한 `evaluate()` 함수로 측정한다. 세 보고서의 Gold/정책 SHA-256이 같다.
- [`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)를 사용한다. 제목·절 제목·본문을 합친 청크와 질문을 모두 정규화된 384차원 벡터로 변환한다. 코사인 유사도로 순위를 매기고 정책 ID별 최고 점수 청크를 남긴다.
- 로컬 경로는 NumPy 점곱으로, DB 경로는 pgvector의 코사인 거리 연산자 `<=>`로 검색한다. DB에는 모델 revision, 청크 ID, 정책 ID, 출처 경로, 벡터를 저장한다. 동일 revision의 데이터만 교체하므로 재실행 결과가 중복되지 않는다.
- 현재 35개 청크에서는 pgvector의 **정확한 탐색**을 사용한다. 근사 인덱스(HNSW/IVFFlat)는 이 단계에서 필요하지 않다. [pgvector 공식 문서](https://github.com/pgvector/pgvector)
- `policy_id` 메타데이터 필터를 지원하고 DB 통합 테스트에서 확인했다.
- latency는 모델 로딩과 문서 임베딩 생성 시간을 제외하고, 질문 임베딩과 검색 호출을 포함한다. 아래 값은 이 로컬 컴퓨터의 단일 실행값이며 운영 환경 지표가 아니다.

## 측정 결과

| 지표 | BM25 기준선 | Dense 로컬 | Dense pgvector |
|---|---:|---:|---:|
| Recall@1 | 0.6081 | 0.7297 | 0.7297 |
| Recall@3 | 0.8378 | 0.8378 | 0.8378 |
| Recall@5 | 0.9459 | 0.9189 | 0.9189 |
| MRR | 0.7883 | 0.8905 | 0.8905 |
| 검색 시간 중앙값 | 0.045 ms | 5.680 ms | 7.071 ms |
| 검색 시간 p95 | 0.092 ms | 7.186 ms | 8.310 ms |

Dense의 Recall@1·MRR은 이 고정 Gold에서 BM25보다 높았지만 Recall@5는 낮았다. pgvector에는 벡터 35개를 실제 저장했으며, 같은 Gold에서 로컬 경로와 모든 검색 지표 및 Top 5 실패 목록이 일치했다. 상세 결과는 [`reports/phase2_dense_local.json`](../reports/phase2_dense_local.json)과 [`reports/phase2_dense_pgvector.json`](../reports/phase2_dense_pgvector.json)에 있다.

## 확인한 실패와 범위

Dense의 Top 5 누락은 `eval_0010`, `eval_0013`, `eval_0016`, `eval_0033`, `eval_0040`이다. 앞의 주문제작·위생·개별 조건 사례는 여러 필수 정책 중 `policy_product_restrictions_v1`이 뒤로 밀렸다. 오타 질문 `eval_0033`도 취소 정책을 찾지 못했다. 이 결과는 이후 검색 개선의 근거로 남기며 Gold나 정책 문구를 성능에 맞춰 수정하지 않는다.

정책 검색만 측정했다. 주문 조회, 답변 생성, 답변 거부, 환불 적격성 로직은 평가하지 않았다.
