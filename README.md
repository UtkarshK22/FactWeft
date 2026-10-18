# FactWeft

Graph-native memory coordination for multi-agent teams — built for the
WeMakeDevs x FalkorDB **Graph Hacks** hackathon, Track 02 (Agent Memory and
Coordination).

Claims have lineage, conflicts are first-class, and every agent-to-agent handoff
carries a receipt of what was included, excluded and why. FalkorDB is the only
memory store: remove it and recall, conflict detection, supersession, scope gating,
handoff assembly and provenance all stop.

> **Status: scaffold.** Verified so far: pinned FalkorDB + persistent volume,
> health/auth, idempotent schema (indexes + unique ids), the full Cypher
> catalogue (compile-checked), the trace ring buffer, 503-on-outage and T01
> persistence. Resolver, retrieval and receipts are the next milestones; their
> queries and decision primitives already exist and are tested.

## Quickstart

Requires Docker (Compose v2). Python runs in the container (3.12); no host venv
needed for the app.

```bash
cp .env.example .env

make up        # build the API image + start FalkorDB and the API
make seed      # idempotent schema + static demo base (no memories)
curl http://localhost:8000/api/health
```

On Windows without GNU make, use the bundled wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/make.ps1 up
powershell -ExecutionPolicy Bypass -File scripts/make.ps1 seed
powershell -ExecutionPolicy Bypass -File scripts/make.ps1 health
```

Once the image exists, the plain `docker compose up -d` from the DoD also works.

### Expected output

```
$ make up
docker buildx build ./backend -t factweft-api:latest --load
...
 Container factweft-falkordb Started
 Container factweft-falkordb Waiting
 Container factweft-falkordb Healthy
 Container factweft-api Started

$ make seed
{"counts": {"agents": 5, "concepts": 5, "episodes": 4, "procedures": 1, "sessions": 3, "sources": 4, "steps": 2}, "graph_name": "ws_demo_atlas_release_lab", "procedure_ids": ["mem_atlas_release_readiness"], "schema": {"constraints_created": [], "constraints_pending": [], "constraints_total": 10, "indexes_created": [], "indexes_total": 13}, "workspace_id": "demo_atlas_release_lab"}
{"counts": {"agents": 5, "concepts": 4, "episodes": 2, "procedures": 1, "sessions": 2, "sources": 2, "steps": 2}, ... "graph_name": "ws_demo_orbit_ops" ...}

$ curl -s http://localhost:8000/api/health
{"api":"ok","falkordb":"ok","graph_seeded":true,"llm_mode":"fixture"}
```

The seed writes only the static base (workspace, agents, concepts with aliases,
sources with authority + `sha256:` content hash, sessions, episodes, and the
readiness procedure with its steps) from `demo_data/atlas_release_lab.json` and
`demo_data/orbit_ops.json` — including the extraction fixtures keyed by source
id, the injection source and the rumour source. Memories are deliberately left
to the scenario runner so the demo shows them being created live.

Running `make seed` again prints empty `indexes_created` / `constraints_created`
lists and identical counts — it really is idempotent.

## URLs

| Service | URL |
| --- | --- |
| API health | http://localhost:8000/api/health |
| API docs (OpenAPI) | http://localhost:8000/docs |
| Bounded graph projection | `GET /api/graph/neighborhood?memory_id=...&hops=1..2&max_nodes=...` |
| FalkorDB Browser | http://localhost:3000 |
| FalkorDB protocol | `localhost:6379` (password: `FALKORDB_PASSWORD`, default `factweft_dev_pw`) |

## API surface

| Endpoint | Auth | Purpose |
| --- | --- | --- |
| `GET /api/health` | public | liveness + FalkorDB ping + `graph_seeded` |
| `GET /api/me` | any token | principal and its server-derived graph |
| `GET /api/memories/{id}` | any token | one memory, scoped to the caller's workspace |
| `GET /api/graph/neighborhood` | any token | bounded projection (`hops` 1–2, `max_nodes`, filters, `as_of_ms`, `truncated`) |
| `GET /api/trace` | coordinator+ | redacted, bounded query trace |
| `POST /api/demo/seed` | owner + `DEMO_MODE` | idempotent static-base seed for the caller's workspace |
| `POST /api/demo/reset` | owner + `DEMO_MODE` | drop the caller's graph and recreate an empty schema |

### Opening the FalkorDB Browser

The `falkordb/falkordb:v4.22.1` image ships the Browser on port 3000. Open
http://localhost:3000, connect with host `falkordb`, port `6379`, password from
`.env`, then pick `ws_demo_atlas_release_lab` in the graph list. Useful checks:

```cypher
MATCH (w:Workspace) RETURN w.id, w.display_name;
CALL db.indexes();
CALL db.constraints();
```

`docker compose logs falkordb` shows the Browser's connection banner at startup.

## Commands

| Make target | PowerShell wrapper | What it does |
| --- | --- | --- |
| `make up` | `... make.ps1 up` | build the image, start FalkorDB + API |
| `make dev` | `... make.ps1 dev` | same, prints URLs; API runs `uvicorn --reload` on the mounted source |
| `make seed` | `... make.ps1 seed` | schema + demo workspace/agent nodes (idempotent) |
| `make test` | `... make.ps1 test` | unit + integration tests in the API container |
| `make test-restart` | `... make.ps1 test-restart` | T01 persistence test from the host (restarts FalkorDB) |
| `make lint` / `make fmt` | `... make.ps1 lint` / `fmt` | ruff check / format |
| `make logs` / `make ps` | `... make.ps1 logs` / `ps` | inspect the stack |
| `make down` / `make clean` | `... make.ps1 down` / `clean` | stop / stop and delete the volume |

T01 needs the host's Docker CLI, so run it from the host once:

```bash
cd backend
python -m venv .venv && ./.venv/Scripts/python -m pip install -r requirements-dev.txt   # Windows
python -m pytest -q -m docker_control
# 1 passed, 51 deselected
```

Inside the container it skips with an explicit reason rather than pretending.

## Tests

`make test` reports **51 passed, 1 skipped** (the skip is T01, see above). Suites:

* `tests/unit` — graph-name guard, settings, token registry/roles, trace buffer,
  redaction, unreachable-store behaviour.
* `tests/integration/test_schema.py` — indexes + UNIQUE(id), idempotency,
  duplicate rejection.
* `tests/integration/test_roundtrip.py` — write/read through `GraphClient`,
  `ro_query` enforcement, trace contents.
* `tests/integration/test_query_catalogue.py` — EXPLAINs every catalogue
  statement against the pinned image.
* `tests/integration/test_api.py` — health, 401/403/404, trace roles, and
  503 when FalkorDB is unreachable.
* `tests/integration/test_persistence.py` — T01 restart persistence.

Every integration test uses its own `ws_test_<random>` graph and deletes it
afterwards.

## Failure behaviour

With FalkorDB stopped:

```
$ curl -s http://localhost:8000/api/health
{"api":"ok","falkordb":"down","graph_seeded":false,"llm_mode":"fixture"}

