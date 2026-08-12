# CardioSense AI — Deployment

## Architecture

```
 Browser ──► Frontend (nginx, static SPA)  ──/api──►  Backend (FastAPI/uvicorn) ──► PostgreSQL
                                                              │
                                                              └──► object storage (local volume / S3)
```

- **Frontend**: Vite build served by nginx, which also reverse-proxies `/api` to the backend.
- **Backend**: FastAPI + uvicorn, ships the trained model artifacts in the image.
- **Database**: PostgreSQL (migrations via Alembic). SQLite is dev-only.
- **Auth**: self-hosted JWT + Argon2 (no third-party identity provider required).

## Run the whole stack locally (Docker)

```bash
cp .env.example .env
# set a strong secret:
python -c "import secrets; print('SECRET_KEY='+secrets.token_urlsafe(64))" >> .env

docker compose up --build
```

- Frontend → http://localhost:8080
- API docs → http://localhost:8000/docs

The backend container runs `alembic upgrade head` on start, then serves. Postgres
data and uploaded signals persist in named volumes (`pgdata`, `storage`).

### Seed demo data (optional)
```bash
docker compose exec backend python ../seed.py --reset
```
Or just register an account — a starter cohort is provisioned automatically.

## Database migrations (Alembic)

```bash
# from backend/, with DATABASE_URL set
alembic upgrade head                     # apply latest
alembic revision --autogenerate -m "..." # create a new migration after model changes
alembic downgrade -1                     # roll back one
```

Production does **not** auto-create tables (that path is dev-only) — schema
changes go through migrations so they are reviewable.

## Managed / cloud deployment

A cheap, reliable split that matches this repo:

| Piece | Suggested host | Notes |
|---|---|---|
| PostgreSQL | Neon / Railway / Supabase / Render | Copy the connection string into `DATABASE_URL` (use `postgresql+psycopg://…`) |
| Backend | Render / Railway / Fly.io (Docker) | Deploy `backend/Dockerfile`. Set `APP_ENV=production`, `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS` |
| Frontend | Vercel / Netlify / Nginx container | Build `frontend/`; point the API base at the backend URL (or keep the nginx `/api` proxy) |
| Object storage | Managed disk or S3/MinIO | Set `STORAGE_BACKEND=s3` + `S3_*` for durable signal storage |

### Required production env vars
```
APP_ENV=production
SECRET_KEY=<64-byte urlsafe random>     # app refuses to boot with the placeholder
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/cardiosense
CORS_ORIGINS=https://your-frontend-domain
STORAGE_LOCAL_PATH=/data/storage        # or S3_* vars
```

### Pre-flight checklist
- [ ] `SECRET_KEY` is a strong random value (not the placeholder)
- [ ] `DATABASE_URL` points at managed Postgres, not SQLite
- [ ] `alembic upgrade head` has run against the target DB
- [ ] `CORS_ORIGINS` lists only your real frontend origin(s)
- [ ] TLS terminated at the load balancer / host (HSTS is emitted in prod)
- [ ] No `.env`, planning docs, or datasets in the deployed image (see `.dockerignore`)

## CI

`.github/workflows/ci.yml` runs on every push/PR:
1. **Backend** — install deps, ruff lint, `pytest` (73 tests)
2. **Frontend** — `tsc` type-check + production build
3. **Docker** — builds both images (gated on the two test jobs)
