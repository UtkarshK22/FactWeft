# Architecture

## System Overview

FactWeft is a **governable shared agent memory** system where multiple agents can propose claims, evaluate conflicts, supersede lower-authority memories, and maintain audit trails via deterministic Cypher-driven resolution. The entire system is graph-native: state transitions, conflict resolution, handoff receipts, and provenance are all expressed as Cypher queries against a FalkorDB graph.

## Architectural Layers

### 1. Database Layer — FalkorDB

- **Graph database** storing all memories, agents, concepts, sources, decisions, and handoff receipts.
- **Per-workspace isolation:** Each `workspace_id` has its own graph. Routes resolve the graph name via `graph_name_for_workspace(workspace_id)` and verify the `Workspace` node exists (`Q_WORKSPACE_PRESENT`).
- **No local cache or fallback:** If FalkorDB is unavailable, the API returns 503 and does not serve memory data from a local copy. This is enforced by the `GraphUnavailable` exception handler in `app/core/errors.py` and the `get_graph_client` dependency in `app/api/deps.py`.
- **Verified-on-this-version notes:** The query catalogue was compiled and executed against FalkorDB v4.22.1; certain constructs (e.g., `EXISTS { ... }` with parameterized variable-length bounds) are known to fail in that version and are worked around with `OPTIONAL MATCH` + validated templates.

### 2. API Layer — FastAPI

- **Route modules** under `backend/app/api/routes/`:
  - `health.py` — `GET /api/health`; FalkorDB liveness check
  - `me.py` — `GET /api/me`; principal identity + derived graph name
  - `memories.py` — `GET /api/memories/{id}`; one memory with provenance
  - `trace.py` — `GET /api/trace`; recent query telemetry
  - `graph.py` — `GET /api/graph/neighborhood`; bounded projection for Cytoscape.js
  - `disputes.py` — `GET /api/disputes`, `GET /api/disputes/compare`; side-by-side claim comparison
  - `handoffs.py` — `POST /api/handoffs`, `GET /api/handoffs`, `GET /api/handoffs/{id}`, `GET /api/handoffs/diff`; receipt creation + diff
  - `demo.py` — `POST /api/demo/seed`, `POST /api/demo/reset`; workspace management
  - `memory.py` — `POST /api/memories/propose`, `POST /api/memories/{id}/review`; full lifecycle

- **Authentication:** Bearer token injected via `Authorization: Bearer <token>` header. Token sourced from localStorage on init or agent switcher. 401 clears stale token.

- **Error handling:** Structured error bodies with `error`, `message`, `detail`, `request_id` (X-Request-ID header). Specific codes: 401 (auth required), 404 (not found), 422 (unprocessable claim), 409 (stale revision), 503 (graph unavailable).

### 3. Repository Layer — `app/graph/repo.py`

- **Thin wrapper** over the Cypher catalogue (`app/graph/queries.py`).
- **One function per query**; raw rows never leave this module. Callers receive Pydantic models from `app/models/graph`.
- **No caching, mirroring, or local reconstruction** — every function is a round trip to FalkorDB.
- **`GraphUnavailable` failure propagates untouched** so the API can answer 503.

### 4. Service Layer — `app/memory/lifecycle.py` + `app/memory/conflicts.py`

- **Deterministic resolution code** + Cypher. No LLM involvement in state transitions.
- **Memory lifecycle:** propose → candidate → (conflict/hold/supersede/promote) → active/rejected.
- **Review actions:** supersede (compare-and-set on revision; 409 on stale), reject, keep_contested, coexist (both cardinality `many`).
- **Conflict rules** (from `conflicts.py`):
  - **Supersede** wins when new memory has higher authority AND valid_from >= old valid_until (or old has valid_until set).
  - **Contested** holds when two active memories share the same predicate + different object_values + cardinality `one`.
  - **Corroboration** when same predicate + same object_value → add SUPPORTED_BY, do NOT create candidate.
  - **Scope denial** at read time: `scope=agent_only` + proposed_by != receiver → excluded; `scope=handoff` + no SHARED_WITH edge → excluded.

