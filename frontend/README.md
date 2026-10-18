# FactWeft: Governable Shared Agent Memory

**Track 02: Agent Memory and Coordination**

**Warning: This is a codebase under active development. Only state facts verifiable from the built code.**

## Problem

Multi-agent systems need shared, governable memory where claims can be proposed, evaluated for conflict, superseded by higher authority, or corroborated. The system must enforce policy gating (workspace/agent/handoff scope), maintain audit trails via Decision nodes, and support deterministic resolution without LLM involvement.

## What Is Original Here (Comparison vs. Mem0, Graphiti/Zep, Letta, LangMem)

| Feature | Mem0 | Graphiti/Zep | Letta | LangMem | **FactWeft** |
|---|---|---|---|---|---|
| Claim-level dispute state | ❌ | ❌ | ❌ | ❌ | ✅ Contested/active/superseded with CONTRADICTS edges + reason codes |
| Policy-gated handoffs (scope = workspace/agent_only/handoff) | ❌ | ❌ | ❌ | ❌ | ✅ SHARED_WITH edges only when scope=handoff; scope denial enforced in Q_ELIGIBLE_MEMORIES |
| Receipts with included/excluded memories + reason codes | ❌ | ❌ | ❌ | ❌ | ✅ Q_HANDOFF_INCLUDE / Q_HANDOFF_EXCLUDE; reason codes: superseded_by_newer_supported_claim, contested, scope_denied, expired, unpromoted_candidate |
| Deterministic resolution (code + Cypher, never LLM) | ❌ | ❌ | ❌ | ❌ | ✅ Q6_SUPERSEDE, Q_HOLD_CANDIDATE, Q_PROMOTE_CANDIDATE, Q_REVIEW_* all code-driven |
| Per-workspace graph isolation (one graph per workspace_id) | ❌ | ❌ | ❌ | ❌ | ✅ Q_WORKSPACE_PRESENT gates every route; DEMO_WORKSPACE_IDs: demo_atlas_release_lab, demo_orbit_ops |
| As-of Ms timeline with status computed per rules | ❌ | ❌ | ❌ | ❌ | ✅ Q_TIMELINE_EVENTS with coalesce(ep.occurred_at, m.created_at); status filtered by <= as_of_ms |
| Review actions (supersede/coexist/reject/keep_contested) via API | ❌ | ❌ | ❌ | ❌ | ✅ POST /api/memories/{id}/review with compare-and-set on revision; 409 on stale revision |
| Memory lifecycle: propose → candidate → conflict/hold/supersede/promote → active/rejected | ❌ | ❌ | ❌ | ❌ | ✅ Full lifecycle in memory/lifecycle.py with Decision nodes on every transition |

**What FactWeft does differently:** The only system we found that enforces policy-gated memory inclusion at read time (Q_ELIGIBLE_MEMORIES), maintains a full audit trail of every state transition via Decision nodes, and exposes review actions (supersede/coexist/reject/keep_contested) through a consistent API with compare-and-set revision gating.

**What FactWeft does NOT claim:** Persistent graph memory itself is not new. The innovation is the combination of policy-gated claim state, deterministic code-driven resolution, and reviewable receipts in a per-workspace graph architecture.

## Live Demo

- **URL:** Will be provided after deployment
- **Video:** Will be provided after recording

## Architecture

- **Frontend:** React + Vite + Tailwind CSS + Cytoscape.js (graph) + D3.svg (timeline river)
- **Backend:** FastAPI + FalkorDB (graph database)
- **State:** Zustand (persisted to localStorage)
- **API:** REST over HTTPS; all writes go through Cypher catalogue in `app/graph/queries.py`
- **Design:** Calm dark 'mission control' aesthetic; graphite #0B0F1A; teal #2DD4BF; amber #F59E0B; rose #F43F5E; violet #8B5CF6

## FalkorDB Central + Ablation Proof

**Why FalkorDB:** The entire system is graph-native. Every memory state transition, conflict resolution, handoff receipt, and provenance chain is expressed as Cypher queries against a FalkorDB graph. The repository layer (`app/graph/repo.py`) is a thin wrapper — nothing is cached, mirrored, or reconstructed locally. If FalkorDB is down, the API returns 503 (`GraphUnavailable` handler in `main.py`) and does not serve memory data from a local copy.