$ curl -s -H "Authorization: Bearer tok_atlas_scout_7c1f9a" \
       http://localhost:8000/api/memories/whatever
{"error":"graph_unavailable","message":"FalkorDB is unavailable. FactWeft does not serve memory data from a local copy; retry once the graph is back.","request_id":"req_..."}
# HTTP 503
```

There is no degraded mode and no local copy to fall back to.

## Layout

```
.
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml            # pytest + ruff config
│   ├── requirements.txt / requirements-dev.txt
│   ├── app/
│   │   ├── main.py               # app factory, CORS, request ids, error handlers
│   │   ├── api/
│   │   │   ├── deps.py           # graph client / settings dependencies
│   │   │   └── routes/           # health, me, memories, trace, demo, graph
│   │   ├── core/                 # config, auth, errors, clock, constants
│   │   ├── graph/
│   │   │   ├── connection.py     # GraphClient, tracing, GraphUnavailable
│   │   │   ├── queries.py        # 39 named Cypher statements, documented
│   │   │   ├── repo.py           # typed wrappers returning Pydantic models
│   │   │   ├── bootstrap.py      # ensure_schema + seed CLI
│   │   │   └── names.py          # graph-name derivation/validation
│   │   ├── memory/               # demo data loader + seed/reset
│   │   ├── agents/               # agent roles (next)
│   │   ├── llm/                  # fixture/live adapter (next)
│   │   └── models/               # domain enums, API models
│   └── tests/{unit,integration}/
├── demo_data/
│   ├── tokens.json              # synthetic demo principals (both workspaces)
│   ├── atlas_release_lab.json   # static base + extraction fixtures (injection, rumour)
│   └── orbit_ops.json           # second workspace, same schema, distinct claims
├── docs/{architecture,decisions}.md
├── frontend/                     # React + TS + Vite (next)
├── scripts/make.ps1              # Windows wrapper for the Makefile
├── docker-compose.yml            # pinned FalkorDB + API + named volume
├── Makefile
├── .env.example
└── LICENSE (MIT)
```

## Guarantees in the scaffold

* **Server-derived graph names.** `ws_<workspace_id>` comes from the bearer
  token and is validated against `^[a-z0-9_]{3,40}$` before any call. Request
  bodies never carry a workspace or a receiver id.
* **Parameterized Cypher.** Values are bound via the client's `CYPHER` params
  header; the only formatted identifiers are index labels/properties drawn from
  a fixed allowlist.
* **Structured errors.** `{error, message, request_id}` with `X-Request-ID`
  echoed on every response.
* **Trace telemetry is bounded.** A `deque(maxlen=TRACE_BUFFER_SIZE)` of query
  metadata; params redacted and strings truncated. No memory data is cached.
* **Synthetic data only.** Tokens, workspaces and (soon) claims are fictional.

## Durability note

Compose pins `falkordb/falkordb:v4.22.1` and uses **RDB snapshots**
(`--appendonly no --save 5 1`) with a named volume at
`/var/lib/falkordb/data`. AOF was disabled deliberately: replaying `GRAPH.EFFECT`
entries from the AOF crashes v4.22.1 during startup. Evidence and trade-offs are
in [docs/decisions.md](docs/decisions.md#d2-rdb-snapshots-instead-of-aof).

## License

MIT — see [LICENSE](LICENSE).