### 5. Frontend Layer — React + Vite + Tailwind + Zustand

- **Components** under `frontend/src/components/`:
  - 19 total: `AgentAvatar`, `AskView`, `AuthorityMeter`, `CypherCodeBlock`, `EmptyState`, `ErrorState`, `InspectorDrawer`, `KeyboardShortcuts`, `LeftRail`, `MainCanvas`, `QueryTraceDrawer`, `ScopeChip`, `StatusBadge`, `Toast`, `TopBar`, `graph/Constellation.tsx`, `memory/Inspector.tsx`, `timeline/MemoryRiver.tsx`, `dispute/DisputeDesk.tsx` (new), `handoff/HandoffCapsule.tsx` (new), `ask/AskPanel.tsx` (new), `trace/QueryTrace.tsx` (new)
- **State:** Zustand store (`store/useStore.ts`) with persistence to localStorage; fields: `panel` (selectedMemoryId, selectedHandoffId, asOfMs, filters), `view`, `llmMode`, `agent`, `toasts`.
- **Routing:** View dispatch in `App.tsx` — constellation/river/disputes/handoffs/ask; new views render as overlays.
- **Graph:** Cytoscape.js + fcose layout (`graph/Constance.tsx`); D3.svg horizontal river timeline (`timeline/MemoryRiver.tsx`).
- **Design:** Calm dark 'mission control' aesthetic; graphite `#0B0F1A`; surface `#111827` at 70% with backdrop-blur; restrained neon accents: teal `#2DD4BF`, amber `#F59E0B`, rose `#F43F5E`, violet `#8B5CF6`; radius 14px panels; 10px controls; `prefers-reduced-motion` media query honored.

### 6. Client Layer — Browser

- **TanStack React Query** for data fetching (health, me, memories, timeline, disputes, handoffs, trace).
- **Bearer token** automatic injection from agent switcher; 401 cleanup.
- **Reduced-motion** honoring via `@media (prefers-reduce-motion: reduce)`.
- **Responsive** down to 900px width.

## Data Flow: Propose a Memory

1. **Frontend** sends `POST /api/memories/propose` with claim details.
2. **Route** (`app/memory/lifecycle.py::propose_memory`) validates Q1: workspace/agent/source/concept exist (zero rows → 422 with missing-reference detail).
3. **Q3** finds active memories contradicting the candidate on same predicate+value.
4. **Resolver logic** in Python:
   - If conflict → `Q_HOLD_CANDIDATE` → status=`contested` + CONTRADICTS edge.
   - If supersede → `Q6_SUPERSEDE` (compare-and-set on revision; 409 if stale) → old → `superseded`, new → `active`.
   - If corroboration (same value) → no candidate written; existing memory gets SUPPORTED_BY link.
   - If no conflict/no corroboration → `Q_PROMOTE_CANDIDATE` → status=`active`.
5. **Decision node** written on every transition via `Q_DECISION_WRITE`.
6. **Handoff SHARED_WITH edges** created if `scope=handoff` + `shared_with` non-empty (`Q1D_SHARE_MEMORY`).
7. **Frontend** receives `{memory_id, status, outcome, decision_id, conflicts[]}` and updates Zustand + graph UI.

## Data Flow: Review Action (supersede/reject/keep_contested/coexist)

1. **Frontend** sends `POST /api/memories/{id}/review` with `action`, `reason_code`.
2. **Route** validates the action and revision state.
3. **Corresponding Cypher query** executes (Q6_SUPERSEDE, Q_REVIEW_REJECT, Q_REVIEW_COEXIST, Q_REVIEW_KEEP_CONTESTED).
4. **Decision node** written via `Q_DECISION_WRITE`.
5. **Frontend** receives updated memory state; Zustand stores new status; graph UI updates (ribbon colors, badges, CONTRADICTS edge highlighting).

## Data Flow: Handoff Creation

