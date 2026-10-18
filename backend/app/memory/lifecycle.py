"""Memory lifecycle: propose, review, supersede, procedural memories, and decision writing.

All functions are async and talk to FalkorDB through ``GraphClient`` / ``repo``.
Every transition that changes a memory's state writes a ``Decision`` node so the
graph is fully auditable (``Q_WHY_DECISIONS`` can reconstruct the history).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import HTTPException, status

from app.core.errors import GraphUnavailable
from app.graph import queries, repo
from app.graph.connection import GraphClient
from app.graph.names import graph_name_for_workspace
from app.memory.conflicts import classify_conflict
from app.models.graph import (
    DisputeRecord,
    MemoryRecord,
    ProposedMemory,
    SourceEvidence,
    WhyDecision,
    WhyHandoff,
    WhySource,
    WhySupersedes,
)


async def _ensure_graph(client: GraphClient, workspace_id: str) -> str:
    """Return the graph name for a workspace, ensuring it exists."""
    graph = graph_name_for_workspace(workspace_id)
    if not await repo.workspace_present(client, workspace_id):
        raise HTTPException(
            status_code=status.HTTP_404,
            detail="Workspace '{}' not found (graph '{}' absent).".format(workspace_id, graph),
        )
    return graph


async def _run_write(client: GraphClient, graph: str, cypher: str, params: dict, **kwargs: Any) -> Any:
    """Thin wrapper around ``client.run(..., write=True)`` that translates errors."""
    try:
        outcome = await client.run(graph, cypher, params, write=True)
    except Exception as exc:  # noqa: BLE001
        raise GraphUnavailable("Graph operation failed: {}".format(exc)) from exc
    return outcome


# ---------------------------------------------------------------------------
# Propose a candidate memory
# ---------------------------------------------------------------------------

async def propose_memory(
    client: GraphClient,
    workspace_id: str,
    *,
    memory_id: str | None = None,
    kind: str,
    subject_key: str,
    predicate: str,
    object_value: str,
    cardinality: str,
    summary: str,
    scope: str,
    confidence: float,
    source_id: str,
    valid_from: int | None = None,
    valid_until: int | None = None,
    episode_id: str | None = None,
    shared_with: list[str] | None = None,  # non-empty when scope=handoff
    now_ms: int | None = None,
) -> ProposedMemory:
    """``POST /api/memories/propose`` implementation.

    Rules (master spec):
    - ``memory_id`` optional; if omitted a UUID prefixed ``mem_`` is generated.
    - Role must be scout/verifier/coordinator/owner (checked by route deps).
    - Run Q1: if zero rows returned (missing workspace/agent/source/concept) → 404/422
      with which reference was missing; nothing written.
    - Link episode if ``episode_id`` given.
    - Set valid_until if provided.
    - SHARED_WITH edge when ``scope=handoff`` and ``shared_with`` non-empty.
    - Then evaluate the deterministic resolver (conflicts/corroboration) before
      promoting to ``active``.
    - Every transition writes a ``Decision`` node.

    Returns ``{memory_id, status, outcome, decision_id, conflicts:[...], notes}``.
    """
    now = now_ms or int(time.time() * 1000)
    graph = await _ensure_graph(client, workspace_id)

    # Generate memory_id if not provided
    mid = memory_id or "mem_{}".format(uuid.uuid4().hex[:12])

    # Q1: verify workspace, agent, source, concept exist; return zero rows if missing.
    # The repo layer already gates on these; we check row count.
    outcome = await repo.propose_memory(
        client,
        workspace_id,
        memory_id=mid,
        agent_id="agent_scout",
        source_id=source_id,
        subject_key=subject_key,
        kind=kind,
        predicate=predicate,
        object_value=object_value,
        cardinality=cardinality,
        summary=summary,
        scope=scope,
        confidence=confidence,
        now_ms=now,
    )

    row = outcome.rows[0] if outcome.rows else None
    if row is None:
        # Nothing was written — caller should answer 404/422 referencing the
        # missing component.  The route layer knows which field was missing.
        raise HTTPException(
            status_code=status.HTTP_422,
            detail={
                "error": "missing_reference",
                "message": "Could not propose memory — one of workspace/agent/source/concept not found",
            },
        )

    # At this point the candidate was created with status='candidate'.
    # Now evaluate conflicts / corroboration using Q3 + the pure resolver.
    conflicts: list[dict[str, Any]] = []
    outcome_key: str = "candidate"

    # Track the last decision_id so we can reference it in the return value.
    last_decision_id: str | None = None

    # Run Q3 to find active memories contradicting this candidate on the same
    # concept+predicate.  The repo wrapper returns a list of ConflictCandidate dicts.
    q3_outcome = await repo.find_conflicts(client, workspace_id, mid)
    for conflict in q3_outcome:
        action, reason = classify_conflict(
            {"cand_value": object_value, "cand_authority": confidence, "_cardinality_many": cardinality == "many"},
            {
                "existing_id": conflict.existing_id,
                "existing_value": conflict.existing_value or "",
                "existing_valid_from": conflict.existing_valid_from,
                "existing_revision": conflict.existing_revision,
                "cand_value": object_value,
                "cand_authority": confidence,
                "_cardinality_many": cardinality == "many",
            },
        )
        if action == "hold":
            # Keep the candidate as‑is; write a decision that it was held.
            dec_id = "dec_{}_held_{}".format(mid, uuid.uuid4().hex[:8])
            last_decision_id = dec_id
            await _run_write(
                client,
                graph,
                queries.Q_DECISION_WRITE,
                {
                    "decision_id": dec_id,
                    "memory_id": mid,
                    "decision_type": "conflict",
                    "outcome": "held",
                    "reason_code": reason or "lower_authority",
                    "decided_at": now,
                    "reviewer_type": "rule",
                },
            )
            conflicts.append(
                {
                    "existing_id": conflict.existing_id,
                    "existing_value": conflict.existing_value,
                    "reason_code": reason,
                    "action": "held",
                }
            )
            # Candidate stays candidate; outcome is "candidate"
            outcome_key = "candidate"
            break
        elif action == "supersede":
            # Supersede the existing memory via Q6 compare-and-set.
            # If zero rows come back, return 409 with current revision.
            sup_outcome = await repo.supersede(
                client,
                workspace_id,
                old_id=conflict.existing_id,
                expected_revision=conflict.existing_revision or 1,
                new_id=mid,
                reason=reason or "newer_higher_authority",
                decision_id="dec_{}_supersede_{}".format(mid, uuid.uuid4().hex[:8]),
            )
            if sup_outcome is None:
                # Revision mismatch — 409 so the caller can retry once.
                raise HTTPException(
                    status_code=status.HTTP_409,
                    detail={
                        "error": "stale_revision",
                        "message": "Memory '{}' has revision {}; expected {}. Retry once with the current revision.".format(conflict.existing_id, conflict.existing_revision, conflict.existing_revision),
                    },
                )
            # Superseded memory becomes the new one; candidate is promoted.
            outcome_key = "active"
            conflicts.append(
                {
                    "existing_id": conflict.existing_id,
                    "new_id": mid,
                    "reason_code": reason or "newer_higher_authority",
                    "action": "superseded",
                }
            )
            # Write a decision for the supersede action.
            dec_id = "dec_{}_supersede_{}".format(mid, uuid.uuid4().hex[:8])
            last_decision_id = dec_id
            await _run_write(
                client,
                graph,
                queries.Q_DECISION_WRITE,
                {
                    "decision_id": dec_id,
                    "memory_id": mid,
                    "decision_type": "supersede",
                    "outcome": "superseded",
                    "reason_code": reason or "newer_higher_authority",
                    "decided_at": now,
                    "reviewer_type": "rule",
                },
            )
            break
        elif action == "corroborate":
            # Same value — corroborate: add SUPPORTED_BY to the existing memory,
            # do NOT create the candidate (it's redundant).
            await repo.link_episode(client, workspace_id, mid, episode_id) if episode_id else None
            outcome_key = "corroborated"
            # Write a decision for corroboration.
            dec_id = "dec_{}_corrob_{}".format(mid, uuid.uuid4().hex[:8])
            last_decision_id = dec_id
            await _run_write(
                client,
                graph,
                queries.Q_DECISION_WRITE,
                {
                    "decision_id": dec_id,
                    "memory_id": mid,
                    "decision_type": "corroborate",
                    "outcome": "corroborated",
                    "reason_code": "duplicate_corroborated",
                    "decided_at": now,
                    "reviewer_type": "rule",
                },
            )
            break
        else:  # promote
            # Promote to active — write a promotion decision.
            dec_id = "dec_{}_promoted_{}".format(mid, uuid.uuid4().hex[:8])
            last_decision_id = dec_id
            await _run_write(
                client,
                graph,
                queries.Q_DECISION_WRITE,
                {
                    "decision_id": dec_id,
                    "memory_id": mid,
                    "decision_type": "promote",
                    "outcome": "active",
                    "reason_code": reason or "promoted_clean",
                    "decided_at": now,
                    "reviewer_type": "rule",
                },
            )
            outcome_key = "active"
            conflicts.append(
                {
                    "existing_id": conflict.existing_id,
                    "reason_code": reason,
                    "action": "resolved",
                }
            )
            # Continue checking remaining conflicts if any
    else:
        # No conflicts found — promote cleanly.
        outcome_key = "active"
        dec_id = "dec_{}_promoted_{}".format(mid, uuid.uuid4().hex[:8])
        last_decision_id = dec_id
        await _run_write(
            client,
            graph,
            queries.Q_DECISION_WRITE,
            {
                "decision_id": dec_id,
                "memory_id": mid,
                "decision_type": "promote",
                "outcome": "active",
                "reason_code": None,
                "decided_at": now,
                "reviewer_type": "rule",
            },
        )

    # If scope=handoff and shared_with was provided, create SHARED_WITH edges.
    if scope == "handoff" and shared_with:
        for agent_id in shared_with:
            await _run_write(
                client,
                graph,
                queries.Q1D_SHARE_MEMORY,
                {"memory_id": mid, "agent_id": agent_id},
                write=True,
            )

    # If episode_id was given, link it.
    if episode_id:
        await repo.link_episode(client, workspace_id, mid, episode_id)

    # Return the structured result.
    return ProposedMemory(
        memory_id=mid,
        status=outcome_key,
        outcome=outcome_key,  # same field for backward compat; route may use status
        decision_id=last_decision_id or "",
        conflicts=conflicts,
        notes=[],
    )


# ---------------------------------------------------------------------------
# Review actions (supersede, coexist, reject, keep_contested)
# ---------------------------------------------------------------------------

async def review_memory(
    client: GraphClient,
    workspace_id: str,
    *,
    memory_id: str,
    action: str,
    decision_id: str,
    reason_code: str | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """``POST /api/memories/{id}/review`` implementation.

    Actions:
    - ``"supersede"`` — needs ``target`` (existing memory id) + ``reason``.
      Uses Q6 compare-and-set; if zero rows → 409 with current revision.
    - ``"coexist"`` — requires changing scope or valid range; validate and
      update both memories' cardinality to ``many``.
    - ``"reject"`` — sets memory status to ``rejected``, increments revision.
    - ``"keep_contested"`` — keeps both as contested, writes a decision.

    Returns a dict with the updated memory state and decision metadata.
    """
    graph = await _ensure_graph(client, workspace_id)
    now = now_ms or int(time.time() * 1000)

    if action == "supersede":
        # The route should have provided a ``target`` memory id; if not, 422.
        # Q6 compare-and-set: if the existing memory's revision has changed,
        # return 409 so the caller can retry.
        result = await repo.supersede(
            client,
            workspace_id,
            old_id=memory_id,  # the candidate being promoted
            expected_revision=1,  # first version; route validates
            new_id=decision_id,
            reason=reason_code or "newer_higher_authority",
            decision_id="dec_{}_supersede_{}".format(memory_id, uuid.uuid4().hex[:8]),
        )
        if result is None:
            # Fetch current revision and return 409.
            cur = await repo.memory_by_id(client, workspace_id, memory_id)
            raise HTTPException(
                status_code=status.HTTP_409,
                detail={
                    "error": "stale_revision",
                    "message": "Memory '{}' revision mismatch; current revision is {}".format(memory_id, cur.revision if cur else "?"),
                },
            )
        # Write decision.
        await _run_write(
            client,
            graph,
            queries.Q_DECISION_WRITE,
            {
                "decision_id": "dec_{}_supersede_{}".format(memory_id, uuid.uuid4().hex[:8]),
                "memory_id": memory_id,
                "decision_type": "supersede",
                "outcome": "superseded",
                "reason_code": reason_code or "newer_higher_authority",
                "decided_at": now,
                "reviewer_type": "rule",
            },
        )
        return {
            "memory_id": memory_id,
            "status": "superseded",
            "outcome": "superseded",
            "decision_id": "dec_{}_supersede_{}".format(memory_id, uuid.uuid4().hex[:8]),
            "notes": ["Superseded"],
        }

    if action == "reject":
        # SET m.status = 'rejected', m.revision = m.revision + 1
        await _run_write(
            client,
            graph,
            """MATCH (m:Memory {id: $memory_id})
               SET m.status = 'rejected', m.revision = m.revision + 1
               RETURN m.id AS memory_id, m.status AS status, m.revision AS revision""",
            {"memory_id": memory_id},
            write=True,
        )
        await _run_write(
            client,
            graph,
            queries.Q_REVIEW_REJECT,
            {
                "memory_id": memory_id,
                "decision_id": decision_id,
                "reason_code": reason_code or "manual_review",
                "now": now,
                "reviewer_type": "human",
            },
            write=True,
        )
        return {
            "memory_id": memory_id,
            "status": "rejected",
            "outcome": "rejected",
            "decision_id": decision_id,
            "notes": ["Memory rejected by {} human reviewer".format(reason_code or "human reviewer")],
        }

    if action == "keep_contested":
        # Both memories remain contested; write a decision.
        dec_id = "dec_{}_keep_{}".format(memory_id, uuid.uuid4().hex[:8])
        await _run_write(
            client,
            graph,
            queries.Q_DECISION_WRITE,
            {
                "decision_id": dec_id,
                "memory_id": memory_id,
                "decision_type": "keep_contested",
                "outcome": "contested",
                "reason_code": reason_code or "scope_split",
                "decided_at": now,
                "reviewer_type": "rule",
            },
            write=True,
        )
        # Also ensure the CONTRADICTS edge exists between the contested pair.
        # (It should already from when they were held, but make sure.)
        await _run_write(
            client,
            graph,
            """MATCH (cand:Memory {id: $mem_id})
               MATCH (active:Memory {status: 'active'})
               WHERE cand.id <> active.id
               MERGE (cand)-[r:CONTRADICTS]->(active)
               SET r.reason = $reason, r.at = $now""",
            {"mem_id": memory_id, "reason": reason_code or "contested", "now": now},
            write=True,
        )
        return {
            "memory_id": memory_id,
            "status": "contested",
            "outcome": "kept_contested",
            "decision_id": dec_id,
            "notes": ["Kept contested with reason {}".format(reason_code or "scope_split")],
        }

    if action == "coexist":
        # Change scope/valid range of both memories to allow coexistence.
        # Set both to cardinality 'many' and adjust scopes.
        await _run_write(
            client,
            graph,
            """MATCH (m:Memory {id: $memory_id})
               SET m.cardinality = 'many', m.scope = 'workspace'""",
            {"memory_id": memory_id},
            write=True,
        )
        # The route should also update the counterpart memory similarly.
        dec_id = "dec_{}_coexist_{}".format(memory_id, uuid.uuid4().hex[:8])
        await _run_write(
            client,
            graph,
            queries.Q_DECISION_WRITE,
            {
                "decision_id": dec_id,
                "memory_id": memory_id,
                "decision_type": "coexist",
                "outcome": "coexist",
                "reason_code": reason_code or "scope_adjusted",
                "decided_at": now,
                "reviewer_type": "rule",
            },
            write=True,
        )
        return {
            "memory_id": memory_id,
            "status": "active",
            "outcome": "coexist",
            "decision_id": dec_id,
            "notes": ["Coexistence activated; both memories now cardinality 'many'"],
        }

    raise HTTPException(
        status_code=status.HTTP_400,
        detail="Unknown review action: {}".format(action),
    )


# ---------------------------------------------------------------------------
# Procedural memory creation (one-call procedure with steps)
# ---------------------------------------------------------------------------

async def seed_procedure_with_steps(
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
    steps: list[dict[str, str | int]],
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Create a procedural memory with ordered steps in one call.

    Rules (master spec):
    - ``kind=procedural``
    - Owner/coordinator may create procedural memories as ``active``;
      any other role creates them as ``candidate``.
    - Steps are written as ``Step`` nodes linked to the procedure via ``HAS_STEP``.
    - The procedure Memory itself is ``active`` when proposed by owner/coordinator,
      ``candidate`` otherwise.

    Returns the procedure memory record and step counts.
    """
    now = now_ms or int(time.time() * 1000)
    graph = await _ensure_graph(client, workspace_id)

    # Determine initial status based on role.
    is_owner_or_coord = agent_id in ("human_owner", "agent_coordinator")

    # Seed the procedure memory.
    result = await repo.propose_memory(
        client,
        workspace_id,
        memory_id=memory_id,
        agent_id=agent_id,
        source_id="",
        subject_key=subject_key,
        kind="procedural",
        predicate=predicate,
        object_value="",
        cardinality="one",
        summary=summary,
        scope="workspace",
        confidence=confidence,
        now_ms=now,
    )

    # Seed steps.
    step_ids: list[str] = []
    for idx, step_def in enumerate(steps):
        step_id = "{}_{}_step_{}".format(memory_id, idx)
        await repo.seed_step(
            client,
            workspace_id,
            procedure_id=memory_id,
            step_id=step_id,
            order=idx,
            label=step_def.get("label", "Step {}".format(idx)),
            check_predicate=step_def.get("check_predicate", ""),
            expected_value=step_def.get("expected_value", ""),
            concept_id=step_def.get("concept_id", ""),
        )
        step_ids.append(step_id)

    return {
        "memory_id": memory_id,
        "status": "active" if is_owner_or_coord else "candidate",
        "kind": "procedural",
        "procedure_id": memory_id,
        "steps_written": len(steps),
        "step_ids": step_ids,
        "created_at": now,
    }


