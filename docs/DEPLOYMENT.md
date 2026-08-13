# CardioSense AI — Deployment Guide

**Stack: Railway (backend + PostgreSQL) · Vercel (frontend).** Full feature set,
including live report-OCR — Railway gives enough RAM for the ML stack.

```
 Browser ──► Vercel (React SPA) ──/api (proxied)──► Railway (FastAPI + models) ──► Railway Postgres
```

> **Time:** ~20 minutes. Accounts: **GitHub**, **Railway**, **Vercel** (all free, GitHub sign-in).
> **Cost:** Railway's free trial credit (~$5/mo) covers a demo comfortably. Watch usage in the dashboard.

---

## Part 1 — Backend + database on Railway · ~12 min

### 1.1 Create the project
1. Go to **https://railway.app** → sign in with GitHub.
2. **New Project ➜ Deploy from GitHub repo** → pick **`CardioSenseAi`**.
3. Railway detects `railway.json` and builds **`backend/Dockerfile`**. Let the first build run (~8–12 min — it installs the ML stack).

### 1.2 Add PostgreSQL
1. In the project → **New ➜ Database ➜ Add PostgreSQL**. Railway provisions it instantly.

### 1.3 Set the backend variables
1. Click the **backend service** → **Variables** tab → add:

   | Variable | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `SECRET_KEY` | run `python -c "import secrets;print(secrets.token_urlsafe(64))"` and paste |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` ← Railway reference; type it exactly |
   | `CORS_ORIGINS` | leave blank for now (filled in Part 3) |

   > `${{Postgres.DATABASE_URL}}` auto-links to the database you just added. The app
   > normalises the `postgresql://` URL to the driver it needs.

### 1.4 Expose a public URL
1. Backend service → **Settings ➜ Networking ➜ Generate Domain**.
2. Copy the URL, e.g. `https://cardiosense-backend-production.up.railway.app`.
3. Verify:
   - `https://<url>/health` → `{"status":"ok","env":"production"}`
   - `https://<url>/docs` → API docs

Migrations run automatically on boot (`alembic upgrade head`), so the schema is created for you.

---

## Part 2 — Frontend on Vercel · ~5 min

1. In the repo, edit **`frontend/vercel.json`** and replace the placeholder with your Railway URL:
   ```json
   "destination": "https://cardiosense-backend-production.up.railway.app/api/:path*"
   ```
   Commit and push.
2. **https://vercel.com** → sign in with GitHub → **Add New ➜ Project** → import **`CardioSenseAi`**.
3. Important settings:
   - **Root Directory** → **`frontend`**  ← the app lives in a subfolder
   - Framework: **Vite** (auto-detected); build/output come from `vercel.json`
4. **Deploy** → you get e.g. `https://cardio-sense-ai.vercel.app`.

The rewrite proxies `/api/*` to Railway, keeping the app **same-origin** so the secure login/refresh cookies work.

---

## Part 3 — Connect them (CORS) · ~2 min

1. Railway → backend service → **Variables** → set:
   ```
   CORS_ORIGINS = https://cardio-sense-ai.vercel.app
   ```
   (your exact Vercel URL, **no trailing slash**) → Railway redeploys.

**Done.** Open the Vercel URL → register (auto-populated with demo patients) → run a screening → try uploading a report photo (first OCR use downloads model weights, ~30s, then cached).

---

## Environment variables (reference)

| Variable | Where | Value |
|---|---|---|
| `APP_ENV` | Railway | `production` |
| `SECRET_KEY` | Railway | 64-char random (app refuses to boot in prod with the placeholder) |
| `DATABASE_URL` | Railway | `${{Postgres.DATABASE_URL}}` |
| `CORS_ORIGINS` | Railway | your Vercel URL |
| `ENABLE_OCR_WARMUP` | optional | `true` (default) — Railway has the RAM |
| `PROVISION_DEMO_DATA` | optional | `true` (default) — new accounts get a starter cohort |

---

## Verification checklist

- [ ] Railway `/health` returns `ok`
- [ ] `/docs` loads
- [ ] Vercel URL loads the marketing site
- [ ] Register → redirected to a **populated** dashboard
- [ ] Run a screening → risk band + explanation appear
- [ ] Upload a report photo → fields auto-fill
- [ ] `CORS_ORIGINS` exactly matches the Vercel URL (no trailing slash)

## Troubleshooting

| Symptom | Fix |
|---|---|
| Login fails / CORS error | `CORS_ORIGINS` must match the Vercel URL exactly, no trailing slash |
| `/api` 404 on Vercel | `destination` in `vercel.json` still has the placeholder, or Root Directory isn't `frontend` |
| Build fails on Railway | Check **Deploy Logs**; confirm `railway.json` points at `backend/Dockerfile` |
| DB connection error | Ensure `DATABASE_URL=${{Postgres.DATABASE_URL}}` and the Postgres plugin is in the same project |
| Credit running low | Railway dashboard shows usage; the service can be paused between demos |

---

## Alternatives

- **Neon** for a longer-lived free Postgres: skip Railway's DB, set `DATABASE_URL` to the Neon string instead.
- **Self-host (fully free, always-on):** `docker compose up --build` on any machine + a free **Cloudflare Tunnel** to expose it.

## Local / self-hosted (Docker)

```bash
cp .env.example .env
python -c "import secrets; print('SECRET_KEY='+secrets.token_urlsafe(64))" >> .env
docker compose up --build
# frontend → http://localhost:8080   ·   API → http://localhost:8000/docs
```
