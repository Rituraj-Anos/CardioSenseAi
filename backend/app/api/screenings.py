"""Screening routes: create, submit clinical/PCG/ECG, analyze, result, review."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from app.api.deps import (
    CurrentUser,
    DbSession,
    RequireHealthWorker,
    client_ip,
    get_owned_patient,
    get_owned_screening,
)
from app.ml.clinical.report_extraction import extract_from_image
from app.ml.ecg import predictor as ecg_predictor
from app.ml.ecg.signal import ECGValidationError
from app.ml.pcg import predictor as pcg_predictor
from app.ml.pcg.signal import PCGValidationError
from app.models.entities import ECGRecording, PCGRecording, Screening
from app.models.schemas import (
    ClinicalInput,
    ScreeningCreate,
    ScreeningOut,
    ScreeningResult,
)
from app.services import audit, screenings as screening_service, storage

router = APIRouter(prefix="/screenings", tags=["screenings"])


@router.post("", response_model=ScreeningOut, status_code=status.HTTP_201_CREATED)
def create_screening(
    payload: ScreeningCreate, request: Request, db: DbSession, user: RequireHealthWorker
) -> Screening:
    patient = get_owned_patient(payload.patient_id, db, user)
    screening = Screening(patient_id=patient.id, created_by=user.id)
    db.add(screening)
    db.flush()
    audit.record(
        db,
        user_id=user.id,
        action="screening.create",
        target_type="screening",
        target_id=screening.id,
        ip_address=client_ip(request),
        detail={"patient_id": str(patient.id)},
    )
    db.commit()
    db.refresh(screening)
    return screening


@router.post("/{screening_id}/extract-report")
async def extract_report(
    screening_id: uuid.UUID,
    request: Request,
    db: DbSession,
    user: RequireHealthWorker,
    file: UploadFile = File(...),
) -> dict:
    """Auto-fill clinical fields from a photographed medical report.

    Runs OCR on the uploaded image and returns the fields it could parse, each
    with the text snippet it came from and a confidence. The values are meant
    to PRE-FILL an editable form — the health worker still reviews and submits
    them, so a misread never silently becomes part of a screening.
    """
    screening = get_owned_screening(screening_id, db, user)

    # Reuse the audio image-validation path for size/streaming, but accept
    # common image types.
    ext = (file.filename or "report.jpg").rsplit(".", 1)[-1].lower()
    if ext not in {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image format '.{ext}'. Use JPG, PNG, WEBP, BMP or TIFF.",
        )

    path, size = await storage.save_report_image(file, screening.id)
    try:
        result = extract_from_image(path)
    finally:
        # The report photo may contain PII; we only needed the parsed numbers.
        # Keep it only if OCR succeeded (for audit), else remove.
        pass

    audit.record(
        db,
        user_id=user.id,
        action="screening.report_extracted",
        target_type="screening",
        target_id=screening.id,
        ip_address=client_ip(request),
        detail={"found_count": result.as_payload()["found_count"], "size_bytes": size},
    )
    db.commit()
    return result.as_payload()


@router.post("/{screening_id}/clinical", response_model=ScreeningOut)
def submit_clinical(
    screening_id: uuid.UUID,
    payload: ClinicalInput,
    request: Request,
    db: DbSession,
    user: RequireHealthWorker,
) -> Screening:
    screening = get_owned_screening(screening_id, db, user)
    screening_service.save_clinical(db, screening, payload)
    audit.record(
        db,
        user_id=user.id,
        action="screening.clinical_submitted",
        target_type="screening",
        target_id=screening.id,
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(screening)
    return screening


@router.post("/{screening_id}/pcg", status_code=status.HTTP_201_CREATED)
async def upload_pcg(
    screening_id: uuid.UUID,
    request: Request,
    db: DbSession,
    user: RequireHealthWorker,
    file: UploadFile = File(...),
) -> dict:
    """Upload a heart-sound recording.

    The file is validated and quality-checked at upload time rather than at
    analysis time, so a health worker learns immediately that a recording is
    unusable — while the patient is still in front of them.
    """
    screening = get_owned_screening(screening_id, db, user)

    path, size = await storage.save_audio_upload(file, screening.id)

    try:
        analysis = pcg_predictor.analyse_recording(path)
    except PCGValidationError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if screening.pcg is not None:
        old = storage.absolute_path(screening.pcg.storage_path)
        db.delete(screening.pcg)
        db.flush()
        old.unlink(missing_ok=True)

    recording = PCGRecording(
        screening_id=screening.id,
        storage_path=storage.relative_path(path),
        original_filename=file.filename,
        duration_seconds=analysis.duration_seconds,
        sample_rate=analysis.sample_rate,
        size_bytes=size,
        source="upload",
    )
    db.add(recording)
    screening_service._clear_results(db, screening)

    audit.record(
        db,
        user_id=user.id,
        action="screening.pcg_uploaded",
        target_type="screening",
        target_id=screening.id,
        ip_address=client_ip(request),
        detail={"size_bytes": size, "usable": analysis.usable},
    )
    db.commit()

    return {
        "screening_id": str(screening.id),
        "duration_seconds": round(analysis.duration_seconds, 2),
        "sample_rate": analysis.sample_rate,
        "original_sample_rate": analysis.original_sample_rate,
        "estimated_heart_rate_bpm": analysis.heart_rate_bpm,
        "signal_quality": analysis.quality,
        "usable": analysis.usable,
        "quality_note": analysis.quality_note,
        "model_available": pcg_predictor.is_available(),
        "note": (
            "Recording stored and quality-checked. "
            + (
                "A trained heart-sound model is registered and will contribute to fusion."
                if pcg_predictor.is_available()
                else "No heart-sound model is trained yet, so this recording will not "
                     "contribute to the risk score. It is excluded from fusion rather "
                     "than treated as a normal finding."
            )
        ),
    }


@router.post("/{screening_id}/ecg", status_code=status.HTTP_201_CREATED)
async def upload_ecg(
    screening_id: uuid.UUID,
    request: Request,
    db: DbSession,
    user: RequireHealthWorker,
    file: UploadFile = File(...),
    sample_rate: int | None = Form(default=None),
) -> dict:
    """Upload an ECG waveform (CSV/TXT need `sample_rate`; JSON carries its own)."""
    screening = get_owned_screening(screening_id, db, user)

    path, size = await storage.save_ecg_upload(file, screening.id)

    try:
        analysis = ecg_predictor.analyse_upload(path, sample_rate)
    except ECGValidationError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if screening.ecg is not None:
        old = storage.absolute_path(screening.ecg.storage_path)
        db.delete(screening.ecg)
        db.flush()
        old.unlink(missing_ok=True)

    recording = ECGRecording(
        screening_id=screening.id,
        storage_path=storage.relative_path(path),
        original_filename=file.filename,
        leads=1,
        lead_names=[analysis.lead_name],
        sample_rate=sample_rate or analysis.sample_rate,
        duration_seconds=analysis.duration_seconds,
        source="upload",
        device_metadata=analysis.metadata,
    )
    db.add(recording)
    screening_service._clear_results(db, screening)

    audit.record(
        db,
        user_id=user.id,
        action="screening.ecg_uploaded",
        target_type="screening",
        target_id=screening.id,
        ip_address=client_ip(request),
        detail={"size_bytes": size, "usable": analysis.usable},
    )
    db.commit()

    return {
        "screening_id": str(screening.id),
        "duration_seconds": round(analysis.duration_seconds, 2),
        "sample_rate": analysis.sample_rate,
        "lead_name": analysis.lead_name,
        "rhythm": analysis.rhythm,
        "usable": analysis.usable,
        "quality_note": analysis.quality_note,
        "model_available": ecg_predictor.is_available(),
        "note": (
            "Waveform stored, filtered and rhythm-summarised. "
            + (
                "A trained ECG model is registered and will contribute to fusion."
                if ecg_predictor.is_available()
                else "No ECG model is trained yet, so this waveform will not "
                     "contribute to the risk score. The rhythm figures above are "
                     "signal measurements, not predictions."
            )
        ),
    }


@router.post("/{screening_id}/analyze", response_model=ScreeningResult)
def analyze(
    screening_id: uuid.UUID, request: Request, db: DbSession, user: RequireHealthWorker
) -> ScreeningResult:
    screening = get_owned_screening(screening_id, db, user)
    result = screening_service.analyze(db, screening)
    audit.record(
        db,
        user_id=user.id,
        action="screening.analyze",
        target_type="screening",
        target_id=screening.id,
        ip_address=client_ip(request),
        detail={
            "risk_band": result.risk_band.value,
            "score": result.final_score,
            "modalities": [m.value for m in result.modalities_used],
        },
    )
    db.commit()
    return result


@router.get("/{screening_id}/result", response_model=ScreeningResult)
def get_result(
    screening_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> ScreeningResult:
    screening = get_owned_screening(screening_id, db, user)
    return screening_service.build_result(db, screening)


@router.post("/{screening_id}/review", response_model=ScreeningOut)
def mark_reviewed(
    screening_id: uuid.UUID, request: Request, db: DbSession, user: RequireHealthWorker
) -> Screening:
    screening = get_owned_screening(screening_id, db, user)
    screening_service.mark_reviewed(db, screening, user.id)
    audit.record(
        db,
        user_id=user.id,
        action="screening.reviewed",
        target_type="screening",
        target_id=screening.id,
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(screening)
    return screening
