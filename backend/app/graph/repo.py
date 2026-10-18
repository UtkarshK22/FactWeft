"""Typed repository over the Cypher catalogue.

One thin wrapper per statement in :mod:`app.graph.queries`. Raw rows never leave
this module: callers receive Pydantic models from :mod:`app.models.graph`.

Nothing here caches, mirrors or reconstructs memories -- every function is a
round trip to FalkorDB, and a ``GraphUnavailable`` failure propagates untouched
so the API can answer 503.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from app.core.clock import utc_now_ms
from app.graph import queries
from app.graph.connection import GraphClient
from app.graph.names import graph_name_for_workspace
from app.models.graph import (
    CoexistResult,
    ConflictCandidate,
    Corroboration,
    DisputeRecord,
    EligibleMemory,
    EpisodeLink,
    GraphEdge,
    GraphNode,
    HandoffCreated,
    IneligibleMemory,
    MemoryRecord,
    MemoryStatusResult,
    NeighborhoodCounts,
    NeighborhoodProjection,
    ProposedMemory,
    ReadinessStep,
    ShareLink,
    SourceEvidence,
    SupersedeResult,
    TimelineEvent,
    ValidUntilUpdate,
    WhyDecision,
    WhyHandoff,
    WhySource,
    WhySupersedes,
)


def _graph(workspace_id: str) -> str:
    return graph_name_for_workspace(workspace_id)


def _first(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    return dict(rows[0]) if rows else None


def _all(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _evidence(raw: Iterable[Any] | None) -> list[SourceEvidence]:
    """Drop the null placeholder OPTIONAL MATCH produces when there is no source."""
    items: list[SourceEvidence] = []
    for item in raw or []:
        if isinstance(item, Mapping) and item.get("id"):
            items.append(
                SourceEvidence(
                    id=str(item["id"]),
                    title=item.get("title"),
                    authority=item.get("authority"),
                )
            )
    return items


def _to_node(value: Mapping[str, Any]) -> GraphNode:
    return GraphNode(
        id=str(value.get("id")),
        labels=[str(label) for label in (value.get("labels") or [])],
        properties=dict(value.get("properties") or {}),
    )


def _render(query: str, hops: int) -> str:
    """Substitute the validated hop bound (Cypher cannot parameterize it)."""
    if hops not in queries.NEIGHBORHOOD_HOP_CHOICES:
        raise ValueError(f"hops must be one of {queries.NEIGHBORHOOD_HOP_CHOICES}")
    return query.replace("{hops}", str(hops))


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


async def workspace_present(client: GraphClient, workspace_id: str) -> bool:
    """``Q_WORKSPACE_PRESENT`` -- is this workspace's node in its graph?

    A graph that was never created (or was dropped) counts as absent: querying
    it would otherwise fail with FalkorDB's "Invalid graph operation".
    """
    graph = _graph(workspace_id)
    if not await client.graph_exists(graph):
        return False
    outcome = await client.run(
        graph,
        "workspace.present",
        queries.Q_WORKSPACE_PRESENT,
        {"workspace_id": workspace_id},
    )
    row = _first(outcome.rows)
    return bool(row and int(row.get("count") or 0) > 0)


async def graph_node_count(client: GraphClient, graph_name: str) -> int:
    """``Q_GRAPH_NODE_COUNT`` -- total nodes (idempotency assertion).

    A missing graph has zero nodes rather than an error, so seeding and reset
    checks can run before the graph exists.
    """
    if not await client.graph_exists(graph_name):
        return 0
    outcome = await client.run(graph_name, "graph.node_count", queries.Q_GRAPH_NODE_COUNT)
    row = _first(outcome.rows)
    return int((row or {}).get("nodes") or 0)


# ---------------------------------------------------------------------------
# Seeding (static base only; memories come from the scenario runner)
# ---------------------------------------------------------------------------


async def merge_workspace(
    client: GraphClient,
    workspace_id: str,
    *,
    display_name: str,
    created_at: int,
) -> str:
    """``Q_MERGE_WORKSPACE``"""
    outcome = await client.run(
        _graph(workspace_id),
        "seed.workspace",
        queries.Q_MERGE_WORKSPACE,
        {"workspace_id": workspace_id, "display_name": display_name, "created_at": created_at},
        write=True,
    )
    return str(_first(outcome.rows)["id"])


async def merge_agent(
    client: GraphClient,
    workspace_id: str,
    *,
    agent_id: str,
    role: str,
    display_name: str,
) -> str:
    """``Q_MERGE_AGENT``"""
    outcome = await client.run(
        _graph(workspace_id),
        "seed.agent",
        queries.Q_MERGE_AGENT,
        {"agent_id": agent_id, "role": role, "display_name": display_name},
        write=True,
    )
    return str(_first(outcome.rows)["id"])


async def seed_concept(
    client: GraphClient,
    workspace_id: str,
    *,
    concept_id: str,
    canonical_name: str,
    concept_type: str,
    aliases: Sequence[str],
) -> str:
    """``Q_SEED_CONCEPT``"""
    outcome = await client.run(
        _graph(workspace_id),
        "seed.concept",
        queries.Q_SEED_CONCEPT,
        {
            "concept_id": concept_id,
            "canonical_name": canonical_name,
            "concept_type": concept_type,
            "aliases": list(aliases),
        },
        write=True,
    )
    return str(_first(outcome.rows)["id"])


async def seed_source(
    client: GraphClient,
    workspace_id: str,
    *,
    source_id: str,
    title: str,
    source_type: str,
    source_ref: str,
    content_hash: str,
    published_at: int,
    authority: int,
    synthetic_flag: bool,
    excerpt: str,
) -> str:
    """``Q_SEED_SOURCE``"""
    outcome = await client.run(
        _graph(workspace_id),
        "seed.source",
        queries.Q_SEED_SOURCE,
        {
            "source_id": source_id,
            "title": title,
            "source_type": source_type,
            "source_ref": source_ref,
            "content_hash": content_hash,
            "published_at": published_at,
            "authority": authority,
            "synthetic_flag": synthetic_flag,
            "excerpt": excerpt,
        },
        write=True,
    )
    return str(_first(outcome.rows)["id"])


async def seed_session(
    client: GraphClient,
    workspace_id: str,
    *,
    session_id: str,
    task_label: str,
    started_at: int,
    ended_at: int | None,
) -> str:
    """``Q_SEED_SESSION``"""
    outcome = await client.run(
        _graph(workspace_id),
        "seed.session",
        queries.Q_SEED_SESSION,
        {
            "session_id": session_id,
            "task_label": task_label,
            "started_at": started_at,
            "ended_at": ended_at,
        },
        write=True,
    )
    return str(_first(outcome.rows)["id"])


async def seed_episode(
    client: GraphClient,
    workspace_id: str,
    *,
    episode_id: str,
    event_type: str,
    occurred_at: int,
    summary: str,
    session_id: str,
) -> str:
    """``Q_SEED_EPISODE`` -- also creates Session -[:CAPTURED]-> Episode."""
    outcome = await client.run(
        _graph(workspace_id),
        "seed.episode",
        queries.Q_SEED_EPISODE,
        {
            "episode_id": episode_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "summary": summary,
            "session_id": session_id,
        },
        write=True,
    )
    return str(_first(outcome.rows)["id"])


async def seed_procedure(
    client: GraphClient,
    workspace_id: str,
    *,
    agent_id: str,
    subject_key: str,
    memory_id: str,
    predicate: str,
    label: str,
    summary: str,
    confidence: float,
    created_at: int,
    valid_from: int,
) -> str:
    """``Q_SEED_PROCEDURE``"""
    outcome = await client.run(
        _graph(workspace_id),
        "seed.procedure",
        queries.Q_SEED_PROCEDURE,
        {
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "subject_key": subject_key,
            "memory_id": memory_id,
            "predicate": predicate,
            "label": label,
            "summary": summary,
            "confidence": confidence,
            "created_at": created_at,
            "valid_from": valid_from,
        },
        write=True,
    )
    return str(_first(outcome.rows)["memory_id"])


async def seed_step(
    client: GraphClient,
    workspace_id: str,
    *,
    procedure_id: str,
    step_id: str,
    order: int,
    label: str,
    check_predicate: str,
    expected_value: str,
    concept_id: str,
) -> str:
    """``Q_SEED_STEP``"""
    outcome = await client.run(
        _graph(workspace_id),
        "seed.step",
        queries.Q_SEED_STEP,
        {
            "procedure_id": procedure_id,
            "step_id": step_id,
            "order": order,
            "label": label,
            "check_predicate": check_predicate,
            "expected_value": expected_value,
            "concept_id": concept_id,
        },
        write=True,
    )
    return str(_first(outcome.rows)["step_id"])


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def memory_by_id(
    client: GraphClient, workspace_id: str, memory_id: str
) -> MemoryRecord | None:
    """``Q_MEMORY_BY_ID``"""
    outcome = await client.run(
        _graph(workspace_id),
        "memory.by_id",
        queries.Q_MEMORY_BY_ID,
        {"workspace_id": workspace_id, "memory_id": memory_id},
    )
    row = _first(outcome.rows)
    if row is None:
        return None
    row["evidence"] = _evidence(row.get("evidence"))
    return MemoryRecord(**row)


async def eligible_memories(
    client: GraphClient,
    workspace_id: str,
    *,
    concept_ids: Sequence[str],
    receiver_id: str,
    now_ms: int | None = None,
) -> list[EligibleMemory]:
    """``Q_ELIGIBLE_MEMORIES`` -- the included set for this receiver."""
    outcome = await client.run(
        _graph(workspace_id),
        "retrieval.eligible",
        queries.Q_ELIGIBLE_MEMORIES,
        {
            "workspace_id": workspace_id,
            "concept_ids": list(concept_ids),
            "receiver_id": receiver_id,
            "now": now_ms if now_ms is not None else utc_now_ms(),
        },
    )
    results: list[EligibleMemory] = []
    for row in _all(outcome.rows):
        row["evidence"] = _evidence(row.get("evidence"))
        if row.get("concept_id") is not None:
            row["concept_id"] = str(row["concept_id"])
        results.append(EligibleMemory(**row))
    return results


async def ineligible_memories(
    client: GraphClient,
    workspace_id: str,
    *,
    concept_ids: Sequence[str],
    receiver_id: str,
    now_ms: int | None = None,
) -> list[IneligibleMemory]:
    """``Q_INELIGIBLE_MEMORIES`` -- the receipt's excluded set with reason codes."""
    outcome = await client.run(
        _graph(workspace_id),
        "retrieval.ineligible",
        queries.Q_INELIGIBLE_MEMORIES,
        {
            "workspace_id": workspace_id,
            "concept_ids": list(concept_ids),
            "receiver_id": receiver_id,
            "now": now_ms if now_ms is not None else utc_now_ms(),
        },
    )
    return [IneligibleMemory(**row) for row in _all(outcome.rows)]