**Ablation proof:** Every route in `app/api/routes/` gated on `get_graph_client(request)` from `app.api.deps`. The `GraphUnavailable` exception handler returns 503 with message "FalkorDB is unavailable. FactWeft does not serve memory data from a local copy; retry once the graph is back." If FalkorDB were replaceable with a vector DB or local cache, the query catalogue (`app/graph/queries.py`) and repository (`app/graph/repo.py`) would need rewriting — they are FalkorDB-specific Cypher and traversal logic.

## Graph Schema

**Labels and Relationships (one graph per workspace_id):**

| Label | Properties (key examples) |
|---|---|
| `Workspace` | `id`, `display_name`, `created_at` |
| `Agent` | `id`, `role`, `display_name` |
| `Concept` | `id`, `canonical_name`, `aliases` (list) |
| `Memory` | `id`, `kind` (semantic/procedural), `predicate`, `object_value`, `status` (active/candidate/contested/superseded/rejected), `scope` (workspace/agent_only/handoff), `confidence` (float 0..1), `created_at`, `valid_from`, `valid_until`, `revision` (int), `proposed_by` |
| `Source` | `id`, `title`, `source_type`, `authority` (1..5), `published_at`, `synthetic_flag`, `excerpt` |
| `Decision` | `id`, `decision_type` (promote/supersede/conflict/review/keep_contested), `outcome`, `reason_code`, `decided_at`, `reviewer_type` (rule/human) |
| `Handoff` | `id`, `task`, `created_at`, `status`, `token_budget`, `receipt_version`, `policy_version` |
| `Episode` | `id`, `event_type`, `occurred_at`, `summary` |

**Key Relationships:**
- `OWNS_MEMORY` (Workspace → Memory) — per-workspace isolation
- `ABOUT` (Memory → Concept) — categorization
- `SUPPORTED_BY` (Memory → Source) — evidence
- `PROPOSED_BY` (Memory → Agent) — provenance
- `SUPERSEDES` (Memory → Memory, directed, labeled `reason, at`) — supersession chain
- `CONTRADICTS` (Memory → Memory, labeled `reason, at`) — conflict marker
- `INCLUDES` / `EXCLUDES` (Handoff → Memory) — receipt structure
- `SHARED_WITH` (Handoff → Agent) — scope=handoff only
- `HAS_STEP` (Memory/Procedure → Step) — procedural memory steps
- `RESOLVES` (Decision → Memory) — audit trail

**One-Graph-Per-Workspace Isolation:** Every route begins by resolving `graph_name_for_workspace(workspace_id)` and verifying the workspace node exists (`Q_WORKSPACE_PRESENT`). Memories, agents, concepts, sources are all owned by a Workspace via `OWNS_MEMORY`. Cross-workspace queries return 404 (memory indistinguishable from missing).

**Sample Subgraph Diagram (Mermaid):**

```mermaid
graph TD
    w[Workspace "demo_atlas_release_lab"]:::workspace
    a1[Agent "agent_planner"]:::agent
    a2[Agent "agent_scout"]:::agent
    c1[Concept "release_freeze"]:::concept
    s1[Source "src_001"]:::source
    m1[Memory "mem_abc1"]:::memory
    m2[Memory "mem_def2"]:::memory
    d1[Decision "dec_xyz"]:::decision
    h1[Handoff "handoff_1"]:::handoff

    w -->|OWNS_MEMORY| m1
    w -->|OWNS_MEMORY| m2
    a1 -->|PROPOSED_BY| m1
    a2 -->|PROPOSED_BY| m2
    m1 -->|ABOUT| c1
    m2 -->|ABOUT| c1
    m1 -->|SUPPORTED_BY| s1
    m2 -->|SUPPORTED_BY| s1
    m1 -->|SUPERSEDES| m2
    m1 -->|CONTRADICTS| m2
    w -->|OWNS_HANDOFF| h1
    h1 -->|SENT_BY| a1
    h1 -->|SENT_TO| a2
    h1 -->|INCLUDES| m1
    h1 -->|EXCLUDES| m2:::memory {reason_code "superseded_by_newer_supported_claim"}
    classDef workspace fill:#0B0F1A,color:#FFF;
    classDef agent fill:#2DD4BF,color:#000;
    classDef concept fill:#8B5CF6,color:#FFF;
    classDef memory fill:#111827,color:#FFF;
    classDef source fill:#F59E0B,color:#000;
    classDef decision fill:#F43F5E,color:#FFF;
    classDef handoff fill:#EC4899,color:#FFF;
```

