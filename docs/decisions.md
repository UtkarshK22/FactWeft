# Decisions log

Short notes on choices that are not obvious from the code, with the evidence
that drove them (all verified against the running stack on 2026-10-18).

## D1. Pin `falkordb/falkordb:v4.22.1`

Docker Hub's `:latest` currently resolves to the same digest as `v4.22.1`.
A `6.0.x` Rust-engine line exists but `:latest` has not moved to it, and the
documentation plus the official Python client's index/constraint APIs match the
4.x behaviour. Pinning the digest-equivalent tag keeps the demo reproducible.

## D2. RDB snapshots instead of AOF

The FalkorDB docs recommend `--appendonly yes`. On v4.22.1 this is unsafe for
this workload: after a clean `docker compose stop` + `start`, the module crashed
while replaying the AOF, repeatedly:

```
------ DUMPING CODE AROUND EIP ------
Symbol: GraphContext_GetSchemaByID
Module: /var/lib/falkordb/bin/falkordb.so
=== REDIS BUG REPORT END. ===
```

The same data loads cleanly from RDB. Compose therefore uses
`--appendonly no --save 5 1` with the named volume at
`/var/lib/falkordb/data`. Verified:

* `docker compose restart falkordb` -> nodes still readable (T01).
* `docker compose stop falkordb` -> `/api/health` reports `"down"`, graph routes
  return 503; `start` -> health `"ok"`.
* RDB load after restart produced zero bug reports.

Trade-off: up to ~5 seconds of writes can be lost on an unclean kill. Acceptable
for a demo workspace; a production deployment would revisit AOF once the module
bug is fixed upstream or the pinned version is upgraded.

## D3. Lazy FalkorDB client construction

`falkordb.asyncio.FalkorDB(...)` performs a synchronous `INFO` probe inside its
constructor (`Is_Cluster`). Constructing it eagerly crashes the API at startup
when the store is down and defeats the "health says down, routes say 503"
behaviour. `GraphClient._connection()` builds it on first use and converts
connection errors into `GraphUnavailable`.

## D4. Build the API image with `docker buildx build`, not `compose build`

Docker 29 + buildx 0.37 runs compose's bake definitions in a sandbox that refused
to read `backend\Dockerfile`:

```
additional privileges requested: pass "--allow=fs.read=backend\\Dockerfile"
```

A direct `docker buildx build ./backend` works, so `make image` (and
`make up`/`make dev`) build that way and bring the stack up with `--no-build`.
`docker compose up -d` then reuses the tagged image.

## D5. Demo auth is a static token file

`demo_data/tokens.json` maps bearer tokens to `{workspace_id, agent_id, role}`.
Tokens are compared with `hmac.compare_digest`. No identity provider, no cookie
session, no way for a request body to choose a workspace. This is intentional for
the hackathon; the dependency boundary (`get_principal`) is the seam where real
auth would plug in.

## D6. Demo data lives in JSON, not Python literals

`demo_data/atlas_release_lab.json` and `orbit_ops.json` are the single source of
the static base and of the per-source extraction fixtures used by fixture mode.
`app.memory.demo_data` validates the files on load: every fixture keys a declared
source, every claim names a declared concept and episode, every `content_hash` is
`sha256:<64 hex>` over the source excerpt. A typo fails at seed time instead of
producing a half-seeded graph. The `scripts/generate_demo_data.py` generator
keeps the two workspaces structurally identical, so T06 can use the same concept
ids in both graphs.

Only the static base is seeded. Memories are created by the scenario runner so
the demo shows candidates, conflicts and supersessions happening live.

## D7. Nodes are identified by their domain `id`

FalkorDB nodes carry a store-internal id (`24`, ...). `_plain()` normalises every
node to `{id: properties.id, labels, properties}` so `GraphNode.id`, the API's
`root_id`, and the `a.id IN $ids` edge lookup all refer to the same identifier.
Without this the projection returned real nodes and silently zero edges. Caught
by executing the catalogue (`test_repo_queries.py`), not by compiling it.

## D8. Missing graphs are "absent", not errors

`workspace_present` and `graph_node_count` return `False`/`0` when the graph key
does not exist. FalkorDB answers `Invalid graph operation on empty key` to any
statement on a missing graph, which would turn a legitimate "not seeded yet"
check into a 502. Verified via `client.graph_exists()` in
`test_repo_queries.py`.
