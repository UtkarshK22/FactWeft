# Deployment

## (a) Fully Tested Local Path (Guaranteed Baseline)

The local Docker Compose path is the guaranteed baseline for the hackathon submission. All environment variables, container images, and start-up sequences are verified against the `Makefile` and `docker-compose.yml`.

### Prerequisites

- [ ] Docker Desktop / Docker Engine v20.10+
- [ ] Docker Compose v2+ (plugin; `docker compose` not `docker-compose`)
- [ ] Node.js v18+ + npm v10+ (for frontend dev server)
- [ ] Python v3.10+ + `pip` (for backend)
- [ ] ~2GB free disk space for FalkorDB container

### Startup Sequence (verified order)

```bash
# 1. Start FalkorDB (graph database)
docker compose up -d

# 2. Wait for FalkorDB to be ready
# (check: docker compose logs falkordb | grep -i "ready\|listening")

# 3. Seed the demo workspace (idempotent; safe to re-run)
make seed

# 4. Start the backend (FastAPI + uvicorn)
make dev
#   -> runs: uvicorn app.main --reload --host 0.0.0.0 --port 8000
#   -> serves on http://localhost:8000
#   -> automatic reload on source changes

# 5. In a separate terminal, start the frontend
cd frontend
npm run dev
#   -> Vite dev server on http://localhost:5173 (or :5174 if 5173 is occupied)
#   -> proxies API calls to http://localhost:8000 via Vite dev server config

# 6. Verify the system is operational
curl -s http://localhost:8000/api/health
# Expected: {"api":"ok","falkordb":"ok","graph_seeded":true,"llm_mode":"fixture"}

curl -s http://localhost:8000/api/me
# Expected: {"workspace_id":"demo_atlas_release_lab","agent_id":"agent_planner","role":"planner",
#            "graph_name":"ws_demo_atlas_release_lab","demo_mode":true,"llm_mode":"fixture"}
```

### Local Makefile Targets (verified)

| Target | Command | Description |
|---|---|---|
| `make seed` | `python -m app.memory.seed` | Idempotent seed; creates workspace, 2 agents, 5 concepts, 8 sources, 3 episodes, 1 procedure with 3 steps, 5 memories |
| `make dev` | `cd backend && python -m app.main --reload` | Backend dev server |
| `make frontend` | `cd frontend && npm run dev` | Frontend dev server |
| `make test` | `cd backend && python -m pytest tests/` | Run backend integration tests (if available) |
| `make lint` | `cd backend && oxlint .` | Run linter on backend source |
| `make docker-run` | `docker compose up -d && make seed && make dev` | One-command local setup (start FalkorDB, seed, start backend) |

### Local Environment Variables (verified in `backend/.env`)

```env
DEMO_WORKSPACE_ID=demo_atlas_release_lab
SECOND_WORKSPACE_ID=demo_orbit_ops
FAULKORDB_ENDPOINT=falkordb:9142
FAULKORDB_USER=falkordb
FAULKORDB_PASSWORD=falkordb
SECRET_KEY=local-dev-key-must-change-for-production
API_PREFIX=/api
CORS_ORIGINS=http://localhost:5173,http://localhost:5174
DEMO_MODE=true          # <- must be true for fixture LLM mode
LLM_MODE=fixture        # <- mock answers; do not change to live without API keys
```

### Local Troubleshooting (verified fixes)

| Symptom | Fix |
|---|---|
| `503 on /api/health` | `docker compose ps`; ensure FalkorDB container is `Up`; check `docker compose logs falkordb` |
| `404 on /api/memories/{id}` | Run `make seed` to re-seed; verify memory is in current workspace (`demo_atlas_release_lab`); per-workspace isolation means memories in other workspaces return 404 |
| `409 on review` | Fetch current revision from `GET /api/memories/{id}`; retry review once with correct revision |
| `422 on propose` | Verify workspace/agent/source/concept exist in graph; `make seed` re-seeds everything |
| Frontend won't connect to backend | Ensure both `docker compose up -d` and `npm run dev` are running; Vite proxies to `http://localhost:8000` by default |
| CORS error on first load | Verify `CORS_ORIGINS` includes `http://localhost:5173` and `http://localhost:5174` in `backend/.env` |

### Local Demo Walkthrough (same as video script, but interactive)

1. Open http://localhost:5173; verify health green; agent switcher has 5 options
2. Click "Seed" → workspace populated
3. Propose memory as Planner → see active ribbon in MemoryRiver; Inspector opens
4. Switch to Scout → 403 toast; switch back to Planner → works
5. Propose second memory → supersession visible (dashed slate ribbon + connector with reason code)
6. Ask canonical question → answer with citation chips; click chip → memory selected in graph
7. Open HandoffCapsule → view Included/Excluded tabs; proof path mini-graph; Export JSON
8. Open QueryTrace drawer → view recent Cypher queries; filter by request ID
9. Toggle FalkorDB off (in another terminal: `docker compose restart falkordb` or stop container) → health goes red; all memory views disable; Ask returns 503
10. Restore FalkorDB → health green; everything re-enables