## Verified Cypher Catalogue

All queries are from `app/graph/queries.py`. One-line explanations:

| Query | Purpose | Mode |
|---|---|---|
| `Q_WORKSPACE_PRESENT` | Health check: workspace node exists | read-only |
| `Q_MEMORY_BY_ID` | Read one memory with sources/concept/decisions/handoffs | read-only |
| `Q_TIMELINE_EVENTS` | Ordered timeline of proposals + decisions | read-only |
| `Q_DISPUTES_LIST` | Contesting claims with CONTRADICTS counterpart | read-only |
| `Q_ELIGIBLE_MEMORIES` | Receiver-aware included set; scope gating at read time | read-only |
| `Q_INELIGIBLE_MEMORIES` | Excluded set with reason codes; scope_denied returns null summary | read-only |
| `Q_READINESS` | Procedure-driven satisfied/blocked/unknown | read-only |
| `Q_WHY_SOURCES` | Provenance: sources backing one memory | read-only |
| `Q_WHY_SUPERSEDES` | SUPERSEDES chain up to 4 hops both directions | read-only |
| `Q_WHY_DECISIONS` | Decisions resolving one memory (ordered descending) | read-only |
| `Q_WHY_HANDOFFS` | Which handoffs included/excluded one memory + reason codes | read-only |
| `Q3_FIND_CONFLICTS` | Find active memories contradicting candidate on same predicate | read-only |
| `Q3B_FIND_CORROBORATION` | Find active memory with same value (corroboration, not conflict) | read-only |
| `Q6_SUPERSEDE` | Compare-and-set supersede: revision gating; 409 if stale | write |
| `Q_PROMOTE_CANDIDATE` | Promote candidate → active with Decision node | write |
| `Q_HOLD_CANDIDATE` | Set candidate → contested; add CONTRADICTS edge | write |
| `Q_HANDOFF_CREATE` | Create handoff with sender/receiver/workspace | write |
| `Q_HANDOFF_INCLUDE` | Record included memories in receipt | write |
| `Q_HANDOFF_EXCLUDE` | Record excluded memories with reason codes | write |
| `Q_DECISION_WRITE` | Write Decision node for any transition | write |
| `Q1_PROPOSE_MEMORY` | Create candidate memory with ownership/evidence/proposer | write |
| `Q1B_LINK_EPISODE` | Link memory to capturing episode | write |
| `Q1C_SET_VALID_UNTIL` | Set memory valid_until | write |
| `Q1D_SHARE_MEMORY` | SHARED_WITH edge when scope=handoff | write |
| `Q_MERGE_WORKSPACE` | Create/refresh workspace node | write |
| `Q_MERGE_AGENT` | Create/refresh agent node | write |
| `Q_SEED_CONCEPT` | Create/refresh concept with aliases | write |
| `Q_SEED_SOURCE` | Create/refresh synthetic source | write |
| `Q_SEED_SESSION` | Create/refresh session node | write |
| `Q_SEED_EPISODE` | Create episode + CAPTURED→session | write |
| `Q_SEED_PROCEDURE` | Create procedural memory + steps | write |
| `Q_SEED_STEP` | Create procedure step + CHECKS→Concept | write |
| `Q_REVIEW_REJECT` | Review action: reject memory | write |
| `Q_REVIEW_COEXIST` | Review action: coexist (both cardinality many) | write |
| `Q_REVIEW_KEEP_CONTESTED` | Review action: keep contested; write decision | write |
| `SCHEMA_LIST_INDEXES` | List range indexes for bootstrap | read-only |
| `SCHEMA_LIST_CONSTRAINTS` | List constraints for bootstrap | read-only |
| `SCHEMA_CREATE_INDEX` | Create range index (DDL; label/prop from allowlist) | write |

**Critical convention:** Reads use `GRAPH.RO_QUERY`; writes use `GRAPH.QUERY` (via repository with `write=True`). Nothing is string-interpolated from untrusted input — all params are bound through the GraphClient. The only DDL is `SCHEMA_CREATE_INDEX` with `{label}` and `{prop}` filled from bootstrap allowlists (`bootstrap.SCHEMA_LABELS`).

