"""요청 하나 동안 Ollama가 쓴 토큰 수를 모아 서비스 로그에 남긴다.

ContextVar를 써서 동시에 들어온 요청끼리 집계가 섞이지 않는다.
"""

from __future__ import annotations

from contextvars import ContextVar

# (입력 토큰 수, 출력 토큰 수). 아직 기록이 없으면 None.
_tokens: ContextVar[tuple[int, int] | None] = ContextVar("supportops_tokens", default=None)


def reset_usage() -> None:
    """새 요청을 처리하기 전에 토큰 집계를 비운다."""
    _tokens.set(None)


def record_usage(input_tokens: int | None, output_tokens: int | None) -> None:
    """모델 응답 하나의 토큰 수를 더한다. 둘 중 하나라도 없으면 기록하지 않는다."""
    if input_tokens is None or output_tokens is None:
        return
    previous = _tokens.get() or (0, 0)
    _tokens.set((previous[0] + input_tokens, previous[1] + output_tokens))


def get_usage() -> tuple[int, int] | None:
    """현재 요청에서 쓴 (입력, 출력) 토큰 수를 돌려준다."""
    return _tokens.get()
