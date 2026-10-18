"""T01 -- persistence across a FalkorDB container restart.

Runs only where the Docker CLI is available (i.e. from the host), because it
restarts ``factweft-falkordb`` via ``docker compose restart``. Inside the api
container it skips with an explicit reason instead of pretending to pass.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
from app.graph.bootstrap import ensure_schema
from app.graph.connection import GraphClient

pytestmark = [pytest.mark.integration, pytest.mark.docker_control]

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _restart_falkordb() -> None:
    subprocess.run(
        ["docker", "compose", "restart", "falkordb"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )


async def _wait_until_reachable(client: GraphClient, timeout_s: float = 90.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if await client.ping():
            return
        await asyncio.sleep(1.0)
    pytest.fail("FalkorDB did not become reachable again after restart")


async def test_t01_memory_survives_falkordb_restart(
    graph_client: GraphClient, throwaway_graph: str
) -> None:
    if shutil.which("docker") is None:
        pytest.skip(
            "docker CLI is unavailable here (running inside a container). "
            "Run `pytest -m docker_control` from the host to exercise T01."
        )

    await ensure_schema(graph_client, throwaway_graph)
    marker = f"mem_t01_{uuid4().hex[:8]}"
    await graph_client.run(
        throwaway_graph,
        "t01.write",
        "CREATE (m:Memory {id: $id, status: 'active', summary: 'persistence check'}) "
        "RETURN m.id AS id",
        {"id": marker},
        write=True,
    )

    _restart_falkordb()
    await _wait_until_reachable(graph_client)

    outcome = await graph_client.run(
        throwaway_graph,
        "t01.read",
        "MATCH (m:Memory {id: $id}) RETURN m.status AS status, m.summary AS summary",
        {"id": marker},
    )
    assert outcome.rows == [{"status": "active", "summary": "persistence check"}]
