"""The Cypher catalogue.

One named constant per query. Above each constant is its documentation block:
**Purpose**, **Params**, **Returns** and **Mode** (read-only or write).

Conventions
-----------
* Values are always bound through ``GraphClient.run`` (the FalkorDB client
  sends them in the ``CYPHER`` params header). Nothing is string-interpolated.
  The two exceptions are DDL identifiers (:data:`SCHEMA_CREATE_INDEX`) and the
  variable-length bound in :data:`Q_NEIGHBORHOOD_NODES` — Cypher cannot
  parameterize either. Both are fed only from validated allowlists
  (``bootstrap.SCHEMA_LABELS`` / ``queries.NEIGHBORHOOD_HOP_CHOICES``).
* Reads use ``GRAPH.RO_QUERY``; anything that creates, deletes or sets uses
  ``GRAPH.QUERY`` (``write=True`` in the repository).
* Every statement here is executed against the pinned FalkorDB image by
  ``tests/integration/test_repo_queries.py`` (behaviour) and EXPLAINed by
  ``tests/integration/test_query_catalogue.py`` (compilation).

Verified-on-this-version notes
------------------------------
* ``EXISTS { ... }`` subqueries and parameterized variable-length bounds
  (``[*1..$hops]``) are not accepted by v4.22.1; the equivalent constructs used
  here are ``OPTIONAL MATCH`` and a validated ``{hops}`` template.
* ``NOT n:Memory`` label predicates, ``properties(r)``, ``coalesce``, ``UNION``,
  ``CASE`` on nulls and ``UNWIND ... MATCH ... MERGE`` all work and are used
  below (each verified by execution, not by reading docs).
"""

from __future__ import annotations

NEIGHBORHOOD_MAX_HOPS = 2
NEIGHBORHOOD_HOP_CHOICES: tuple[int, ...] = (1, 2)

# ---------------------------------------------------------------------------
# Schema / bootstrap
# ---------------------------------------------------------------------------

# Purpose: list range indices so bootstrap only creates what is missing.
# Params:  none
# Returns: label, properties, ... (FalkorDB index metadata)
# Mode:    read-only
SCHEMA_LIST_INDEXES = """CALL db.indexes()"""

# Purpose: list constraints so bootstrap only creates what is missing.
# Params:  none
# Returns: type, label, properties, entitytype, status
# Mode:    read-only
SCHEMA_LIST_CONSTRAINTS = """CALL db.constraints()"""

# Purpose: create a range index (DDL identifiers cannot be parameters).
# Params:  none -- {label} and {prop} are filled from bootstrap allowlists.
# Returns: nothing (statistics only)
# Mode:    write
SCHEMA_CREATE_INDEX = "CREATE INDEX FOR (n:{label}) ON (n.{prop})"

# Purpose: health check that this workspace graph holds its Workspace node.
# Params:  $workspace_id
# Returns: count
# Mode:    read-only
Q_WORKSPACE_PRESENT = """MATCH (w:Workspace {id: $workspace_id})
RETURN count(w) AS count"""

# Purpose: total node count, used to prove seeding is idempotent.
# Params:  none
# Returns: nodes
# Mode:    read-only
Q_GRAPH_NODE_COUNT = """MATCH (n)
RETURN count(n) AS nodes"""

# ---------------------------------------------------------------------------
# Seeding (static base: workspace, agents, concepts, sources, sessions,
# episodes, the procedure and its steps). Memories are created by the scenario
# runner so the demo shows them appearing live.
# ---------------------------------------------------------------------------

# Purpose: create or refresh the workspace node.
# Params:  $workspace_id, $display_name, $created_at
# Returns: id
# Mode:    write
Q_MERGE_WORKSPACE = """MERGE (w:Workspace {id: $workspace_id})
SET w.display_name = $display_name,
    w.created_at = $created_at
RETURN w.id AS id"""

# Purpose: create or refresh an agent of the workspace.
# Params:  $agent_id, $role, $display_name
# Returns: id
# Mode:    write
Q_MERGE_AGENT = """MERGE (a:Agent {id: $agent_id})
SET a.role = $role,
    a.display_name = $display_name
RETURN a.id AS id"""

