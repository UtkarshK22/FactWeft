"""Structured application errors.

Every error surfaced by the API has a stable machine-readable ``error`` code.
``GraphUnavailable`` is deliberately *not* an ``ApiError``: it signals that the
only memory store cannot be reached, and the app answers 503 without pretending
to know anything about memories.
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    status_code: int = 400
    code: str = "invalid_request"

    def __init__(
        self,
        message: str,
        *,
        detail: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.headers = headers

    def as_body(self, request_id: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error": self.code,
            "message": self.message,
            "request_id": request_id,
        }
        if self.detail is not None:
            body["detail"] = self.detail
        return body


class AuthRequired(ApiError):
    status_code = 401
    code = "auth_required"


class RoleForbidden(ApiError):
    status_code = 403
    code = "role_forbidden"


class NotFound(ApiError):
    status_code = 404
    code = "not_found"


class DemoDisabled(ApiError):
    """Demo-only endpoints are switched off (DEMO_MODE=false)."""

    status_code = 403
    code = "demo_disabled"


class StaleRevision(ApiError):
    status_code = 409
    code = "stale_revision"


class UnprocessableClaim(ApiError):
    """Insufficient evidence or an unresolved conflict; ``detail`` carries the reason."""

    status_code = 422
    code = "unprocessable_claim"


class GraphQueryFailed(ApiError):
    """A Cypher statement failed. Never masked as a data result."""

    status_code = 500
    code = "graph_query_failed"


class GraphUnavailable(Exception):
    """FalkorDB cannot be reached or dropped the connection.

    Handled at the app level as HTTP 503 ``{"error": "graph_unavailable"}``.
    Callers must never answer from a local copy of memory data.
    """


class InvalidGraphName(ValueError):
    """Graph name failed the ``^[a-z0-9_]{3,40}$`` guard."""
