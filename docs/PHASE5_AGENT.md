# Phase 5 — 주문 Tool Calling 고객지원 흐름

## 재현

로컬 Ollama 서버와 `qwen2.5:3b` 모델이 필요하다. Ollama 앱을 실행하거나 `ollama serve`를 사용한다. API 키는 필요하지 않다.

```bash
ollama pull qwen2.5:3b
python3 -m pip install -e '.[dev]'
python3 scripts/ask_support.py 'ORD-1008 지금 취소 가능해?' --as-of 2026-10-05
python3 scripts/validate_gold_dataset.py
python3 -m pytest -q
python3 scripts/evaluate_agent.py > reports/phase5_agent_local.json
python3 scripts/summarize_agent_review.py
```

기본 실행일은 시스템 날짜다. 질문에 `YYYY-MM-DD`가 있으면 그 날짜를 우선 사용한다. Gold 평가는 원래 질문의 기준일에 맞춰 `2026-10-05`를 고정했다. `SUPPORTOPS_AGENT_MODEL` 환경 변수로 주문 의도 모델을 바꿀 수 있다. 보고서의 모델 digest는 `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`다.

## 경로와 역할

```text
질문 → Ollama 네이티브 get_order(order_id, intent) 호출 제안
     → 주문 ID·Tool 이름·intent 검증 → CSV get_order
     → 필요할 때 CSV get_product → Python 환불/취소 규칙
     → 결과와 정책 청크 출처를 담은 답변 또는 판단 보류
```

모델은 첫 Tool과 `refund`/`cancel`/`shipping` 의도만 고른다. 질문의 주문 ID와 다른 ID를 제안하면 실행하지 않는다. `get_product`와 `check_refund_eligibility`/`check_cancel_eligibility` 호출은 조회 결과와 의도에 따라 코드가 결정한다. 따라서 전체 Tool 순서 정확도는 모델 혼자 모든 Tool을 선택한 수치가 아니다. 이 호출 형태는 [Ollama 공식 Tool Calling 문서](https://docs.ollama.com/capabilities/tool-calling)의 함수 스키마와 응답 구조를 사용한다.

정책만 묻는 질문은 Phase 4 RAG로 넘길 수 있다. 이 단계의 새 평가는 구조화 데이터가 필요한 Gold 11개에 집중한다. 주문·상품 Tool은 합성 CSV를 읽기만 한다. 취소나 환불을 실제로 실행하거나 티켓을 생성하지 않는다. 다단계 진행 상태의 저장, 재개, 승인 분기가 없어서 이번에는 LangGraph를 추가하지 않았다.

환불 규칙은 신청 기간, 주문 상태, 주문제작·위생·디지털 상품 제한, 구성품 확인, 재판매 어려운 상태를 Python으로 판단한다. `used=true`만으로 재판매 불가를 추정하지 않는다. 하자/오배송 주장 또는 확인할 수 없는 상품별 조건이 있으면 일반 단순 변심 규칙으로 결론내지 않고 확인을 요청한다. 회사 귀책이 **확인된** 경우에는 별도 인자로만 규칙에 전달할 수 있으며, 현재 CSV에는 확인 결과가 없어 실제 주문 질문에서 이를 임의로 설정하지 않는다. 금액·기간·예외를 모델이 자유롭게 판정하지 않는다.

## Gold 결과

Gold의 Tool 필요 질문 11개를 같은 주문·상품 CSV와 정책 Corpus로 평가했다. 누락 주문 `ORD-9999`, 송장·위치 정보가 없는 `ORD-1002`, 오타가 있는 취소 질문도 포함된다.

| 지표 | 결과 |
|---|---:|
| 첫 `get_order` Tool 선택 | 11/11 |
| 주문 ID·의도와 후속 엔티티 ID 인자 | 11/11 |
| Gold의 전체 Tool 순서 | 11/11 |
| 기대 판정 결과 | 11/11 |
| 보류 여부 | 11/11 |
| 전체 Workflow 성공(위 자동 조건 모두 충족) | 11/11 |
| 답변의 Gold 필수 사실 포함(수동 검토) | 11/11 |
| 질문당 시간 중앙값 / p95 | 0.759초 / 2.899초 |

상세 Tool 요청·인자·결과·답변·정책 인용은 [`reports/phase5_agent_local.json`](../reports/phase5_agent_local.json)에 있다. 수동 검토는 [`reports/phase5_review.json`](../reports/phase5_review.json)에 결과 파일 해시와 함께 남겼다. 한 사람이 검토했고 독립 재검토자는 없다. Gold 11개를 구현 중에도 사용했으므로 이 100%는 미지 질문에 대한 일반화 성능이 아니다. 시간은 로컬 Ollama의 단일 실행에서 모델 다운로드와 서버 시작을 제외한 값이다.

## 확인한 경계와 남은 범위

- `used=true`만 있고 재판매가 어려운지 불명확하면 `needs_review`다. 착용·오염과 재판매 불가가 명시된 `ORD-1007`은 단순 변심 환불 불가다.
- 고객의 하자·오배송 주장은 회사 귀책 확정으로 취급하지 않는다. 상품별 별도 조건의 실내용 데이터가 없으면 보류한다.
- `PAID`/`PREPARING`의 전체 취소 요청 가능 여부와 주문제작 시작 여부를 분리한다. `SHIPPED` 이후는 일반 취소 절차가 아니다.
- `ORD-1002`의 `SHIPPED` 상태는 알려주지만 실제 택배 위치는 알 수 없다고 답한다. `ORD-9999`는 조회 실패 후 멈춘다.
- 단순 변심 환불 기간의 7일째와 8일째를 테스트했다. 최종 환불 승인은 반품 검수와 실제 개별 조건 확인이 필요하다.

Phase 6의 API, SQLAlchemy, 서비스 DB, 실제 외부 시스템 연결은 포함하지 않았다.
