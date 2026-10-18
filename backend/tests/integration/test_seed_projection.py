"""Seeding idempotency, bounded projections and workspace isolation (T06)."""

from __future__ import annotations

import pytest
from app.core.clock import utc_now_ms
from app.core.config import Settings
from app.graph import repo
from app.graph.connection import GraphClient
from app.graph.names import graph_name_for_workspace
from app.main import create_app
from app.memory.demo_data import DemoWorkspace, load_demo_workspace
from app.memory.seed import seed_workspace
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

NOW = utc_now_ms()
ATLAS_OWNER = {"Authorization": "Bearer tok_atlas_owner_4f0b13"}
ORBIT_OWNER = {"Authorization": "Bearer tok_orbit_owner_3e9c81"}
SCOUT = {"Authorization": "Bearer tok_orbit_scout_1a7d58"}


def as_workspace(source_id: str, workspace_id: str) -> DemoWorkspace:
    """The demo payload retargeted at a throwaway workspace (same ids inside)."""
    base = load_demo_workspace(source_id)
    return base.model_copy(
        deep=True,
        update={"workspace": base.workspace.model_copy(update={"id": workspace_id})},
    )


async def count(client: GraphClient, graph: str, cypher: str) -> int:
    outcome = await client.run(graph, "test.count", cypher)
    row = outcome.rows[0] if outcome.rows else {}
    return int(row.get("n") or 0)


async def test_seed_workspace_is_idempotent(
    graph_client: GraphClient, throwaway_workspace: str
) -> None:
    payload = as_workspace("demo_atlas_release_lab", throwaway_workspace)
    first = await seed_workspace(throwaway_workspace, client=graph_client, data=payload)
    nodes_after_first = await repo.graph_node_count(graph_client, first.graph_name)
    steps_after_first = await count(
        graph_client, first.graph_name, "MATCH (s:Step) RETURN count(s) AS n"
    )

    second = await seed_workspace(throwaway_workspace, client=graph_client, data=payload)
    nodes_after_second = await repo.graph_node_count(graph_client, second.graph_name)
    steps_after_second = await count(
        graph_client, second.graph_name, "MATCH (s:Step) RETURN count(s) AS n"
    )

    assert first.counts == second.counts
    assert nodes_after_first == nodes_after_second
    assert steps_after_first == steps_after_second == len(payload.procedures[0].steps)
    assert len(second.procedure_ids) == len(payload.procedures)
    # One Concept per alias-bearing seed concept, no MERGE duplicates.
    concepts = await count(
        graph_client, second.graph_name, "MATCH (c:Concept) RETURN count(c) AS n"
    )
    assert concepts == len(payload.concepts)


async def test_neighborhood_respects_node_cap_and_reports_counts(
    graph_client: GraphClient, throwaway_workspace: str
) -> None:
    payload = as_workspace("demo_atlas_release_lab", throwaway_workspace)
    await seed_workspace(throwaway_workspace, client=graph_client, data=payload)

    root = "mem_neighborhood_root"
    for index in range(9):
        memory_id = root if index == 0 else f"{root}_{index}"
        await repo.propose_memory(
            graph_client,
            throwaway_workspace,
            memory_id=memory_id,
            agent_id="agent_scout",
            source_id="src_planning_note",
            subject_key="release_freeze",
            kind="semantic",
            predicate="freeze_date",
            object_value=f"2026-10-{10 + index:02d}",
            cardinality="many",
            summary=f"Synthetic projection fixture claim {index}.",
            scope="workspace",
            confidence=0.9,
            now_ms=NOW,
        )

    full = await repo.neighborhood(
        graph_client, throwaway_workspace, root, hops=2, max_nodes=500
    )
    assert full is not None
    assert full.truncated is False
    assert full.counts.shown_nodes == len(full.nodes) == full.counts.total_nodes
    assert full.counts.showing == f"{len(full.nodes)} of {len(full.nodes)} nodes"
    node_ids = {node.id for node in full.nodes}
    assert len(node_ids) == len(full.nodes), "duplicate nodes in projection"
    assert all(edge.source in node_ids and edge.target in node_ids for edge in full.edges)
    assert full.edges, "projection should contain relationships"

    tiny = await repo.neighborhood(
        graph_client, throwaway_workspace, root, hops=2, max_nodes=4
    )
    assert tiny is not None
    assert len(tiny.nodes) <= 4
    assert tiny.truncated is True
    assert tiny.counts.shown_nodes == len(tiny.nodes) < tiny.counts.total_nodes
    assert tiny.counts.total_nodes == full.counts.total_nodes
    assert tiny.counts.showing.startswith(f"{len(tiny.nodes)} of {tiny.counts.total_nodes} ")

    filtered = await repo.neighborhood(
        graph_client,
        throwaway_workspace,
        root,
        hops=2,
        max_nodes=500,
        kind="semantic",
        agent_id="agent_scout",
    )
    assert filtered is not None
    assert filtered.root_id == root
    assert filtered.filters == {
        "status": None,
        "kind": "semantic",
        "scope": None,
        "agent_id": "agent_scout",
        "as_of_ms": None,
    }