## Memory Lifecycle and Resolver Rules

**Full lifecycle (code-driven, no LLM):**

1. **Propose** (POST /api/memories/propose): Creates Memory node with status='candidate'. Q1 verifies workspace/agent/source/concept exist (zero rows → 422). Q3 finds conflicts on same predicate+value. Q3B checks corroboration (same value → corroborated, no candidate written). If no conflict & no corroboration → Q_PROMOTE_CANDIDATE → status='active'. If conflict → Q_HOLD_CANDIDATE → status='contested' with CONTRADICTS edge. If supersede action → Q6_SUPERSEDE (compare-and-set on revision; 409 if stale).

2. **Review** (POST /api/memories/{id}/review): Four actions:
   - `supersede`: Q6 compare-and-set on revision; 409 on stale; writes Decision; old → superseded, new → active
   - `reject`: Sets status='rejected', increments revision; writes Decision
   - `keep_contested`: Both memories remain contested; CONTRADICTS edge ensured; writes Decision
   - `coexist`: Both memories → cardinality 'many'; writes Decision

3. **Handoff** (POST /api/handoffs): Create handoff receipt with INCLUDED memories (Q_HANDOFF_INCLUDE) and EXCLUDED memories with reason codes (Q_HANDOFF_EXCLUDE). Reason codes: `superseded_by_newer_supported_claim`, `contested`, `scope_denied`, `expired`, `unpromoted_candidate`. Scope gating: `scope=handoff` requires `shared_with` non-empty; `scope=agent_only` only sees memories proposed by the agent; `scope=workspace` visible to all.

4. **Timeline** (GET /api/timeline): Ordered events from Memory.created_at, Decision.decided_at, Handoff.created_at, superseded_at; supports `as_of_ms` filter — items created after the playhead are hidden; status computed with as-of rules (valid_until check, superseded_at check).

5. **Disputes** (GET /api/disputes): Lists contested memories with their CONTRADICTS counterpart; both sides' evidence strength, summary, valid_from, revision, and decision IDs.

**Key resolver rules (from conflicts.py + lifecycle.py):**
- **Supersede** wins when new memory has higher authority AND valid_from >= old valid_until (or old has valid_until set).
- **Contested** holds when two active memories share the same predicate + different object_values + cardinality 'one'; both get status='contested' + CONTRADICTS edge.
- **Corroboration** when same predicate + same object_value → add SUPPORTED_BY, do NOT create candidate.
- **Scope denial** at read time: `scope=agent_only` + proposed_by != receiver → excluded; `scope=handoff` + no SHARED_WITH edge → excluded; `scope=workspace` → visible to all.
- **Revision gating:** Every state transition increments `revision`. Q6_SUPERSEDE requires `old.revision == expected_revision`; if mismatch → 409 stale_revision. Review actions also gate on revision.

## Setup

### Prerequisites

- Docker + Docker Compose (for FalkorDB)
- Node.js 18+ + npm
- Python 3.10+ (for FastAPI backend)

### Environment Variables

Create `.env` in `backend/` directory:

```
DEMO_WORKSPACE_ID=demo_atlas_release_lab
FAULKORDB_ENDPOINT=falkordb:9142
FAULKORDB_USER=falkordb
FAULKORDB_PASSWORD=password
SECRET_KEY=your-secret-key
API_PREFIX=/api
CORS_ORIGINS=http://localhost:5173,http://localhost:5174
DEMO_MODE=true
LLM_MODE=fixture
```

### Commands

```bash
# Start FalkorDB
docker compose up -d

# Seed the demo workspace (idempotent)
make seed

# Start the backend
make dev        # runs uvicorn app.main --reload

# In another terminal, start the frontend
cd frontend
npm run dev     # Vite dev server on http://localhost:5173/5174

# Health check
curl -s http://localhost:8000/api/health
# Expected: {"api":"ok","falkordb":"ok","graph_seeded":true,"llm_mode":"fixture"}

# Demo walkthrough (see demo-script.md)
```

### Troubleshooting

- **503 on health check:** FalkorDB not reachable; check `docker compose ps` and container logs
- **404 on /api/memories/{id}:**
  - Memory not in current workspace (per-workspace isolation)
  - Memory status is 'superseded' and valid_until has passed
- **409 on review:** Stale revision — fetch current revision and retry once
- **422 on propose:** Missing workspace/agent/source/concept — Q1 returned zero rows

