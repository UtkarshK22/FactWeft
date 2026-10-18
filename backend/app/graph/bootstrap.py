"""Idempotent graph schema bootstrap.

``ensure_schema`` inspects ``CALL db.indexes()`` / ``CALL db.constraints()``
first and only creates what is missing, so running it repeatedly is safe. Unique
constraints are supported by the pinned FalkorDB version (verified live), and
are created on ``id`` for every label; ``MERGE`` remains the write path so the
schema never *depends* on the constraint for correctness.

``python -m app.graph.bootstrap`` ensures the schema for the demo workspaces and
MERGEs their Workspace/Agent nodes (the demo memories are seeded separately).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.core.auth import TokenRegistry, get_token_registry
from app.core.config import Settings, get_settings
from app.core.constants import DEMO_WORKSPACE_ID
from app.graph import queries
from app.graph.connection import GraphClient
from app.graph.names import graph_name_for_workspace, validate_graph_name

SCHEMA_LABELS: tuple[str, ...] = (
    "Workspace",
    "Agent",
    "Session",
    "Episode",
    "Concept",
    "Source",
    "Memory",
    "Step",
    "Handoff",
    "Decision",
)

MEMORY_INDEXES: tuple[tuple[str, str], ...] = (
    ("Memory", "status"),
    ("Memory", "subject_key"),
    ("Memory", "predicate"),
)

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class SchemaReport:
    graph_name: str
    indexes_created: tuple[str, ...]
    constraints_created: tuple[str, ...]
    indexes_total: int
    constraints_total: int
    constraints_pending: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "graph_name": self.graph_name,
            "indexes_created": list(self.indexes_created),
            "constraints_created": list(self.constraints_created),
            "indexes_total": self.indexes_total,
            "constraints_total": self.constraints_total,
            "constraints_pending": list(self.constraints_pending),
        }


def _required_indexes() -> tuple[tuple[str, str], ...]:
    return tuple((label, "id") for label in SCHEMA_LABELS) + MEMORY_INDEXES


def _index_keys(rows: Iterable[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in rows:
        label = row.get("label")
        properties = row.get("properties") or []
        if isinstance(properties, str):
            properties = [properties]
        for prop in properties:
            if isinstance(label, str) and isinstance(prop, str):
                keys.add((label, prop))
    return keys


def _constraint_keys(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], str]:
    found: dict[tuple[str, str], str] = {}
    for row in rows:
        if row.get("type") != "UNIQUE":
            continue
        label = row.get("label")
        properties = row.get("properties") or []
        if isinstance(properties, str):
            properties = [properties]
        for prop in properties:
            if isinstance(label, str) and isinstance(prop, str):
                found[(label, prop)] = str(row.get("status") or "unknown")
    return found


async def _read_schema_metadata(
    client: GraphClient, graph_name: str
) -> tuple[set[tuple[str, str]], dict[tuple[str, str], str]]:
    indexes = await client.run(graph_name, "schema.indexes", queries.SCHEMA_LIST_INDEXES)
    constraints = await client.run(
        graph_name, "schema.constraints", queries.SCHEMA_LIST_CONSTRAINTS
    )
    return _index_keys(indexes.rows), _constraint_keys(constraints.rows)


async def ensure_schema(
    client: GraphClient,
    graph_name: str,
    *,
    constraint_timeout_ms: int = 5000,
) -> SchemaReport:
    """Create missing indexes and UNIQUE(id) constraints; never duplicates them."""
    graph_name = validate_graph_name(graph_name)

    exists = await client.graph_exists(graph_name)
    # A brand-new graph cannot answer CALL db.indexes() until something writes
    # to it, so the first CREATE INDEX below also creates the graph.
    existing_indexes: set[tuple[str, str]] = set()
    if exists:
        existing_indexes, _ = await _read_schema_metadata(client, graph_name)

    created_indexes: list[str] = []
    for label, prop in _required_indexes():
        if (label, prop) in existing_indexes:
            continue
        if not _IDENTIFIER.match(label) or not _IDENTIFIER.match(prop):
            raise ValueError(f"refusing to format DDL identifiers: {label}.{prop}")
        statement = queries.SCHEMA_CREATE_INDEX.format(label=label, prop=prop)
        await client.run(
            graph_name,
            f"schema.index.{label}.{prop}",
            statement,
            write=True,
        )
        created_indexes.append(f"{label}.{prop}")

    existing_indexes, existing_constraints = await _read_schema_metadata(client, graph_name)

    created_constraints: list[str] = []
    for label in SCHEMA_LABELS:
        key = (label, "id")
        if key in existing_constraints:
            continue
        await client.create_unique_constraint(graph_name, label, "id")
        created_constraints.append(f"{label}.id")

    pending = await _wait_for_constraints(
        client,
        graph_name,
        expected={(label, "id") for label in SCHEMA_LABELS},
        timeout_ms=constraint_timeout_ms,
    )

    _, final_constraints = await _read_schema_metadata(client, graph_name)
    return SchemaReport(
        graph_name=graph_name,
        indexes_created=tuple(created_indexes),
        constraints_created=tuple(created_constraints),
        indexes_total=len(existing_indexes),
        constraints_total=len(final_constraints),
        constraints_pending=pending,
    )


async def _wait_for_constraints(
    client: GraphClient,
    graph_name: str,
    *,
    expected: set[tuple[str, str]],
    timeout_ms: int,
) -> tuple[str, ...]:
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        _, constraints = await _read_schema_metadata(client, graph_name)
        pending = tuple(
            sorted(
                f"{label}.{prop}"
                for (label, prop) in expected
                if constraints.get((label, prop)) != "OPERATIONAL"
            )
        )
        if not pending or time.monotonic() >= deadline:
            return pending
        await asyncio.sleep(0.1)


async def is_workspace_seeded(client: GraphClient, workspace_id: str = DEMO_WORKSPACE_ID) -> bool:
    """True when the workspace graph exists and holds its Workspace node."""
    graph_name = graph_name_for_workspace(workspace_id)
    if not await client.graph_exists(graph_name):
        return False
    outcome = await client.run(
        graph_name,
        "health.workspace_present",
        queries.Q_WORKSPACE_PRESENT,
        {"workspace_id": workspace_id},
    )
    if not outcome.rows:
        return False
    return int(outcome.rows[0].get("count") or 0) > 0


async def bootstrap_async(
    settings: Settings, registry: TokenRegistry, workspace_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    client = GraphClient(settings)
    try:
        if not await client.ping():
            raise ConnectionError(f"FalkorDB is not reachable at {settings.falkordb_endpoint}")
        targets = workspace_ids or list(registry.workspace_ids)
        results: list[dict[str, Any]] = []
        for workspace_id in targets:
            graph_name = graph_name_for_workspace(workspace_id)
            report = await ensure_schema(client, graph_name)
            results.append({**report.as_dict(), "workspace_id": workspace_id})
        return results
    finally:
        await client.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.graph.bootstrap",
        description="Ensure the FactWeft schema (indexes + unique ids). Data: app.memory.seed.",
    )
    parser.add_argument(
        "--workspace",
        action="append",
        dest="workspaces",
        help="workspace id to bootstrap (repeatable; defaults to every workspace in tokens.json)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    try:
        registry = get_token_registry()
        results = asyncio.run(bootstrap_async(settings, registry, args.workspaces))
    except ConnectionError as exc:
        print(
            json.dumps({"error": "graph_unavailable", "message": str(exc)}),
            file=sys.stderr,
        )
        return 2
    for result in results:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
