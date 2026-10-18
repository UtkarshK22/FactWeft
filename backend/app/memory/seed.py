"""Demo workspace seeding.

``seed_workspace`` writes only the **static base**: workspace, agents, concepts,
sources, sessions, episodes and the readiness procedure with its steps. The
memories themselves are created by the scenario runner so the demo shows claims
appearing, conflicting and superseding live.

Both functions are idempotent (``MERGE`` everywhere) and reuse ``ensure_schema``.
``reset_workspace`` drops the graph and then re-creates the schema so the next
scenario run starts from an empty but ready graph.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.graph import repo
from app.graph.bootstrap import SchemaReport, ensure_schema
from app.graph.connection import GraphClient
from app.graph.names import graph_name_for_workspace, validate_graph_name
from app.memory.demo_data import (
    DemoWorkspace,
    demo_workspace_ids,
    load_demo_workspace,
)


@dataclass(frozen=True, slots=True)
class SeedReport:
    workspace_id: str
    graph_name: str
    counts: dict[str, int]
    procedure_ids: list[str]
    schema: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "graph_name": self.graph_name,
            "counts": self.counts,
            "procedure_ids": self.procedure_ids,
            "schema": self.schema,
        }


@dataclass(frozen=True, slots=True)
class ResetReport:
    workspace_id: str
    graph_name: str
    dropped: bool
    nodes_after_reset: int
    schema: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "graph_name": self.graph_name,
            "dropped": self.dropped,
            "nodes_after_reset": self.nodes_after_reset,
            "schema": self.schema,
        }


async def _with_client(client: GraphClient | None) -> tuple[GraphClient, bool]:
    if client is not None:
        return client, False
    return GraphClient(get_settings()), True


async def seed_workspace(
    workspace_id: str,
    *,
    client: GraphClient | None = None,
    data: DemoWorkspace | None = None,
) -> SeedReport:
    """Seed (or refresh) the static base of one workspace. Safe to re-run."""
    graph_name = graph_name_for_workspace(workspace_id)
    payload = data if data is not None else load_demo_workspace(workspace_id)
    if payload.workspace.id != workspace_id:
        raise ValueError(
            f"demo data declares workspace {payload.workspace.id!r}, got {workspace_id!r}"
        )

    owned_client, should_close = await _with_client(client)
    try:
        schema: SchemaReport = await ensure_schema(owned_client, graph_name)

        await repo.merge_workspace(
            owned_client,
            workspace_id,
            display_name=payload.workspace.display_name,
            created_at=payload.workspace.created_at,
        )
        for agent in payload.agents:
            await repo.merge_agent(
                owned_client,
                workspace_id,
                agent_id=agent.id,
                role=agent.role,
                display_name=agent.display_name,
            )
        for concept in payload.concepts:
            await repo.seed_concept(
                owned_client,
                workspace_id,
                concept_id=concept.id,
                canonical_name=concept.canonical_name,
                concept_type=concept.concept_type,
                aliases=concept.aliases,
            )
        for source in payload.sources:
            await repo.seed_source(
                owned_client,
                workspace_id,
                source_id=source.id,
                title=source.title,
                source_type=source.source_type,
                source_ref=source.source_ref,
                content_hash=source.content_hash,
                published_at=source.published_at,
                authority=source.authority,
                synthetic_flag=source.synthetic_flag,
                excerpt=source.excerpt,
            )
        for session in payload.sessions:
            await repo.seed_session(
                owned_client,
                workspace_id,
                session_id=session.id,
                task_label=session.task_label,
                started_at=session.started_at,
                ended_at=session.ended_at,
            )
        for episode in payload.episodes:
            await repo.seed_episode(
                owned_client,
                workspace_id,
                episode_id=episode.id,
                event_type=episode.event_type,
                occurred_at=episode.occurred_at,
                summary=episode.summary,
                session_id=episode.session_id,
            )

        steps_written = 0
        procedure_ids: list[str] = []
        for procedure in payload.procedures:
            procedure_ids.append(
                await repo.seed_procedure(
                    owned_client,
                    workspace_id,
                    agent_id=procedure.agent_id,
                    subject_key=procedure.subject_key,
                    memory_id=procedure.id,
                    predicate=procedure.predicate,
                    label=procedure.label,
                    summary=procedure.summary,
                    confidence=procedure.confidence,
                    created_at=procedure.created_at,
                    valid_from=procedure.valid_from,
                )
            )
            for step in procedure.steps:
                await repo.seed_step(
                    owned_client,
                    workspace_id,
                    procedure_id=procedure.id,
                    step_id=f"{procedure.id}_step_{step.order}",
                    order=step.order,
                    label=step.label,
                    check_predicate=step.check_predicate,
                    expected_value=step.expected_value,
                    concept_id=step.concept_id,
                )
                steps_written += 1

        return SeedReport(
            workspace_id=workspace_id,
            graph_name=graph_name,
            counts={
                "agents": len(payload.agents),
                "concepts": len(payload.concepts),
                "sources": len(payload.sources),
                "sessions": len(payload.sessions),
                "episodes": len(payload.episodes),
                "procedures": len(payload.procedures),
                "steps": steps_written,
            },
            procedure_ids=procedure_ids,
            schema=schema.as_dict(),
        )
    finally:
        if should_close:
            await owned_client.aclose()


async def reset_workspace(
    workspace_id: str, *, client: GraphClient | None = None
) -> ResetReport:
    """Drop the workspace graph, then recreate an empty schema for it."""
    graph_name = validate_graph_name(graph_name_for_workspace(workspace_id))
    owned_client, should_close = await _with_client(client)
    try:
        dropped = await owned_client.delete_graph(graph_name)
        schema = await ensure_schema(owned_client, graph_name)
        nodes = await repo.graph_node_count(owned_client, graph_name)
        return ResetReport(
            workspace_id=workspace_id,
            graph_name=graph_name,
            dropped=dropped,
            nodes_after_reset=nodes,
            schema=schema.as_dict(),
        )
    finally:
        if should_close:
            await owned_client.aclose()


async def seed_all(client: GraphClient | None = None) -> list[SeedReport]:
    owned_client, should_close = await _with_client(client)
    try:
        return [
            await seed_workspace(workspace_id, client=owned_client)
            for workspace_id in demo_workspace_ids()
        ]
    finally:
        if should_close:
            await owned_client.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.memory.seed",
        description="Seed the FactWeft demo workspaces (static base only).",
    )
    parser.add_argument(
        "--workspace",
        action="append",
        dest="workspaces",
        help="workspace id (repeatable; defaults to every demo workspace)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop the graph before seeding",
    )
    args = parser.parse_args(argv)
    targets: list[str] = args.workspaces or list(demo_workspace_ids())

    async def run() -> list[dict[str, Any]]:
        client = GraphClient(get_settings())
        try:
            if not await client.ping():
                raise ConnectionError(
                    f"FalkorDB is not reachable at {get_settings().falkordb_endpoint}"
                )
            results: list[dict[str, Any]] = []
            for workspace_id in targets:
                if args.reset:
                    results.append(
                        (await reset_workspace(workspace_id, client=client)).as_dict()
                    )
                results.append(
                    (await seed_workspace(workspace_id, client=client)).as_dict()
                )
            return results
        finally:
            await client.aclose()

    try:
        results = asyncio.run(run())
    except ConnectionError as exc:
        print(json.dumps({"error": "graph_unavailable", "message": str(exc)}), file=sys.stderr)
        return 2
    for result in results:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
