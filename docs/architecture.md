# FactWeft architecture (scaffold)

FactWeft is a graph-native memory coordination layer. FalkorDB is the **only**
memory store: claims, evidence, contradictions, supersession, handoff receipts
and their provenance all live in the graph. There is no SQL table, no JSON
snapshot and no in-process map of memories to answer from.

The single in-memory structure is a bounded ring buffer of recent query traces
(`app/graph/connection.py::TraceBuffer`). It is telemetry for the Trace drawer,
never a source of memory data.

## Request path

```
HTTP -> FastAPI (request id, CORS, error mapping)
     -> Principal (Bearer token -> workspace_id, agent_id, role)
     -> graph name = "ws_" + workspace_id   (validated ^[a-z0-9_]{3,40}$)
     -> GraphClient.run(graph, query_name, cypher, params, write)
     -> FalkorDB (GRAPH.RO_QUERY for reads, GRAPH.QUERY for writes)
     -> rows + write stats + trace entry
```

* Graph names come from the principal only. A client string never reaches
  `select_graph`.
* Values are bound through the client's `CYPHER` params header. Labels and
  property names cannot be parameters, so the only formatted Cypher is the
  `CREATE INDEX` template in `queries.py`, fed from the fixed allowlists in
  `bootstrap.py`.
* Connection failures raise `GraphUnavailable` -> HTTP 503
  `{"error": "graph_unavailable"}`. Cypher errors raise `GraphQueryFailed`
  (500) and are never converted into "no rows".

## Graph model

One graph per workspace (`ws_<workspace_id>`), with:

* Nodes: `Workspace`, `Agent`, `Session`, `Episode`, `Concept`, `Source`,
  `Memory`, `Step`, `Handoff`, `Decision`.
* Every label has a range index on `id`; `Memory` also indexes `status`,
  `subject_key`, `predicate`. Unique constraints on `id` are created when the
  server supports them (v4.22.1 does); `MERGE` remains the write path.
* Relationships: `OWNS_MEMORY`, `OWNS_HANDOFF`, `CAPTURED`, `DERIVED_FROM`,
  `SUPPORTED_BY`, `ABOUT`, `PROPOSED_BY`, `CONTRADICTS`, `SUPERSEDES`,
  `SHARED_WITH`, `HAS_STEP`, `CHECKS`, `RESOLVES`, `SENT_BY`, `SENT_TO`,
  `INCLUDES`, `EXCLUDES`.
* Timestamps are integer epoch milliseconds.

`app/graph/queries.py` is the catalogue: 39 named statements, each documenting
purpose, params, returned columns and whether it writes. `app/graph/repo.py`
wraps them in typed functions that return Pydantic models, never raw rows, so
routes and the scenario runner never build Cypher themselves. Two tests keep it
honest: `test_query_catalogue.py` EXPLAINs every statement against the pinned
image, and `test_repo_queries.py` executes the full propose → conflict → hold →
supersede → review → handoff → projection lifecycle against a real graph.

Dialect notes for v4.22.1 (all found by execution): `EXISTS { ... }` subqueries
and parameterized variable-length bounds (`[*1..$hops]`) are rejected, so the
catalogue uses `OPTIONAL MATCH` and a validated `{hops}` literal (1 or 2).
Label predicates (`NOT n:Memory`), `properties()`, `coalesce`, `UNION`, `CASE`
on nulls, `UNWIND ... MATCH ... MERGE` and `LIMIT $param` all work.

## Seeding and demo data

`demo_data/*.json` holds the fictional static base (including the injection and
rumour sources and the per-source extraction fixtures). `app.memory.seed`
validates it on load and `MERGE`s it in, so `seed_workspace` is idempotent and
`reset_workspace` drop-and-recreates the graph. Only the static base is seeded;
memories are created by the scenario runner so the demo shows them arriving
live.

## Bounded projection

`GET /api/graph/neighborhood` answers from three statements (root, page, total)
with hard caps: `hops` ≤ 2, `max_nodes` ≤ `MAX_GRAPH_NODES` (default 500), edges
≤ `max(8, 4 × max_nodes)`. `GraphNode.id` is the domain `id` property, so edge
endpoints and API ids agree. Responses carry `truncated` and
`counts.showing = "X of Y nodes"`; `as_of_ms` reconstructs the past by hiding
later claims and re-deriving `superseded`/`expired` statuses.

## Memory lifecycle (next steps)

LLM output can only create `candidate`. Promotion, supersession, conflict
handling and receipts are deterministic code + Cypher:

* `Q3` finds a value conflict; the resolver compares source authority and
  publication time (`Q6` supersedes with compare-and-set, otherwise `Q_HOLD`).
* A newer timestamp alone never wins.
* Retrieval is receiver-aware (`Q_ELIGIBLE_MEMORIES` / `Q_INELIGIBLE_MEMORIES`);
  excluded rows carry a stable `reason_code`, and `scope_denied` rows never
  include the summary.

The resolver and receipt assembly land in the next milestones; the queries,
decision primitives and typed wrappers are already in place and are exercised
end to end by `test_repo_queries.py`.

## Errors

| Situation | Status | `error` |
| --- | --- | --- |
| Missing/invalid bearer | 401 | `auth_required` |
| Role not allowed | 403 | `role_forbidden` |
| Not found in this workspace | 404 | `not_found` |
| Stale revision (compare-and-set) | 409 | `stale_revision` |
| Insufficient evidence / unresolved conflict | 422 | `unprocessable_claim` |
| FalkorDB unreachable | 503 | `graph_unavailable` |

Every error body carries `message` and `request_id`; the `X-Request-ID` response
header echoes the client's value (or the generated one).

## Configuration

`app/core/config.py` (pydantic-settings): `FALKORDB_HOST/PORT/PASSWORD`,
`LLM_MODE`, `LLM_MODEL`, `LLM_API_KEY`, `DEMO_MODE`, `TOKENS_FILE`,
`CORS_ORIGINS`, `QUERY_TIMEOUT_MS`, `MAX_GRAPH_NODES`, `TRACE_BUFFER_SIZE`.
Secrets are `SecretStr` and never logged.
