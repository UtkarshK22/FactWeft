"""Execute every catalogue query through repo.py against a real FalkorDB.

Each test step is a live statement, not a mock: this file is what proves the
catalogue (and the typed wrappers) behave as documented on the pinned image.
"""

from __future__ import annotations

import pytest
from app.core.clock import epoch_ms
from app.graph import repo
from app.graph.connection import GraphClient
from app.memory.demo_data import DemoWorkspace, load_demo_workspace
from app.memory.seed import seed_workspace

pytestmark = pytest.mark.integration

NOW = epoch_ms("2026-10-20T00:00:00Z")
SOURCES = {"planning": "src_orbit_planning", "bulletin": "src_orbit_bulletin"}


def as_workspace(workspace_id: str) -> DemoWorkspace:
    base = load_demo_workspace("demo_orbit_ops")
    return base.model_copy(
        deep=True,
        update={"workspace": base.workspace.model_copy(update={"id": workspace_id})},
    )


async def claim(client: GraphClient, graph: str, memory_id: str, value: str, source: str):
    return await repo.propose_memory(
        client,
        graph,
        memory_id=memory_id,
        agent_id="agent_scout",
        source_id=source,
        subject_key="release_freeze",
        kind="semantic",
        predicate="freeze_date",
        object_value=value,
        cardinality="one",
        summary=f"Synthetic freeze claim {value}.",
        scope="workspace",
        confidence=0.9,
        now_ms=NOW,
    )