# Purpose: create or refresh a concept with its aliases.
# Params:  $concept_id, $canonical_name, $concept_type, $aliases
# Returns: id
# Mode:    write
Q_SEED_CONCEPT = """MERGE (c:Concept {id: $concept_id})
SET c.canonical_name = $canonical_name,
    c.concept_type = $concept_type,
    c.aliases = $aliases
RETURN c.id AS id"""

# Purpose: create or refresh a synthetic source (authority 1..5).
# Params:  $source_id, $title, $source_type, $source_ref, $content_hash,
#          $published_at, $authority, $synthetic_flag, $excerpt
# Returns: id
# Mode:    write
Q_SEED_SOURCE = """MERGE (s:Source {id: $source_id})
SET s.title = $title,
    s.source_type = $source_type,
    s.source_ref = $source_ref,
    s.content_hash = $content_hash,
    s.published_at = $published_at,
    s.authority = $authority,
    s.synthetic_flag = $synthetic_flag,
    s.excerpt = $excerpt
RETURN s.id AS id"""

# Purpose: create or refresh a session (a bounded period of agent work).
# Params:  $session_id, $task_label, $started_at, $ended_at
# Returns: id
# Mode:    write
Q_SEED_SESSION = """MERGE (s:Session {id: $session_id})
SET s.task_label = $task_label,
    s.started_at = $started_at,
    s.ended_at = $ended_at
RETURN s.id AS id"""

# Purpose: create or refresh an episode and link it to its capturing session.
# Params:  $episode_id, $event_type, $occurred_at, $summary, $session_id
# Returns: id
# Mode:    write
Q_SEED_EPISODE = """MERGE (e:Episode {id: $episode_id})
SET e.event_type = $event_type,
    e.occurred_at = $occurred_at,
    e.summary = $summary
WITH e
MATCH (s:Session {id: $session_id})
MERGE (s)-[:CAPTURED]->(e)
RETURN e.id AS id"""

# Purpose: create or refresh the procedural memory that drives readiness checks.
# Params:  $workspace_id, $agent_id, $subject_key, $memory_id, $predicate,
#          $label, $summary, $confidence, $created_at, $valid_from
# Returns: memory_id
# Mode:    write
Q_SEED_PROCEDURE = """MATCH (w:Workspace {id: $workspace_id})
MATCH (a:Agent {id: $agent_id})
MATCH (c:Concept {id: $subject_key})
MERGE (m:Memory {id: $memory_id})
SET m.kind = 'procedural',
    m.subject_key = $subject_key,
    m.predicate = $predicate,
    m.object_value = $label,
    m.cardinality = 'one',
    m.summary = $summary,
    m.status = 'active',
    m.scope = 'workspace',
    m.confidence = $confidence,
    m.created_at = $created_at,
    m.valid_from = $valid_from,
    m.revision = 1,
    m.proposed_by = $agent_id
MERGE (w)-[:OWNS_MEMORY]->(m)
MERGE (m)-[:ABOUT]->(c)
MERGE (m)-[:PROPOSED_BY]->(a)
RETURN m.id AS memory_id"""

# Purpose: create or refresh one procedure step and what it checks.
# Params:  $procedure_id, $step_id, $order, $label, $check_predicate,
#          $expected_value, $concept_id
# Returns: step_id
# Mode:    write
Q_SEED_STEP = """MATCH (p:Memory {id: $procedure_id})
MATCH (c:Concept {id: $concept_id})
MERGE (s:Step {id: $step_id})
SET s.label = $label,
    s.check_predicate = $check_predicate,
    s.expected_value = $expected_value
MERGE (p)-[h:HAS_STEP]->(s)
SET h.order = $order
MERGE (s)-[:CHECKS]->(c)
RETURN s.id AS step_id"""

# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