async def readiness(
    client: GraphClient, workspace_id: str, procedure_id: str
) -> list[ReadinessStep]:
    """``Q_READINESS`` -- procedure steps resolved against active semantic memories."""
    outcome = await client.run(
        _graph(workspace_id),
        "readiness",
        queries.Q_READINESS,
        {"procedure_id": procedure_id},
    )
    return [ReadinessStep(**row) for row in _all(outcome.rows)]


async def why_sources(client: GraphClient, workspace_id: str, memory_id: str) -> list[WhySource]:
    """``Q_WHY_SOURCES``"""
    outcome = await client.run(
        _graph(workspace_id),
        "why.sources",
        queries.Q_WHY_SOURCES,
        {"memory_id": memory_id},
    )
    return [WhySource(**row) for row in _all(outcome.rows)]


async def why_supersedes(
    client: GraphClient, workspace_id: str, memory_id: str
) -> WhySupersedes:
    """``Q_WHY_SUPERSEDES`` -- lineage both directions, up to 4 hops."""
    outcome = await client.run(
        _graph(workspace_id),
        "why.supersedes",
        queries.Q_WHY_SUPERSEDES,
        {"memory_id": memory_id},
    )
    row = _first(outcome.rows) or {}
    return WhySupersedes(
        older_ids=[str(item) for item in (row.get("older_ids") or []) if item],
        newer_ids=[str(item) for item in (row.get("newer_ids") or []) if item],
    )


