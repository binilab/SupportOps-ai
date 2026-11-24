"""고객지원 에이전트를 HTTP API로 제공한다 (FastAPI, 읽기 전용).

엔드포인트
- GET  /health     : DB 연결 확인
- POST /v1/answer  : 질문을 받아 답변, 보류 여부, 인용, 도구 실행 내역을 돌려준다.

요청마다 요청 ID, 결과 코드, 지연 시간, 토큰 수를 JSON 한 줄로 로그에 남긴다.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import AsyncIterator, Callable, Iterator
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from ollama import RequestError, ResponseError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from supportops.agent import OllamaOrderRouter, OrderRouter, SupportAgent
from supportops.database import SQLAlchemyStructuredStore, make_engine
from supportops.lexical import load_policy_chunks
from supportops.rag import ORDER_ID_RE, OllamaAnswerModel, PolicyRAG
from supportops.usage import get_usage, reset_usage

ROOT = Path(__file__).resolve().parents[2]
# 구조화 로그: 메시지에 JSON 한 줄만 찍어서 로그 수집 도구가 바로 파싱할 수 있게 한다.
LOG = logging.getLogger("supportops.api")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOG.addHandler(handler)
LOG.propagate = False


class QuestionRequest(BaseModel):
    """POST /v1/answer 요청 본문. 정의되지 않은 필드가 오면 거부한다."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    as_of: date | None = None  # 환불 기간 계산 기준일. 없으면 오늘

    @field_validator("question")
    @classmethod
    def non_blank_question(cls, value: str) -> str:
        """앞뒤 공백을 지우고, 공백만 있는 질문은 거부한다."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class CitationResponse(BaseModel):
    """응답의 인용 한 건."""

    policy_id: str
    chunk_id: str
    source_path: str


class ToolTraceResponse(BaseModel):
    """응답의 도구 실행 내역 한 건."""

    name: str
    arguments: dict[str, object]
    result: str


class AnswerResponse(BaseModel):
    """POST /v1/answer 응답 본문."""

    answer: str
    abstained: bool
    outcome: str
    citations: list[CitationResponse]
    trace: list[ToolTraceResponse]


@lru_cache(maxsize=1)
def _production_rag() -> PolicyRAG:
    """서비스용 정책 RAG를 만든다 (하이브리드 검색 + Ollama).

    임베딩 모델을 불러오는 데 시간이 걸려서, 서버 시작 시점이 아니라 첫 정책 질문이 올 때 한 번만 만든다.
    """
    from supportops.dense import DensePolicyIndex, load_embedding_model
    from supportops.hybrid import HybridPolicyIndex
    from supportops.lexical import BM25PolicyIndex

    chunks = load_policy_chunks(ROOT / "data/raw/policies", ROOT)
    retriever = HybridPolicyIndex(BM25PolicyIndex(chunks), DensePolicyIndex(chunks, load_embedding_model()))
    return PolicyRAG(retriever, OllamaAnswerModel())


def create_app(
    database_url: str | None = None,
    *,
    router: OrderRouter | None = None,
    policy_rag: PolicyRAG | None = None,
) -> FastAPI:
    """FastAPI 앱을 만든다.

    router와 policy_rag를 넘기면 실제 LLM 대신 그 객체를 쓴다.
    테스트에서 가짜 모델을 넣어 결과를 항상 같게 만들기 위한 인자다.
    """
    configured_url = database_url or os.environ.get("SUPPORTOPS_DATABASE_URL")
    engine: Engine | None = make_engine(configured_url) if configured_url else None
    order_router = router or OllamaOrderRouter()
    chunks = load_policy_chunks(ROOT / "data/raw/policies", ROOT)
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """서버가 종료될 때 DB 연결 풀을 정리한다."""
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    service = FastAPI(title="SupportOps AI", version="0.1.0", lifespan=lifespan)

    @service.middleware("http")
    async def log_request(request: Request, call_next: Callable) -> Response:
        """모든 요청에 요청 ID를 붙이고, 처리 결과를 구조화 로그로 남긴다.

        DB나 모델 서버 장애는 503, 그 밖의 예외는 500으로 바꿔서 내부 오류 내용이 응답에 노출되지 않게 한다.
        """
        request_id = uuid4().hex
        started = perf_counter()
        try:
            response = await call_next(request)
        except SQLAlchemyError:
            LOG.exception("database request failed")
            response = JSONResponse({"detail": "database unavailable"}, status_code=503)
        except (httpx.HTTPError, RequestError, ResponseError):
            LOG.exception("model request failed")
            response = JSONResponse({"detail": "model unavailable"}, status_code=503)
        except Exception:
            LOG.exception("unexpected API failure")
            response = JSONResponse({"detail": "internal server error"}, status_code=500)
        response.headers["X-Request-ID"] = request_id
        # outcome·토큰 수는 /v1/answer 핸들러가 request.state에 넣어 둔 값이다.
        LOG.info(json.dumps({
            "event": "http_request",
            "request_id": request_id,
            "path": request.url.path,
            "status_code": response.status_code,
            "outcome": getattr(request.state, "outcome", None),
            "abstained": getattr(request.state, "abstained", None),
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "token_count": (
                request.state.input_tokens + request.state.output_tokens
                if hasattr(request.state, "input_tokens") else None
            ),
            "input_tokens": getattr(request.state, "input_tokens", None),
            "output_tokens": getattr(request.state, "output_tokens", None),
            # 로컬 Ollama라 금전 비용은 추정하지 않는다.
            "model_cost": None,
        }, ensure_ascii=False))
        return response

    def get_store() -> Iterator[SQLAlchemyStructuredStore]:
        """요청마다 DB 세션을 열고, 요청이 끝나면 닫는다 (FastAPI 의존성)."""
        if engine is None:
            raise HTTPException(status_code=503, detail="database not configured")
        with Session(engine) as session:
            yield SQLAlchemyStructuredStore(session)

    @service.get("/health")
    def health() -> dict[str, str]:
        """DB에 실제로 쿼리를 보내 연결 상태를 확인한다."""
        if engine is None:
            raise HTTPException(status_code=503, detail="database not configured")
        with engine.connect() as connection:
            connection.execute(sql_text("SELECT 1"))
        return {"status": "ok"}

    @service.post("/v1/answer", response_model=AnswerResponse)
    def answer(payload: QuestionRequest, request: Request, store: SQLAlchemyStructuredStore = Depends(get_store)) -> AnswerResponse:
        """질문 하나에 답한다. 실제 환불·취소는 실행하지 않는다."""
        reset_usage()
        # 주문 질문에는 정책 RAG가 필요 없으므로 임베딩 모델을 불러오지 않는다.
        rag = (policy_rag or _production_rag()) if ORDER_ID_RE.search(payload.question) is None else None
        result = SupportAgent(store, order_router, chunks, rag).run(payload.question, payload.as_of)
        request.state.outcome = result.outcome
        request.state.abstained = result.abstained
        usage = get_usage()
        if usage is not None:
            request.state.input_tokens, request.state.output_tokens = usage
        return AnswerResponse(
            answer=result.answer,
            abstained=result.abstained,
            outcome=result.outcome,
            citations=[CitationResponse(**vars(item)) for item in result.citations],
            trace=[ToolTraceResponse(**vars(item)) for item in result.trace],
        )

    return service


app = create_app()
