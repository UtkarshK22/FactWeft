"""FalkorDB access layer.

``GraphClient.run`` is the only way application code talks to FalkorDB:

* the graph name is validated against ``^[a-z0-9_]{3,40}$`` before use;
* reads use ``GRAPH.RO_QUERY``, writes use ``GRAPH.QUERY``;
* every call is timed and recorded in a **bounded in-memory trace buffer**
  (telemetry for the Trace drawer only -- never a source of memory data);
* write statistics are surfaced for compare-and-set checks;
* connection failures become ``GraphUnavailable`` and are never retried
  against a local copy, because no local copy exists.
"""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import redis
from falkordb.asyncio import FalkorDB
from falkordb.edge import Edge
from falkordb.node import Node
from falkordb.path import Path as GraphPath

from app.core.clock import utc_now_ms
from app.core.config import Settings
from app.core.context import get_request_id
from app.core.errors import GraphQueryFailed, GraphUnavailable
from app.graph.names import validate_graph_name

# Errors that mean "the store is not reachable / usable right now". A Cypher
# error (ResponseError) is NOT in this list: that is a bug in our query, not an
# outage, and must not be reported as 503.
_CONNECTION_ERRORS: tuple[type[BaseException], ...] = (
    redis.exceptions.ConnectionError,
    redis.exceptions.TimeoutError,
    redis.exceptions.AuthenticationError,
    ConnectionError,
    TimeoutError,
    OSError,
)

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

# Trace params are redacted and truncated so the drawer never leaks secrets and
# a giant document cannot bloat the ring buffer.
_SENSITIVE_KEY = re.compile(
    r"(pass(word)?|secret|token|api[-_]?key|authorization|credential)", re.IGNORECASE
)
_TRACE_STRING_LIMIT = 240


@dataclass(frozen=True, slots=True)
class WriteStats:
    """Graph mutation counters reported by FalkorDB."""

    nodes_created: int = 0
    relationships_created: int = 0
    properties_set: int = 0

    @property
    def mutated(self) -> bool:
        return bool(self.nodes_created or self.relationships_created or self.properties_set)

    def as_dict(self) -> dict[str, int]:
        return {
            "nodes_created": self.nodes_created,
            "relationships_created": self.relationships_created,
            "properties_set": self.properties_set,
        }


@dataclass(frozen=True, slots=True)
class TraceEntry:
    id: str
    request_id: str
    query_name: str
    cypher: str
    params: dict[str, Any]
    duration_ms: float
    rows: int
    write: bool
    ts: int
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "query_name": self.query_name,
            "cypher": self.cypher,
            "params": self.params,
            "duration_ms": self.duration_ms,
            "rows": self.rows,
            "write": self.write,
            "ts": self.ts,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    """Rows and statistics for one executed statement."""

    query_name: str
    columns: list[str]
    rows: list[dict[str, Any]]
    stats: WriteStats
    duration_ms: float

    @property
    def returned_rows(self) -> int:
        return len(self.rows)