async def why_decisions(
    client: GraphClient, workspace_id: str, memory_id: str
) -> list[WhyDecision]:
    """``Q_WHY_DECISIONS``"""
    outcome = await client.run(
        _graph(workspace_id),
        "why.decisions",
        queries.Q_WHY_DECISIONS,
        {"memory_id": memory_id},
    )
    return [WhyDecision(**row) for row in _all(outcome.rows)]


async def why_handoffs(
    client: GraphClient, workspace_id: str, memory_id: str
) -> list[WhyHandoff]:
    """``Q_WHY_HANDOFFS``"""
    outcome = await client.run(
        _graph(workspace_id),
        "why.handoffs",
        queries.Q_WHY_HANDOFFS,
        {"memory_id": memory_id},
    )
    return [WhyHandoff(**row) for row in _all(outcome.rows)]


async def timeline(
    client: GraphClient, workspace_id: str, *, limit: int = 50
) -> list[TimelineEvent]:
    """``Q_TIMELINE_EVENTS`` -- newest first.

    FalkorDB applies ``ORDER BY``/``LIMIT`` to the last UNION arm only, so the
    merge and the limit happen here over the two bounded streams.
    """
    outcome = await client.run(
        _graph(workspace_id),
        "timeline.events",
        queries.Q_TIMELINE_EVENTS,
        {"workspace_id": workspace_id},
    )
    events = [TimelineEvent(**row) for row in _all(outcome.rows)]
    events.sort(key=lambda event: (event.at_ms or 0), reverse=True)
    return events[:limit]


