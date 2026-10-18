from __future__ import annotations

import pytest
from app.core.errors import GraphQueryFailed
from app.graph.connection import GraphClient

pytestmark = pytest.mark.integration


async def test_write_then_read_through_falkordb(
    graph_client: GraphClient, throwaway_graph: str
) -> None:
    write = await graph_client.run(
        throwaway_graph,
        "test.create",
        "CREATE (m:Memory {id: $id, status: $status, revision: 1}) RETURN m.id AS id",
        {"id": "mem_1", "status": "active"},
        write=True,
    )
    assert write.rows == [{"id": "mem_1"}]
    assert write.stats.nodes_created == 1
    assert write.stats.mutated is True

    read = await graph_client.run(
        throwaway_graph,
        "test.read",
        "MATCH (m:Memory {id: $id}) RETURN m.status AS status, m.revision AS revision",
        {"id": "mem_1"},
    )
    assert read.rows == [{"status": "active", "revision": 1}]
    assert read.stats.mutated is False
    assert read.duration_ms >= 0


async def test_read_is_served_by_ro_query(graph_client: GraphClient, throwaway_graph: str) -> None:
    await graph_client.run(
        throwaway_graph,
        "test.seed",
        "CREATE (:Memory {id: $id})",
        {"id": "mem_ro"},
        write=True,
    )
    # A mutating statement on the read path must fail at the server, proving
    # reads do not use GRAPH.QUERY.
    with pytest.raises(GraphQueryFailed):
        await graph_client.run(
            throwaway_graph,
            "test.write_on_read_path",
            "CREATE (:Memory {id: 'bad'})",
        )


async def test_trace_buffer_records_queries(
    graph_client: GraphClient, throwaway_graph: str
) -> None:
    # A fresh FalkorDB graph only exists after its first write, so seed it first.
    await graph_client.run(
        throwaway_graph,
        "trace.seed",
        "CREATE (:Memory {id: 'trace_seed'})",
        write=True,
    )
    await graph_client.run(
        throwaway_graph,
        "trace.probe",
        "RETURN $value AS value",
        {"value": "x", "api_key": "sk-secret"},
    )
    traces = graph_client.recent_traces(10)
    assert traces, "expected at least one trace entry"
    latest = traces[0]
    assert latest["query_name"] == "trace.probe"
    assert latest["request_id"] == "-"  # outside a request context
    assert latest["params"]["api_key"] == "***"
    assert latest["rows"] == 1
    assert latest["error"] is None
