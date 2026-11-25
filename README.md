# Thyme

AI meal-planning agent — modular FastAPI + React/Vite scaffold for a six-person team.

- Schematic: [docs/SCHEMATIC.md](docs/SCHEMATIC.md)
- AWS Plan B: [docs/PLAN_B_AWS.md](docs/PLAN_B_AWS.md)

## Setup

### Backend

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
copy .env.example .env
```

### Frontend

```powershell
cd frontend
npm install
```

### Ollama (laptop testing)

Same as 590R-AI labs — default model `qwen2.5:7b`:

```powershell
ollama pull qwen2.5:7b
```

## Run locally

From the repo root (venv already created & deps installed):

Terminal 1 — API:

```powershell
npm start
```

Terminal 2 — web:

```powershell
npm run web
```

Or from `frontend/`: `npm run dev`.

Open http://localhost:5173 → **Find** to search recipes, **Upload** to add files/web previews, **AI** for Ollama vs BYOK, or **Profile** for theme / allergies.

> On some Windows setups port `8080` hits WinError 10013; this repo’s Vite proxy targets `8765`.

## LLM / BYOK

| Mode | Who pays | How |
|------|----------|-----|
| Ollama `qwen2.5:7b` (default) | Nobody | Local |
| OpenAI / Anthropic | The user who pasted the key | AI settings → save key → Test chat |

**AI settings** has a default provider plus optional per-task overrides (web cleanup, summarize, suggest sides, scale, upload segmentation). **Profile** holds theme, units, default servings, and always-exclude allergies.

Keys are encrypted under `backend/data/` (gitignored). On AWS (Plan B) they go to DynamoDB instead.

**Auth:** Find / recipes / search require Cognito sign-in (`THYME_ALLOW_ANON=false` by default). Without a Bearer token the API returns 401.

**Recipe storage locally:** JSON files under `backend/data/recipes/` + Chroma under `backend/data/chroma/` — **not** DynamoDB. DynamoDB `thyme-recipes` is used only when `THYME_ENV=aws`.

## Tests

```powershell
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pytest backend\tests
```

## LLM Phase 1 — filter-driven recipe RAG (non-agentic)

Not a chatbot:

1. **Upload** (`/upload`): add recipes from a PDF/TXT file, or run a filtered **web** search (Tavily) and add previews you want
2. Recipes are embedded into **local Chroma** (`backend/data/chroma/`)
3. **Find** (`/find`): search **only your library** — hard filters + embedding similarity (`include_web: false`)

Env (see `.env.example`):

| Variable | Purpose |
|----------|---------|
| `RECIPES_TABLE` | DynamoDB table when `THYME_ENV=aws` (default `thyme-recipes`) |
| `CHROMA_DIR` | Local Chroma path (default `backend/data/chroma`) |
| `TAVILY_API_KEY` | Required only if “also search the web” is on |
| `EMBEDDING_MODEL` | Default `sentence-transformers/all-MiniLM-L6-v2` |

**Naming:** “AWS phase 1” = static site + Cognito + DynamoDB (no hosted API). “LLM Phase 1” = this filter RAG feature. Agentic multi-tool planning is later.

## Module ownership

| Area | Backend | Frontend |
|------|---------|----------|
| RAG / Find | `backend/app/modules/rag`, `recipes` | `frontend/src/modules/rag` |
| Plan | `calendar` | `calendar` |
| Shop | `shop` | `shop` |
| Budget | `budget` | `budget` |
| AI settings / BYOK | `settings`, `shared/llm.py` | `pages/AiSettings.tsx` |
| Profile | `settings` | `pages/Profile.tsx` |
| Shared UI | — | `components`, `pages` |

## Auth

- **Log in** is in the top nav (`/login`) — Cognito email/password  
- **Admin** (`/admin`) lists Cognito users and can grant/revoke the `admins` group  

- Your admin invite went to `nathan.felix@gmail.com` (temp password in email → set a new one on first login)

## AWS (phase 1 — no hosted API)

- Static site: https://dv5md9hmzm76i.cloudfront.net  
- Backend: run on a laptop (`uvicorn`).  
- Details: [docs/PLAN_B_AWS.md](docs/PLAN_B_AWS.md)

Day-to-day: **local Vite + local API**. CloudFront hosts the UI; AI features need someone’s API running.

### Production via laptop tunnel ($0)

CloudFront has no API. To make the live site work, expose your local API with a free Cloudflare quick tunnel and publish the URL in `api-config.json` (the frontend reads that at runtime).

1. Deploy a frontend build that includes the `api-config.json` loader (push the tunnel-related frontend changes once).
2. Terminal A — API:
   ```powershell
   npm start
   ```
3. Terminal B — tunnel (requires `cloudflared` + AWS CLI credentials that can write the web bucket):
   ```powershell
   npm run tunnel
   ```
4. Wait for the CloudFront invalidation (~10–60s), then use https://dv5md9hmzm76i.cloudfront.net

The tunnel script uploads only `api-config.json` to S3 (no full rebuild). When you stop the tunnel (Ctrl+C), it clears `apiBase` so the site doesn’t keep pointing at a dead URL.

```powershell
winget install Cloudflare.cloudflared   # once
aws sts get-caller-identity             # confirm AWS CLI works
```

Optional: `.\scripts\tunnel.ps1 -SkipPublish` prints a tunnel URL without touching S3.

## CI/CD

Push to `main` (frontend changes) runs [`.github/workflows/deploy-frontend.yml`](.github/workflows/deploy-frontend.yml):

1. Build Vite app  
2. Assume IAM role `thyme-github-deploy` via GitHub OIDC  
3. Sync to S3 + invalidate CloudFront  

Repo variable required: `AWS_DEPLOY_ROLE_ARN` = `arn:aws:iam::248189945218:role/thyme-github-deploy`