async def disputes(client: GraphClient, workspace_id: str) -> list[DisputeRecord]:
    """``Q_DISPUTES_LIST``"""
    outcome = await client.run(
        _graph(workspace_id),
        "disputes.list",
        queries.Q_DISPUTES_LIST,
        {"workspace_id": workspace_id},
    )
    return [DisputeRecord(**row) for row in _all(outcome.rows)]


async def neighborhood(
    client: GraphClient,
    workspace_id: str,
    memory_id: str,
    *,
    hops: int = queries.NEIGHBORHOOD_MAX_HOPS,
    max_nodes: int = 50,
    status: str | None = None,
    kind: str | None = None,
    scope: str | None = None,
    agent_id: str | None = None,
    as_of_ms: int | None = None,
) -> NeighborhoodProjection | None:
    """Q-neighborhood -- bounded projection with caps and a truncation flag.

    Returns ``None`` when the memory is not in this workspace (the API answers
    404), so a cross-workspace id is indistinguishable from a missing one.
    """
    if max_nodes < 1:
        raise ValueError("max_nodes must be >= 1")
    graph = _graph(workspace_id)
    filters: dict[str, Any] = {
        "status": status,
        "kind": kind,
        "scope": scope,
        "agent_id": agent_id,
        "as_of_ms": as_of_ms,
    }
    common = {
        "workspace_id": workspace_id,
        "memory_id": memory_id,
        "status": status,
        "kind": kind,
        "scope": scope,
        "agent_id": agent_id,
        "as_of_ms": as_of_ms,
    }

    root_outcome = await client.run(
        graph, "neighborhood.root", queries.Q_NEIGHBORHOOD_ROOT, common
    )
    root_row = _first(root_outcome.rows)
    if root_row is None:
        return None

    total_outcome = await client.run(
        graph,
        "neighborhood.total",
        _render(queries.Q_NEIGHBORHOOD_TOTAL, hops),
        common,
    )
    total_neighbours = int((_first(total_outcome.rows) or {}).get("total") or 0)

    # The cap counts the whole projection, root included.
    neighbour_cap = max(max_nodes - 1, 0)
    node_outcome = await client.run(
        graph,
        "neighborhood.nodes",
        _render(queries.Q_NEIGHBORHOOD_NODES, hops),
        {**common, "max_nodes": neighbour_cap},
    )
    root_node = _to_node(root_row["root"])
    neighbour_nodes = [_to_node(row["neighbour"]) for row in _all(node_outcome.rows)]
    nodes = [root_node, *neighbour_nodes]

    ids = [node.id for node in nodes]
    edge_cap = max(8, max_nodes * 4)
    edge_outcome = await client.run(
        graph,
        "neighborhood.edges",
        queries.Q_NEIGHBORHOOD_EDGES,
        {"ids": ids, "edge_cap": edge_cap},
        write=False,
    )
    edges = [
        GraphEdge(
            source=str(row["source"]),
            target=str(row["target"]),
            type=str(row["type"]),
            properties=dict(row.get("properties") or {}),
        )
        for row in _all(edge_outcome.rows)
    ]

    shown_nodes = len(nodes)
    total_nodes = total_neighbours + 1
    truncated = total_neighbours > len(neighbour_nodes) or len(edges) >= edge_cap
    return NeighborhoodProjection(
        root_id=root_node.id,
        hops=hops,
        as_of_ms=as_of_ms,
        filters=filters,
        nodes=nodes,
        edges=edges,
        counts=NeighborhoodCounts(
            shown_nodes=shown_nodes,
            total_nodes=total_nodes,
            shown_edges=len(edges),
            showing=f"{shown_nodes} of {total_nodes} nodes",
        ),
        truncated=truncated,
    )


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


