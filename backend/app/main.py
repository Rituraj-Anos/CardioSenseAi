"""FastAPI application entrypoint."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, dashboard, patients, screenings
from app.core.config import settings
from app.core.db import engine
from app.core.logging import configure_logging, get_logger, request_id_ctx
from app.ml.clinical.predictor import get_clinical_predictor
from app.ml.ecg import predictor as ecg_predictor
from app.ml.models_status import modality_status  # noqa: F401  (re-exported helper)
from app.ml.pcg import predictor as pcg_predictor
from app.models.base import Base

configure_logging(settings.log_level, json_output=not settings.is_dev)
log = get_logger("cardiosense")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: create tables directly. Staging/production go through
    # Alembic migrations instead, so schema changes are reviewable.
    if settings.is_dev:
        Base.metadata.create_all(bind=engine)
        log.info("schema_ensured", mode="create_all", env=settings.app_env)

    settings.storage_root.mkdir(parents=True, exist_ok=True)

    # Warm the clinical model so the first real request is not the slow one.
    predictor = get_clinical_predictor()

    # Warm the OCR document parser in a BACKGROUND thread — loading the engine
    # takes ~20-25s and must not block app startup. The first report upload
    # before it finishes will simply load it on demand. Skipped on low-RAM
    # hosts (set ENABLE_OCR_WARMUP=false) so boot doesn't OOM.
    if settings.enable_ocr_warmup:
        import threading

        from app.ml.clinical.report_extraction import warm_up as warm_ocr

        threading.Thread(target=warm_ocr, name="ocr-warmup", daemon=True).start()

    log.info(
        "startup",
        app=settings.app_name,
        env=settings.app_env,
        clinical_model=predictor.artifact.version if predictor else None,
        pcg_model=pcg_predictor.is_available(),
        ecg_model=ecg_predictor.is_available(),
    )
    yield
    log.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Multimodal cardiovascular screening and clinical decision support. "
        "This API returns screening risk estimates with explicit uncertainty. "
        "It does not diagnose."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a trace ID to every request and its logs (Blueprint Section 31)."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_ctx.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["x-request-id"] = rid
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if not settings.is_dev:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log the detail, return a generic message.

    Stack traces and driver errors must not reach a client of a health API —
    they leak schema and dependency versions.
    """
    log.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. The incident has been logged."},
    )


api_prefix = settings.api_v1_prefix
app.include_router(auth.router, prefix=api_prefix)
app.include_router(patients.router, prefix=api_prefix)
app.include_router(screenings.router, prefix=api_prefix)
app.include_router(dashboard.router, prefix=api_prefix)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


@app.get(f"{api_prefix}/system/models", tags=["meta"])
def models() -> dict:
    """Which modalities can actually contribute a score right now.

    Exposed deliberately: the frontend uses it to label absent modalities
    honestly instead of showing an empty state that looks like a normal result.
    """
    return modality_status()


@app.get(f"{api_prefix}/system/model-card", tags=["meta"])
def model_card() -> dict:
    """Real, published evaluation metrics for the clinical model.

    Read straight from the trained artifact's manifest — the numbers the model
    was actually evaluated at, not marketing figures. Powers the Methodology
    page so the product can show its working.
    """
    from app.ml.model_card import build_model_card

    return build_model_card()