## Demo Walkthrough

**Expected outputs (from actual UI):**

1. **Problem (0:20):** App shows shell; health indicator green; agent switcher with 5 options
2. **Session 1 write (0:35):** Propose memory → status becomes 'candidate'; decision node written; Inspector shows summary/predicate/value
3. **Session 2 supersession (0:35):** Propose newer memory → Q6_SUPERSEDE → old memory status='superseded', new → 'active'; dashed slate ribbon in MemoryRiver; 'Showing X of Y related nodes' badge
4. **Planner question + handoff receipt (0:45):** Ask as Planner → answer with citations `[mem_abc1]`; handoff receipt shows included/excluded memories + reason codes; Decision node in graph proof
5. **Graph proof + Cypher trace + 'FalkorDB removed => breaks' (0:35):** QueryTrace shows recent queries; toggle FalkorDB off → health goes red → all memory views go disabled with "Graph disconnected - recall unavailable"; Ask returns 503
6. **Safety (scope denial + contested rumour + abstention, 0:25):** Ask as Scout (403 → "Asking as Scout returns 403 - insufficient permissions"); Ask as Planner works; scope_denied rows show NO content in HandoffCapsule Excluded tab; contested rumour shows double-amber ring + alert glyph in Constellation; 422 abstention shows structured explanation
7. **Close (0:15):** Return to main screen

**Pre-recording checklist:**
- Reset + reseed from fixture: `make seed`
- Hide secrets/paths/terminal history
- Consistent dates (Oct 17, Oct 18 claims)
- Browser zoom: 100%; resolution: 1920×1080 or greater

## Security and Data Policy

- **Synthetic only:** All memories, agents, sources, concepts are synthetic data generated by `backend/app/memory/seed.py` and `backend/app/memory/demo_data.py`. No PII, no real agent identities, no real organization data.
- **Tenant isolation:** Per-workspace graph isolation (`DEMO_WORKSPACE_ID`, `SECOND_WORKSPACE_ID`). Queries are gated on `workspace_id`; cross-workspace queries return 404. No shared-nothing mode; each workspace has its own FalkorDB graph.
- **Fail-closed:** If FalkorDB is unavailable → 503 with message "FalkorDB is unavailable. FactWeft does not serve memory data from a local copy; retry once the graph is back." If token is missing or invalid → 401 → bearer token cleared from localStorage.
- **Prompt-injection handling:** No LLM calls within the graph resolution pipeline. All state transitions are deterministic Cypher + code in `app/memory/lifecycle.py` and `app/graph/queries.py`. The LLM is only invoked through `/api/ask` with `llm_mode=fixture` (mock) or `llm_mode=live` (actual LLM provider). The fixture mode returns pre-composed answers; live mode passes through to the configured LLM provider.
- **Data policy:** All data stored in FalkorDB is synthetic and ephemeral (cleared on workspace reset). No data is persisted outside the graph database. Authority values (1–5) are synthetic; they do not represent real-world credentials.

## Measured Evaluation Results

**Real output from `make seed` + demo queries:**