async def propose_memory(
    client: GraphClient,
    workspace_id: str,
    *,
    memory_id: str,
    agent_id: str,
    source_id: str,
    subject_key: str,
    kind: str,
    predicate: str,
    object_value: str,
    cardinality: str,
    summary: str,
    scope: str,
    confidence: float,
    now_ms: int | None = None,
    valid_from: int | None = None,
) -> ProposedMemory | None:
    """``Q1_PROPOSE_MEMORY`` -- creates a candidate (and nothing else)."""
    now = now_ms if now_ms is not None else utc_now_ms()
    outcome = await client.run(
        _graph(workspace_id),
        "memory.propose",
        queries.Q1_PROPOSE_MEMORY,
        {
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "source_id": source_id,
            "subject_key": subject_key,
            "memory_id": memory_id,
            "kind": kind,
            "predicate": predicate,
            "object_value": object_value,
            "cardinality": cardinality,
            "summary": summary,
            "scope": scope,
            "confidence": confidence,
            "now": now,
            "valid_from": valid_from if valid_from is not None else now,
        },
        write=True,
    )
    row = _first(outcome.rows)
    return ProposedMemory(**row) if row else None


async def link_episode(
    client: GraphClient, workspace_id: str, memory_id: str, episode_id: str
) -> EpisodeLink | None:
    """``Q1B_LINK_EPISODE``"""
    outcome = await client.run(
        _graph(workspace_id),
        "memory.link_episode",
        queries.Q1B_LINK_EPISODE,
        {"memory_id": memory_id, "episode_id": episode_id},
        write=True,
    )
    row = _first(outcome.rows)
    return EpisodeLink(**row) if row else None


async def set_valid_until(
    client: GraphClient, workspace_id: str, memory_id: str, valid_until: int | None
) -> ValidUntilUpdate | None:
    """``Q1C_SET_VALID_UNTIL``"""
    outcome = await client.run(
        _graph(workspace_id),
        "memory.set_valid_until",
        queries.Q1C_SET_VALID_UNTIL,
        {"memory_id": memory_id, "valid_until": valid_until},
        write=True,
    )
    row = _first(outcome.rows)
    return ValidUntilUpdate(**row) if row else None


async def share_memory(
    client: GraphClient, workspace_id: str, memory_id: str, agent_id: str
) -> ShareLink | None:
    """``Q1D_SHARE_MEMORY`` -- scope=handoff visibility for one receiver."""
    outcome = await client.run(
        _graph(workspace_id),
        "memory.share",
        queries.Q1D_SHARE_MEMORY,
        {"memory_id": memory_id, "agent_id": agent_id},
        write=True,
    )
    row = _first(outcome.rows)
    return ShareLink(**row) if row else None


