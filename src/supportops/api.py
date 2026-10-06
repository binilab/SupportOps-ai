"""Read-only Phase 6 API for the existing support workflow."""

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
LOG = logging.getLogger("supportops.api")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOG.addHandler(handler)
LOG.propagate = False


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    as_of: date | None = None

    @field_validator("question")
    @classmethod
    def non_blank_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class CitationResponse(BaseModel):
    policy_id: str
    chunk_id: str
    source_path: str


class ToolTraceResponse(BaseModel):
    name: str
    arguments: dict[str, object]
    result: str


class AnswerResponse(BaseModel):
    answer: str
    abstained: bool
    outcome: str
    citations: list[CitationResponse]
    trace: list[ToolTraceResponse]


@lru_cache(maxsize=1)
def _production_rag() -> PolicyRAG:
    """Load the Phase 3 hybrid index only when the first policy question arrives."""
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
    """Build the service; optional collaborators keep integration tests deterministic."""
    configured_url = database_url or os.environ.get("SUPPORTOPS_DATABASE_URL")
    engine: Engine | None = make_engine(configured_url) if configured_url else None
    order_router = router or OllamaOrderRouter()
    chunks = load_policy_chunks(ROOT / "data/raw/policies", ROOT)
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    service = FastAPI(title="SupportOps AI", version="0.1.0", lifespan=lifespan)

    @service.middleware("http")
    async def log_request(request: Request, call_next: Callable) -> Response:
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
            "model_cost": None,
        }, ensure_ascii=False))
        return response

    def get_store() -> Iterator[SQLAlchemyStructuredStore]:
        if engine is None:
            raise HTTPException(status_code=503, detail="database not configured")
        with Session(engine) as session:
            yield SQLAlchemyStructuredStore(session)

    @service.get("/health")
    def health() -> dict[str, str]:
        if engine is None:
            raise HTTPException(status_code=503, detail="database not configured")
        with engine.connect() as connection:
            connection.execute(sql_text("SELECT 1"))
        return {"status": "ok"}

    @service.post("/v1/answer", response_model=AnswerResponse)
    def answer(payload: QuestionRequest, request: Request, store: SQLAlchemyStructuredStore = Depends(get_store)) -> AnswerResponse:
        reset_usage()
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
