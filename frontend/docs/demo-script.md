# Demo Video Script (3:30)

## Shot List & Click Path (Exact UI Matching)

| Time | Action | Expected UI Output |
|---|---|---|
| **0:20 — Problem** | | |
| 0:20 | Open browser; navigate to http://localhost:5173 (or deployed URL) | Vite dev shell loads; graphite `#0B0F1A` background; top bar appears with workspace name, agent switcher, LLM mode badge ("fixture"), Demo menu, health indicator (green), Fixture/Live badge |
| 0:20 | Verify health indicator is green | Banner at top-right: "Graph connected — recall available" (polling every 3s) |
| 0:20 | Observe agent switcher | 5 agent chips: Planner, Coordinator, Scout, Verifier, Owner; default agent = Planner |
| 0:20 | Observe top bar components | Workspace name ("Atlas Release Lab"), LLM mode badge ("fixture"), Demo menu (Seed, Reset, Session 1/2, Ask canonical), health indicator, Fixture/Live badge |
| **0:35 — Session 1 Write** | | |
| 0:35 | Click agent switcher → select "Scout" → observe 403 toast | Toast: "Access denied" / "Asking as Scout returns 403 - insufficient permissions"; bearer token cleared from localStorage |
| 0:35 | Click agent switcher → select "Planner" → observe working state | Toast: "Working" / "Asking as Planner works - full permissions"; bearer token injected |
| 0:35 | Click "Seed" demo button | Toast: "Workspace seeded"; FalkorDB graph populated; health shows `graph_seeded: true` |
| 0:35 | Propose first memory (Session 1): use Ask panel → canonical question "What is the status of the release freeze claim?" → Send | Answer displays with citations `[mem_abc1]`; MemoryRiver swimlane appears with one ribbon (active, teal); Inspector opens with summary/predicate/value/confidence/scope/chips; Decision node visible in graph proof |
| 0:35 | State after Session 1 | Playback shows: "Session 1 write complete"; active ribbon in river; claim selected in graph; Inspector shows full details; `asOfMs` = null (all memories visible) |
| **0:35 — Session 2 Supersession** | | |
| 0:35 | Propose second memory (Session 2): use Ask panel → canonical question "Compare the Oct 17 and Oct 18 claims" → Send | Answer displays; MemoryRiver: two ribbons — Oct 17 claim (active teal), Oct 18 claim (superseded, dashed slate); badge "Showing 2 of Y related nodes"; "Expand one hop" action available on selected node; Constellation graph: Oct 18 claim double-ringed (contested) or dashed (superseded) linked by SUPERSEDES edge |
| 0:35 | State after Session 2 | Playback shows: "Session 2 supersession visible"; dashed slate ribbon ending exactly where successor begins; small curved connector labelled with reason code; Oct 17 claim active; Oct 18 claim superseded |
| **0:45 — Planner Question + Handoff Receipt** | | |
| 0:45 | Ask as Planner: canonical Atlas question → "Show me the decision evidence" → Send | Answer displays with inline citation chips `[mem_abc1]` `[mem_def2]`; clicking a chip selects that memory in the graph (zustand `selectedMemoryId` updates); Inspector for that memory opens; "What changed" block shows added/removed/changed claims; Caveats list with reason codes; Excluded list with reason codes; Grounding badge: "verified citations"; Buttons: "Show proof path" and "Open handoff" |
| 0:45 | Click "Open handoff" button | HandoffCapsule renders: capsule card with sender→receiver avatars + animated hand-off line; task displayed; token estimate vs budget bar; Included tab with claim cards (title, authority, "click-to-inspect"); Excluded tab with reason badges (superseded_by_newer_supported_claim, contested, scope_denied, expired, unpromoted_candidate); Caveats tab; Readiness step checklist with satisfied/blocked/unknown icons; Proof Path mini-graph (Source→Claim→Decision→Answer); "Diff with previous handoff" picker; Export JSON button |
| 0:45 | Handoff receipt details visible | Included: memory title + authority; Excluded: reason code only (no content for scope_denied); Readiness: step "Resolve concepts" ✅, step "Check scope" ⚠️, step "Run readiness" ❓; Token estimate: 245 / budget: 1000 |
| **0:35 — Graph Proof + Cypher Trace + "FalkorDB Removed => Breaks"** | | |
| 0:35 | Click "Show proof path" in AskPanel | Modal opens: Source → Claim → Decision → Answer; labeled spans with teal/amber/violet/rose circles; Close button returns to AskPanel |
| 0:35 | Open QueryTrace drawer | Drawer opens: live list of recent graph operations; name, read/write badge, duration, rows, timestamp; expanding shows syntax-highlighted Cypher with params and result summary; filter by request ID; "FalkorDB powers this" header with graph name and connection state |
| 0:35 | Toggle FalkorDB off (health check) | Health indicator flips red: "Graph disconnected — recall unavailable"; all memory views disable with banner; Ask panel: POST /api/ask returns 503; Ask as Planner → 503 error toast; "FalkorDB is unavailable. FactWeft does not serve memory data from a local copy; retry once the graph is back." |
| 0:35 | Restore FalkorDB | Health flips green; memory views re-enable; Ask works again |
| **0:25 — Safety** | | |
| 0:25 | Scope denial demo | HandoffCapsule Excluded tab: scope_denied rows show NO content — just reason badge; "No content" placeholder |
| 0:25 | Contested rumour demo | Constellation graph: rumour claim double-ringed (contested) with alert glyph (!); hovering shows tooltip "Contested — double amber ring + alert icon"; Inspector: status badge = contested; reason code displayed |
| 0:25 | Abstention / 422 demo | Ask as Scout → 403 toast; Ask as Planner with abstention-prone question → answer includes "abstain" or "unable" structured explanation; toast: "Abstention — The agent was unable to answer the question"; what_changed block shows added/removed/changed; caveats and excluded lists present |
| **0:15 — Close** | | |
| 0:15 | Fade to black; show "Demo complete" | |

## Pre-Recording Checklist

- [ ] **Reset + reseed from fixture:** `make seed` (idempotent; clears and re-seeds `demo_atlas_release_lab`)
- [ ] **Hide secrets/paths/terminal history:** No FalkorDB passwords, no API keys, no internal file paths visible in screen recording
- [ ] **Consistent dates:** Oct 17 claim (valid_from = 1723459200000 = Oct 17 2024), Oct 18 claim (valid_from = 1723545600000 = Oct 18 2024); all demo data uses these dates
- [ ] **Browser zoom:** 100%; **Resolution:** 1920×1080 or greater (graph components are width-sensitive)
- [ ] **Clean localStorage:** Clear browser localStorage to avoid stale Zustand state; or run `make seed` fresh
- [ ] **Agent switcher pre-seeded:** Agent chips load with correct default (Planner); 403/working flow is deterministic
- [ ] **Health check green:** `curl -s http://localhost:8000/api/health` returns `falkordb: "ok"` and `graph_seeded: true`
- [ ] **No LLM rate-limit issues:** LLM_MODE=fixture (mock answers); if live mode, ensure API keys are set and not rate-limited
- [ ] **Audio narration script prepared:** Time each shot to 0:20 / 0:35 / 0:45 / 0:25 / 0:15 boundaries