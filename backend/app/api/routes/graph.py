"""Graph projection endpoints.

The root memory is resolved inside the principal's workspace, so an id from
another workspace reads as 404. The projection is bounded in FalkorDB: the cap
and the total count are separate statements, and ``truncated`` says whether the
cap bit.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_app_settings, get_graph_client
from app.core.auth import Principal, get_principal
from app.core.config import Settings
from app.core.errors import NotFound
from app.graph import queries, repo
from app.graph.connection import GraphClient
from app.models.graph import NeighborhoodProjection

router = APIRouter(tags=["graph"])


@router.get(
    "/graph/neighborhood",
    response_model=NeighborhoodProjection,
    summary="Bounded projection around one memory",
)
async def neighborhood(
    principal: Annotated[Principal, Depends(get_principal)],
    client: Annotated[GraphClient, Depends(get_graph_client)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    memory_id: Annotated[str, Query(description="root memory id (must be in this workspace)")],
    hops: Annotated[int, Query(ge=1, le=queries.NEIGHBORHOOD_MAX_HOPS)] = (
        queries.NEIGHBORHOOD_MAX_HOPS
    ),
    max_nodes: Annotated[
        int, Query(ge=0, le=500, description="cap; 0 uses MAX_GRAPH_NODES (also the ceiling)")
    ] = 0,
    status: Annotated[str | None, Query(description="filter Memory nodes by status")] = None,
    kind: Annotated[str | None, Query(description="filter Memory nodes by kind")] = None,
    scope: Annotated[str | None, Query(description="filter Memory nodes by scope")] = None,
    agent_id: Annotated[str | None, Query(description="filter by proposing agent")] = None,
    as_of_ms: Annotated[int | None, Query(ge=0, description="epoch ms; hides later claims")] = None,
) -> NeighborhoodProjection:
    cap = settings.max_graph_nodes if max_nodes < 1 else min(max_nodes, settings.max_graph_nodes)
    projection = await repo.neighborhood(
        client,
        principal.workspace_id,
        memory_id,
        hops=hops,
        max_nodes=cap,
        status=status,
        kind=kind,
        scope=scope,
        agent_id=agent_id,
        as_of_ms=as_of_ms,
    )
    if projection is None:
        raise NotFound(f"memory '{memory_id}' not found in this workspace")
    return projection
