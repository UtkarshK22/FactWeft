"""FactWeft API application.

Wiring only: settings, CORS, request-id propagation, structured error bodies and
the route modules. FalkorDB availability is surfaced as 503; the API never
answers memory questions from a local copy.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import get_app_settings
from app.api.routes import demo, graph, health, me, memories, handoffs, trace
from app.core.auth import get_token_registry
from app.core.config import Settings, get_settings
from app.core.context import (
    get_request_id,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from app.core.errors import ApiError, GraphUnavailable
from app.graph.connection import GraphClient

logger = logging.getLogger("factweft.api")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    # Fail fast on a malformed token file instead of 401-ing everything later.
    get_token_registry()
    client = GraphClient(settings)
    app.state.graph_client = client
    logger.info("FactWeft api started (falkordb=%s)", settings.falkordb_endpoint)
    try:
        yield
    finally:
        await client.aclose()
        logger.info("FactWeft api stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Graph-native memory coordination for multi-agent teams.",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        candidate = request.headers.get("X-Request-ID", "")
        request_id = candidate if _REQUEST_ID.match(candidate) else new_request_id()
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            exc.as_body(get_request_id()),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(GraphUnavailable)
    async def graph_unavailable_handler(_request: Request, exc: GraphUnavailable) -> JSONResponse:
        logger.warning("falkordb unavailable: %s", exc)
        return JSONResponse(
            {
                "error": "graph_unavailable",
                "message": (
                    "FalkorDB is unavailable. FactWeft does not serve memory data "
                    "from a local copy; retry once the graph is back."
                ),
                "request_id": get_request_id(),
            },
            status_code=503,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        detail = [
            {
                "loc": list(error.get("loc", [])),
                "msg": str(error.get("msg", "")),
                "type": error.get("type"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            {
                "error": "invalid_request",
                "message": "Request validation failed",
                "detail": detail,
                "request_id": get_request_id(),
            },
            status_code=400,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            {
                "error": "internal_error",
                "message": "Unexpected server error",
                "request_id": get_request_id(),
            },
            status_code=500,
        )

    for router in (
        health.router,
        me.router,
        memories.router,
        handoffs.router,
        trace.router,
        graph.router,
        demo.router,
    ):
        app.include_router(router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    async def root(
        settings: Annotated[Settings, Depends(get_app_settings)],
    ) -> dict[str, str]:
        return {"app": settings.app_name, "health": f"{settings.api_prefix}/health"}

    return app


app = create_app()
