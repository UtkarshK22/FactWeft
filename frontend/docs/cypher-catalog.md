# Cypher Catalogue

**All queries are from `app/graph/queries.py`. One constant per query with documentation block: Purpose, Params, Returns, Mode (read-only or write).**

## Conventions

- Values are always bound through `GraphClient.run` (the FalkorDB client sends them in the `CYPHER` params header). Nothing is string-interpolated from untrusted input.
- The two exceptions are DDL identifiers (`SCHEMA_CREATE_INDEX`) and the variable-length bound in `Q_NEIGHBORHOOD_NODES` — Cypher cannot parameterize either. Both are fed only from validated allowlists (`bootstrap.SCHEMA_LABELS` / `queries.NEIGHBORHOOD_HOP_CHOICES`).
- Reads use `GRAPH.RO_QUERY`; anything that creates, deletes or sets uses `GRAPH.QUERY` (repository layer with `write=True`).
- Every statement is executed against the pinned FalkorDB image by `tests/integration/test_repo_queries.py` (behaviour) and `tests/integration/test_query_catalogue.py` (compilation).
- `EXISTS { ... }` subqueries and parameterized variable-length bounds (`[*1..$hops]`) are **not** accepted by FalkorDB v4.22.1; the equivalent constructs used here are `OPTIONAL MATCH` and a validated `{hops}` template.

## Schema / Bootstrap

| Query | Purpose | Mode |
|---|---|---|
| `SCHEMA_LIST_INDEXES` | List range indexes so bootstrap only creates what is missing | read-only |
| `SCHEMA_LIST_CONSTRAINTS` | List constraints so bootstrap only creates what is missing | read-only |
| `SCHEMA_CREATE_INDEX` | Create a range index (DDL identifiers cannot be parameters). `{label}` and `{prop}` are filled from bootstrap allowlists. | write |

## Workspace & Agent

| Query | Purpose | Params | Returns | Mode |
|---|---|---|---|---|
| `Q_WORKSPACE_PRESENT` | Health check: workspace node exists | `$workspace_id` (String) | `count` (Integer) | read-only |
| `Q_MERGE_WORKSPACE` | Create or refresh workspace node | `$workspace_id`, `$display_name`, `$created_at` | `id` (String) | write |
| `Q_MERGE_AGENT` | Create or refresh agent node | `$agent_id`, `$role`, `$display_name` | `id` (String) | write |

## Seeding (static base)

| Query | Purpose | Params | Returns | Mode |
|---|---|---|---|---|
| `Q_SEED_CONCEPT` | Create or refresh a concept with aliases | `$concept_id`, `$canonical_name`, `$concept_type`, `$aliases` | `id` (String) | write |
| `Q_SEED_SOURCE` | Create or refresh a synthetic source (authority 1..5) | `$source_id`, `$title`, `$source_type`, `$source_ref`, `$content_hash`, `$published_at`, `$authority`, `$synthetic_flag`, `$excerpt` | `id` (String) | write |
| `Q_SEED_SESSION` | Create or refresh a session | `$session_id`, `$task_label`, `$started_at`, `$ended_at` | `id` (String) | write |
| `Q_SEED_EPISODE` | Create episode and link to capturing session | `$episode_id`, `$event_type`, `$occurred_at`, `$summary`, `$session_id` | `id` (String) | write |
| `Q_SEED_PROCEDURE` | Create procedural memory with subject_key/concept links | `$workspace_id`, `$agent_id`, `$subject_key`, `$memory_id`, `$predicate`, `$label`, `$summary`, `$confidence`, `$created_at`, `$valid_from` | `memory_id` (String) | write |
| `Q_SEED_STEP` | Create one procedure step and CHECKS→Concept | `$procedure_id`, `$step_id`, `$order`, `$label`, `$check_predicate`, `$expected_value`, `$concept_id` | `step_id` (String) | write |

## Reads (the core query set)