# Purpose: read one memory with its evidence and concept name.
# Params:  $workspace_id, $memory_id
# Returns: memory fields, concept_name, evidence[]
# Mode:    read-only
Q_MEMORY_BY_ID = """MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(m:Memory {id: $memory_id})
OPTIONAL MATCH (m)-[:SUPPORTED_BY]->(s:Source)
OPTIONAL MATCH (m)-[:ABOUT]->(c:Concept)
RETURN m.id AS id,
       m.kind AS kind,
       m.subject_key AS subject_key,
       m.predicate AS predicate,
       m.object_value AS object_value,
       m.cardinality AS cardinality,
       m.summary AS summary,
       m.status AS status,
       m.scope AS scope,
       m.confidence AS confidence,
       m.created_at AS created_at,
       m.valid_from AS valid_from,
       m.valid_until AS valid_until,
       m.superseded_at AS superseded_at,
       m.revision AS revision,
       m.proposed_by AS proposed_by,
       c.canonical_name AS concept_name,
       collect(DISTINCT {id: s.id, title: s.title, authority: s.authority}) AS evidence"""

# Purpose: receiver-aware included set for a handoff/answer. Scope gating happens
#          in the graph, and $receiver_id always comes from the principal.
# Params:  $workspace_id, $concept_ids[], $receiver_id, $now
# Returns: id, kind, predicate, value, summary, confidence, valid_from,
#          concept_id, evidence[]
# Mode:    read-only
Q_ELIGIBLE_MEMORIES = """MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(m:Memory)-[:ABOUT]->(c:Concept)
WHERE c.id IN $concept_ids
  AND m.status = 'active'
  AND (m.valid_until IS NULL OR m.valid_until > $now)
OPTIONAL MATCH (m)-[sw:SHARED_WITH]->(:Agent {id: $receiver_id})
WITH m, c, sw
WHERE m.scope = 'workspace'
   OR (m.scope = 'agent_only' AND m.proposed_by = $receiver_id)
   OR (m.scope = 'handoff' AND sw IS NOT NULL)
OPTIONAL MATCH (m)-[:SUPPORTED_BY]->(s:Source)
RETURN m.id AS id,
       m.kind AS kind,
       m.predicate AS predicate,
       m.object_value AS value,
       m.summary AS summary,
       m.confidence AS confidence,
       m.valid_from AS valid_from,
       c.id AS concept_id,
       collect(DISTINCT {id: s.id, title: s.title, authority: s.authority}) AS evidence"""

# Purpose: the receipt's excluded set with stable reason codes. Status is
#          checked before validity (superseded rows also carry valid_until), and
#          'scope_denied' rows return only id + reason -- never the summary.
# Params:  $workspace_id, $concept_ids[], $receiver_id, $now
# Returns: id, reason_code, summary (null when scope_denied)
# Mode:    read-only
Q_INELIGIBLE_MEMORIES = """MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(m:Memory)-[:ABOUT]->(c:Concept)
WHERE c.id IN $concept_ids
OPTIONAL MATCH (m)-[sw:SHARED_WITH]->(:Agent {id: $receiver_id})
WITH m, sw,
     CASE
       WHEN m.status = 'superseded' THEN 'superseded_by_newer_supported_claim'
       WHEN m.status = 'contested' THEN 'contested'
       WHEN m.status = 'candidate' THEN 'unpromoted_candidate'
       WHEN m.status = 'rejected' THEN 'rejected'
       WHEN m.valid_until IS NOT NULL AND m.valid_until <= $now THEN 'expired'
       WHEN m.scope = 'agent_only' AND m.proposed_by <> $receiver_id THEN 'scope_denied'
       WHEN m.scope = 'handoff' AND sw IS NULL THEN 'scope_denied'
       ELSE NULL
     END AS reason
WHERE reason IS NOT NULL
RETURN m.id AS id,
       reason AS reason_code,
       CASE WHEN reason = 'scope_denied' THEN null ELSE m.summary END AS summary"""

# Purpose: procedure-driven readiness; the graph decides satisfied/blocked/unknown.
# Params:  $procedure_id
# Returns: step_order, step, expected, memory_id, actual, state
# Mode:    read-only
Q_READINESS = """MATCH (p:Memory {id: $procedure_id, kind: 'procedural'})-[hs:HAS_STEP]->(st:Step)-[:CHECKS]->(c:Concept)
OPTIONAL MATCH (m:Memory)-[:ABOUT]->(c)
WHERE m.status = 'active' AND m.kind = 'semantic' AND m.predicate = st.check_predicate
RETURN hs.order AS step_order,
       st.label AS step,
       st.expected_value AS expected,
       m.id AS memory_id,
       m.object_value AS actual,
       CASE
         WHEN m IS NULL THEN 'unknown'
         WHEN m.object_value = st.expected_value THEN 'satisfied'
         ELSE 'blocked'
       END AS state
ORDER BY step_order"""

