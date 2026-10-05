# Phase 3 — Hybrid 검색 실험

## 재현 방법과 고정 조건

```bash
python3 -m pip install -e '.[dev]'
python3 scripts/validate_gold_dataset.py
python3 -m pytest -q
python3 scripts/evaluate_hybrid.py > reports/phase3_hybrid_rrf.json
```

Phase 1·2와 같은 정책 8개/청크 35개 및 Gold 40개를 사용했다. 정책 ID가 표시된 37개만 검색 지표에 포함하고 나머지 3개는 제외했다. 세 보고서의 Gold SHA-256은 `aa7988d1364a4a3e8020845fe761cbfb545e074d02b5cba55d31a0d2248c5b6c`, 정책 원본 SHA-256은 `7d336e6ee69406f488f0f9677be34adf5e8930193028f0a81f3fcb2f51e4a1ce`로 같다. Gold나 정책 문구는 바꾸지 않았다.

## 방법

BM25와 로컬 Dense에서 각각 정책 ID별 최고 점수 청크로 순위를 만든다. 각 검색기가 모든 8개 정책까지 후보를 반환하면 동일한 정책의 순위를 `1 / (60 + 순위)`로 합산한다. 최종 점수 동점은 정책 ID 순서로 결정한다. 결과에는 해당 정책을 가장 높은 순위에 놓은 검색기의 출처 청크를 남기고, 동일 순위이면 BM25 청크를 사용한다. BM25와 코사인 점수의 수치 범위가 달라 원점수를 직접 합하지 않았다. RRF의 60은 실험 중 Gold에 맞춰 조정하지 않은 고정 상수다. [RRF 원 논문](https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/)

질문 → BM25 정책 순위 + Dense 정책 순위 → 정책 ID별 RRF → 상위 K개의 정책 ID·청크 출처가 평가 경로다. 모델은 Phase 2와 같은 revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`의 `paraphrase-multilingual-MiniLM-L12-v2`를 CPU에서 사용했다.

## 측정 결과

| 지표 | BM25 | Dense 로컬 | Hybrid RRF |
|---|---:|---:|---:|
| Recall@1 | 0.6081 | 0.7297 | **0.7432** |
| Recall@3 | 0.8378 | 0.8378 | **0.9324** |
| Recall@5 | 0.9459 | 0.9189 | **0.9730** |
| MRR | 0.7883 | 0.8905 | **0.9009** |
| 검색 시간 중앙값 | 0.045 ms | 5.680 ms | 6.208 ms |
| 검색 시간 p95 | 0.092 ms | 7.186 ms | 7.803 ms |
| Top 5 필수 정책 누락 사례 | 2 | 5 | **1** |

Hybrid는 Dense 대비 Recall@3 +0.0946, Recall@5 +0.0541, MRR +0.0104다. Dense에서 누락됐던 `eval_0010`, `eval_0013`, `eval_0016`, `eval_0040`을 회복하고, BM25의 `eval_0018`도 회복했다. 중앙 검색 시간은 Dense 대비 약 0.528ms, p95는 약 0.617ms 길었다. 이 latency는 각 스크립트의 단일 로컬 실행에서 모델 적재와 문서 임베딩 생성을 제외한 검색 호출 시간이다. 환경과 실행마다 변할 수 있어 운영 latency나 통계적 유의성으로 해석하지 않는다. 원본 수치와 실패 목록은 [`reports/phase3_hybrid_rrf.json`](../reports/phase3_hybrid_rrf.json)에 있다.

## 선택과 남은 실패

같은 Gold에서 모든 검색 품질 지표가 개선됐고 추가 중앙 시간이 약 0.5ms여서 Phase 3의 기본 검색 실험 결과로 Hybrid RRF를 선택한다. CrossEncoder 재순위화는 이 단계의 완료 조건을 충족하는 데 필요하지 않아 도입하지 않았다.

`eval_0033`(오타가 있는 주문 취소 질문)는 여전히 필수 `policy_cancel_v1`이 Top 5에 없다. 두 검색기의 약한 순위가 결합돼도 해결되지 않은 사례다. 정책 ID 검색 지표만 측정했으며, 청크 단위 적합성·답변 정확도·인용 정확도·주문 조회는 이 수치로 보증하지 않는다.
