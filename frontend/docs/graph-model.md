# Graph Model

## Overview

FactWeft uses a **single FalkorDB graph per workspace** (`workspace_id` is the primary key for graph isolation). Every route begins by resolving `graph_name_for_workspace(workspace_id)` and verifying the `Workspace` node exists (`Q_WORKSPACE_PRESENT`). All memories, agents, concepts, and sources are owned by a `Workspace` via the `OWNS_MEMORY` relationship.

## Node Labels

### `Workspace`
- `id` (String) — e.g. `demo_atlas_release_lab`, `demo_orbit_ops`
- `display_name` (String)
- `created_at` (Integer, epoch ms)

### `Agent`
- `id` (String) — unique agent identifier
- `role` (String) — e.g. `scout`, `planner`, `coordinator`, `owner`
- `display_name` (String)

### `Concept`
- `id` (String) — used as `subject_key` on memories; canonical identifier for a topic/predicate
- `canonical_name` (String)
- `aliases` (List<String>) — alternative names for the same concept

### `Memory`
- `id` (String) — generated as `mem_` + 12 hex chars if not provided; or provided explicitly
- `kind` (String) — `semantic` or `procedural`
- `predicate` (String) — the property/relation being claimed
- `object_value` (String) — the claim value
- `status` (String) — `active`, `candidate`, `contested`, `superseded`, `rejected`
- `scope` (String) — `workspace`, `agent_only`, `handoff`
- `confidence` (Float) — 0.0 to 1.0
- `created_at` (Integer, epoch ms)
- `valid_from` (Integer, epoch ms) — start of validity
- `valid_until` (Integer, epoch ms | null) — end of validity; `null` = open-ended
- `revision` (Integer) — incremented on every state transition; used for compare-and-set gating
- `proposed_by` (String) — Agent `id` who proposed this memory
- `summary` (String | null) — one-sentence description

### `Source`
- `id` (String)
- `title` (String)
- `source_type` (String) — e.g. `synthetic`, `document`, `api`
- `authority` (Integer) — 1 to 5
- `published_at` (Integer, epoch ms)
- `synthetic_flag` (Boolean)
- `excerpt` (String | null)

### `Decision`
- `id` (String) — generated as `dec_` + 8 hex chars
- `decision_type` (String) — `promote`, `supersede`, `conflict`, `review`, `keep_contested`
- `outcome` (String) — `active`, `superseded`, `held`, `rejected`, `coexist`
- `reason_code` (String | null) — e.g. `newer_higher_authority`, `contested`, `duplicate_corroborated`, `scope_split`, `manual_review`
- `decided_at` (Integer, epoch ms)
- `reviewer_type` (String) — `rule` or `human`

### `Handoff`
- `id` (String) — UUID
- `task` (String) — the question or task the handoff addresses
- `created_at` (Integer, epoch ms)
- `status` (String) — typically `pending` or `active`
- `token_budget` (Integer)
- `receipt_version` (String)
- `policy_version` (String)

### `Episode`
- `id` (String)
- `event_type` (String)
- `occurred_at` (Integer, epoch ms)
- `summary` (String | null)

## Relationships

| Relationship | Direction | Type | Properties (key examples) |
|---|---|---|---|
| `OWNS_MEMORY` | `Workspace` → `Memory` | — | establishes per-workspace ownership |
| `ABOUT` | `Memory` → `Concept` | — | categorizes the memory by concept |
| `SUPPORTED_BY` | `Memory` → `Source` | — | evidence backing the memory |
| `PROPOSED_BY` | `Memory` → `Agent` | — | who proposed this memory |
| `SUPERSEDES` | `Memory` → `Memory` | labeled `reason, at` | directed; old → new supersession chain |
| `CONTRADICTS` | `Memory` → `Memory` | labeled `reason, at` | directed; marks active vs contested |
| `INCLUDES` | `Handoff` → `Memory` | — | receipt: this memory is included |
| `EXCLUDES` | `Handoff` → `Memory` | labeled `reason_code` | receipt: this memory is excluded with reason |
| `SHARED_WITH` | `Handoff` → `Agent` | — | only when `scope=handoff`; specifies receiving agent |
| `HAS_STEP` | `Memory` (procedural) → `Step` | — | procedural memory steps |
| `RESOLVES` | `Decision` → `Memory` | — | audit trail: which decision resolved which memory |
| `CAPTURED` | `Session` → `Episode` | — | which episode was captured in which session |

