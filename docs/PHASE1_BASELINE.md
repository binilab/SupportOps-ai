# Phase 1 — BM25 정책 검색 기준선

## 재현 방법

```bash
python3 -m pip install -e '.[dev]'
python3 scripts/validate_gold_dataset.py
python3 -m pytest -q
python3 scripts/evaluate_bm25.py > reports/phase1_bm25_baseline.json
```

고정 Gold 40개 중 `expected_policy_ids`가 있는 37개만 정책 검색 지표에 사용한다. 정책 ID가 비어 있는 범위 밖 질문 3개는 제외한다. 원본 Gold와 정책 파일은 수정하지 않고 SHA-256을 결과에 기록한다.

## 데이터와 검색 단위

- 입력: `data/raw/policies/*.md` 8개를 `PolicyDocument(policy_id, source_path, title, text)`로 읽는다. `##` 절마다 청크를 만들어 35개 청크를 인덱싱한다.
- 청크 스키마: `chunk_id`, `policy_id`, `source_path`, `title`, `heading`, `text`. 검색 텍스트는 제목·절 제목·본문이다.
- 토큰화: 소문자화 후 `[가-힣A-Za-z0-9]+` 정규식으로 분리한다. 정책과 질문에 동일하게 적용한다. 형태소 분석과 질의 재작성은 하지 않는다.
- 순위: `rank-bm25==0.2.2`의 `BM25Okapi` 기본 설정으로 청크 점수를 계산한다. 점수가 0 이하인 청크는 버리고 정책 ID별 최고 점수 청크만 남긴다. 동점은 정책 ID 순으로 정렬한다.
- 평가: 각 질문의 필수 정책 ID 중 상위 k개의 **서로 다른 정책 ID**에서 찾은 비율을 Recall@k로 계산한 뒤 질문별 평균을 낸다. MRR은 첫 관련 정책의 역순위를 질문별 평균한다. 여러 정책이 필요한 질문은 Recall에 부분 점수가 반영된다.
- latency: 인덱스 생성 및 파일 읽기를 제외한 `search()` 호출 시간. 아래 수치는 이번 로컬 실행의 관측값이다.

`rank-bm25`는 전처리를 제공하지 않으므로 이 토큰화는 프로젝트 코드에서 고정한다. [패키지 사용법](https://github.com/dorianbrown/rank_bm25/blob/master/README.md)

## 첫 기준선 결과

| 지표 | 결과 |
|---|---:|
| Gold 전체 / 평가 / 제외 | 40 / 37 / 3 |
| 정책 / 청크 | 8 / 35 |
| Recall@1 | 0.6081 |
| Recall@3 | 0.8378 |
| Recall@5 | 0.9459 |
| MRR | 0.7883 |
| 검색 시간 중앙값 / p95 | 0.045 / 0.092 ms |

상세 수치, 입력 해시, Top 5 실패 목록은 [`reports/phase1_bm25_baseline.json`](../reports/phase1_bm25_baseline.json)에 있다. 이 지표는 **정책 검색**만 측정하며 답변 정확성, 주문 조회, 답변 거부 능력을 의미하지 않는다. 작은 합성 Corpus의 로컬 latency는 운영 환경의 응답 시간을 대표하지 않는다.

## 실패 사례

- `eval_0018` (`ORD-9999 환불돼?`): `환불돼`와 정책의 `환불`이 단순 토큰화에서 일치하지 않아 관련 정책이 Top 5에 없다. 주문 존재 여부 판단은 이 검색 평가 대상이 아니다.
- `eval_0033` (`취쏘` 오타): 취소 정책과 맞는 토큰이 없어 관련 정책이 Top 5에 없다.

이 실패는 기준선의 관측 결과로 남긴다. Gold 질문을 수정하거나 이후 단계의 검색 개선을 미리 적용하지 않는다.