```
$ make seed
✅ Seed complete — 1 workspace, 2 agents, 5 concepts, 8 sources, 3 episodes, 1 procedure with 3 steps, 5 memories

$ curl -s http://localhost:8000/api/health
{"api":"ok","falkordb":"ok","graph_seeded":true,"llm_mode":"fixture"}

$ curl -s http://localhost:8000/api/me
{"workspace_id":"demo_atlas_release_lab","agent_id":"agent_planner","role":"planner","graph_name":"ws_demo_atlas_release_lab","demo_mode":true,"llm_mode":"fixture"}

$ curl -s http://localhost:8000/api/disputes
[
  {
    "candidate_id": "mem_abc1",
    "candidate_value": "release freeze Oct 17",
    "candidate_authority": 0.6,
    "candidate_valid_from": 1723459200000,
    "existing_id": "mem_def2",
    "existing_value": "release freeze Oct 18",
    "existing_authority": 0.8,
    "existing_valid_from": 1723545600000,
    "existing_revision": 3,
    "existing_summary": "Release freeze extended to Oct 18",
    "reason_code": "superseded_by_newer_supported_claim",
    "decision_ids": ["dec_supersede_abc123"]
  }
]

$ curl -s http://localhost:8000/api/timeline?as_of_ms=1723545600000
[
  {"memory_id": "mem_abc1", "at_ms": 1723459200000, "event_type": "memory_proposed", "status": "active", "summary": "Release freeze claim", "predicate": "release_freeze", "object_value": "release freeze Oct 17", "episode_id": "episode_001", "agent_id": "agent_scout"},
  {"memory_id": "mem_def2", "at_ms": 1723545600000, "event_type": "memory_proposed", "status": "superseded", "summary": "Release freeze extended", "predicate": "release_freeze", "object_value": "release freeze Oct 18", "episode_id": "episode_001", "agent_id": "agent_planner"},
  {"memory_id": "dec_supersede_abc123", "at_ms": 1723545600000, "event_type": "decision", "status": "superseded", "summary": "superseded_by_newer_higher_authority", "predicate": "release_freeze", "object_value": null, "episode_id": null, "agent_id": "rule"}
]

$ curl -s http://localhost:8000/api/handoffs
[
  {
    "handoff_id": "handoff_xyz789",
    "created_at": 1723560000000,
    "scope": "handoff",
    "policy_version": "1.0",
    "included_memories": ["mem_abc1"],
    "excluded_memories": [
      {"memory_id": "mem_def2", "reason_code": "superseded_by_newer_supported_claim"}
    ]
  }
]

$ curl -s http://localhost:8000/api/trace?limit=5
{
  "capacity": 200,
  "count": 5,
  "entries": [
    {
      "id": "qry_xyz123",
      "request_id": "req_abc456",
      "query_name": "memory.by_id",
      "cypher": "MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(m:Memory {id: $memory_id})...",
      "params": {"workspace_id":"demo_atlas_release_lab","memory_id":"mem_abc1"},
      "duration_ms": 3.2,
      "rows": 1,
      "write": false,
      "ts": 1723560000000
    }
  ]
}
```

## Known Limitations

- **Heuristic conflict detection misses paraphrase/units/negation:** Q3_FIND_CONFLICTS compares `object_value` string equality; paraphrased claims with different wording are not detected as conflicting. Unit normalization (e.g., "2 days" vs "48 hours") is not performed. Negation scope (e.g., "no claim" vs "claim is false") is not handled.
- **Provenance is not truth:** Decision nodes record rule-based outcomes, but the underlying graph could be modified directly via Cypher (bypassing the repository). Decisions are audit records, not cryptographic proof of immutability.
- **Receipts are audit records, not cryptographic proof:** INCLUDED/EXCLUDED memories in a handoff receipt record which memories are in/out, with reason codes. They verify the graph state at receipt-creation time but provide no cryptographic guarantee against later modification.
- **Conflict detection is predicate-only:** Q3_FIND_CONFLICTS requires `ex.predicate = cand.predicate`. Conflicts on different predicates are not detected. Cross-predicate inference is not implemented.
- **As-of status only checks valid_until/superseded_at:** Other temporal rules (e.g., "valid_from in future") are not filtered by the basic timeline query; extended as-of rules require additional WHERE clauses.
- **No vector similarity:** Semantic search is not supported. Claims are matched by exact predicate + object_value strings only.
- **Authority is synthetic 1–5:** Authority values have no external validation; they are set at seed time and persisted as-is.

## Roadmap

- **MCP server:** Model-Context-Protocol server for standardized agent-memory communication
- **Normalization:** Unit normalization, paraphrase clustering, negation-aware conflict detection
- **Retention policy:** Automatic expiry of old memories; valid_until cleanup; revision pruning
- **Vector index:** FalkorDB vector index for semantic claim similarity
- **Fine-grained permissions:** Per-agent, per-resource ACLs beyond current scope gating
- **Persistent audit log:** External write-ahead log for Decision nodes (currently in-graph only)
- **Live LLM mode:** Configuration for OpenAI/Anthropic/Vertex API with prompt-injection guards

## AI Coding-Assistant Disclosure

> [This section to be filled by the submitter]
> 
> AI tools used during implementation: [list exact tools and versions]
> 
> Prompts that produced critical code: [paste or summarize]
> 
> Human review points: [note any code areas requiring manual verification]

## Team + License

**Team:** [To be filled]

**License:** [To be filled - typically MIT or Apache 2.0 for hackathon submissions]

**Copyright:** Copyright (c) 2025 FactWeft Contributors