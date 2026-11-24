"""SupportOps AI: 근거 기반 한국어 커머스 고객지원 에이전트.

모듈 구성
- structured, database: 주문·상품 데이터 (CSV, PostgreSQL)
- lexical, dense, hybrid, vector_store: 정책 문서 검색 (BM25, 임베딩, RRF 결합)
- rag: 검색한 정책 근거로 답변을 생성하고 인용을 검증
- eligibility, agent: 주문 질문 라우팅과 환불·취소 규칙 판단
- api: FastAPI 서비스
"""
