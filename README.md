<div align="center">

# 🫀 CardioSense AI

### Multimodal cardiovascular screening & decision support for low-resource settings

*Scan a report. Fuse the signals. Get a calibrated, explainable heart-risk read — in seconds.*

[![CI](https://github.com/Rituraj-Anos/CardioSenseAi/actions/workflows/ci.yml/badge.svg)](https://github.com/Rituraj-Anos/CardioSenseAi/actions/workflows/ci.yml)
![Backend](https://img.shields.io/badge/backend-FastAPI%20%C2%B7%20Python%203.11-0E6E64)
![Frontend](https://img.shields.io/badge/frontend-React%2018%20%C2%B7%20TypeScript%20%C2%B7%20Vite-3B82C4)
![Tests](https://img.shields.io/badge/tests-73%20backend%20%C2%B7%2018%20frontend-12866F)
![License](https://img.shields.io/badge/license-MIT-475467)

</div>

---

> **A screening aid, not a diagnosis.** Every result carries an explicit confidence level and the reasoning behind it. Only a qualified clinician can diagnose or rule out heart disease — and CardioSense says so on every result.

---

## ✨ What it does

CardioSense turns the data a frontline health worker actually has into an honest cardiovascular risk signal:

1. **📷 Scan** — photograph a lab/clinical report; OCR reads the values and pre-fills the intake form (no manual typing of 13 fields).
2. **🧠 Analyse** — a validated model weighs **13 clinical signals**, and — when available — **heart sound (PCG)** and **ECG** recordings, into one calibrated estimate.
3. **📋 Explain** — the result shows the risk band, a confidence level, the exact factors that drove it, and a clear recommendation.

The whole system is built around **graceful degradation**: a clinical-only screening is a *full, valid result* — missing modalities are excluded and the weights renormalised, never assumed normal.

---

## 🎬 The experience

| | |
|---|---|
| **Marketing site** | Scroll-driven story: scan → predict → explain, with a live report-scan animation |
| **Intake wizard** | Report auto-fill → editable, range-checked clinical form → optional PCG/ECG upload |
| **Result screen** | Radial risk gauge, confidence meter, SHAP explanation, per-modality contribution |
| **Dashboard** | Risk-sorted triage queue, cohort insights, model methodology, clinical reference |

---

## 🧪 The models (honest numbers)

Every metric below is from the project's **own held-out evaluation** on public research datasets. Full reports live in [`docs/eval/`](docs/eval).

| Modality | Data | Model | ROC-AUC | Sensitivity | Notes |
|---|---|---|---|---|---|
| **Clinical** | UCI Cleveland (303) | Random Forest (calibrated) | **0.889** | **1.00** | Threshold tuned for recall — a missed high-risk patient is the costly error |
| **Heart sound (PCG)** | PhysioNet CinC-2016 (669) | RF on MFCC + spectral features | **0.806** | 0.855 | Classical model; CNN is the documented upgrade path |
| **ECG** | MIT-BIH (single-lead) | XGBoost on rhythm features | **0.943** | 0.869 | Split **by record** — no subject leaks across train/test |
| **Fusion** | — | Late (decision-level) | — | — | Weights renormalise over present modalities |

> ⚠️ These are research datasets, not the target population. Absolute risk needs local validation before deployment — this is stated in-product, not hidden.

---

## 🏗️ Architecture

```
                    React SPA (Vite + Tailwind)
                    marketing · auth · dashboard · intake · results
                                   │  REST/JSON (HTTPS)
                                   ▼
                    FastAPI (modular monolith)
        auth · patients · screenings · fusion · explain · dashboard
                                   │
        ┌──────────────┬───────────┴───────────┬───────────────┐
        ▼              ▼                        ▼               ▼
   Clinical ML     PCG model               ECG model      Report OCR
   (SHAP)          (heart sound)           (rhythm)       (PaddleOCR)
        └──────────────┴───────────┬───────────┴───────────────┘
                                   ▼
        PostgreSQL (PII isolated · audit-logged)   +   Object storage (raw signals)
```

**Design principles**
- 🔒 PII lives in its own table; ML & audit paths reference `patient_id` only
- 🧾 Append-only audit log on every state change and clinical-data read
- 🧩 Modular monolith — the ML layer sits behind service interfaces, ready to split out
- ♿ Explainability + uncertainty are first-class, never bolted on

---

## 🛠️ Tech stack

**Backend** · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · Argon2 + JWT · scikit-learn · XGBoost · SHAP · librosa · wfdb · PaddleOCR
**Frontend** · React 18 · TypeScript · Vite · Tailwind · TanStack Query · Zustand · Motion · Recharts · Vitest
**Ops** · Docker · docker-compose · GitHub Actions

---

## 🔐 Security

- **Argon2** password hashing with transparent rehash-on-login
- **JWT** access tokens (15 min) + refresh token in an **httpOnly** cookie
- **Account lockout** after repeated failures + **rate limiting** on auth endpoints
- **Strong password policy** with a live, server-backed strength meter
- **RBAC** + per-creator row-level scoping (404, not 403, to avoid leaking existence)
- Security headers, generic error responses (no stack-trace leakage), secrets via env only

---

## 🚀 Quick start

### Option A — Docker (full stack)

```bash
cp .env.example .env
python -c "import secrets; print('SECRET_KEY='+secrets.token_urlsafe(64))" >> .env
docker compose up --build
```

- Frontend → http://localhost:8080 · API docs → http://localhost:8000/docs

### Option B — local dev

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # (Windows)
pip install -r requirements.txt
python seed.py --reset                               # demo data
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

**Demo login** · `asha@cardiosense.demo` / `demo-pass-2026`
Or register a new account — it's provisioned with a realistic starter cohort automatically.

---

## 🧫 Retrain the models

```bash
python ml/clinical/train.py            # UCI Cleveland (ships with repo)
python ml/pcg/download_data.py         # fetch CinC-2016 heart sounds
python ml/pcg/train.py
python ml/ecg/train.py                 # auto-downloads MIT-BIH via wfdb
```

Each writes a versioned artifact + `manifest.json` + an eval report to `docs/eval/`.

---

## ✅ Testing

```bash
cd backend && pytest tests -q          # 73 tests
cd frontend && npm run test            # 18 tests
```

Also see [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md) for the full 137-case plan and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for cloud deployment.

---

## 📁 Structure

```
cardiosense/
├── backend/            FastAPI app, ML inference, Alembic migrations, tests
│   └── app/{api,services,ml,models,core}
├── frontend/           React SPA (marketing + clinical app), Vitest
├── ml/                 training scripts + registered model artifacts
├── docs/               eval reports, test plan, deployment guide
├── docker-compose.yml
└── .github/workflows/  CI
```

---

## ⚖️ Disclaimer

CardioSense AI is a **decision-support and screening tool for research and demonstration**. It does not provide a medical diagnosis and must not be used as a substitute for professional clinical judgement.

<div align="center">

Built for screening where specialist care is hardest to reach.

</div>