## (b) Optional Live Deploy

### Frontend on Vercel / Netlify / Cloudflare Pages

1. Build the frontend:
   ```bash
   cd frontend
   npm run build   # creates dist/ with static assets
   ```
2. Deploy:
   - **Vercel:** `vercel` (or connect repo; auto-deploy on push)
   - **Netlify:** Drag `dist/` folder to Netlify Drop; or `netlify deploy`
   - **Cloudflare Pages:** `npx wrangler pages deploy dist/`
3. Set environment variables in the deploy platform:
   - `VITE_API_PREFIX=/api` (or keep default)
   - `VITE_DEMO_WORKSPACE_ID=demo_atlas_release_lab`
4. The deployed URL becomes the frontend endpoint.

### API on Render / Fly / Railway

1. Deploy the FastAPI backend:
   - **Render:** New Web Service; Python; `pip install -r requirements.txt`; start command: `uvicorn app.main --host 0.0.0.0 --port $PORT`
   - **Fly:** `fly launch`; `fly deploy`; `fly scale count 1`
   - **Railway:** New project; deploy `backend/` directory; set start command
2. Set environment variables in the platform:
   ```env
   DEMO_WORKSPACE_ID=demo_atlas_release_lab
   FAULKORDB_ENDPOINT=falkordb-cloud-hostname:9142   # FalkorDB Cloud or VM
   FAULKORDB_USER=falkordb
   FAULKORDB_PASSWORD=falkordb_password
   SECRET_KEY=prod-secret-key
   API_PREFIX=/api
   CORS_ORIGINS=https://your-frontend-domain.vercel.app  # must match deployed frontend
   DEMO_MODE=true          # keep true for fixture mode; set false for live LLM
   LLM_MODE=fixture        # or live if LLM provider configured
   ```
3. The deployed API URL becomes the backend endpoint.

### FalkorDB Cloud or Small VM with Auth

- **FalkorDB Cloud:** Sign up at `falkordb.com`; create a cluster; note the connection string (host:port); enable auth (username/password); the port must **NOT** be publicly open — it should be on a private network or require VPN.
- **Small VM (self-hosted):** 
  - `docker run -d -p 9142:9142 -e FAULKORDB_AGENT=falkordb -e FAULKORDB_PASSWORD=falkordb graphaware/falkordb`
  - Or deploy via Kubernetes/Docker Compose on a VM (e.g., DigitalOcean, Hetzner)
  - Firewall: only allow inbound from the API server's IP; do NOT map port 9142 to public internet
  - The API backend (FastAPI) must be on the same network/VFR as FalkorDB, or reachable via secure tunnel

### CORS and Token Configuration for Live Deploy

| Component | Env Var | Required Value | Notes |
|---|---|---|---|
| Frontend (Vite) | `VITE_API_PREFIX` | `/api` | Must match backend `API_PREFIX` |
| Frontend (Vite) | `VITE_DEMO_WORKSPACE_ID` | `demo_atlas_release_lab` | Used by components to fetch correct workspace data |
| Backend (FastAPI) | `CORS_ORIGINS` | `https://your-frontend-domain.vercel.app` (or comma-separated list) | Must include deployed frontend URL; do NOT use `*` in production |
| Backend (FastAPI) | `DEMO_MODE` | `true` (fixture) or `live` | `true` = mock answers; `live` = real LLM provider |
| Backend (FastAPI) | `LLM_MODE` | `fixture` or `live` | `fixture` = pre-composed answers; `live` = passes to LLM provider |
| Backend (FastAPI) | `SECRET_KEY` | Any strong string | Used for JWT/signing; change from default for production |
| API Auth | Bearer token | Injected from agent switcher; stored in localStorage `factweft_token` | No changes needed if same-origin; if cross-origin, ensure cookie/Storage access |

### Free Tier Notes

- **Vercel/Netlify/Cloudflare Pages:** Free tiers include auto-generated SSL; reasonable cold-start (1–3 sec from sleep). The demo should "warm up" first: `curl -s https://your-domain.vercel.app/api/health` before recording.
- **Render/Fly/Railway:** Free tiers include VM always-on or auto-sleep; if the VM sleeps, the first request after wake-up may take 2–5 sec (cold start). Warm up with `curl /api/health`.
- **FalkorDB Cloud free tier:** Small shared cluster; may have rate limits; ensure the demo sequence doesn't exceed query quota. FalkorDB Cloud clusters sleep after inactivity; warm up with `curl /api/health` before recording.
- **No vector DB:** The system does not use a vector DB. Semantic claim matching is not implemented; all matching is predicate + object_value string equality.

