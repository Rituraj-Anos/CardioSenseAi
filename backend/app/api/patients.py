"""Patient routes. All reads are scoped to the requesting health worker."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request, status

from app.api.deps import (
    CurrentUser,
    DbSession,
    RequireHealthWorker,
    client_ip,
    get_owned_patient,
)
from app.models.entities import FusionResult, Modality, Screening
from app.models.schemas import (
    PatientCreate,
    PatientDetail,
    PatientOut,
    PatientSummary,
    ScreeningHistoryItem,
)
from app.services import audit, patients as patient_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate, request: Request, db: DbSession, user: RequireHealthWorker
) -> PatientOut:
    patient = patient_service.create_patient(db, payload, user)
    audit.record(
        db,
        user_id=user.id,
        action="patient.create",
        target_type="patient",
        target_id=patient.id,
        ip_address=client_ip(request),
    )
    db.commit()
    db.refresh(patient)
    return patient_service.to_out(patient, include_contact=True)


@router.get("", response_model=list[PatientSummary])
def list_patients(
    db: DbSession,
    user: CurrentUser,
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[PatientSummary]:
    return patient_service.list_patients(
        db, user, search=search, limit=limit, offset=offset
    )


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(
    patient_id: uuid.UUID, request: Request, db: DbSession, user: CurrentUser
) -> PatientDetail:
    patient = get_owned_patient(patient_id, db, user)

    # Reading a patient's clinical history is an auditable event, not just a GET.
    audit.record(
        db,
        user_id=user.id,
        action="patient.read",
        target_type="patient",
        target_id=patient.id,
        ip_address=client_ip(request),
        commit=True,
    )

    history = []
    for screening in patient.screenings:
        fusion: FusionResult | None = screening.fusion
        history.append(
            ScreeningHistoryItem(
                id=screening.id,
                created_at=screening.created_at,
                status=screening.status,
                risk_band=fusion.risk_band if fusion else None,
                final_score=fusion.final_score if fusion else None,
                modalities_used=(
                    [Modality(m) for m in fusion.modalities_used] if fusion else []
                ),
            )
        )

    return PatientDetail(
        patient=patient_service.to_out(patient, include_contact=True), screenings=history
    )
