"""Request-scoped context (request id for traces and error bodies)."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

_request_id: ContextVar[str] = ContextVar("factweft_request_id", default="-")


def new_request_id() -> str:
    return f"req_{uuid4().hex[:16]}"


def set_request_id(value: str) -> object:
    return _request_id.set(value)


def reset_request_id(token: object) -> None:
    _request_id.reset(token)  # type: ignore[arg-type]


def get_request_id() -> str:
    return _request_id.get()
