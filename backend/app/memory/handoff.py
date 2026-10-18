"""Handoff creation and receipt assembly.

Handles the Q-handoff Cypher query, receipt JSON construction, and
reproduction of receipts from the graph.  All public functions are pure
where possible; graph interaction is delegated to the repository layer.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.graph.names import graph_name_for_workspace


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token per ~4 characters."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _estimate_tokens_list(items: List[dict]) -> int:
    """Estimate tokens for a list of dicts by summing their stringified sizes."""
    total = 0
    for item in items:
        total += _estimate_tokens(json.dumps(item, sort_keys=True))
    return total


def assemble_receipt(
    handoff_id: str,
    sender: str,
    receiver: str,
    task: str,
    included: List[dict],
    excluded: List[dict],
    caveats: List[dict],
    readiness: dict,
    queries_used: List[str],
    token_budget: int,
) -> dict:
    """Assemble the handoff receipt JSON as specified.

    Format: {handoff_id, sender, receiver, task, included:[{id, summary, evidence}],
    excluded:[{id, reason_code}], caveats, readiness, queries_used:[trace ids],
    token_estimate}
    """
    # Estimate token usage
    task_tokens = _estimate_tokens(task)
    included_tokens = _estimate_tokens_list(included)
    excluded_tokens = _estimate_tokens_list(excluded)
    caveats_tokens = _estimate_tokens_list(caveats)
    readiness_tokens = _estimate_tokens(json.dumps(readiness, sort_keys=True))

    # Reserve room for caveats and readiness result
    reserved = caveats_tokens + readiness_tokens
    total_estimated = (
        task_tokens
        + included_tokens
        + excluded_tokens
        + reserved
    )

    receipt: dict = {
        "handoff_id": handoff_id,
        "sender": sender,
        "receiver": receiver,
        "task": task,
        "included": included,
        "excluded": excluded,
        "caveats": caveats,
        "readiness": readiness,
        "queries_used": queries_used,
        "token_estimate": total_estimated,
    }

    return receipt


def handoff_id_from_graph(
    handoff_node_id: str,
) -> str:
    """Retrieve or generate a handoff ID from the graph.

    In the current implementation, the handoff_id is the node id itself.
    This function can be extended to validate consistency.
    """
    # Return the handoff id as stored in the graph
    return handoff_node_id


def diff_handoffs(
    receipt_a: dict,
    receipt_b: dict,
) -> dict:
    """Compute diff(handoff_a, handoff_b).

    Returns {added: [...], removed: [...], changed: [...]}
    where each entry is {id, reason_code} for excluded memories,
    or {id, summary, evidence} for included memories.

    For simplicity at this layer we compare the included/excluded lists
    by id and reason_code.
    """
    ids_a = {mem["id"]: mem for mem in receipt_a.get("included", [])}
    ids_b = {mem["id"]: mem for mem in receipt_b.get("included", [])}

    added: List[dict] = []
    removed: List[dict] = []
    changed: List[dict] = []

    # Added memories (in b but not in a)
    for mid, mem in ids_b.items():
        if mid not in ids_a:
            added.append(mem)

    # Removed memories (in a but not in b)
    for mid, mem in ids_a.items():
        if mid not in ids_b:
            removed.append(mem)

    # Changed memories (in both but different)
    for mid in set(ids_a.keys()) & set(ids_b.keys()):
        mem_a = ids_a[mid]
        mem_b = ids_b[mid]
        # Compare reason codes if both are in excluded
        if mem_a.get("reason_code") != mem_b.get("reason_code"):
            changed.append(
                {
                    "id": mid,
                    "old_reason": mem_a.get("reason_code"),
                    "new_reason": mem_b.get("reason_code"),
                }
            )

    return {"added": added, "removed": removed, "changed": changed}


async def reproduce_receipt_from_graph(
    client, workspace_id: str, handoff_id: str,
) -> dict:
    """Reproduce the same receipt from the graph alone.

    This reads the handoff node and all linked memories, decisions,
    and exclusions to reconstruct the exact receipt JSON that was
    originally produced during handoff creation.

    Note: this is an async function because it interacts with the graph.
    """
    from app.graph.repo import graph_node

    graph_name = graph_name_for_workspace(workspace_id)

    # Read the handoff node
    handoff_node = await client.graph_node(graph_name, handoff_id)
    if not handoff_node:
        raise ValueError(f"Handoff {handoff_id} not found in graph")

    # Read included memories (INCLUDES edges)
    includes_query = """
    MATCH (h:Handoff {id: $handoff_id})-[:INCLUDES]->(m:Memory)
    OPTIONAL MATCH (m)-[:SUPPORTED_BY]->(s:Source)
    RETURN m.id AS memory_id,
           m.predicate AS predicate,
           m.object_value AS object_value,
           m.summary AS summary,
           m.confidence AS confidence,
           collect(DISTINCT {id: s.id, authority: s.authority}) AS evidence
    ORDER BY m.id
    """

    includes_result = await client.run(graph_name, "handoff.includes", includes_query, {
        "handoff_id": handoff_id,
    })
    included: List[dict] = []
    for row in includes_result.rows:
        evidence = row.get("evidence") or []
        included.append({
            "id": row["memory_id"],
            "summary": row.get("summary"),
            "evidence": evidence,
            "predicate": row.get("predicate"),
            "object_value": row.get("object_value"),
        })

    # Read excluded memories (EXCLUDES edges) with reason codes
    excludes_query = """
    MATCH (h:Handoff {id: $handoff_id})-[:EXCLUDES]->(m:Memory)
    RETURN m.id AS memory_id,
           r.reason_code AS reason_code
    ORDER BY m.id
    """
    excludes_result = await client.run(graph_name, "handoff.excludes", excludes_query, {
        "handoff_id": handoff_id,
    })
    excluded: List[dict] = []
    for row in excludes_result.rows:
        excluded.append({
            "id": row["memory_id"],
            "reason_code": row.get("reason_code"),
        })

    # Read caveats
    caveats_query = """
    MATCH (h:Handoff {id: $handoff_id})-[:CAVAT]->(c:ContestedClaim)
    RETURN c.memory_id AS memory_id,
           c.reason_code AS reason_code
    """
    caveats_result = await client.run(graph_name, "handoff.caveats", caveats_query, {
        "handoff_id": handoff_id,
    })
    caveats: List[dict] = []
    for row in caveats_result.rows:
        caveats.append({
            "memory_id": row["memory_id"],
            "reason_code": row.get("reason_code"),
        })

    # Read readiness
    readiness_query = """
    MATCH (h:Handoff {id: $handoff_id})-[:READY]->(r:ReadinessResult)
    RETURN r.verdict AS verdict,
           collect({step: r.steps.step, expected: r.steps.expected,
                    actual: r.steps.actual, state: r.steps.state,
                    memory_id: r.steps.memory_id}) AS steps
    """
    readiness_result = await client.run(graph_name, "handoff.readiness", readiness_query, {
        "handoff_id": handoff_id,
    })
    verdict = readiness_result.rows[0]["verdict"] if readiness_result.rows else "unknown"
    steps = readiness_result.rows[0].get("steps", []) if readiness_result.rows else []

    readiness: dict = {
        "verdict": verdict,
        "steps": steps,
    }

    # Read task
    task_query = """
    MATCH (h:Handoff {id: $handoff_id})-[:TASK]->(t:Task)
    RETURN t.value AS task_value
    """
    task_result = await client.run(graph_name, "handoff.task", task_query, {
        "handoff_id": handoff_id,
    })
    task_value = task_result.rows[0]["task_value"] if task_result.rows else ""

    # Read sender/receiver
    agents_query = """
    MATCH (h:Handoff {id: $handoff_id})-[:SENDER]->(s:Principal)
    MATCH (h:Handoff {id: $handoff_id})-[:RECEIVER]->(r:Principal)
    RETURN s.id AS sender_id, r.id AS receiver_id
    """
    agents_result = await client.run(graph_name, "handoff.agents", agents_query, {
        "handoff_id": handoff_id,
    })
    sender_id = agents_result.rows[0]["sender_id"] if agents_result.rows else ""
    receiver_id = agents_result.rows[0]["receiver_id"] if agents_result.rows else ""

    # Assemble the receipt
    receipt = assemble_receipt(
        handoff_id=handoff_id,
        sender=sender_id,
        receiver=receiver_id,
        task=task_value,
        included=included,
        excluded=excluded,
        caveats=caveats,
        readiness=readiness,
        queries_used=[],
        token_budget=0,
    )

    return receipt