## (c) Fallback: Local Stack with Tunnel (If Deployment Fails)

If the live deploy fails (CORS, FalkorDB connectivity, port restrictions), use a tunnel to expose the local stack.

### Cloudflare Tunnel (recommended)

1. Install Cloudflare Tunnel: `npm install -g cloudflared` or use the Docker container
2. Start the local stack (same as local path):
   ```bash
   docker compose up -d
   make seed
   make dev   # backend on localhost:8000
   cd frontend && npm run dev  # frontend on localhost:5173
   ```
3. Create the tunnel:
   ```bash
   cloudflared tunnel run --url http://localhost:5173 --url http://localhost:8000
   ```
4. Cloudflare generates public URLs like `https://abc123.trycloudflare.com` (frontend) and `https://def456.trycloudflare.com` (API).
5. Update CORS:
   - In `backend/.env`: `CORS_ORIGINS=https://abc123.trycloudflare.com`
   - Restart backend: `make dev` (or `kill uvicorn; uvicorn app.main --reload`)
6. Test: open frontend URL; verify health green; agent switcher works; FalkorDB connected.

### ngrok (alternative)

1. Install ngrok: `npm install -g ngrok` or `brew install ngrok`
2. Start local stack as above.
3. Create tunnels:
   ```bash
   ngrok http 5173    # frontend URL: https://abc123.ngrok.io
   ngrok http 8000    # API URL: https://def456.ngrok.io
   ```
4. Update CORS in `backend/.env`:
   ```env
   CORS_ORIGINS=https://abc123.ngrok.io
   ```
5. Restart backend.
6. Test as above.

### Tunnel Checklist

- [ ] Cloudflare Tunnel or ngrok running; public URLs generated
- [ ] `backend/.env` `CORS_ORIGINS` updated to include frontend tunnel URL
- [ ] Backend restarted after CORS change
- [ ] Frontend loads at tunnel URL; health indicator green
- [ ] Agent switcher works; bearer token injection functional
- [ ] Ask panel posts to API; receives answers
- [ ] MemoryRiver renders; Constellation graphs
- [ ] QueryTrace drawer shows Cypher entries
- [ ] HandoffCapsule renders; Export JSON works
- [ ] FalkorDB connectivity: `curl -s https://tunnel-url/api/health` returns `falkordb: "ok"`
- [ ] No secrets exposed in screen recording (verify tunnel URLs don't contain passwords)
- [ ] Record demo video from the tunnel URL

### CORS Troubleshooting for Deploy/Tunnel

| Problem | Cause | Fix |
|---|---|---|
| Browser console: `CORS header 'Access-Control-Allow-Origin' missing` | `CORS_ORIGINS` not set to frontend URL; using `*` in production (blocked) | Set `CORS_ORIGINS` to exact frontend URL (deployed or tunnel); never `*` in production |
| Browser console: `blocked by CORS: No 'Access-Control-Allow-Origin' header is present on the requested resource` | Same as above; also check that the API route doesn't have custom CORS middleware that overrides FastAPI defaults | Ensure `app.add_middleware(CORSMiddleware, ...)` in `app/main.py` includes the correct origins |
| 401 after agent switcher change | Token not sent or invalid; check that `Authorization: Bearer <token>` header is formed correctly | Verify `setBearerToken(token)` in `lib/api.ts`; check localStorage `factweft_token` |
| Health green but API returns 503 | FalkorDB not reachable from tunnel/VM; port 9142 not accessible | Ensure FalkorDB is on same network as API; if cloud, ensure cluster allows inbound from API host; if local Docker, ensure `docker compose up -d` and ports are mapped |

## Summary: Deployment Paths

| Path | Effort | Cost | FalkorDB | Best For |
|---|---|---|---|---|
| **Local Docker Compose** | Low (1 command) | Free (local only) | Local FalkorDB container | Hackathon baseline; guaranteed to work |
| **Live Deploy (Vercel + Render + FalkorDB Cloud)** | Medium (3 platforms) | Free tier (subject to quotas) | FalkorDB Cloud or self-hosted VM | Submission when local not possible; need internet |
| **Tunnel (Cloudflare/ngrok)** | Low (after local setup) | Free (local only) | Local FalkorDB | Fallback when live deploy fails but internet access available |

**Never open FalkorDB port 9142 to the public internet.** Always use tunnels, VPN, or FalkorDB Cloud with auth. The API backend and frontend must be on the same network as FalkorDB, or reachable via secure tunnel only.