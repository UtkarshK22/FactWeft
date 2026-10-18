"""Query trace telemetry.

The ring buffer is telemetry only: it holds query metadata for the UI's Trace
drawer and is explicitly *not* a memory store. The browser never receives a
graph name it can query, only the traced statements.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_graph_client
from app.core.auth import Principal, require_roles
from app.graph.connection import GraphClient
from app.models.api import TraceResponse
from app.models.domain import Role

router = APIRouter(tags=["trace"])

TraceViewer = Annotated[Principal, Depends(require_roles(Role.COORDINATOR, Role.OWNER))]


@router.get("/trace", response_model=TraceResponse, summary="Recent query traces (newest first)")
async def get_trace(
    principal: TraceViewer,
    client: Annotated[GraphClient, Depends(get_graph_client)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> TraceResponse:
    entries = client.recent_traces(limit)
    return TraceResponse(
        capacity=client.trace_capacity,
        count=client.trace_count,
        entries=entries,  # type: ignore[arg-type]
    )