# ---------------------------------------------------------------------------
# Dispute listing (GET /api/disputes)
# ---------------------------------------------------------------------------

async def list_disputes(client: GraphClient, workspace_id: str) -> list[DisputeRecord]:
    """``GET /api/disputes`` — contested memories with their CONTRADICTS counterpart.

    Returns one ``DisputeRecord`` per contested memory, containing:
    - the candidate claim (id, value, authority, published_at)
    - the active claim (id, value, authority, published_at)
    - the CONTRADICTS edge reason code
    - both sides' source summaries + authority + published_at
    """
    graph = graph_name_for_workspace(workspace_id)
    outcome = await client.run(
        graph,
        "disputes.list",
        queries.Q_DISPUTES_LIST,
        {"workspace_id": workspace_id},
        write=False,
    )
    records: list[DisputeRecord] = []
    for row in outcome.rows or []:
        records.append(
            DisputeRecord(
                candidate_id=row.get("candidate_id") or "",
                candidate_value=row.get("candidate_value"),
                candidate_authority=row.get("cand_authority"),
                candidate_published_at=row.get("cand_published_at"),
                existing_id=row.get("existing_id") or "",
                existing_value=row.get("existing_value"),
                existing_authority=row.get("existing_authority"),
                existing_published_at=row.get("existing_published_at"),
                reason_code=row.get("reason_code"),
                excerpt=row.get("excerpt"),
            )
        )
    return records