1. **Frontend** sends `POST /api/handoffs` with task, scope, shared_with, included/excluded memories + reason codes.
2. **Route** (`app/handoffs.py::handoff_create`) runs Q_HANDOFF_CREATE (handoff node + sender/receiver/workspace links), Q_HANDOFF_INCLUDE (UNWIND memory_ids → INCLUDES), Q_HANDOFF_EXCLUDE (UNWIND excluded maps → EXCLUDES with reason_code).
3. **Receipt** returned with `handoff_id`, `included_memories`, `excluded_memories` (each with `memory_id`, `reason_code`, and `summary` — `null` when `reason_code = scope_denied`).
4. **Frontend** `HandoffCapsule` component displays the capsule card, tabs, proof path mini-graph, diff picker, and Export JSON.

## Data Flow: Timeline

1. **Frontend** sends `GET /api/timeline?as_of_ms=<timestamp>`.
2. **Query** `Q_TIMELINE_EVENTS` returns UNION of memory proposals + decisions, sorted by `at_ms`.
3. **`as_of_ms` filter:** WHERE clauses clamp to `created_at <= as_of_ms` / `decided_at <= as_of_ms` / `created_at <= as_of_ms`; items created after the playhead are hidden; status computed with as-of rules (valid_until check, superseded_at check).
4. **Frontend** `MemoryRiver` component renders swimlanes with ribbons, playhead, brush/zoom, and handoff markers.

## Failure Modes & Fallbacks

| Failure | Response | Code |
|---|---|---|
| FalkorDB unreachable | 503 + "FalkorDB is unavailable. FactWeft does not serve memory data from a local copy; retry once the graph is back." | 503 |
| Invalid/missing bearer token | 401; token cleared from localStorage | 401 |
| Stale revision on review | 409 + current revision detail; caller can retry once | 409 |
| Missing workspace/agent/source/concept | 422 + `{"error":"missing_reference","message":"Could not propose memory — one of workspace/agent/source/concept not found"}` | 422 |
| Unknown review action | 400 + "Unknown review action: {action}" | 400 |
| CORS mismatch | 403 (handled by FastAPI CORS middleware) | 403 |
| Graph schema violation (e.g., missing constraint) | 503 (wrapped by `GraphUnavailable`) | 503 |

## Per-Workspace Isolation (Proof)

Every route begins by:
1. Resolving `graph_name_for_workspace(workspace_id)` from `app/graph/names.py`.
2. Verifying the `Workspace` node exists via `Q_WORKSPACE_PRESENT` (returns 404 if absent).
3. All Memory queries are gated by `MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(m:Memory {id: $memory_id})`.
4. If the workspace does not own the memory, the query returns zero rows → the route raises `HTTPException(404, ...)`.

This means a memory in workspace A is indistinguishable from a missing memory in workspace B. There is no cross-workspace query that returns data from another workspace.

## Deployment Architecture

### Local (Docker Compose, guaranteed baseline)

```
+----------------------+       +----------------------+
|   Frontend (Vite)    | <-->  |   Backend (FastAPI)  |
|   http://localhost:  |       |   http://localhost:  |
|   5173/5174          |       |   8000               |
+----------+-----------+       +----------+-----------+
           |                             |
           v                             v
+----------------------+       +----------------------+
|    FalkorDB          |       |    Redis (optional)  |
|   graph database     |       |   (session state)    |
|   port 9142          |       |   port 6379          |
+----------------------+       +----------------------+
```

### Optional Live Deploy

- **Frontend:** Vercel / Netlify / Cloudflare Pages (static serve from `frontend/dist`)
- **API:** Render / Fly / Railway (Python FastAPI)
- **FalkorDB:** FalkorDB Cloud or a small VM with auth enabled; port **NOT** publicly open; access via internal network only
- **CORS:** `ALLOWED_ORIGINS` set to deployed frontend URL
- **Token:** Environment variable `FAULKORDB_TOKEN` or bearer token from auth service
- **Free tiers:** May cold-start; the demo should warm up first (`curl /api/health` before use)

### Fallback: Tunnel if Deployment Fails

