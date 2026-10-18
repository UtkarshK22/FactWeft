# Submission Checklist (Mapped to Hackathon Rules)

## 1. Public Repo Verified in a Private Window
- [ ] Repository is public (confirmed in browser incognito/private window)
- [ ] No secret values in commit history or `.git/logs/`
- [ ] `.gitignore` covers `.env`, `localStorage` keys, `node_modules/`, `dist/`
- [ ] Repository URL included in submission form

## 2. README.md
- [ ] `README.md` present at repo root
- [ ] Problem & Track 02 fit stated (Agent Memory and Coordination)
- [ ] Honest comparison table vs. Mem0/Graphiti/Zep/LangMem (claim-level dispute state, policy-gated handoffs, receipts)
- [ ] What is original here (fact-stated, not claimed)
- [ ] Live demo link (URL)
- [ ] Demo video link (URL or path)
- [ ] Architecture diagram (Mermaid) included
- [ ] Why FalkorDB is central + ablation proof stated
- [ ] Graph schema (labels, relationships, properties, enums, one-graph-per-workspace isolation) with sample subgraph diagram
- [ ] Verified Cypher catalogue (copy of final working queries from queries.py with one-line explanations)
- [ ] Memory lifecycle and resolver rules documented
- [ ] Setup (prerequisites, env vars, `docker compose up -d`, `make seed`, `make dev`, `npm run dev`, health check, troubleshooting)
- [ ] Demo walkthrough with expected outputs
- [ ] Security and data policy (synthetic only, tenant isolation, fail-closed, prompt-injection handling)
- [ ] Measured evaluation results (real output pasted)
- [ ] Known limitations (heuristic conflict detection misses paraphrase/units/negation; provenance is not truth; receipts are audit records, not cryptographic proof)
- [ ] Roadmap (MCP server, normalization, retention)
- [ ] AI coding-assistant disclosure (placeholders for exact tools; I will fill them)
- [ ] Team + license

## 3. docs/ Directory
- [ ] `docs/graph-model.md` — graph model with labels, relationships, properties, enums, one-graph-per-workspace isolation, sample subgraph diagram
- [ ] `docs/cypher-catalog.md` — verified Cypher catalogue (copy of final working queries from queries.py with one-line explanations)
- [ ] `docs/architecture.md` — full architecture diagram description (layers, data flows, failure modes)
- [ ] `docs/demo-script.md` — 3:30 min demo video script with exact click path matching UI; shot list; pre-recording checklist (reset + reseed, hide secrets/paths/terminal history, consistent dates, browser zoom and resolution)

## 4. Deployment
- [ ] **(a) Fully tested local path via docker compose as the guaranteed baseline**
  - [ ] `docker compose up -d` starts FalkorDB
  - [ ] `make seed` seeds the demo workspace (idempotent)
  - [ ] `make dev` starts backend; `npm run dev` starts frontend
  - [ ] Health check: `curl -s http://localhost:8000/api/health` returns `falkordb: "ok"`
  - [ ] All env vars documented (backend `.env` + frontend `.env`)
  - [ ] CORS and token configuration verified for local path
- [ ] **(b) Optional live deploy: frontend on Vercel/Netlify/Cloudflare Pages, API on Render/Fly/Railway, FalkorDB Cloud or a small VM with auth enabled and the port NOT publicly open**
  - [ ] List every env var for live deploy
  - [ ] Note free tiers may cold-start; demo should warm up first
- [ ] **(c) Fallback to expose the local stack with a tunnel (Cloudflare Tunnel/ngrok) if deployment fails**
  - [ ] CORS and token configuration for each tunnel type documented
  - [ ] Tunnel tested and working

## 5. Demo Video Script (3:30) with Exact Click Path Matching the UI
- [ ] Problem (0:20) — UI state verified
- [ ] Session 1 write (0:35) — memory proposed; Inspector opens; active ribbon
- [ ] Session 2 supersession (0:35) — dashed slate ribbon; connector with reason code; "Showing X of Y"
- [ ] Planner question + handoff receipt (0:45) — Ask panel answer; citation chips; HandoffCapsule Included/Excluded/Readiness/Proof Path/Diff/Export
- [ ] Graph proof + Cypher trace + "FalkorDB removed => breaks" (0:35) — QueryTrace; health toggle red; all views disable
- [ ] Safety (scope denial + contested rumour + abstention, 0:25) — scope_denied no content; contested double-ring; 422 abstention structured explanation
- [ ] Close (0:15) — fade out
- [ ] Pre-recording checklist completed:
  - [ ] Reset + reseed from fixture (`make seed`)
  - [ ] Hide secrets/paths/terminal history
  - [ ] Consistent dates (Oct 17/Oct 18 claims)
  - [ ] Browser zoom 100%; resolution 1920×1080 or greater