# Purpose: provenance -- the sources backing one memory.
# Params:  $memory_id
# Returns: id, title, source_type, authority, published_at, excerpt
# Mode:    read-only
Q_WHY_SOURCES = """MATCH (m:Memory {id: $memory_id})-[:SUPPORTED_BY]->(s:Source)
RETURN s.id AS id,
       s.title AS title,
       s.source_type AS source_type,
       s.authority AS authority,
       s.published_at AS published_at,
       s.excerpt AS excerpt
ORDER BY authority DESC, published_at DESC"""

# Purpose: lineage -- the SUPERSEDES chain up to 4 hops in both directions.
# Params:  $memory_id
# Returns: older_ids[], newer_ids[]
# Mode:    read-only
Q_WHY_SUPERSEDES = """MATCH (m:Memory {id: $memory_id})
OPTIONAL MATCH (m)-[:SUPERSEDES*1..4]->(older:Memory)
OPTIONAL MATCH (newer:Memory)-[:SUPERSEDES*1..4]->(m)
RETURN collect(DISTINCT older.id) AS older_ids,
       collect(DISTINCT newer.id) AS newer_ids"""

# Purpose: the decisions that resolve one memory.
# Params:  $memory_id
# Returns: id, decision_type, outcome, reason_code, reviewer_type, decided_at
# Mode:    read-only
Q_WHY_DECISIONS = """MATCH (d:Decision)-[:RESOLVES]->(m:Memory {id: $memory_id})
RETURN d.id AS id,
       d.decision_type AS decision_type,
       d.outcome AS outcome,
       d.reason_code AS reason_code,
       d.reviewer_type AS reviewer_type,
       d.decided_at AS decided_at
ORDER BY decided_at DESC"""

# Purpose: which handoffs included or excluded one memory, and why.
# Params:  $memory_id
# Returns: handoff_id, relation, reason_code, created_at
# Mode:    read-only
Q_WHY_HANDOFFS = """MATCH (h:Handoff)-[r]->(m:Memory {id: $memory_id})
WHERE type(r) IN ['INCLUDES', 'EXCLUDES']
RETURN h.id AS handoff_id,
       type(r) AS relation,
       r.reason_code AS reason_code,
       h.created_at AS created_at
ORDER BY created_at DESC"""

# Purpose: timeline of memory proposals and the decisions taken on them.
# Params:  $workspace_id, $limit
# Returns: memory_id, at_ms, event_type, status, summary, predicate,
#          object_value, episode_id
# Mode:    read-only
# Note: the UNION arms carry the same columns; the caller sorts/limits because
#       FalkorDB applies ORDER BY to the last arm only.
Q_TIMELINE_EVENTS = """MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(m:Memory)
OPTIONAL MATCH (m)-[:DERIVED_FROM]->(ep:Episode)
OPTIONAL MATCH (m)-[:PROPOSED_BY]->(a:Agent)
RETURN m.id AS memory_id,
       coalesce(ep.occurred_at, m.created_at) AS at_ms,
       'memory_proposed' AS event_type,
       m.status AS status,
       m.summary AS summary,
       m.predicate AS predicate,
       m.object_value AS object_value,
       ep.id AS episode_id,
       a.id AS agent_id
UNION
MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(m:Memory)<-[:RESOLVES]-(d:Decision)
RETURN m.id AS memory_id,
       d.decided_at AS at_ms,
       'decision' AS event_type,
       d.outcome AS status,
       d.reason_code AS summary,
       m.predicate AS predicate,
       m.object_value AS object_value,
       d.id AS episode_id,
       d.reviewer_type AS agent_id"""

