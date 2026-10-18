"""Shared fixtures.

Integration tests talk to a real FalkorDB (inside the compose network when run
through `make test`, or localhost from a host virtualenv). Each test that writes
gets its own throwaway graph, deleted afterwards.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from app.core.config import Settings
from app.graph.connection import GraphClient
from app.graph.names import graph_name_for_workspace


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest_asyncio.fixture
async def graph_client(settings: Settings) -> AsyncIterator[GraphClient]:
    client = GraphClient(settings)
    if not await client.ping():
        await client.aclose()
        pytest.fail(
            f"FalkorDB unreachable at {settings.falkordb_endpoint}. "
            "Start it with `docker compose up -d`."
        )
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def throwaway_graph(graph_client: GraphClient) -> AsyncIterator[str]:
    name = f"ws_test_{uuid.uuid4().hex[:10]}"
    yield name
    await graph_client.delete_graph(name)


@pytest_asyncio.fixture
async def throwaway_workspace(graph_client: GraphClient) -> AsyncIterator[str]:
    """A workspace id whose derived graph (``ws_<id>``) is deleted afterwards."""
    workspace_id = f"test_{uuid.uuid4().hex[:10]}"
    yield workspace_id
    await graph_client.delete_graph(graph_name_for_workspace(workspace_id))