| Query | Purpose | Params | Returns | Mode |
|---|---|---|---|---|
| `Q_MEMORY_BY_ID` | Read one memory with evidence and concept name | `$workspace_id`, `$memory_id` | Memory fields, `concept_name`, `evidence[]` | read-only |
| `Q_TIMELINE_EVENTS` | Timeline of memory proposals and decisions | `$workspace_id`, `$limit` (optional) | `memory_id`, `at_ms`, `event_type`, `status`, `summary`, `predicate`, `object_value`, `episode_id` | read-only |
| `Q_DISPUTES_LIST` | Open disputes: contested claims with active counterpart | `$workspace_id` | `candidate_id`, `predicate`, `candidate_value`, `candidate_summary`, `candidate_valid_from`, `candidate_revision`, `candidate_authority`, `existing_id`, `existing_value`, `existing_summary`, `existing_valid_from`, `existing_revision`, `existing_authority`, `decision_ids[]` | read-only |
| `Q_ELIGIBLE_MEMORIES` | Receiver-aware included set; scope gating at read time | `$workspace_id`, `$concept_ids[]`, `$receiver_id`, `$now` | `id`, `kind`, `predicate`, `value`, `summary`, `confidence`, `valid_from`, `concept_id`, `evidence[]` | read-only |
| `Q_INELIGIBLE_MEMORIES` | Excluded set with stable reason codes; `scope_denied` returns null summary | `$workspace_id`, `$concept_ids[]`, `$receiver_id`, `$now` | `id`, `reason_code`, `summary` (null when `scope_denied`) | read-only |
| `Q_READINESS` | Procedure-driven: satisfied/blocked/unknown per step | `$procedure_id` | `step_order`, `step`, `expected`, `memory_id`, `actual`, `state` | read-only |
| `Q_WHY_SOURCES` | Provenance: sources backing one memory | `$memory_id` | `id`, `title`, `source_type`, `authority`, `published_at`, `excerpt` (ordered by authority DESC, published_at DESC) | read-only |
| `Q_WHY_SUPERSEDES` | Lineage: SUPERSEDES chain up to 4 hops both directions | `$memory_id` | `older_ids[]`, `newer_ids[]` | read-only |
| `Q_WHY_DECISIONS` | Decisions resolving one memory (ordered descending) | `$memory_id` | `id`, `decision_type`, `outcome`, `reason_code`, `reviewer_type`, `decided_at` | read-only |
| `Q_WHY_HANDOFFS` | Which handoffs included/excluded one memory, and why | `$memory_id` | `handoff_id`, `relation` (INCLUDES/EXCLUDES), `reason_code`, `created_at` (ordered descending) | read-only |
| `Q3_FIND_CONFLICTS` | Find active memories contradicting candidate on same predicate | `$candidate_id` | `existing_id`, `existing_value`, `existing_valid_from`, `existing_revision`, `cand_valid_from`, `existing_authority`, `existing_published_at`, `cand_authority`, `cand_published_at` | read-only |
| `Q3B_FIND_CORROBORATION` | Find active memory with same value (corroboration, not conflict) | `$candidate_id` | `existing_id`, `existing_revision` (LIMIT 1) | read-only |

## Writes (deterministic resolution, never LLM)

| Query | Purpose | Mode |
|---|---|---|
| `Q1_PROPOSE_MEMORY` | Create candidate memory with ownership/evidence/proposer | write |
| `Q1B_LINK_EPISODE` | Link memory to capturing episode | write |
| `Q1C_SET_VALID_UNTIL` | Set memory `valid_until` | write |
| `Q1D_SHARE_MEMORY` | `SHARED_WITH` edge when `scope=handoff` | write |
| `Q6_SUPERSEDE` | Compare-and-set supersede: revision gating; 409 if stale | write |
| `Q_PROMOTE_CANDIDATE` | Promote candidate → active with Decision node | write |
| `Q_HOLD_CANDIDATE` | Set candidate → contested; add CONTRADICTS edge | write |
| `Q_HANDOFF_CREATE` | Create handoff with sender/receiver/workspace | write |
| `Q_HANDOFF_INCLUDE` | Record included memories in receipt (UNWIND list) | write |
| `Q_HANDOFF_EXCLUDE` | Record excluded memories with reason codes (UNWIND list) | write |
| `Q_DECISION_WRITE` | Write Decision node for any memory state transition | write |
| `Q_REVIEW_REJECT` | Review action: reject memory | write |
| `Q_REVIEW_COEXIST` | Review action: coexist (both cardinality `many`) | write |
| `Q_REVIEW_KEEP_CONTESTED` | Review action: keep contested; write decision | write |

## Q1 — Propose a Candidate (All MATCHes run first: missing workspace/agent/source/concept → zero rows → 404/422)

```cypher
MATCH (w:Workspace {id: $workspace_id})
MATCH (a:Agent {id: $agent_id})
MATCH (s:Source {id: $source_id})
MATCH (c:Concept {id: $subject_key})
MERGE (m:Memory {id: $memory_id})
ON CREATE SET m.kind = $kind,
              m.subject_key = $subject_key,
              m.predicate = $predicate,
              m.object_value = $object_value,
              m.cardinality = $cardinality,
              m.summary = $summary,
              m.status = 'candidate',
              m.scope = $scope,
              m.confidence = $confidence,
              m.created_at = $now,
              m.valid_from = $valid_from,
              m.revision = 1,
              m.proposed_by = $agent_id
MERGE (w)-[:OWNS_MEMORY]->(m)
MERGE (m)-[:SUPPORTED_BY]->(s)
MERGE (m)-[:PROPOSED_BY]->(a)
MERGE (m)-[:ABOUT]->(c)
RETURN m.id AS memory_id, m.status AS status
```

