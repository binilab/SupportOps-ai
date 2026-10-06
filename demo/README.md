# 실제 API 응답 데모

![SupportOps AI API 응답 재생](supportops-demo.gif)

이 GIF는 2026-10-06에 Docker Compose의 FastAPI, 합성 PostgreSQL, 호스트 Ollama로 실행한 **세 개의 실제 HTTP 응답을 장면으로 재생**한 것이다. 연속 화면 녹화는 아니다. 질문·답변·보류 결과·인용 ID의 원본은 [`api_examples.json`](api_examples.json)에 있다. 주문 취소, 존재하지 않는 주문, 제주 배송비 정책을 보여준다. 실제 취소/환불은 실행하지 않았다.

다시 확인하려면 [Compose 실행 안내](../docs/PHASE7_OPERATIONS.md)에 따라 서비스를 시작하고 아래 요청을 보낸다. 모델과 실행 환경에 따라 문구는 조금 달라질 수 있으며, 인용·보류·결정적 주문 판정 경계를 확인하는 것이 목적이다.

```bash
curl -sS http://127.0.0.1:8000/v1/answer -H 'Content-Type: application/json' \
  -d '{"question":"ORD-1008 지금 취소 가능해?","as_of":"2026-10-05"}'
curl -sS http://127.0.0.1:8000/v1/answer -H 'Content-Type: application/json' \
  -d '{"question":"ORD-9999 취소 가능해?","as_of":"2026-10-05"}'
curl -sS http://127.0.0.1:8000/v1/answer -H 'Content-Type: application/json' \
  -d '{"question":"제주도는 배송비가 더 붙어?"}'
```
