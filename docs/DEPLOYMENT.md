# CardioSense AI — Deployment Guide

Free-tier deployment: **frontend on Vercel · backend on Render · PostgreSQL on Render (or Neon)**.

```
 Browser ──► Vercel (React SPA)  ──/api (proxied)──►  Render (FastAPI + models)  ──►  PostgreSQL
```

> **Time:** ~20–30 minutes. You'll need free accounts on **GitHub**, **Render**, and **Vercel**.
> **Note on OCR:** the report-scan (OCR) feature needs >1GB RAM. On Render's free 512MB plan it's turned off (everything else — clinical/PCG/ECG screening, dashboard — works). To enable live OCR, use a Render **Starter** instance or Hugging Face Spaces (see the end).

---

## Part 1 — Backend + database on Render (one-click Blueprint)

The repo ships a `render.yaml`, so Render provisions the web service **and** the database automatically.

1. Go to **https://render.com** → sign in with GitHub.
2. **New ➜ Blueprint**.
3. Select the **`CardioSenseAi`** repository → **Apply**.
4. Render reads `render.yaml` and creates:
   - `cardiosense-backend` (Docker web service)
   - `cardiosense-db` (free PostgreSQL)
   - a strong `SECRET_KEY` (auto-generated) and `DATABASE_URL` (auto-wired)
5. Wait for the first build (~5–10 min; it installs the ML stack). When it shows **Live**, copy the backend URL — it looks like:
   ```
   https://cardiosense-backend.onrender.com
   ```
6. Test it: open `https://<your-backend>.onrender.com/health` → should return `{"status":"ok",...}`
   and `https://<your-backend>.onrender.com/docs` for the API docs.

Migrations run automatically on boot (`alembic upgrade head`), so the schema is created for you.

> ⏸️ Render's free web service **sleeps after 15 min idle** and takes ~30s to wake on the next request. That's normal for free tier.

---

## Part 2 — Frontend on Vercel

1. Edit **`frontend/vercel.json`** in the repo and replace the placeholder with your real Render backend URL:
   ```json
   "destination": "https://cardiosense-backend.onrender.com/api/:path*"
   ```
   Commit + push this change.
2. Go to **https://vercel.com** → sign in with GitHub → **Add New ➜ Project**.
3. Import the **`CardioSenseAi`** repo.
4. In the import settings:
   - **Root Directory** → set to **`frontend`** (important — the app lives in a subfolder)
   - Framework preset: **Vite** (auto-detected)
   - Build command / output are read from `vercel.json` (`npm run build` → `dist`)
5. Click **Deploy**. After ~2 min you get a URL like `https://cardiosense-ai.vercel.app`.

The `vercel.json` rewrite proxies `/api/*` to your backend, so the app stays **same-origin** — which keeps the secure login/refresh cookies working.

---

## Part 3 — Wire the two together (CORS)

1. Back in **Render** → `cardiosense-backend` → **Environment**.
2. Set **`CORS_ORIGINS`** to your Vercel URL (no trailing slash):
   ```
   CORS_ORIGINS=https://cardiosense-ai.vercel.app
   ```
3. Save → Render redeploys automatically.

Done. Open your Vercel URL, register an account (it auto-populates with demo patients), and run a screening.

---

## Environment variables (reference)

Set on the **backend** host (Render sets the first three for you via the Blueprint):

| Variable | Value | Set by |
|---|---|---|
| `APP_ENV` | `production` | Blueprint |
| `SECRET_KEY` | strong random (64+ chars) | Blueprint (auto) |
| `DATABASE_URL` | Postgres connection string | Blueprint (auto) |
| `CORS_ORIGINS` | your Vercel URL | **you** (Part 3) |
| `ENABLE_OCR_WARMUP` | `false` on 512MB, `true` if ≥1GB | Blueprint |
| `PROVISION_DEMO_DATA` | `true` | Blueprint |

`DATABASE_URL` accepts `postgres://…`, `postgresql://…`, or `postgresql+psycopg://…` — the app normalises it automatically.

---

## Using Neon for Postgres instead (optional, more durable)

Render's free DB expires after ~30 days. For a longer-lived free database use **Neon**:

1. Create a project at **https://neon.tech** → copy the connection string.
2. In `render.yaml`, remove the `databases:` block and the `fromDatabase` mapping, and instead set `DATABASE_URL` in the Render dashboard to the Neon string.

---

## Enabling live OCR (optional)

The report-scan feature needs more RAM than the 512MB free plan. Two options:

- **Render Starter** ($7/mo, 512MB→2GB): set `ENABLE_OCR_WARMUP=true`.
- **Hugging Face Spaces (free, 16GB RAM)**: create a **Docker Space**, push `backend/Dockerfile`, add `app_port: 8000` to the Space README front-matter, and set the same env vars. Then point `vercel.json` at the Space URL.

Everything except OCR works fully on the free 512MB plan.

---

## Local / self-hosted (Docker)

```bash
cp .env.example .env
python -c "import secrets; print('SECRET_KEY='+secrets.token_urlsafe(64))" >> .env
docker compose up --build
# frontend → http://localhost:8080   ·   API → http://localhost:8000/docs
```

## Verify a deployment

- [ ] `GET /health` returns `ok`
- [ ] `/docs` loads (API is up)
- [ ] Frontend loads; register → dashboard is populated
- [ ] Run a screening → result shows risk band + explanation
- [ ] `CORS_ORIGINS` matches the frontend URL exactly (no trailing slash)
