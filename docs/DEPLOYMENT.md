# CardioSense AI — Deployment Guide

**100% free stack, full features (including live report OCR):**

| Piece | Host | Free tier | Why |
|---|---|---|---|
| **Frontend** | **Vercel** | unlimited hobby | Built for Vite SPAs |
| **Backend** | **Hugging Face Spaces** (Docker) | **16GB RAM / 2 vCPU** | Only free host with enough RAM for the ML stack + OCR |
| **Database** | **Neon** | 0.5GB, always-on | Serverless Postgres, doesn't expire |

```
 Browser ──► Vercel (React SPA) ──/api (proxied)──► HF Space (FastAPI + models) ──► Neon Postgres
```

> **Time:** ~25 minutes. Accounts needed: **GitHub**, **Hugging Face**, **Vercel**, **Neon** (all free, all GitHub sign-in).

---

## Part 1 — Database (Neon) · ~3 min

1. Go to **https://neon.tech** → sign in with GitHub → **Create project**.
2. Name it `cardiosense`, pick the region closest to you → **Create**.
3. On the dashboard, copy the **connection string**. It looks like:
   ```
   postgresql://user:pass@ep-xxx-yyy.aws.neon.tech/neondb?sslmode=require
   ```
4. Save it — you'll paste it into the Space in Part 2.

> The app auto-normalises this URL to the driver it needs, so paste it exactly as Neon gives it.

---

## Part 2 — Backend (Hugging Face Space) · ~15 min

### 2.1 Create the Space
1. Go to **https://huggingface.co** → sign in → **New ➜ Space**.
2. Fill in:
   - **Space name**: `cardiosense-backend`
   - **License**: MIT
   - **SDK**: **Docker** → template **Blank**
   - **Hardware**: *CPU basic (free)*
   - **Visibility**: Public
3. **Create Space**.

### 2.2 Add the secrets
In the Space → **Settings** → **Variables and secrets** → add each as a **Secret**:

| Name | Value |
|---|---|
| `SECRET_KEY` | run `python -c "import secrets;print(secrets.token_urlsafe(64))"` and paste |
| `DATABASE_URL` | the Neon connection string from Part 1 |
| `APP_ENV` | `production` |
| `CORS_ORIGINS` | leave blank for now — filled in Part 4 |

### 2.3 Push the code to the Space
The Space is its own git repo. From your machine:

```bash
# clone the app repo if you don't have it
git clone https://github.com/Rituraj-Anos/CardioSenseAi.git
cd CardioSenseAi

# clone the (empty) Space repo next to it
cd ..
git clone https://huggingface.co/spaces/<YOUR-HF-USERNAME>/cardiosense-backend
cd cardiosense-backend

# copy in what the backend needs
cp -r ../CardioSenseAi/backend ./backend
cp -r ../CardioSenseAi/ml ./ml
cp ../CardioSenseAi/backend/Dockerfile.hfspace ./Dockerfile
cp ../CardioSenseAi/deploy/hf-space-README.md ./README.md

git add -A
git commit -m "Deploy CardioSense backend"
git push
```

> On Windows PowerShell, use `Copy-Item -Recurse ..\CardioSenseAi\backend .\backend` instead of `cp -r`.
> If push asks for a password, use a **HF access token** (huggingface.co → Settings → Access Tokens → *write* role).

### 2.4 Wait for the build
The Space shows **Building** (~8–12 min — it installs the ML stack). When it goes **Running**, your API is at:
```
https://<YOUR-HF-USERNAME>-cardiosense-backend.hf.space
```
Verify:
- `https://<...>.hf.space/health` → `{"status":"ok","env":"production"}`
- `https://<...>.hf.space/docs` → interactive API docs

Migrations run automatically on boot, so the Neon schema is created for you.

---

## Part 3 — Frontend (Vercel) · ~5 min

1. In the **CardioSenseAi** repo, edit **`frontend/vercel.json`** and replace the placeholder with your real Space URL:
   ```json
   "destination": "https://YOUR-HF-USERNAME-cardiosense-backend.hf.space/api/:path*"
   ```
   Commit and push.
2. Go to **https://vercel.com** → sign in with GitHub → **Add New ➜ Project**.
3. Import **`CardioSenseAi`**.
4. Important settings:
   - **Root Directory** → **`frontend`**  ← the app lives in a subfolder
   - Framework: **Vite** (auto-detected); build/output come from `vercel.json`
5. **Deploy** → you get e.g. `https://cardio-sense-ai.vercel.app`.

The rewrite proxies `/api/*` to the Space, keeping the app **same-origin** so the secure login/refresh cookies work.

---

## Part 4 — Connect them (CORS) · ~2 min

1. HF Space → **Settings** → **Variables and secrets** → set:
   ```
   CORS_ORIGINS = https://cardio-sense-ai.vercel.app
   ```
   (your exact Vercel URL, **no trailing slash**)
2. The Space restarts automatically.

**Done.** Open the Vercel URL → register an account (auto-populated with demo patients) → run a screening.

---

## Environment variables (reference)

| Variable | Where | Value |
|---|---|---|
| `SECRET_KEY` | HF Space secret | 64-char random (app refuses to boot in production with the placeholder) |
| `DATABASE_URL` | HF Space secret | Neon connection string |
| `APP_ENV` | HF Space secret | `production` |
| `CORS_ORIGINS` | HF Space secret | your Vercel URL |
| `ENABLE_OCR_WARMUP` | optional | `true` (default) — the free Space has RAM for it |
| `PROVISION_DEMO_DATA` | optional | `true` (default) — new accounts get a starter cohort |

---

## Verification checklist

- [ ] `/health` on the Space returns `ok`
- [ ] `/docs` loads
- [ ] Vercel URL loads the marketing site
- [ ] Register → redirected to a **populated** dashboard
- [ ] Run a screening → risk band + explanation appear
- [ ] Upload a report photo → fields auto-fill (first use downloads OCR weights, ~30s)
- [ ] `CORS_ORIGINS` exactly matches the Vercel URL

## Troubleshooting

| Symptom | Fix |
|---|---|
| Login fails / CORS error | `CORS_ORIGINS` must match the Vercel URL exactly, no trailing slash |
| `/api` 404 on Vercel | The `destination` in `vercel.json` still has the placeholder, or Root Directory isn't `frontend` |
| Space build fails | Check the Space **Logs** tab; ensure `Dockerfile` (from `Dockerfile.hfspace`) is at the Space root |
| DB connection error | Re-copy the Neon string; keep `?sslmode=require` |
| First OCR scan is slow | Expected — model weights download once, then cached |

---

## Local / self-hosted alternative (Docker)

```bash
cp .env.example .env
python -c "import secrets; print('SECRET_KEY='+secrets.token_urlsafe(64))" >> .env
docker compose up --build
# frontend → http://localhost:8080   ·   API → http://localhost:8000/docs
```