- **Cloudflare Tunnel** or **ngrok** to expose local stack
- **CORS:** Must allow `http://localhost:5173` and `http://localhost:5174` (or deployed URL)
- **Token:** Bearer token from localStorage; no changes needed if same origin
- **FalkorDB:** Must be reachable from the tunnel's public URL; if FalkorDB is local (docker compose), ensure port 9142 is not publicly open — use tunnel only for frontend+API, keep FalkorDB internal

## Environment Variables (Full List)

**Backend (`backend/.env`):**
```
DEMO_WORKSPACE_ID=demo_atlas_release_lab
SECOND_WORKSPACE_ID=demo_orbit_ops
FAULKORDB_ENDPOINT=falkordb:9142
FAULKORDB_USER=falkordb
FAULKORDB_PASSWORD=password
SECRET_KEY=change-this-in-production
API_PREFIX=/api
CORS_ORIGINS=http://localhost:5173,http://localhost:5174
DEMO_MODE=true
LLM_MODE=fixture
```

**Frontend (`frontend/.env`):**
```
VITE_API_PREFIX=/api
VITE_DEMO_WORKSPACE_ID=demo_atlas_release_lab
```

**Live Deploy Overrides:**
- `FAULKORDB_ENDPOINT` → FalkorDB Cloud hostname + port (auth enabled)
- `CORS_ORIGINS` → deployed frontend URL (e.g. `https://my-app.vercel.app`)
- `DEMO_MODE` → `false` when LLM mode is live
- `LLM_MODE` → `live` when actual LLM provider is configured
- API `SECRET_KEY` → production secret
- Frontend `VITE_API_PREFIX` → `/api` (same) or custom prefix

## Verified Cypher Catalogue (Summary)

All queries from `app/graph/queries.py` with one-line explanations:

- **Schema:** `SCHEMA_LIST_INDEXES`, `SCHEMA_LIST_CONSTRAINTS`, `SCHEMA_CREATE_INDEX`
- **Workspace/Agent:** `Q_WORKSPACE_PRESENT`, `Q_MERGE_WORKSPACE`, `Q_MERGE_AGENT`
- **Seeding:** `Q_SEED_CONCEPT`, `Q_SEED_SOURCE`, `Q_SEED_SESSION`, `Q_SEED_EPISODE`, `Q_SEED_PROCEDURE`, `Q_SEED_STEP`
- **Core reads:** `Q_MEMORY_BY_ID`, `Q_TIMELINE_EVENTS`, `Q_DISPUTES_LIST`, `Q_ELIGIBLE_MEMORIES`, `Q_INELIGIBLE_MEMORIES`, `Q_READINESS`, `Q_WHY_SOURCES`, `Q_WHY_SUPERSEDES`, `Q_WHY_DECISIONS`, `Q_WHY_HANDOFFS`, `Q3_FIND_CONFLICTS`, `Q3B_FIND_CORROBORATION`
- **Writes:** `Q1_PROPOSE_MEMORY`, `Q1B_LINK_EPISODE`, `Q1C_SET_VALID_UNTIL`, `Q1D_SHARE_MEMORY`, `Q6_SUPERSEDE`, `Q_PROMOTE_CANDIDATE`, `Q_HOLD_CANDIDATE`, `Q_HANDOFF_CREATE`, `Q_HANDOFF_INCLUDE`, `Q_HANDOFF_EXCLUDE`, `Q_DECISION_WRITE`, `Q_REVIEW_REJECT`, `Q_REVIEW_COEXIST`, `Q_REVIEW_KEEP_CONTESTED`
- **Q-neighbourhood:** `Q_NEIGHBORHOOD_ROOT`, `Q_NEIGHBORHOOD_NODES`, `Q_NEIGHBORHOOD_TOTAL`, `Q_NEIGHBORHOOD_EDGES`

## AI Coding-Assistant Disclosure

> [This section to be filled by the submitter]
> 
> AI tools used during implementation: [exact tools and versions]
> 
> Prompts that produced critical code: [summarize or paste]
> 
> Human review points: [note any code areas requiring manual verification]

## Team + License

**Team:** [To be filled]

**License:** [Typically MIT or Apache 2.0 for hackathon submissions]

**Copyright:** Copyright (c) 2025 FactWeft Contributors