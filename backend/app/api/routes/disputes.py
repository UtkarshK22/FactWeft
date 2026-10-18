"""Dispute routes: side-by-side claim comparison.

``GET /api/disputes``           — list disputes (optionally filtered by concept)
``GET /api/disputes/compare``   — compare two specific memories on a shared predicate
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_app_settings, get_graph_client
from app.core.auth import Principal, get_principal
from app.core.config import Settings
from app.graph import queries
from app.graph.connection import GraphClient

router = APIRouter(tags=["disputes"])


@router.get(
    "/disputes",
    response_model=list,
    summary="List disputes (memory comparisons) filtered by concept",
)
async def disputes_list(
    principal: Annotated[Principal, Depends(get_principal)],
    client: Annotated[GraphClient, Depends(get_graph_client)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    concept: str | None = Query(
        None, description="Filter disputes by concept/predicate identifier"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum disputes to return"),
) -> Any:
    """List disputes from the graph.

    A dispute exists between two memories that share the same concept/predicate
    but have conflicting or competing claims.
    """
    q_limit = min(limit, queries.NEIGHBORHOOD_MAX_HOPS)

    query = """"
    MATCH (m1:Memory)-[:INCLUDES|EXCLUDES|TASK]->(t:Task)<-[:TASK]-(m2:Memory)
    WHERE m1.id <> m2.id
    OPTIONAL MATCH (m1)-[r1:STATUS]->(), (m2)-[r2:STATUS]->()

    """

    params = {
        "concept": concept or "",
        "limit": q_limit
    }

    if concept:
        query += " AND (m1.predicate = $concept OR m2.predicate = $concept) "
    
    query += """
    WITH m1, m2, collect(DISTINCT {id: m1.id, predicate: m1.predicate, object_value: m1.object_value, summary: m1.summary, created_at: m1.created_at}) AS m1_colls,
         collect(DISTINCT {id: m2.id, predicate: m2.predicate, object_value: m2.object_value, summary: m2.summary, created_at: m2.created_at}) AS m2_colls
    RETURN m1_colls[0], m2_colls[0], t.task AS shared_task
    LIMIT $limit
    """

    result = await client.run(
        client.graph_name, "disputes.list", query, params
    )

    disputes: list[dict] = []
    for row in result.rows:
        m1 = row[0]
        m2 = row[1]
        disputes.append(
            {
                "memory_a": {
                    "id": m1.get("id"),
                    "predicate": m1.get("predicate"),
                    "object_value": m1.get("object_value"),
                    "summary": m1.get("summary"),
                    "created_at": m1.get("created_at"),
                },
                "memory_b": {
                    "id": m2.get("id"),
                    "predicate": m2.get("predicate"),
                    "object_value": m2.get("object_value"),
                    "summary": m2.get("summary"),
                    "created_at": m2.get("created_at"),
                },
                "shared_task": m2.get("shared_task"),
            }
        )

    return disputes


@router.get(
    "/disputes/compare",
    response_model=dict,
    summary="Compare two memories on a shared predicate",
)
async def disputes_compare(
    principal: Annotated[Principal, Depends(get_principal)],
    client: Annotated[GraphClient, Depends(get_graph_client)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    memory_a_id: str = Query(..., description="First memory id"),
    memory_b_id: str = Query(..., description="Second memory id"),
) -> Any:
    """Compare two memories sharing a predicate.

    Returns side-by-side claim data, including values, sources,
    authority, published dates, proposing agents, and confidence.
    """
    # Fetch both memories
    mem_a = await client.run(
        client.graph_name,
        "memory.by_id",
        {"workspace_id": principal.workspace_id, "memory_id": memory_a_id},
    )
    mem_b = await client.run(
        client.graph_name,
        "memory.by_id",
        {"workspace_id": principal.workspace_id, "memory_id": memory_b_id},
    )

    if not mem_a.rows or not mem_b.rows:
        raise HTTPException(
            status_code=status.HTTP_404,
            detail="One or both memories not found",
        )

    row_a = dict(mem_a.rows[0])
    row_b = dict(mem_b.rows[0])

    # Build side-by-side comparison
    result = {
        "memory_a": {
            "id": row_a.get("id"),
            "predicate": row_a.get("predicate"),
            "object_value": row_a.get("object_value"),
            "summary": row_a.get("summary"),
            "authority": row_a.get("authority"),
            "published_at": row_a.get("published_at"),
            "valid_from": row_a.get("valid_from"),
            "confidence": row_a.get("confidence", 0.0),
            "evidence": row_a.get("evidence", []),
            "proposing_agent": row_a.get("proposing_agent"),
        },
        "memory_b": {
            "id": row_b.get("id"),
            "predicate": row_b.get("predicate"),
            "object_value": row_b.get("object_value"),
            "summary": row_b.get("summary"),
            "authority": row_b.get("authority"),
            "published_at": row_b.get("published_at"),
            "valid_from": row_b.get("valid_from"),
            "confidence": row_b.get("confidence", 0.0),
            "evidence": row_b.get("evidence", []),
            "proposing_agent": row_b.get("proposing_agent"),
        },
        "resolver_table": [
            {
                "criteria": "authority",
                "a_value": row_a.get("authority"),
                "b_value": row_b.get("authority"),
            },
            {
                "criteria": "published_at",
                "a_value": row_a.get("published_at"),
                "b_value": row_b.get("published_at"),
            },
            {
                "criteria": "valid_from",
                "a_value": row_a.get("valid_from"),
                "b_value": row_b.get("valid_from"),
            },
        ],
        "reason_code": row_b.get("reason_code"),  # if superseded/contested
    }

    return result