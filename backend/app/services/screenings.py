"""Screening orchestration: run whatever modalities are present, then fuse.

This is where graceful degradation actually happens (Blueprint Section 20). The
rules, in order of importance:

1. A modality is included only if it has data AND a working model. Data without
   a model is reported as "recorded, not analysed" — never silently counted as
   a normal finding, which would be the dangerous failure mode.
2. If a modality's model raises at inference time, the screening still returns a
   result from the remaining modalities and the failure is recorded. A model
   service being down must not deny a health worker a clinical-only result.
3. If no modality can produce a score, the request fails loudly. A screening
   with no signal behind it is not a result.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ml.clinical.predictor import get_clinical_predictor
from app.ml.ecg import predictor as ecg_predictor
from app.ml.fusion.engine import DISCLAIMER, ModalityScore, fuse
from app.ml.pcg import predictor as pcg_predictor
from app.ml.registry import ModelNotAvailable
from app.models.entities import (
    ClinicalMeasurement,
    Explanation,
    FusionResult,
    Modality,
    ModelPrediction,
    RiskBand,
    Screening,
    ScreeningStatus,
)
from app.models.schemas import (
    ClinicalInput,
    ExplanationOut,
    PredictionOut,
    ScreeningResult,
)

log = get_logger(__name__)


# --------------------------------------------------------------------------
# Clinical intake
# --------------------------------------------------------------------------
def save_clinical(db: Session, screening: Screening, payload: ClinicalInput) -> ClinicalMeasurement:
    existing = screening.clinical
    data = payload.model_dump()

    if existing is not None:
        for key, value in data.items():
            setattr(existing, key, value)
        measurement = existing
    else:
        measurement = ClinicalMeasurement(**data)
        # Assign through the relationship so screening.clinical is populated
        # immediately in this session — not just on the next fresh load.
        measurement.screening = screening
        screening.clinical = measurement
        db.add(measurement)

    # New clinical data invalidates any previous analysis for this screening.
    _clear_results(db, screening)
    screening.status = ScreeningStatus.ready
    db.flush()
    return measurement


def _clear_results(db: Session, screening: Screening) -> None:
    """Drop stale predictions when inputs change.

    Leaving an old fusion result attached to changed inputs would show a health
    worker a risk score that no longer corresponds to the data on screen.

    Mutation goes through the relationships (not bare `db.delete` plus
    reassignment) so the in-memory object graph and the database agree. Setting
    `screening.fusion = None` while separately inserting a new row leaves the
    relationship cached as None, which is how a freshly analysed screening ends
    up looking unanalysed.
    """
    for prediction in list(screening.predictions):
        db.delete(prediction)
    screening.predictions.clear()

    if screening.fusion is not None:
        db.delete(screening.fusion)
        screening.fusion = None

    db.flush()
    db.expire(screening, ["predictions", "fusion"])


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------
def analyze(db: Session, screening: Screening) -> ScreeningResult:
    if screening.clinical is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Clinical measurements are required before analysis. Clinical data "
                "is the one modality this tool always needs."
            ),
        )

    _clear_results(db, screening)

    scores: list[ModalityScore] = []
    skipped: list[dict[str, str]] = []

    # ---- clinical ----
    clinical_result = _run_clinical(db, screening)
    if clinical_result is not None:
        scores.append(clinical_result)
    else:
        skipped.append(
            {
                "modality": "clinical",
                "reason": "No trained clinical model is registered.",
            }
        )

    # ---- pcg ----
    if screening.pcg is not None:
        outcome = _run_pcg(db, screening)
        if isinstance(outcome, ModalityScore):
            scores.append(outcome)
        else:
            skipped.append({"modality": "pcg", "reason": outcome})

    # ---- ecg ----
    if screening.ecg is not None:
        outcome = _run_ecg(db, screening)
        if isinstance(outcome, ModalityScore):
            scores.append(outcome)
        else:
            skipped.append({"modality": "ecg", "reason": outcome})

    if not scores:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No model was available to analyse this screening. Train the "
                "clinical model (python ml/clinical/train.py) before running analysis."
            ),
        )

    outcome = fuse(scores)

    fusion_row = FusionResult(
        final_score=outcome.final_score,
        risk_band=RiskBand(outcome.risk_band),
        confidence=outcome.confidence,
        modalities_used=list(outcome.modalities_used),
        weights=outcome.weights,
        recommendation=outcome.recommendation,
        uncertainty_note=_augment_uncertainty(outcome.uncertainty_note, skipped),
        fusion_version=outcome.fusion_version,
    )
    # Assigned through the relationship so the in-memory graph is correct
    # immediately, without needing a refresh round-trip.
    screening.fusion = fusion_row
    screening.status = ScreeningStatus.analyzed
    db.flush()

    log.info(
        "screening_analyzed",
        screening_id=str(screening.id),
        risk_band=outcome.risk_band,
        score=outcome.final_score,
        modalities=outcome.modalities_used,
        skipped=[s["modality"] for s in skipped],
    )

    return build_result(db, screening)


def _augment_uncertainty(note: str, skipped: list[dict[str, str]]) -> str:
    if not skipped:
        return note
    detail = "; ".join(f"{s['modality']}: {s['reason']}" for s in skipped)
    return (
        f"{note} Data was present but not analysed for — {detail} "
        f"Unanalysed modalities were excluded from the score, not assumed normal."
    )


def _run_clinical(db: Session, screening: Screening) -> ModalityScore | None:
    predictor = get_clinical_predictor()
    if predictor is None:
        return None

    features = {
        c: getattr(screening.clinical, c)
        for c in (
            "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
            "thalach", "exang", "oldpeak", "slope", "ca", "thal",
        )
    }
    try:
        result = predictor.predict(features)
    except Exception as exc:  # pragma: no cover - defensive
        log.error("clinical_inference_failed", error=str(exc))
        return None

    prediction = ModelPrediction(
        screening_id=screening.id,
        modality=Modality.clinical,
        model_version=result.model_version,
        score=result.score,
        confidence=result.confidence,
        threshold=result.threshold,
    )
    db.add(prediction)
    db.flush()

    if result.top_factors:
        db.add(
            Explanation(
                prediction_id=prediction.id,
                method=result.explanation_method,
                top_factors=result.top_factors,
                base_value=result.base_value,
            )
        )
        db.flush()

    return ModalityScore("clinical", result.score, result.confidence)


def _run_pcg(db: Session, screening: Screening) -> ModalityScore | str:
    from app.services.storage import absolute_path

    try:
        result = pcg_predictor.predict(absolute_path(screening.pcg.storage_path))
    except ModelNotAvailable as exc:
        log.info("pcg_model_unavailable", screening_id=str(screening.id))
        return (
            "no trained heart-sound model is registered yet, so the recording was "
            "stored and quality-checked but not scored"
        )
    except Exception as exc:  # pragma: no cover
        log.error("pcg_inference_failed", error=str(exc))
        return f"heart-sound analysis failed ({exc})"

    prediction = ModelPrediction(
        screening_id=screening.id,
        modality=Modality.pcg,
        model_version=result.model_version,
        score=result.score,
        confidence=result.confidence,
        threshold=result.threshold,
    )
    db.add(prediction)
    db.flush()
    if result.top_factors:
        db.add(
            Explanation(
                prediction_id=prediction.id,
                method=result.explanation_method,
                top_factors=result.top_factors,
            )
        )
        db.flush()
    return ModalityScore("pcg", result.score, result.confidence)


def _run_ecg(db: Session, screening: Screening) -> ModalityScore | str:
    from app.ml.ecg.signal import from_upload
    from app.services.storage import absolute_path

    try:
        ecg = from_upload(
            absolute_path(screening.ecg.storage_path), screening.ecg.sample_rate
        )
        result = ecg_predictor.predict(ecg)
    except ModelNotAvailable:
        log.info("ecg_model_unavailable", screening_id=str(screening.id))
        return (
            "no trained ECG model is registered yet, so the waveform was stored "
            "and rhythm-summarised but not scored"
        )
    except Exception as exc:  # pragma: no cover
        log.error("ecg_inference_failed", error=str(exc))
        return f"ECG analysis failed ({exc})"

    prediction = ModelPrediction(
        screening_id=screening.id,
        modality=Modality.ecg,
        model_version=result.model_version,
        score=result.score,
        confidence=result.confidence,
        threshold=result.threshold,
    )
    db.add(prediction)
    db.flush()
    return ModalityScore("ecg", result.score, result.confidence)


# --------------------------------------------------------------------------
# Result assembly
# --------------------------------------------------------------------------
def build_result(db: Session, screening: Screening) -> ScreeningResult:
    # Queried rather than read off the relationship so a stale identity-map
    # entry cannot make an analysed screening look unanalysed.
    fusion = db.scalar(
        select(FusionResult).where(FusionResult.screening_id == screening.id)
    )
    if fusion is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This screening has not been analysed yet. POST to /analyze first.",
        )

    predictions = db.scalars(
        select(ModelPrediction).where(ModelPrediction.screening_id == screening.id)
    ).all()

    per_modality = [
        PredictionOut(
            modality=p.modality,
            model_version=p.model_version,
            score=round(p.score, 4),
            confidence=round(p.confidence, 4),
            threshold=p.threshold,
            explanation=(
                ExplanationOut(
                    method=p.explanation.method,
                    base_value=p.explanation.base_value,
                    top_factors=p.explanation.top_factors,
                )
                if p.explanation is not None
                else None
            ),
        )
        for p in predictions
    ]

    return ScreeningResult(
        screening_id=screening.id,
        patient_id=screening.patient_id,
        status=screening.status,
        created_at=screening.created_at,
        final_score=fusion.final_score,
        risk_band=fusion.risk_band,
        confidence=fusion.confidence,
        modalities_used=[Modality(m) for m in fusion.modalities_used],
        weights=fusion.weights or {},
        recommendation=fusion.recommendation,
        uncertainty_note=fusion.uncertainty_note,
        fusion_version=fusion.fusion_version,
        per_modality=per_modality,
        disclaimer=DISCLAIMER,
    )


def mark_reviewed(db: Session, screening: Screening, reviewer_id: uuid.UUID) -> Screening:
    screening.status = ScreeningStatus.reviewed
    screening.reviewed_by = reviewer_id
    screening.reviewed_at = datetime.now(UTC)
    db.flush()
    return screening