## Q3 — Conflict Discovery (read-only, never mutates)

**Find active memories contradicting a candidate on same predicate+value:**

```cypher
MATCH (cand:Memory {id: $candidate_id})-[:ABOUT]->(c:Concept)<-[:ABOUT]-(ex:Memory)
WHERE ex.id <> cand.id
  AND ex.status = 'active'
  AND ex.predicate = cand.predicate
  AND cand.cardinality = 'one'
  AND ex.object_value <> cand.object_value
OPTIONAL MATCH (cand)-[:SUPPORTED_BY]->(cs:Source)
OPTIONAL MATCH (ex)-[:SUPPORTED_BY]->(es:Source)
RETURN ex.id AS existing_id,
       ex.object_value AS existing_value,
       ex.valid_from AS existing_valid_from,
       ex.revision AS existing_revision,
       cand.valid_from AS cand_valid_from,
       max(es.authority) AS existing_authority,
       max(es.published_at) AS existing_published_at,
       max(cs.authority) AS cand_authority,
       max(cs.published_at) AS cand_published_at
```

**Find an active memory that already holds the candidate's exact value (corroboration):**

```cypher
MATCH (cand:Memory {id: $candidate_id})-[:ABOUT]->(c:Concept)<-[:ABOUT]-(ex:Memory)
WHERE ex.id <> cand.id
  AND ex.status = 'active'
  AND ex.predicate = cand.predicate
  AND ex.object_value = cand.object_value
RETURN ex.id AS existing_id, ex.revision AS existing_revision
LIMIT 1
```

## Q6 — Deterministic Resolution (code + Cypher, never LLM)

**Supersede an active memory with a candidate using compare-and-set on revision:**

```cypher
MATCH (old:Memory {id: $old_id})
WHERE old.status = 'active' AND old.revision = $expected_revision
MATCH (new:Memory {id: $new_id})
WHERE new.status = 'candidate'
SET old.status = 'superseded',
    old.superseded_at = $now,
    old.valid_until = $new_valid_from,
    old.revision = $expected_revision + 1
SET new.status = 'active',
    new.revision = $expected_revision + 1
CREATE (new)-[:SUPERSEDES {reason: $reason, at: $now}]->(old)
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'supersede',
                    outcome: 'superseded',
                    reason_code: $reason,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(new)
CREATE (d)-[:RESOLVES]->(old)
RETURN new.id AS new_id, old.id AS old_id
```

**Promote a clean candidate to active with a Decision row:**

```cypher
MATCH (m:Memory {id: $memory_id})
WHERE m.status = 'candidate'
SET m.status = 'active', m.revision = m.revision + 1
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'promote',
                    outcome: 'promoted',
                    reason_code: $reason_code,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(m)
RETURN m.id AS memory_id, m.status AS status
```

**Hold a candidate as contested and record the contradiction:**

```cypher
MATCH (cand:Memory {id: $candidate_id})
WHERE cand.status = 'candidate'
MATCH (ex:Memory {id: $existing_id})
WHERE ex.status = 'active'
SET cand.status = 'contested', cand.revision = cand.revision + 1
MERGE (cand)-[r:CONTRADICTS]->(ex)
SET r.reason = $reason, r.at = $now
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'conflict',
                    outcome: 'held',
                    reason_code: $reason,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(cand)
RETURN cand.id AS candidate_id, cand.status AS status
```

## Review Actions

**Human/rule review: reject:**

```cypher
MATCH (m:Memory {id: $memory_id})
WHERE m.status IN ['candidate', 'contested']
SET m.status = 'rejected', m.revision = m.revision + 1
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'review',
                    outcome: 'rejected',
                    reason_code: $reason_code,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(m)
RETURN m.id AS memory_id, m.status AS status
```

**Human/rule review: coexist (both memories cardinality `many`):**

```cypher
MATCH (cand:Memory {id: $candidate_id})
WHERE cand.status = 'contested'
MATCH (ex:Memory {id: $existing_id})
WHERE ex.status = 'active'
SET cand.status = 'active',
    cand.cardinality = 'many',
    cand.revision = cand.revision + 1,
    ex.cardinality = 'many'
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'review',
                    outcome: 'coexist',
                    reason_code: $reason_code,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(cand)
CREATE (d)-[:RESOLVES]->(ex)
RETURN cand.id AS candidate_id, ex.id AS existing_id
```

