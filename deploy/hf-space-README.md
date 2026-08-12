---
title: CardioSense AI Backend
emoji: 🫀
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# CardioSense AI — Backend API

FastAPI service powering CardioSense AI: multimodal cardiovascular screening
(clinical + heart-sound + ECG) with explainable, calibrated risk scores and
lab-report OCR auto-fill.

- Health check: `/health`
- Interactive API docs: `/docs`

> A screening aid, not a diagnosis. Every result includes explicit uncertainty.

## Configuration

Set these as **Repository secrets** in the Space settings:

| Secret | Value |
|---|---|
| `SECRET_KEY` | a strong 64-char random string |
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `CORS_ORIGINS` | your Vercel frontend URL |
| `APP_ENV` | `production` |
