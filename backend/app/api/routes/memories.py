"""Memory reads.

The workspace and therefore the graph name come from the principal. A memory
that lives in another workspace is indistinguishable from a missing one (404).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_graph_client
from app.core.auth import Principal, get_principal
from app.core.errors import NotFound
from app.graph import queries
from app.graph.connection import GraphClient
from app.models.api import MemoryDetail, SourceEvidence

router = APIRouter(tags=["memories"])


@router.get(
    "/memories/{memory_id}",
    response_model=MemoryDetail,
    summary="Read one memory with its evidence",
)
async def get_memory(
    memory_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    client: Annotated[GraphClient, Depends(get_graph_client)],
) -> MemoryDetail:
    outcome = await client.run(
        principal.graph_name,
        "memory.by_id",
        queries.Q_MEMORY_BY_ID,
        {"workspace_id": principal.workspace_id, "memory_id": memory_id},
    )
    if not outcome.rows:
        raise NotFound(f"memory '{memory_id}' not found in this workspace")

    row = dict(outcome.rows[0])
    raw_evidence = row.pop("evidence", []) or []
    evidence = [
        SourceEvidence(
            id=str(item["id"]),
            title=item.get("title"),
            authority=item.get("authority"),
        )
        for item in raw_evidence
        if isinstance(item, dict) and item.get("id")
    ]
    return MemoryDetail(**row, evidence=evidence)
