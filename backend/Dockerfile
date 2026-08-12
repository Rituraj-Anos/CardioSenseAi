# CardioSense AI — backend image
# Python 3.11 slim + the native libs the ML/audio stack needs.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FLAGS_use_mkldnn=0

# System deps:
#  - libsndfile1: soundfile / librosa (PCG audio)
#  - libgomp1: OpenMP for xgboost / scikit-learn / paddle
#  - tesseract-ocr: OCR fallback engine
#  - curl: container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 libgomp1 tesseract-ocr curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --only-binary=:all: -r requirements.txt

# App code + trained model artifacts (raw datasets are NOT copied).
COPY backend/ ./backend/
COPY ml/artifacts/ ./ml/artifacts/

WORKDIR /app/backend

# Non-root runtime user.
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Production entrypoint. APP_ENV/SECRET_KEY/DATABASE_URL supplied via env.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