async def test_every_catalogue_query_runs(
    graph_client: GraphClient, throwaway_workspace: str
) -> None:
    graph = throwaway_workspace
    report = await seed_workspace(graph, client=graph_client, data=as_workspace(graph))

    assert await repo.workspace_present(graph_client, graph) is True
    assert await repo.workspace_present(graph_client, f"{graph}_missing") is False
    assert await repo.graph_node_count(graph_client, report.graph_name) > 0
    assert await repo.graph_node_count(graph_client, f"{graph}_missing") == 0
    procedure = await repo.memory_by_id(graph_client, graph, "mem_orbit_release_readiness")
    assert procedure is not None and procedure.kind == "procedural"

    # Q1 + Q1b-d, promote.
    assert await claim(graph_client, graph, "mem_a", "2026-11-05", SOURCES["planning"])
    assert await repo.link_episode(
        graph_client, graph, "mem_a", "ep_orbit_s1_planning"
    )
    assert await repo.set_valid_until(graph_client, graph, "mem_a", None)
    assert await repo.share_memory(graph_client, graph, "mem_a", "agent_planner")
    promoted = await repo.promote_candidate(
        graph_client, graph, memory_id="mem_a", decision_id="dec_promote_a"
    )
    assert promoted is not None and promoted.status == "active"

    # Q3 conflicts, Q3b corroboration.
    assert await claim(graph_client, graph, "mem_b", "2026-11-09", SOURCES["planning"])
    conflicts = await repo.find_conflicts(graph_client, graph, "mem_b")
    assert [row.existing_id for row in conflicts] == ["mem_a"]
    assert conflicts[0].existing_value == "2026-11-05"
    assert conflicts[0].existing_authority == 3
    assert await repo.find_corroboration(graph_client, graph, "mem_c") is None
    await claim(graph_client, graph, "mem_c", "2026-11-05", SOURCES["planning"])
    corroboration = await repo.find_corroboration(graph_client, graph, "mem_c")
    assert corroboration is not None and corroboration.existing_id == "mem_a"

    # Hold + conflict resolution actions.
    held = await repo.hold_candidate(
        graph_client,
        graph,
        candidate_id="mem_b",
        existing_id="mem_a",
        reason="lower_authority",
        decision_id="dec_hold_b",
    )
    assert held is not None and held.memory_id == "mem_b" and held.status == "contested"

    await claim(graph_client, graph, "mem_d", "2026-11-01", SOURCES["bulletin"])
    assert (
        await repo.supersede(
            graph_client,
            graph,
            old_id="mem_a",
            expected_revision=1,
            new_id="mem_d",
            reason="newer_higher_authority",
            decision_id="dec_stale",
        )
        is None
    ), "stale revision must be a no-op"
    superseded = await repo.supersede(
        graph_client,
        graph,
        old_id="mem_a",
        expected_revision=2,
        new_id="mem_d",
        reason="newer_higher_authority",
        decision_id="dec_supersede_d",
    )
    assert superseded is not None and superseded.new_id == "mem_d"
    assert (await repo.memory_by_id(graph_client, graph, "mem_a")).status == "superseded"

    coexisted = await repo.review_coexist(
        graph_client,
        graph,
        candidate_id="mem_b",
        existing_id="mem_d",
        decision_id="dec_coexist",
        reason_code="scope_split",
    )
    assert coexisted is not None
    await claim(graph_client, graph, "mem_e", "2026-11-11", SOURCES["planning"])
    rejected = await repo.review_reject(
        graph_client,
        graph,
        memory_id="mem_e",
        decision_id="dec_reject_e",
        reason_code="insufficient_evidence",
    )
    assert rejected is not None and rejected.status == "rejected"
    await claim(graph_client, graph, "mem_f", "2026-11-12", SOURCES["planning"])
    await repo.hold_candidate(
        graph_client,
        graph,
        candidate_id="mem_f",
        existing_id="mem_d",
        reason="lower_authority",
        decision_id="dec_hold_f",
    )
    kept = await repo.review_keep_contested(
        graph_client, graph, memory_id="mem_f", decision_id="dec_keep_f"
    )
    assert kept is not None and kept.status == "contested"

    # Eligibility / readiness.
    eligible = await repo.eligible_memories(
        graph_client,
        graph,
        concept_ids=["release_freeze"],
        receiver_id="agent_planner",
        now_ms=NOW,
    )
    assert {row.id for row in eligible} == {"mem_b", "mem_d"}
    ineligible = await repo.ineligible_memories(
        graph_client,
        graph,
        concept_ids=["release_freeze"],
        receiver_id="agent_planner",
        now_ms=NOW + 1,
    )
    reasons = {row.id: row.reason_code for row in ineligible}
    assert reasons["mem_a"] == "superseded_by_newer_supported_claim"
    assert reasons["mem_c"] == "unpromoted_candidate"
    assert reasons["mem_e"] == "rejected"
    assert reasons["mem_f"] == "contested"
    readiness = await repo.readiness(graph_client, graph, "mem_orbit_release_readiness")
    assert len(readiness) == 2
    assert {row.state for row in readiness} == {"unknown"}
    assert all(row.memory_id is None for row in readiness)

    # Why / provenance.
    sources = await repo.why_sources(graph_client, graph, "mem_d")
    assert [row.id for row in sources] == ["src_orbit_bulletin"]
    supersedes = await repo.why_supersedes(graph_client, graph, "mem_d")
    assert supersedes is not None and supersedes.older_ids == ["mem_a"]
    decisions = await repo.why_decisions(graph_client, graph, "mem_d")
    assert {row.outcome for row in decisions} >= {"superseded", "coexist"}

    # Handoffs.
    handoff = await repo.create_handoff(
        graph_client,
        graph,
        handoff_id="handoff_1",
        sender_id="agent_scout",
        receiver_id="agent_planner",
        task="orbit readiness",
        token_budget=500,
        now_ms=NOW,
    )
    assert handoff is not None
    assert (
        await repo.handoff_include(
            graph_client, graph, "handoff_1", ["mem_c", "mem_d"]
        )
        == 2
    )
    assert (
        await repo.handoff_exclude(
            graph_client,
            graph,
            "handoff_1",
            [{"memory_id": "mem_f", "reason_code": "contested"}],
        )
        == 1
    )
    links = await repo.why_handoffs(graph_client, graph, "mem_d")
    assert [row.handoff_id for row in links] == ["handoff_1"]

    # Timeline + disputes.
    timeline = await repo.timeline(graph_client, graph, limit=50)
    event_types = {event.event_type for event in timeline}
    assert {"memory_proposed", "decision"} <= event_types
    assert all(event.at_ms is not None and event.memory_id for event in timeline)
    assert [event.at_ms for event in timeline] == sorted(
        (event.at_ms for event in timeline), reverse=True
    )
    disputes = await repo.disputes(graph_client, graph)
    assert [row.candidate_id for row in disputes] == ["mem_f"]
    assert disputes[0].existing_id == "mem_d"

    # Bounded projection + filters.
    projection = await repo.neighborhood(
        graph_client, graph, "mem_d", hops=2, max_nodes=500
    )
    assert projection is not None and projection.truncated is False
    ids = {node.id for node in projection.nodes}
    assert all(edge.source in ids and edge.target in ids for edge in projection.edges)
    capped = await repo.neighborhood(
        graph_client, graph, "mem_d", hops=2, max_nodes=3
    )
    assert capped is not None and len(capped.nodes) <= 3 and capped.truncated is True
    active = await repo.neighborhood(
        graph_client, graph, "mem_d", status="active", as_of_ms=NOW, max_nodes=500
    )
    assert active is not None
    assert all(
        node.properties.get("status") == "active"
        for node in active.nodes
        if "Memory" in node.labels
    )
