# Thyme

AI meal-planning agent — modular FastAPI + React/Vite scaffold for a six-person team.

- Schematic: [docs/SCHEMATIC.md](docs/SCHEMATIC.md)
- AWS Plan B (not applied yet): [docs/PLAN_B_AWS.md](docs/PLAN_B_AWS.md)

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

Terminal 1 — API:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --app-dir backend --port 8080
```

Terminal 2 — web:

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173 → **Settings** to pick Ollama or paste a personal OpenAI/Anthropic key (BYOK).

## LLM / BYOK

| Mode | Who pays | How |
|------|----------|-----|
| Ollama `qwen2.5:7b` (default) | Nobody | Local |
| OpenAI / Anthropic | The user who pasted the key | Settings → save key → Test chat |

Keys are encrypted under `backend/data/` (gitignored). On AWS (Plan B) they go to DynamoDB instead.

## Module ownership

| Area | Backend | Frontend |
|------|---------|----------|
| RAG / Understand | `backend/app/modules/rag`, `recipes` | `frontend/src/modules/rag` |
| Plan | `calendar` | `calendar` |
| Shop | `shop` | `shop` |
| Budget | `budget` | `budget` |
| Settings / BYOK | `settings`, `shared/llm.py` | `pages/Settings.tsx` |
| Shared UI | — | `components`, `pages` |

## Auth

- **Log in** is in the top nav (`/login`) — Cognito email/password  
- **Admin** (`/admin`) lists all Cognito users — only accounts in the `admins` group  
- Your admin invite went to `nathan.felix@gmail.com` (temp password in email → set a new one on first login)

## AWS (phase 1 — no hosted API)

- Static site: https://dv5md9hmzm76i.cloudfront.net  
- Backend: run on a laptop (`uvicorn`).  
- Details: [docs/PLAN_B_AWS.md](docs/PLAN_B_AWS.md)

Day-to-day: **local Vite + local API**. CloudFront hosts the UI; AI features need someone’s API running.

## CI/CD

Push to `main` (frontend changes) runs [`.github/workflows/deploy-frontend.yml`](.github/workflows/deploy-frontend.yml):

1. Build Vite app  
2. Assume IAM role `thyme-github-deploy` via GitHub OIDC  
3. Sync to S3 + invalidate CloudFront  

Repo variable required: `AWS_DEPLOY_ROLE_ARN` = `arn:aws:iam::248189945218:role/thyme-github-deploy`