class TraceBuffer:
    """Bounded ring buffer of recent query traces (telemetry, not memory)."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("trace buffer capacity must be positive")
        self._entries: deque[TraceEntry] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        return self._entries.maxlen or 0

    def add(self, entry: TraceEntry) -> None:
        self._entries.append(entry)

    def snapshot(self, limit: int) -> list[TraceEntry]:
        if limit < 0:
            raise ValueError("limit must be >= 0")
        newest_first = list(self._entries)[::-1]
        return newest_first[:limit]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


def redact_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    """Copy params for the trace buffer with secrets masked and longs truncated."""
    if not params:
        return {}
    return {str(key): _redact_value(str(key), value) for key, value in params.items()}


def _redact_value(key: str, value: Any) -> Any:
    if _SENSITIVE_KEY.search(key):
        return "***"
    if isinstance(value, Mapping):
        return {str(k): _redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_redact_value(key, item) for item in value]
    if isinstance(value, str):
        if len(value) > _TRACE_STRING_LIMIT:
            return value[:_TRACE_STRING_LIMIT] + "...(truncated)"
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def _plain(value: Any) -> Any:
    """Convert client entities into JSON-safe structures for API responses."""
    if isinstance(value, Node):
        properties = {str(k): _plain(v) for k, v in (value.properties or {}).items()}
        # Every domain node carries an ``id`` property; expose that instead of the
        # store-internal id so API responses and edge lookups agree on identity.
        return {
            "id": str(properties.get("id", value.id)),
            "labels": list(value.labels or []),
            "properties": properties,
        }
    if isinstance(value, Edge):
        return {
            "type": value.relation,
            "source": _plain(value.src_node),
            "target": _plain(value.dest_node),
            "properties": {str(k): _plain(v) for k, v in (value.properties or {}).items()},
        }
    if isinstance(value, GraphPath):
        return {
            "nodes": [_plain(node) for node in value.nodes()],
            "relationships": [_plain(edge) for edge in value.edges()],
        }
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    return value


class GraphClient:
    """Thin, observable wrapper around the FalkorDB asyncio client."""

    def __init__(
        self,
        settings: Settings,
        *,
        db: FalkorDB | None = None,
        buffer_size: int | None = None,
    ) -> None:
        self._settings = settings
        self._timeout_ms = settings.query_timeout_ms
        self._db: FalkorDB | None = db
        self._traces = TraceBuffer(buffer_size or settings.trace_buffer_size)

    # -- lifecycle ---------------------------------------------------------
    @property
    def endpoint(self) -> str:
        return self._settings.falkordb_endpoint

    def _connection(self) -> FalkorDB:
        """Build the client lazily.

        The FalkorDB client probes the server (``INFO``) while constructing, so
        building it eagerly would make the API fail to start when the store is
        down. Lazy construction keeps /api/health useful and lets graph routes
        answer 503 instead of crashing the process.
        """
        if self._db is None:
            try:
                self._db = FalkorDB(
                    host=self._settings.falkordb_host,
                    port=self._settings.falkordb_port,
                    password=self._settings.falkordb_password_value,
                    socket_timeout=self._settings.query_timeout_ms / 1000,
                    socket_connect_timeout=min(5.0, self._settings.query_timeout_ms / 1000),
                )
            except _CONNECTION_ERRORS as exc:
                raise GraphUnavailable(f"FalkorDB unreachable at {self.endpoint}") from exc
        return self._db

    async def aclose(self) -> None:
        if self._db is not None:
            await self._db.aclose()
            self._db = None

    # -- health / metadata -------------------------------------------------
    async def ping(self) -> bool:
        """Return ``True`` only when the server answers PING.

        Used by /api/health. A down server is a status, not an exception; graph
        routes call ``run``/``list_graphs`` and get ``GraphUnavailable`` instead.
        """
        try:
            return bool(await self._connection().connection.ping())
        except (GraphUnavailable, redis.exceptions.RedisError, OSError):
            return False

    async def list_graphs(self) -> list[str]:
        try:
            names = await self._connection().list_graphs()
        except _CONNECTION_ERRORS as exc:
            raise GraphUnavailable(f"FalkorDB unreachable at {self.endpoint}") from exc
        return sorted(str(name) for name in names)

    async def graph_exists(self, graph_name: str) -> bool:
        name = validate_graph_name(graph_name)
        return name in await self.list_graphs()

    # -- queries -----------------------------------------------------------
    async def run(
        self,
        graph_name: str,
        query_name: str,
        query: str,
        params: Mapping[str, Any] | None = None,
        write: bool = False,
    ) -> QueryOutcome:
        """Execute one parameterized Cypher statement and trace it.

        Reads use ``ro_query`` (GRAPH.RO_QUERY); writes use ``query``
        (GRAPH.QUERY). ``write=False`` with a mutating statement fails at the
        server rather than silently writing.
        """
        name = validate_graph_name(graph_name)
        values = dict(params or {})
        started = time.perf_counter()
        entry_id = f"tr_{uuid4().hex[:12]}"
        try:
            graph = self._connection().select_graph(name)
            if write:
                result = await graph.query(query, values, timeout=self._timeout_ms)
            else:
                result = await graph.ro_query(query, values, timeout=self._timeout_ms)
        except _CONNECTION_ERRORS as exc:
            self._record(
                entry_id=entry_id,
                query_name=query_name,
                query=query,
                params=values,
                started=started,
                rows=0,
                write=write,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise GraphUnavailable(f"FalkorDB unreachable at {self.endpoint}") from exc
        except redis.exceptions.ResponseError as exc:
            self._record(
                entry_id=entry_id,
                query_name=query_name,
                query=query,
                params=values,
                started=started,
                rows=0,
                write=write,
                error=f"ResponseError: {exc}",
            )
            raise GraphQueryFailed(
                f"{query_name} failed: {exc}",
                detail={"query_name": query_name},
            ) from exc

        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        columns = [
            str(header[1]) if isinstance(header, (list, tuple)) and len(header) > 1 else str(header)
            for header in result.header
        ]
        rows = [
            {column: _plain(value) for column, value in zip(columns, row, strict=False)}
            for row in result.result_set
        ]
        stats = (
            WriteStats(
                nodes_created=int(result.nodes_created),
                relationships_created=int(result.relationships_created),
                properties_set=int(result.properties_set),
            )
            if write
            else WriteStats()
        )
        self._record(
            entry_id=entry_id,
            query_name=query_name,
            query=query,
            params=values,
            started=started,
            rows=len(rows),
            write=write,
        )
        return QueryOutcome(
            query_name=query_name,
            columns=columns,
            rows=rows,
            stats=stats,
            duration_ms=duration_ms,
        )

    async def explain(
        self,
        graph_name: str,
        query_name: str,
        query: str,
        params: Mapping[str, Any] | None = None,
    ) -> str:
        """Return the execution plan for a statement (compile check, no execution)."""
        name = validate_graph_name(graph_name)
        values = dict(params or {})
        started = time.perf_counter()
        entry_id = f"tr_{uuid4().hex[:12]}"
        try:
            plan = await self._connection().select_graph(name).explain(query, values)
        except _CONNECTION_ERRORS as exc:
            self._record(
                entry_id=entry_id,
                query_name=f"explain:{query_name}",
                query=query,
                params=values,
                started=started,
                rows=0,
                write=False,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise GraphUnavailable(f"FalkorDB unreachable at {self.endpoint}") from exc
        except redis.exceptions.ResponseError as exc:
            self._record(
                entry_id=entry_id,
                query_name=f"explain:{query_name}",
                query=query,
                params=values,
                started=started,
                rows=0,
                write=False,
                error=f"ResponseError: {exc}",
            )
            raise GraphQueryFailed(
                f"EXPLAIN {query_name} failed: {exc}",
                detail={"query_name": query_name},
            ) from exc
        self._record(
            entry_id=entry_id,
            query_name=f"explain:{query_name}",
            query=query,
            params=values,
            started=started,
            rows=0,
            write=False,
        )
        return str(plan)

    async def create_unique_constraint(
        self, graph_name: str, label: str, property_name: str = "id"
    ) -> str:
        """Create a UNIQUE node constraint (DDL cannot be expressed as parameters)."""
        name = validate_graph_name(graph_name)
        for identifier in (label, property_name):
            if not _IDENTIFIER.match(identifier):
                raise ValueError(f"invalid DDL identifier: {identifier!r}")
        started = time.perf_counter()
        entry_id = f"tr_{uuid4().hex[:12]}"
        command_text = (
            f"GRAPH.CONSTRAINT CREATE {name} UNIQUE NODE {label} PROPERTIES 1 {property_name}"
        )
        try:
            status = (
                await self._connection()
                .select_graph(name)
                .execute_command(
                    "GRAPH.CONSTRAINT",
                    "CREATE",
                    name,
                    "UNIQUE",
                    "NODE",
                    label,
                    "PROPERTIES",
                    1,
                    property_name,
                )
            )
        except _CONNECTION_ERRORS as exc:
            self._record(
                entry_id=entry_id,
                query_name="schema.constraint.unique",
                query=command_text,
                params={},
                started=started,
                rows=0,
                write=True,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise GraphUnavailable(f"FalkorDB unreachable at {self.endpoint}") from exc
        except redis.exceptions.ResponseError as exc:
            self._record(
                entry_id=entry_id,
                query_name="schema.constraint.unique",
                query=command_text,
                params={},
                started=started,
                rows=0,
                write=True,
                error=f"ResponseError: {exc}",
            )
            raise GraphQueryFailed(f"constraint on {label}.{property_name} failed: {exc}") from exc
        self._record(
            entry_id=entry_id,
            query_name="schema.constraint.unique",
            query=command_text,
            params={},
            started=started,
            rows=0,
            write=True,
        )
        return str(status)

    async def delete_graph(self, graph_name: str) -> bool:
        """Drop a graph entirely (used by tests and /demo/reset)."""
        name = validate_graph_name(graph_name)
        if not await self.graph_exists(name):
            return False
        started = time.perf_counter()
        entry_id = f"tr_{uuid4().hex[:12]}"
        try:
            await self._connection().select_graph(name).delete()
        except _CONNECTION_ERRORS as exc:
            raise GraphUnavailable(f"FalkorDB unreachable at {self.endpoint}") from exc
        self._record(
            entry_id=entry_id,
            query_name="graph.delete",
            query="GRAPH.DELETE",
            params={"graph_name": name},
            started=started,
            rows=0,
            write=True,
        )
        return True

    # -- tracing -----------------------------------------------------------
    def recent_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        return [entry.as_dict() for entry in self._traces.snapshot(limit)]

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    @property
    def trace_capacity(self) -> int:
        return self._traces.capacity

    # -- internals ---------------------------------------------------------
    def _record(
        self,
        *,
        entry_id: str,
        query_name: str,
        query: str,
        params: Mapping[str, Any],
        started: float,
        rows: int,
        write: bool,
        error: str | None = None,
    ) -> None:
        self._traces.add(
            TraceEntry(
                id=entry_id,
                request_id=get_request_id(),
                query_name=query_name,
                cypher=query,
                params=redact_params(params),
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                rows=rows,
                write=write,
                ts=utc_now_ms(),
                error=error,
            )
        )