**Human/rule review: keep contested (no value change, conflict was reviewed and left open):**

```cypher
MATCH (m:Memory {id: $memory_id})
WHERE m.status = 'contested'
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'review',
                    outcome: 'kept_contested',
                    reason_code: $reason_code,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(m)
RETURN m.id AS memory_id, m.status AS status
```

## Handoffs (the receipt is included + excluded with reason codes)

**Create a handoff and wire sender, receiver and workspace ownership:**

```cypher
MATCH (w:Workspace {id: $workspace_id})
MATCH (sender:Agent {id: $sender_id})
MATCH (receiver:Agent {id: $receiver_id})
CREATE (h:Handoff {id: $handoff_id,
                   task: $task,
                   created_at: $now,
                   status: $status,
                   token_budget: $token_budget,
                   receipt_version: $receipt_version,
                   policy_version: $policy_version})
MERGE (w)-[:OWNS_HANDOFF]->(h)
MERGE (h)-[:SENT_BY]->(sender)
MERGE (h)-[:SENT_TO]->(receiver)
RETURN h.id AS handoff_id
```

**Record the receipt's included memories:**

```cypher
UNWIND $memory_ids AS mid
MATCH (h:Handoff {id: $handoff_id})
MATCH (m:Memory {id: mid})
MERGE (h)-[:INCLUDES]->(m)
RETURN count(m) AS included
```

**Record the receipt's excluded memories with their reason codes:**

```cypher
UNWIND $excluded AS row
MATCH (h:Handoff {id: $handoff_id})
MATCH (m:Memory {id: row.memory_id})
MERGE (h)-[r:EXCLUDES]->(m)
SET r.reason_code = row.reason_code
RETURN count(r) AS excluded
```

## Q-Neurhood: Bounded Projection

**Four statements because the node cap, total count and edge list cannot be expressed in one parameterized query (Cypher cannot parameterize a variable-length bound).**

**Confirm the root memory exists inside the caller's workspace:**

```cypher
MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(root:Memory {id: $memory_id})
RETURN root
```

**One page of the projection (root excluded; the caller adds it):**

```cypher
MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(root:Memory {id: $memory_id})
MATCH (root)-[*1..{hops}]-(neighbour)
WITH DISTINCT neighbour
WHERE (NOT neighbour:Memory)
   OR (
        ($as_of_ms IS NULL OR neighbour.created_at <= $as_of_ms)
        AND ($status IS NULL OR (
            CASE
              WHEN $as_of_ms IS NULL THEN neighbour.status
              WHEN neighbour.superseded_at IS NOT NULL AND neighbour.superseded_at <= $as_of_ms THEN 'superseded'
              WHEN neighbour.valid_until IS NOT NULL AND neighbour.valid_until <= $as_of_ms THEN 'expired'
              WHEN neighbour.superseded_at IS NOT NULL THEN 'active'
              ELSE neighbour.status
            END) = $status)
        AND ($kind IS NULL OR neighbour.kind = $kind)
        AND ($scope IS NULL OR neighbour.scope = $scope)
        AND ($agent_id IS NULL OR neighbour.proposed_by = $agent_id)
      )
RETURN neighbour
ORDER BY neighbour.id
LIMIT $max_nodes
```

**How many neighbours exist before the cap ("showing X of Y"):**

```cypher
MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(root:Memory {id: $memory_id})
MATCH (root)-[*1..{hops}]-(neighbour)
WITH DISTINCT neighbour
WHERE (NOT neighbour:Memory)
   OR (
        ($as_of_ms IS NULL OR neighbour.created_at <= $as_of_ms)
        AND ($status IS NULL OR (
            CASE
              WHEN $as_of_ms IS NULL THEN neighbour.status
              WHEN neighbour.superseded_at IS NOT NULL AND neighbour.superseded_at <= $as_of_ms THEN 'superseded'
              WHEN neighbour.valid_until IS NOT NULL AND neighbour.valid_until <= $as_of_ms THEN 'expired'
              WHEN neighbour.superseded_at IS NOT NULL THEN 'active'
              ELSE neighbour.status
            END) = $status)
        AND ($kind IS NULL OR neighbour.kind = $kind)
        AND ($scope IS NULL OR neighbour.scope = $scope)
        AND ($agent_id IS NULL OR neighbour.proposed_by = $agent_id)
      )
RETURN count(neighbour) AS total
```

**Edges whose endpoints are both inside the shown node set:**

```cypher
MATCH (a)-[r]->(b)
WHERE a.id IN $ids AND b.id IN $ids
RETURN a.id AS source,
       b.id AS target,
       type(r) AS type,
       properties(r) AS properties
ORDER BY source, target
LIMIT $edge_cap
```