# Purpose: open disputes -- contested claims with their active counterpart,
#          both sides' evidence strength and the decisions so far.
# Params:  $workspace_id
# Returns: candidate_*, existing_*, decision_ids[]
# Mode:    read-only
Q_DISPUTES_LIST = """MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(cand:Memory {status: 'contested'})
MATCH (cand)-[:CONTRADICTS]->(ex:Memory)
OPTIONAL MATCH (d:Decision)-[:RESOLVES]->(cand)
OPTIONAL MATCH (cand)-[:SUPPORTED_BY]->(cs:Source)
OPTIONAL MATCH (ex)-[:SUPPORTED_BY]->(es:Source)
RETURN cand.id AS candidate_id,
       cand.predicate AS predicate,
       cand.object_value AS candidate_value,
       cand.summary AS candidate_summary,
       cand.valid_from AS candidate_valid_from,
       cand.revision AS candidate_revision,
       max(cs.authority) AS candidate_authority,
       ex.id AS existing_id,
       ex.object_value AS existing_value,
       ex.summary AS existing_summary,
       ex.valid_from AS existing_valid_from,
       ex.revision AS existing_revision,
       max(es.authority) AS existing_authority,
       collect(DISTINCT d.id) AS decision_ids
ORDER BY candidate_valid_from DESC"""

# ---------------------------------------------------------------------------
# Q-neighborhood: bounded projection. Split into four statements because the
# node cap, the total count and the edge list cannot be expressed in one
# parameterized query (Cypher cannot parameterize a variable-length bound).
# ---------------------------------------------------------------------------

# Purpose: confirm the root memory exists inside the caller's workspace.
# Params:  $workspace_id, $memory_id
# Returns: root (node)
# Mode:    read-only
Q_NEIGHBORHOOD_ROOT = """MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(root:Memory {id: $memory_id})
RETURN root"""

# Purpose: one page of the projection (root excluded; the caller adds it).
# Params:  $workspace_id, $memory_id, $max_nodes, $status, $kind, $scope,
#          $agent_id, $as_of_ms ; {hops} is a validated literal (1 or 2)
# Returns: neighbour (node)
# Mode:    read-only
# Note: `[*1..$hops]` is rejected by v4.22.1 (\"unhandled type in inlined
#       properties\"), so the bound is a formatted literal restricted to
#       NEIGHBORHOOD_HOP_CHOICES. Filters apply to Memory nodes only; the
#       surrounding Concept/Source/Agent context is always shown.
Q_NEIGHBORHOOD_NODES = """MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(root:Memory {id: $memory_id})
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
LIMIT $max_nodes"""

# Purpose: how many neighbours exist before the cap (\"showing X of Y\").
# Params:  $workspace_id, $memory_id, $status, $kind, $scope, $agent_id,
#          $as_of_ms ; {hops} is a validated literal (1 or 2)
# Returns: total
# Mode:    read-only
Q_NEIGHBORHOOD_TOTAL = """MATCH (w:Workspace {id: $workspace_id})-[:OWNS_MEMORY]->(root:Memory {id: $memory_id})
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
RETURN count(neighbour) AS total"""

# Purpose: edges whose endpoints are both inside the shown node set.
# Params:  $ids[], $edge_cap
# Returns: source, target, type, properties
# Mode:    read-only
Q_NEIGHBORHOOD_EDGES = """MATCH (a)-[r]->(b)
WHERE a.id IN $ids AND b.id IN $ids
RETURN a.id AS source,
       b.id AS target,
       type(r) AS type,
       properties(r) AS properties
ORDER BY source, target
LIMIT $edge_cap"""

# ---------------------------------------------------------------------------
# Q1 -- propose a candidate. All MATCHes run first: a missing workspace, agent,
# source or concept writes nothing and returns zero rows.
# ---------------------------------------------------------------------------

# Purpose: create a candidate memory with its ownership, evidence, proposer and
#          concept links.
# Params:  $workspace_id, $agent_id, $source_id, $subject_key, $memory_id,
#          $kind, $predicate, $object_value, $cardinality, $summary, $scope,
#          $confidence, $now, $valid_from
# Returns: memory_id, status ('candidate')
# Mode:    write
Q1_PROPOSE_MEMORY = """MATCH (w:Workspace {id: $workspace_id})
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
RETURN m.id AS memory_id, m.status AS status"""