async def find_conflicts(
    client: GraphClient, workspace_id: str, candidate_id: str
) -> list[ConflictCandidate]:
    """``Q3_FIND_CONFLICTS`` -- read-only."""
    outcome = await client.run(
        _graph(workspace_id),
        "conflict.find",
        queries.Q3_FIND_CONFLICTS,
        {"candidate_id": candidate_id},
    )
    return [ConflictCandidate(**row) for row in _all(outcome.rows)]


async def find_corroboration(
    client: GraphClient, workspace_id: str, candidate_id: str
) -> Corroboration | None:
    """``Q3B_FIND_CORROBORATION`` -- read-only."""
    outcome = await client.run(
        _graph(workspace_id),
        "conflict.corroboration",
        queries.Q3B_FIND_CORROBORATION,
        {"candidate_id": candidate_id},
    )
    row = _first(outcome.rows)
    return Corroboration(**row) if row else None


async def supersede(
    client: GraphClient,
    workspace_id: str,
    *,
    old_id: str,
    expected_revision: int,
    new_id: str,
    reason: str,
    decision_id: str,
    reviewer_type: str = "rule",
    now_ms: int | None = None,
    new_valid_from: int | None = None,
) -> SupersedeResult | None:
    """``Q6_SUPERSEDE`` -- compare-and-set; ``None`` means a stale revision (409)."""
    now = now_ms if now_ms is not None else utc_now_ms()
    outcome = await client.run(
        _graph(workspace_id),
        "memory.supersede",
        queries.Q6_SUPERSEDE,
        {
            "old_id": old_id,
            "expected_revision": expected_revision,
            "new_id": new_id,
            "now": now,
            "new_valid_from": new_valid_from if new_valid_from is not None else now,
            "reason": reason,
            "decision_id": decision_id,
            "reviewer_type": reviewer_type,
        },
        write=True,
    )
    row = _first(outcome.rows)
    return SupersedeResult(**row) if row else None


async def promote_candidate(
    client: GraphClient,
    workspace_id: str,
    *,
    memory_id: str,
    decision_id: str,
    reason_code: str = "clean_promotion",
    reviewer_type: str = "rule",
    now_ms: int | None = None,
) -> MemoryStatusResult | None:
    """``Q_PROMOTE_CANDIDATE``"""
    outcome = await client.run(
        _graph(workspace_id),
        "memory.promote",
        queries.Q_PROMOTE_CANDIDATE,
        {
            "memory_id": memory_id,
            "decision_id": decision_id,
            "reason_code": reason_code,
            "now": now_ms if now_ms is not None else utc_now_ms(),
            "reviewer_type": reviewer_type,
        },
        write=True,
    )
    row = _first(outcome.rows)
    return MemoryStatusResult(**row) if row else None


async def hold_candidate(
    client: GraphClient,
    workspace_id: str,
    *,
    candidate_id: str,
    existing_id: str,
    reason: str,
    decision_id: str,
    reviewer_type: str = "rule",
    now_ms: int | None = None,
) -> MemoryStatusResult | None:
    """``Q_HOLD_CANDIDATE`` -- contested + CONTRADICTS edge + Decision."""
    outcome = await client.run(
        _graph(workspace_id),
        "memory.hold",
        queries.Q_HOLD_CANDIDATE,
        {
            "candidate_id": candidate_id,
            "existing_id": existing_id,
            "reason": reason,
            "decision_id": decision_id,
            "now": now_ms if now_ms is not None else utc_now_ms(),
            "reviewer_type": reviewer_type,
        },
        write=True,
    )
    row = _first(outcome.rows)
    if row is None:
        return None
    # Q_HOLD_CANDIDATE projects the candidate's own id as ``candidate_id``; the
    # wrapper's contract is the generic MemoryStatusResult.
    return MemoryStatusResult(memory_id=str(row["candidate_id"]), status=str(row["status"]))


async def review_reject(
    client: GraphClient,
    workspace_id: str,
    *,
    memory_id: str,
    decision_id: str,
    reason_code: str,
    reviewer_type: str = "human",
    now_ms: int | None = None,
) -> MemoryStatusResult | None:
    """``Q_REVIEW_REJECT``"""
    outcome = await client.run(
        _graph(workspace_id),
        "review.reject",
        queries.Q_REVIEW_REJECT,
        {
            "memory_id": memory_id,
            "decision_id": decision_id,
            "reason_code": reason_code,
            "now": now_ms if now_ms is not None else utc_now_ms(),
            "reviewer_type": reviewer_type,
        },
        write=True,
    )
    row = _first(outcome.rows)
    return MemoryStatusResult(**row) if row else None