## Per-Workspace Isolation

Every route resolves the graph name from `workspace_id` and verifies the `Workspace` node exists. Memory queries are gated by `OWNS_MEMORY`:
```
MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(m:Memory {id: $memory_id})
```
If the workspace does not own the memory, the query returns zero rows → 404. This means a memory in workspace A is indistinguishable from a missing memory in workspace B.

Agents and concepts are also workspace-scoped. Cross-workspace queries return 404.

## Sample Subgraph

```mermaid
graph TD
    w[Workspace "demo_atlas_release_lab"]:::workspace
    a1[Agent "agent_planner"]:::agent
    a2[Agent "agent_scout"]:::agent
    c1[Concept "release_freeze"]:::concept
    s1[Source "src_001"]:::source
    m1[Memory "mem_abc1"]:::memory {status:active, predicate:release_freeze, object_value:"release freeze Oct 17"}
    m2[Memory "mem_def2"]:::memory {status:superseded, predicate:release_freeze, object_value:"release freeze Oct 18"}
    d1[Decision "dec_xyz"]:::decision {decision_type:supersede, outcome:superseded}
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
    m2 -->|SUPERSEDES| m1
    w -->|OWNS_HANDOFF| h1
    h1 -->|SENT_BY| a1
    h1 -->|SENT_TO| a2
    h1 -->|INCLUDES| m1
    h1 -->|EXCLUDES| m2 {reason_code:"superseded_by_newer_supported_claim"}
    classDef workspace fill:#0B0F1A,color:#FFF;
    classDef agent fill:#2DD4BF,color:#000;
    classDef concept fill:#8B5CF6,color:#FFF;
    classDef memory fill:#111827,color:#FFF;
    classDef source fill:#F59E0B,color:#000;
    classDef decision fill:#F43F5E,color:#FFF;
    classDef handoff fill:#EC4899,color:#FFF;
```

## Read-Only Query Catalogue (verified)

All queries listed in `app/graph/queries.py`. Each has a documented **Purpose**, **Params**, **Returns**, and **Mode** (read-only or write). Reads use `GRAPH.RO_QUERY`; writes use `GRAPH.QUERY` via the repository layer.

**Key read queries:**
- `Q_MEMORY_BY_ID` — one memory with evidence/concept/decisions/handoffs
- `Q_TIMELINE_EVENTS` — ordered proposals + decisions
- `Q_DISPUTES_LIST` — contested claims with CONTRADICTS counterpart
- `Q_ELIGIBLE_MEMORIES` — receiver-aware included set; scope gating at read time
- `Q_INELIGIBLE_MEMORIES` — excluded set with reason codes; `scope_denied` returns null summary
- `Q_READINESS` — procedure-driven satisfied/blocked/unknown
- `Q_WHY_SOURCES` — provenance: sources backing one memory
- `Q_WHY_SUPERSEDES` — SUPERSEDES chain up to 4 hops both directions
- `Q_WHY_DECISIONS` — decisions resolving one memory (ordered descending)
- `Q_WHY_HANDOFFS` — which handoffs included/excluded one memory + reason codes
- `Q3_FIND_CONFLICTS` — active memories contradicting candidate on same predicate
- `Q3B_FIND_CORROBORATION` — active memory with same value (corroboration, not conflict)

**Critical convention:** Values are always bound through `GraphClient.run` (params sent in `CYPHER` header). Nothing is string-interpolated. The only exceptions are DDL identifiers in `SCHEMA_CREATE_INDEX`, filled from bootstrap allowlists, and the variable-length bound in `Q_NEIGHBORHOOD_NODES`, restricted to validated `NEIGHBORHOOD_HOP_CHOICES` (1 or 2).