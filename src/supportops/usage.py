"""Per-request Ollama token counters for service logs."""

from __future__ import annotations

from contextvars import ContextVar

_tokens: ContextVar[tuple[int, int] | None] = ContextVar("supportops_tokens", default=None)


def reset_usage() -> None:
    """Start a fresh counter for one support request."""
    _tokens.set(None)


def record_usage(input_tokens: int | None, output_tokens: int | None) -> None:
    """Add provider counts only when both fields are available."""
    if input_tokens is None or output_tokens is None:
        return
    previous = _tokens.get() or (0, 0)
    _tokens.set((previous[0] + input_tokens, previous[1] + output_tokens))


def get_usage() -> tuple[int, int] | None:
    """Return this request's prompt and generated token counts."""
    return _tokens.get()