## 6. Submission Checklist Mapped to Hackathon Rules
- [ ] Public repo verified in a private window ✅ (see item 1)
- [ ] README present and complete ✅ (see item 2)
- [ ] Graph model (docs/graph-model.md) ✅
- [ ] Cypher catalogue (docs/cypher-catalog.md) ✅
- [ ] Demo video present ✅ (see item 6)
- [ ] Live deployment OR complete local instructions ✅ (see item 4)
- [ ] Track declaration: 'Agent Memory and Coordination (Track 02)' ✅
- [ ] AI disclosure ✅ (placeholders left; I will fill them)
- [ ] No secrets in repo ✅ (enforced by .gitignore + private window check)
- [ ] Synthetic data statement ✅ (stated in README security section)
- [ ] Code of Conduct acknowledged ✅ (standard open-source notice)

## 7. Project Description (150 words)
- [ ] Written; pasted below

## 8. 600-Word Blog Post Outline (for best-blog-post side prize)
- [ ] Built around 'making shared agent memory governable'
- [ ] Structured with headings; enough content to expand into a full post

---

### Project Description (150 words)

FactWeft is a governable shared agent memory system where multiple agents can propose claims, evaluate conflicts, supersede lower-authority memories, and maintain full audit trails via deterministic Cypher-driven resolution. Unlike vector-memory systems, FactWeft enforces policy-gated inclusion at read time (scope = workspace/agent_only/handoff), uses deterministic code + Cypher for all state transitions (never LLM-driven resolution), and exposes review actions (supersede/reject/keep_contested/coexist) through a consistent API with compare-and-set revision gating. The system operates on a per-workspace graph isolation model: each `workspace_id` has its own FalkorDB graph, and cross-workspace queries return 404 (memory indistinguishable from missing). Every state transition writes a Decision node, enabling full provenance reconstruction (Q_WHY_DECISIONS). The UI (React + Cytoscape.js + D3.svg) visualizes the graph and a horizontal timeline river; agents can switch, propose memories, view disputes, create handoff receipts with reason codes, and trace query history. The design is a calm dark 'mission control' aesthetic with policy-encoded colors (teal=active, amber=contested, slate=superseded, dotted=candidate). The innovation is not persistent graph memory itself, but the combination of policy-gated claim state, deterministic code-driven resolution, and reviewable receipts in a per-workspace graph architecture — making shared agent memory governable.

---

### 600-Word Blog Post Outline (for best-blog-post side prize)

**Title:** Making Shared Agent Memory Governable

**1. Introduction (80 words)**
- Problem: Multi-agent systems lack shared, governable memory
- Observation: Existing systems (Mem0, Graphiti, Letta, LangMem) don't enforce policy-gated claim state or deterministic resolution
- Solution: FactWeft — policy-gated, code-driven, receipted

**2. The Governability Stack (100 words)**
- Per-workspace graph isolation (one FalkorDB graph per workspace_id)
- Policy-gated inclusion at read time (Q_ELIGIBLE_MEMORIES)
- Deterministic resolution code + Cypher (Q6_SUPERSEDE, Q_HOLD_CANDIDATE, Q_PROMOTE_CANDIDATE)
- Review actions with compare-and-set revision gating (Q_REVIEW_*)
- Full audit trail via Decision nodes (Q_WHY_DECISIONS)
- Receipts with included/excluded memories and reason codes (Q_HANDOFF_INCLUDE/EXCLUDE)

**3. The Conflict Resolution Engine (100 words)**
- Supersede: new memory wins when higher authority + valid_from >= old valid_until
- Contested: two active memories with same predicate + different object_values + cardinality 'one'
- Corroboration: same predicate + same object_value → add SUPPORTED_BY, don't create candidate
- Scope denial at read time: agent_only / handoff / workspace gating

**4. The UI: Making Governability Visible (100 words)**
- Calm dark 'mission control' aesthetic (graphite #0B0F1A, teal #2DD4BF, amber #F59E0B, rose #F43F5E)
- Constellation graph: node/edge encoding per spec; status never conveyed by color alone (always glyph + border)
- MemoryRiver: horizontal swimlanes; ribbons with status coloring; playhead + brush/zoom; 'Showing X of Y' badge; 'Expand one hop'
- HandoffCapsule: capsule card; Included/Excluded tabs; proof path mini-graph; diff with previous; Export JSON
- AskPanel: command-bar input; staged progress ticker from /api/events; answer with citation chips; what_changed/caveats/excluded; grounding badge; proof path/handoff buttons

**5. Safety by Design (80 words)**
- Scope denial: scope_denied rows show NO content (only reason badge)
- Contested claims: double-amber ring + alert glyph in graph; Inspector status badge
- Abstention / 422: structured explanation; toast; what_changed block
- Fail-closed: if FalkorDB unavailable → 503; no local memory fallback

**6. Roadmap: From Governable to Usable (60 words)**
- MCP server for standardized agent-memory communication
- Normalization: unit/paraphrase/negation-aware conflict detection
- Retention policy: automatic expiry; revision pruning
- Vector index for semantic similarity (supplementary, not primary match)

**7. Conclusion (40 words)**
- Shared agent memory is governable when policy, provenance, and user interface are designed together
- FactWeft demonstrates this with a full-stack, open implementation
- The governability stack is extensible; the UI makes abstract rules visible and actionable

**8. Appendix: Quick-Start Commands (40 words)**
- `docker compose up -d`
- `make seed`
- `make dev`
- `npm run dev`
- `curl -s /api/health`