async def review_coexist(
    client: GraphClient,
    workspace_id: str,
    *,
    candidate_id: str,
    existing_id: str,
    decision_id: str,
    reason_code: str,
    reviewer_type: str = "human",
    now_ms: int | None = None,
) -> CoexistResult | None:
    """``Q_REVIEW_COEXIST`` -- scope split: both claims become cardinality 'many'."""
    outcome = await client.run(
        _graph(workspace_id),
        "review.coexist",
        queries.Q_REVIEW_COEXIST,
        {
            "candidate_id": candidate_id,
            "existing_id": existing_id,
            "decision_id": decision_id,
            "reason_code": reason_code,
            "now": now_ms if now_ms is not None else utc_now_ms(),
            "reviewer_type": reviewer_type,
        },
        write=True,
    )
    row = _first(outcome.rows)
    return CoexistResult(**row) if row else None


async def review_keep_contested(
    client: GraphClient,
    workspace_id: str,
    *,
    memory_id: str,
    decision_id: str,
    reason_code: str = "reviewed_left_open",
    reviewer_type: str = "human",
    now_ms: int | None = None,
) -> MemoryStatusResult | None:
    """``Q_REVIEW_KEEP_CONTESTED``"""
    outcome = await client.run(
        _graph(workspace_id),
        "review.keep_contested",
        queries.Q_REVIEW_KEEP_CONTESTED,
        {
            "memory_id": memory_id,
            "decision_id": decision_id,
            "reason_code": reason_code,
            "now": now_ms if now_ms is not None else utc_now_ms(),
            "reviewer_type": reviewer_type,
        },
        write=True,
    )
    row = _first(outcome.rows)
    return MemoryStatusResult(**row) if row else None


async def create_handoff(
    client: GraphClient,
    workspace_id: str,
    *,
    handoff_id: str,
    sender_id: str,
    receiver_id: str,
    task: str,
    token_budget: int,
    receipt_version: int = 1,
    policy_version: int = 1,
    status: str = "sent",
    now_ms: int | None = None,
) -> HandoffCreated | None:
    """``Q_HANDOFF_CREATE``"""
    outcome = await client.run(
        _graph(workspace_id),
        "handoff.create",
        queries.Q_HANDOFF_CREATE,
        {
            "workspace_id": workspace_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "handoff_id": handoff_id,
            "task": task,
            "now": now_ms if now_ms is not None else utc_now_ms(),
            "status": status,
            "token_budget": token_budget,
            "receipt_version": receipt_version,
            "policy_version": policy_version,
        },
        write=True,
    )
    row = _first(outcome.rows)
    return HandoffCreated(**row) if row else None


async def handoff_include(
    client: GraphClient, workspace_id: str, handoff_id: str, memory_ids: Sequence[str]
) -> int:
    """``Q_HANDOFF_INCLUDE`` -- returns the number of INCLUDES edges merged."""
    outcome = await client.run(
        _graph(workspace_id),
        "handoff.include",
        queries.Q_HANDOFF_INCLUDE,
        {"handoff_id": handoff_id, "memory_ids": list(memory_ids)},
        write=True,
    )
    return int((_first(outcome.rows) or {}).get("included") or 0)


async def handoff_exclude(
    client: GraphClient,
    workspace_id: str,
    handoff_id: str,
    excluded: Sequence[Mapping[str, str]],
) -> int:
    """``Q_HANDOFF_EXCLUDE`` -- rows must carry ``memory_id`` and ``reason_code``."""
    outcome = await client.run(
        _graph(workspace_id),
        "handoff.exclude",
        queries.Q_HANDOFF_EXCLUDE,
        {"handoff_id": handoff_id, "excluded": [dict(item) for item in excluded]},
        write=True,
    )
    return int((_first(outcome.rows) or {}).get("excluded") or 0)
