"""Health endpoint.

Always answers 200 with the *status* of the store: a demo that is up while
FalkorDB is down should say ``falkordb: "down"`` (and every graph route answers
503). It never fabricates graph_seeded from local state.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings, get_graph_client
from app.core.config import Settings
from app.core.errors import GraphUnavailable
from app.graph.bootstrap import is_workspace_seeded
from app.graph.connection import GraphClient
from app.models.api import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="API + FalkorDB health")
async def health(
    client: Annotated[GraphClient, Depends(get_graph_client)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> HealthResponse:
    falkordb_ok = await client.ping()
    graph_seeded = False
    if falkordb_ok:
        try:
            graph_seeded = await is_workspace_seeded(client)
        except GraphUnavailable:
            falkordb_ok = False
            graph_seeded = False
    return HealthResponse(
        falkordb="ok" if falkordb_ok else "down",
        graph_seeded=graph_seeded,
        llm_mode=settings.llm_mode,
    )
