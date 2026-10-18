from __future__ import annotations

import pytest
from app.core.config import Settings
from app.core.errors import GraphUnavailable, InvalidGraphName
from app.graph.connection import GraphClient


async def test_unreachable_server_pings_false_and_raises_typed_error() -> None:
    settings = Settings(falkordb_host="127.0.0.1", falkordb_port=6390)
    client = GraphClient(settings)
    try:
        assert await client.ping() is False
        with pytest.raises(GraphUnavailable):
            await client.run("ws_unreachable", "q.smoke", "RETURN 1 AS ok")
        with pytest.raises(GraphUnavailable):
            await client.list_graphs()
    finally:
        await client.aclose()


async def test_invalid_graph_name_is_rejected_before_connecting() -> None:
    settings = Settings()
    client = GraphClient(settings)
    try:
        with pytest.raises(InvalidGraphName):
            await client.run("ws demo", "q.bad", "RETURN 1")
    finally:
        await client.aclose()