# Purpose: link a memory to the episode it was derived from.
# Params:  $memory_id, $episode_id
# Returns: memory_id, episode_id
# Mode:    write
Q1B_LINK_EPISODE = """MATCH (m:Memory {id: $memory_id})
MATCH (e:Episode {id: $episode_id})
MERGE (m)-[:DERIVED_FROM]->(e)
RETURN m.id AS memory_id, e.id AS episode_id"""

# Purpose: set (or clear) a memory's validity end.
# Params:  $memory_id, $valid_until
# Returns: memory_id, valid_until
# Mode:    write
Q1C_SET_VALID_UNTIL = """MATCH (m:Memory {id: $memory_id})
SET m.valid_until = $valid_until
RETURN m.id AS memory_id, m.valid_until AS valid_until"""

# Purpose: share a handoff-scoped memory with one receiving agent.
# Params:  $memory_id, $agent_id
# Returns: memory_id, agent_id
# Mode:    write
Q1D_SHARE_MEMORY = """MATCH (m:Memory {id: $memory_id})
MATCH (a:Agent {id: $agent_id})
MERGE (m)-[:SHARED_WITH]->(a)
RETURN m.id AS memory_id, a.id AS agent_id"""

# ---------------------------------------------------------------------------
# Q3 -- conflict discovery (read-only, never mutates)
# ---------------------------------------------------------------------------

# Purpose: find active memories that contradict a candidate on the same
#          concept+predicate, with both sides' authority and publication time.
# Params:  $candidate_id
# Returns: existing_id, existing_value, existing_valid_from, existing_revision,
#          cand_valid_from, existing_authority, existing_published_at,
#          cand_authority, cand_published_at
# Mode:    read-only
Q3_FIND_CONFLICTS = """MATCH (cand:Memory {id: $candidate_id})-[:ABOUT]->(c:Concept)<-[:ABOUT]-(ex:Memory)
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
       max(cs.published_at) AS cand_published_at"""

# Purpose: find an active memory that already holds the candidate's exact value
#          (corroboration, not conflict).
# Params:  $candidate_id
# Returns: existing_id, existing_revision
# Mode:    read-only
Q3B_FIND_CORROBORATION = """MATCH (cand:Memory {id: $candidate_id})-[:ABOUT]->(c:Concept)<-[:ABOUT]-(ex:Memory)
WHERE ex.id <> cand.id
  AND ex.status = 'active'
  AND ex.predicate = cand.predicate
  AND ex.object_value = cand.object_value
RETURN ex.id AS existing_id, ex.revision AS existing_revision
LIMIT 1"""

# ---------------------------------------------------------------------------
# Writes: deterministic resolution (promotion is code + Cypher, never an LLM)
# ---------------------------------------------------------------------------

# Purpose: supersede an active memory with a candidate using compare-and-set on
#          the revision. Zero rows means the caller's revision was stale -> 409.
#          Human review reuses this with reviewer_type='human'.
# Params:  $old_id, $expected_revision, $new_id, $now, $new_valid_from, $reason,
#          $decision_id, $reviewer_type
# Returns: new_id, old_id
# Mode:    write
Q6_SUPERSEDE = """MATCH (old:Memory {id: $old_id})
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
RETURN new.id AS new_id, old.id AS old_id"""

# Purpose: promote a clean candidate to active with a Decision row.
# Params:  $memory_id, $decision_id, $reason_code, $now, $reviewer_type
# Returns: memory_id, status ('active')
# Mode:    write
Q_PROMOTE_CANDIDATE = """MATCH (m:Memory {id: $memory_id})
WHERE m.status = 'candidate'
SET m.status = 'active', m.revision = m.revision + 1
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'promote',
                    outcome: 'promoted',
                    reason_code: $reason_code,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(m)
RETURN m.id AS memory_id, m.status AS status"""

# Purpose: hold a candidate as contested and record the contradiction.
# Params:  $candidate_id, $existing_id, $reason, $decision_id, $now,
#          $reviewer_type
# Returns: candidate_id, status ('contested')
# Mode:    write
Q_HOLD_CANDIDATE = """MATCH (cand:Memory {id: $candidate_id})
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
RETURN cand.id AS candidate_id, cand.status AS status"""