# ---------------------------------------------------------------------------
# Get one memory by ID (GET /api/memories/{id})
# ---------------------------------------------------------------------------

async def get_memory(client: GraphClient, workspace_id: str, memory_id: str) -> MemoryRecord:
    """``GET /api/memories/{id}`` — return one memory with its provenance.

    Includes:
    - the memory node (id, labels, properties)
    - sources that support it (via Q_WHY_SOURCES)
    - supersede chain (via Q_WHY_SUPERSEDES)
    - decisions that resolved it (via Q_WHY_DECISIONS)
    - handoffs that included/excluded it (via Q_WHY_HANDOFFS)
    """
    graph = graph_name_for_workspace(workspace_id)

    # Fetch the memory itself.
    mem_outcome = await repo.memory_by_id(client, workspace_id, memory_id)
    if not mem_outcome:
        raise HTTPException(
            status_code=status.HTTP_404,
            detail="Memory '{}' not found in workspace '{}'.".format(memory_id, workspace_id),
        )

    # Why sources.
    why_src = await repo.why_sources(client, workspace_id, memory_id)

    # Why supersedes.
    why_sup = await repo.why_supersedes(client, workspace_id, memory_id)

    # Why decisions.
    why_dec = await repo.why_decisions(client, workspace_id, memory_id)

    # Why handoffs.
    why_handoff = await repo.why_handoffs(client, workspace_id, memory_id)

    return MemoryRecord(
        id=mem_outcome.id,
        kind=mem_outcome.kind,
        subject_key=mem_outcome.subject_key,
        predicate=mem_outcome.predicate,
        object_value=mem_outcome.object_value,
        cardinality=mem_outcome.cardinality,
        summary=mem_outcome.summary,
        status=mem_outcome.status,
        scope=mem_outcome.scope,
        confidence=mem_outcome.confidence,
        created_at=mem_outcome.created_at,
        valid_from=mem_outcome.valid_from,
        valid_until=mem_outcome.valid_until,
        superseded_at=mem_outcome.superseded_at,
        revision=mem_outcome.revision,
        proposed_by=mem_outcome.proposed_by,
        concept_name=mem_outcome.concept_name,
        evidence=[SourceEvidence(**s) for s in (mem_outcome.evidence or [])],
        why_sources=[WhySource(**s) for s in why_src],
        why_supersedes=WhySupersedes(**why_sup) if why_sup else None,
        why_decisions=[WhyDecision(**d) for d in why_dec],
        why_handoffs=[WhyHandoff(**h) for h in why_handoff],
    )
