from __future__ import annotations

import pytest
from app.graph.bootstrap import MEMORY_INDEXES, SCHEMA_LABELS, ensure_schema
from app.graph.connection import GraphClient

pytestmark = pytest.mark.integration


async def test_ensure_schema_creates_indexes_and_unique_ids(
    graph_client: GraphClient, throwaway_graph: str
) -> None:
    report = await ensure_schema(graph_client, throwaway_graph)

    assert report.constraints_pending == ()
    for label in SCHEMA_LABELS:
        assert f"{label}.id" in report.indexes_created
        assert f"{label}.id" in report.constraints_created
    for label, prop in MEMORY_INDEXES:
        assert f"{label}.{prop}" in report.indexes_created
    assert report.constraints_total >= len(SCHEMA_LABELS)


async def test_ensure_schema_is_idempotent(graph_client: GraphClient, throwaway_graph: str) -> None:
    first = await ensure_schema(graph_client, throwaway_graph)
    second = await ensure_schema(graph_client, throwaway_graph)

    assert second.indexes_created == ()
    assert second.constraints_created == ()
    assert second.constraints_pending == ()
    assert second.indexes_total == first.indexes_total
    assert second.constraints_total == first.constraints_total


async def test_unique_constraint_rejects_duplicate_ids(
    graph_client: GraphClient, throwaway_graph: str
) -> None:
    from app.core.errors import GraphQueryFailed

    await ensure_schema(graph_client, throwaway_graph)
    await graph_client.run(
        throwaway_graph,
        "test.create_unique",
        "CREATE (m:Memory {id: $id})",
        {"id": "mem_dup"},
        write=True,
    )
    with pytest.raises(GraphQueryFailed):
        await graph_client.run(
            throwaway_graph,
            "test.create_duplicate",
            "CREATE (m:Memory {id: $id})",
            {"id": "mem_dup"},
            write=True,
        )
