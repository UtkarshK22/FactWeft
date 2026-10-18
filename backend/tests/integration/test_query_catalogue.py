"""Compile-check the whole Cypher catalogue against the pinned FalkorDB image.

FalkorDB only accepts EXPLAIN on an existing graph, so the fixture bootstraps
the throwaway graph first. Any syntax the server rejects fails this test.
"""

from __future__ import annotations

import pytest
from app.graph import queries
from app.graph.bootstrap import ensure_schema
from app.graph.connection import GraphClient

pytestmark = pytest.mark.integration

# One superset of parameters used by the catalogue; unused keys are harmless.
PARAMS: dict[str, object] = {
    "workspace_id": "ws_test_catalogue",
    "display_name": "Catalogue Test",
    "agent_id": "agent_scout",
    "source_id": "src_1",
    "subject_key": "concept_1",
    "concept_ids": ["concept_1"],
    "memory_id": "mem_1",
    "candidate_id": "mem_candidate",
    "existing_id": "mem_existing",
    "old_id": "mem_old",
    "new_id": "mem_new",
    "episode_id": "ep_1",
    "receiver_id": "agent_planner",
    "sender_id": "agent_scout",
    "handoff_id": "handoff_1",
    "procedure_id": "mem_procedure",
    "decision_id": "dec_1",
    "memory_ids": ["mem_1"],
    "excluded": [{"memory_id": "mem_2", "reason_code": "scope_denied"}],
    "kind": "semantic",
    "predicate": "freeze_date",
    "object_value": "2026-10-18",
    "cardinality": "one",
    "summary": "freeze moved to Oct 18",
    "scope": "workspace",
    "confidence": 0.8,
    "now": 1,
    "valid_from": 1,
    "valid_until": None,
    "expected_revision": 1,
    "new_valid_from": 2,
    "reason": "newer_higher_authority",
    "reason_code": "needs_review",
    "reviewer_type": "rule",
    "task": "hand off release readiness",
    "status": "sent",
    "token_budget": 100,
    "receipt_version": 1,
    "policy_version": 1,
    "role": "scout",
    # Seeding statements.
    "canonical_name": "Atlas Release",
    "concept_type": "release",
    "aliases": ["atlas"],
    "title": "Synthetic planning note",
    "source_type": "planning_doc",
    "source_ref": "synthetic://atlas/planning-note",
    "content_hash": "sha256:" + "0" * 64,
    "published_at": 1,
    "synthetic_flag": True,
    "excerpt": "Synthetic excerpt.",
    "session_id": "session_1",
    "task_label": "plan the release",
    "started_at": 1,
    "ended_at": None,
    "event_type": "session_started",
    "occurred_at": 1,
    "label": "QA sign-off complete",
    "check_predicate": "status",
    "expected_value": "complete",
    "concept_id": "concept_1",
    "step_id": "mem_procedure_step_1",
    "order": 1,
    "created_at": 1,
    # Projection limits and id lists (also used by EXPLAIN).
    "max_nodes": 50,
    "edge_cap": 32,
    "ids": ["mem_1"],
    "limit": 50,
}


def catalogue() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(queries).items()
        if name.isupper() and isinstance(value, str) and name != "SCHEMA_CREATE_INDEX"
    }


async def test_every_catalogue_query_compiles(
    graph_client: GraphClient, throwaway_graph: str
) -> None:
    await ensure_schema(graph_client, throwaway_graph)
    failures: list[str] = []
    for name, cypher in catalogue().items():
        # Variable-length bounds cannot be parameters; the repository substitutes
        # a validated literal (see queries.NEIGHBORHOOD_HOP_CHOICES).
        cypher = cypher.replace("{hops}", str(queries.NEIGHBORHOOD_MAX_HOPS))
        try:
            await graph_client.explain(throwaway_graph, name, cypher, PARAMS)
        except Exception as exc:  # noqa: BLE001 - collected for one clear failure
            failures.append(f"{name}: {exc}")
    assert failures == [], "catalogue statements failed to compile:\n" + "\n".join(failures)