async def test_identical_concept_ids_do_not_leak_between_workspaces(
    graph_client: GraphClient, throwaway_workspace: str
) -> None:
    other_graph = f"{throwaway_workspace}_b"
    left = as_workspace("demo_atlas_release_lab", throwaway_workspace)
    right = as_workspace("demo_atlas_release_lab", other_graph)
    await seed_workspace(throwaway_workspace, client=graph_client, data=left)
    await seed_workspace(other_graph, client=graph_client, data=right)
    try:
        shared_memory = "mem_shared_claim"
        for graph, value in ((throwaway_workspace, "left"), (other_graph, "right")):
            await repo.propose_memory(
                graph_client,
                graph,
                memory_id=shared_memory,
                agent_id="agent_scout",
                source_id="src_planning_note",
                subject_key="release_freeze",
                kind="semantic",
                predicate="freeze_date",
                object_value=value,
                cardinality="one",
                summary=f"Synthetic {value} claim on the shared concept id.",
                scope="workspace",
                confidence=0.9,
                now_ms=NOW,
            )
        await repo.propose_memory(
            graph_client,
            throwaway_workspace,
            memory_id="mem_left_only",
            agent_id="agent_scout",
            source_id="src_planning_note",
            subject_key="release_freeze",
            kind="semantic",
            predicate="owner",
            object_value="left",
            cardinality="one",
            summary="Only the left workspace has this claim.",
            scope="workspace",
            confidence=0.9,
            now_ms=NOW,
        )

        left_claim = await repo.memory_by_id(graph_client, throwaway_workspace, shared_memory)
        right_claim = await repo.memory_by_id(graph_client, other_graph, shared_memory)
        assert left_claim is not None and left_claim.object_value == "left"
        assert right_claim is not None and right_claim.object_value == "right"
        assert await repo.memory_by_id(graph_client, other_graph, "mem_left_only") is None
        assert (
            await repo.neighborhood(graph_client, other_graph, "mem_left_only")
        ) is None

        left_projection = await repo.neighborhood(
            graph_client, throwaway_workspace, shared_memory, hops=2, max_nodes=50
        )
        assert left_projection is not None
        # The concept id is identical in both graphs; each graph still returns
        # its own version of the shared memory and never the other's value.
        assert left_projection.root_id == shared_memory
        assert any(
            node.id == shared_memory and node.properties.get("object_value") == "left"
            for node in left_projection.nodes
        )
        assert all(
            node.properties.get("object_value") != "right"
            for node in left_projection.nodes
        )
    finally:
        await graph_client.delete_graph(graph_name_for_workspace(other_graph))


async def test_demo_routes_are_owner_only_and_resettable(settings: Settings) -> None:
    with TestClient(create_app(settings)) as api:
        assert api.post("/api/demo/seed", headers=ORBIT_OWNER).status_code == 200
        forbidden = api.post("/api/demo/seed", headers=SCOUT)
        assert forbidden.status_code == 403
        assert forbidden.json()["error"] == "role_forbidden"

        reset = api.post("/api/demo/reset", headers=ORBIT_OWNER)
        body = reset.json()
        assert reset.status_code == 200, body
        assert body["dropped"] is True
        assert body["nodes_after_reset"] == 0

        reseeded = api.post("/api/demo/seed", headers=ORBIT_OWNER)
        assert reseeded.status_code == 200
        assert reseeded.json()["counts"]["agents"] == 5

    disabled = settings.model_copy(update={"demo_mode": False})
    with TestClient(create_app(disabled)) as api:
        blocked = api.post("/api/demo/seed", headers=ORBIT_OWNER)
        assert blocked.status_code == 403
        assert blocked.json()["error"] == "demo_disabled"


async def test_api_rejects_a_memory_id_from_another_workspace(
    settings: Settings, graph_client: GraphClient
) -> None:
    """T06 at the HTTP boundary: atlas' procedure id is 404 for an orbit owner."""
    await seed_workspace("demo_atlas_release_lab", client=graph_client)
    await seed_workspace("demo_orbit_ops", client=graph_client)
    with TestClient(create_app(settings)) as api:
        atlas = api.get(
            "/api/graph/neighborhood",
            params={"memory_id": "mem_atlas_release_readiness"},
            headers=ATLAS_OWNER,
        )
        orbit = api.get(
            "/api/graph/neighborhood",
            params={"memory_id": "mem_atlas_release_readiness"},
            headers=ORBIT_OWNER,
        )
        assert atlas.status_code == 200
        assert orbit.status_code == 404
        assert orbit.json()["error"] == "not_found"
        assert (
            api.get(
                "/api/graph/neighborhood",
                params={"memory_id": "mem_atlas_release_readiness"},
            ).status_code
            == 401
        )