# Purpose: human/rule review action -- reject a candidate or contested memory.
# Params:  $memory_id, $decision_id, $reason_code, $now, $reviewer_type
# Returns: memory_id, status ('rejected')
# Mode:    write
Q_REVIEW_REJECT = """MATCH (m:Memory {id: $memory_id})
WHERE m.status IN ['candidate', 'contested']
SET m.status = 'rejected', m.revision = m.revision + 1
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'review',
                    outcome: 'rejected',
                    reason_code: $reason_code,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(m)
RETURN m.id AS memory_id, m.status AS status"""

# Purpose: human/rule review action -- the contested claim and the active claim
#          coexist, so both become cardinality 'many'.
# Params:  $candidate_id, $existing_id, $decision_id, $reason_code, $now,
#          $reviewer_type
# Returns: candidate_id, existing_id
# Mode:    write
Q_REVIEW_COEXIST = """MATCH (cand:Memory {id: $candidate_id})
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
RETURN cand.id AS candidate_id, ex.id AS existing_id"""

# Purpose: human/rule review action -- keep a claim contested (no value change),
#          recording that the conflict was reviewed and left open.
# Params:  $memory_id, $decision_id, $reason_code, $now, $reviewer_type
# Returns: memory_id, status ('contested')
# Mode:    write
Q_REVIEW_KEEP_CONTESTED = """MATCH (m:Memory {id: $memory_id})
WHERE m.status = 'contested'
CREATE (d:Decision {id: $decision_id,
                    decision_type: 'review',
                    outcome: 'kept_contested',
                    reason_code: $reason_code,
                    decided_at: $now,
                    reviewer_type: $reviewer_type})
CREATE (d)-[:RESOLVES]->(m)
RETURN m.id AS memory_id, m.status AS status"""

# ---------------------------------------------------------------------------
# Q_DECISION_WRITE - write a decision node for any memory state transition
# ---------------------------------------------------------------------------

# Purpose: write a decision node for any memory state transition.
# Params:  $memory_id, $decision_id, $decision_type, $outcome, $reason_code, $decided_at, $reviewer_type
# Returns: written decision record
# Mode:    write
Q_DECISION_WRITE = """CREATE (d:Decision {id: $decision_id,
                decision_type: $decision_type,
                outcome: $outcome,
                reason_code: $reason_code,
                decided_at: $decided_at,
                reviewer_type: $reviewer_type})
RETURN d"""

# ---------------------------------------------------------------------------
# Handoffs (the receipt is included + excluded with reason codes)
# ---------------------------------------------------------------------------

# Purpose: create a handoff and wire sender, receiver and workspace ownership.
# Params:  $workspace_id, $sender_id, $receiver_id, $handoff_id, $task, $now,
#          $status, $token_budget, $receipt_version, $policy_version
# Returns: handoff_id
# Mode:    write
Q_HANDOFF_CREATE = """MATCH (w:Workspace {id: $workspace_id})
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
RETURN h.id AS handoff_id"""

# Purpose: record the receipt's included memories.
# Params:  $handoff_id, $memory_ids[]
# Returns: included (count)
# Mode:    write
Q_HANDOFF_INCLUDE = """UNWIND $memory_ids AS mid
MATCH (h:Handoff {id: $handoff_id})
MATCH (m:Memory {id: mid})
MERGE (h)-[:INCLUDES]->(m)
RETURN count(m) AS included"""

# Purpose: record the receipt's excluded memories with their reason codes.
# Params:  $handoff_id, $excluded[] (maps with memory_id + reason_code)
# Returns: excluded (count)
# Mode:    write
# Note: UNWIND + MATCH + MERGE over a list of maps is supported and verified.
Q_HANDOFF_EXCLUDE = """UNWIND $excluded AS row
MATCH (h:Handoff {id: $handoff_id})
MATCH (m:Memory {id: row.memory_id})
MERGE (h)-[r:EXCLUDES]->(m)
SET r.reason_code = row.reason_code
RETURN count(r) AS excluded"""