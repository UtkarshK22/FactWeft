# 15-Judge Q&A Cheat Sheet (Accurate Answers About This Codebase)

## Graph Model

**Q1: How many graphs does FactWeft use, and how is the graph determined for a given request?**
**A1:** FactWeft uses one FalkorDB graph per `workspace_id`. Every route resolves the graph name via `graph_name_for_workspace(workspace_id)` from `app/graph/names.py` and verifies the `Workspace` node exists (`Q_WORKSPACE_PRESENT`). Cross-workspace queries return 404 because memories are owned by a `Workspace` via `OWNS_MEMORY` — a memory in workspace A is indistinguishable from a missing memory in workspace B.

**Q2: What does `Q_WORKSPACE_PRESENT` check, and what happens if it returns zero rows?**
**A2:** `Q_WORKSPACE_PRESENT` executes `MATCH (w:Workspace {id: $workspace_id}) RETURN count(w) AS count`. If zero rows, the route raises `HTTPException(404, "Workspace '{}' not found (graph '{}' absent)."`) — the API does not serve memory data from a local copy.

**Q3: What are the Memory label properties, and what does `status` enumerate?**
**A3:** Memory properties include `id`, `kind` (semantic/procedural), `predicate`, `object_value`, `status` (active/candidate/contested/superseded/rejected), `scope` (workspace/agent_only/handoff), `confidence` (float 0..1), `created_at`, `valid_from`, `valid_until`, `revision` (incremented on every state transition), `proposed_by`. The `status` enumerates: active, candidate, contested, superseded, rejected.

**Q4: What does `scope=handoff` require, and how is it enforced?**
**A4:** `scope=handoff` requires a non-empty `shared_with` list (enforced in `handoff_create` route; 400 if missing). SHARED_WITH edges are only created when `scope=handoff` + `shared_with` non-empty (`Q1D_SHARE_MEMORY`). At read time, `Q_ELIGIBLE_MEMORIES` only includes handoff-scoped memories where `sw IS NOT NULL`; others are excluded with `reason_code = scope_denied`.

**Q5: What are the valid reason codes for EXCLUDED memories in a handoff receipt?**
**A5:** `superseded_by_newer_supported_claim`, `contested`, `scope_denied`, `expired`, `unpromoted_candidate`. `scope_denied` rows return `null` for summary — they show no content in the HandoffCapsule Excluded tab.

## Resolver Rules

**Q6: What are the four review actions, and what does each do?**
**A6:** 
- `supersede`: Q6 compare-and-set on revision; 409 on stale; old memory → `superseded`, new → `active`; Decision node written.
- `reject`: Sets memory `status = 'rejected'`, increments `revision`; Decision node written.
- `keep_contested`: Both memories remain `contested`; CONTRADICTS edge ensured; Decision node written.
- `coexist`: Both memories → `cardinality = 'many'`; both `revision` incremented; Decision node written.

**Q7: How does the supersede compare-and-set work?**
**A7:** Q6_SUPERSEDE executes `MATCH (old:Memory {id: $old_id}) WHERE old.status = 'active' AND old.revision = $expected_revision MATCH (new:Memory {id: $new_id}) WHERE new.status = 'candidate'`. If zero rows (revision mismatch), the route returns 409 with the current revision detail. If one row, it sets `old.status = 'superseded'`, `old.superseded_at = $now`, `old.valid_until = $new_valid_from`, `old.revision = $expected_revision + 1`; sets `new.status = 'active'`, `new.revision = $expected_revision + 1`; creates SUPERSEDES edge + Decision node.

**Q8: How are conflicts detected between a candidate and existing memories?**
**A8:** Q3_FIND_CONFLICTS matches `(cand:Memory {id: $candidate_id})-[:ABOUT]->(c:Concept)<-[:ABOUT]-(ex:Memory) WHERE ex.id <> cand.id AND ex.status = 'active' AND ex.predicate = cand.predicate AND cand.cardinality = 'one' AND ex.object_value <> cand.object_value`. If no conflict and no corroboration (Q3B_FIND_CORROBORATION finds same value), the candidate is promoted to active. If conflict, Q_HOLD_CANDIDATE sets status=`contested` + CONTRADICTS edge. If corroboration, no candidate is written; existing memory gets SUPPORTED_BY link.

**Q9: What does `as_of_ms` do in `GET /api/timeline`?**
**A9:** `as_of_ms` filters the timeline to show the state as of that timestamp. WHERE clauses clamp to `created_at <= as_of_ms` / `decided_at <= as_of_ms` / `created_at <= as_of_ms`; items created after the playhead are hidden; status is computed with as-of rules (valid_until check: `valid_until <= as_of_ms` → expired; superseded_at check: `superseded_at <= as_of_ms` → superseded; otherwise current status).

## Concurrency & Compare-and-Set

**Q10: What happens if a review action is called with a stale revision?**
**A10:** The route returns 409 with detail `{"error":"stale_revision","message":"Memory '{}' revision mismatch; current revision is {}"}`. The caller can fetch the current revision and retry once. This applies to `supersede` and all review actions that gate on revision.

**Q11: Is there any LLM involvement in state transitions?**
**A11:** No. All state transitions are deterministic Cypher + Python code. The only LLM call is `/api/ask` with `llm_mode=fixture` (mock answers) or `llm_mode=live` (actual LLM provider). Memory propose/conflict/resolve/cohesion/review are all code-driven via the Cypher catalogue and lifecycle module.

**Q12: What is the role of the `revision` field, and how is it incremented?**
**A12:** The `revision` field is an integer incremented on every memory state transition (propose → candidate → hold/supersede/promote → active/rejected; review actions all increment). It gates all compare-and-set operations: Q6_SUPERSEDE, Q_REVIEW_REJECT, Q_REVIEW_COEXIST, Q_REVIEW_KEEP_CONTESTED all require `old.revision == expected_revision`. If mismatch → 409 stale revision.

## Why No Vector DB?

**Q13: Does FactWeft use a vector database for semantic search?**
**A13:** No. The system does not use a vector DB. Claims are matched by exact predicate + object_value string equality only. Q3_FIND_CONFLICTS requires `ex.predicate = cand.predicate AND ex.object_value <> cand.object_value`. There is no cosine similarity or vector search. (A vector index could be added as a supplementary layer but is not part of the current implementation.)

## Injection & Safety

**Q14: How is prompt injection handled?**
**A14:** No LLM calls occur within the graph resolution pipeline. All state transitions are deterministic Cypher + code. The `/api/ask` endpoint passes user questions to an LLM, but the graph memory itself is injection-safe: no Cypher statement string-interpolates untrusted input; all params are bound through GraphClient. The fixture mode returns pre-composed answers; live mode passes through to the configured LLM provider with the user's own guardrails.

**Q15: What is the difference between fixture and live LLM mode?**
**A15:** `fixture` mode returns pre-composed, deterministic answers (used in demos; no external API call). `live` mode passes the user's question to the configured LLM provider (OpenAI/Anthropic/Vertex) via the `/api/ask` endpoint; the system itself does not determine the LLM or API keys — those are set via environment variables (`FAULKORDB_ENDPOINT`, LLM provider creds) and are out of scope for the graph memory logic.

---
*All answers are verified against the actual codebase in `app/graph/queries.py`, `app/memory/lifecycle.py`, `app/graph/repo.py`, and `backend/app/main.py`. State only facts that are true of the code as built; flag anything unverified.*