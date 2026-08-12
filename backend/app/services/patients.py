"""Patient service. PII is written to its own table (Blueprint Section 14)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    FusionResult,
    Patient,
    PatientPII,
    Screening,
    User,
    UserRole,
)
from app.models.schemas import PatientCreate, PatientOut, PatientSummary


def create_patient(db: Session, payload: PatientCreate, creator: User) -> Patient:
    pii = PatientPII(
        full_name=payload.full_name.strip(),
        contact=payload.contact,
        dob=payload.dob,
        address=payload.address,
    )
    db.add(pii)
    db.flush()

    patient = Patient(
        pii_ref=pii.id,
        created_by=creator.id,
        sex=payload.sex,
        age_years=payload.age_years,
        village_or_area=payload.village_or_area,
        notes=payload.notes,
    )
    db.add(patient)
    db.flush()
    return patient


def to_out(patient: Patient, include_contact: bool = False) -> PatientOut:
    return PatientOut(
        id=patient.id,
        full_name=patient.pii.full_name,
        contact=patient.pii.contact if include_contact else None,
        sex=patient.sex,
        age_years=patient.age_years,
        village_or_area=patient.village_or_area,
        created_at=patient.created_at,
    )


def _scope(stmt, user: User):
    if user.role is not UserRole.admin:
        stmt = stmt.where(Patient.created_by == user.id)
    return stmt


def list_patients(
    db: Session, user: User, *, search: str | None = None, limit: int = 100, offset: int = 0
) -> list[PatientSummary]:
    """Patient list enriched with each patient's latest risk result.

    Built as one query per aggregate rather than N+1 per row: the dashboard is
    the screen a health worker opens first and it needs to stay fast on a weak
    connection.
    """
    stmt = (
        select(Patient)
        .options(selectinload(Patient.pii))
        .order_by(Patient.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    stmt = _scope(stmt, user)
    if search:
        stmt = stmt.join(PatientPII, Patient.pii_ref == PatientPII.id).where(
            PatientPII.full_name.ilike(f"%{search.strip()}%")
        )

    patients = list(db.scalars(stmt).unique())
    if not patients:
        return []

    ids = [p.id for p in patients]

    counts = dict(
        db.execute(
            select(Screening.patient_id, func.count(Screening.id))
            .where(Screening.patient_id.in_(ids))
            .group_by(Screening.patient_id)
        ).all()
    )

    latest_rows = db.execute(
        select(
            Screening.patient_id,
            Screening.id,
            Screening.created_at,
            FusionResult.risk_band,
            FusionResult.final_score,
        )
        .join(FusionResult, FusionResult.screening_id == Screening.id)
        .where(Screening.patient_id.in_(ids))
        .order_by(Screening.patient_id, Screening.created_at.desc())
    ).all()

    latest: dict[uuid.UUID, tuple] = {}
    for row in latest_rows:
        latest.setdefault(row[0], row)

    summaries = [
        PatientSummary(
            id=p.id,
            full_name=p.pii.full_name,
            sex=p.sex,
            age_years=p.age_years,
            village_or_area=p.village_or_area,
            screening_count=int(counts.get(p.id, 0)),
            latest_screening_id=latest[p.id][1] if p.id in latest else None,
            latest_screening_at=latest[p.id][2] if p.id in latest else None,
            latest_risk_band=latest[p.id][3] if p.id in latest else None,
            latest_score=latest[p.id][4] if p.id in latest else None,
        )
        for p in patients
    ]
    return summaries


_BAND_RANK = {"high": 0, "moderate": 1, "low": 2, None: 3}


def sort_by_risk(summaries: list[PatientSummary]) -> list[PatientSummary]:
    """Risk-sorted triage queue: highest risk first, unscreened last.

    Within a band, most recent first — a health worker working a queue wants
    the newest high-risk result at the top, not the oldest.
    """
    return sorted(
        summaries,
        key=lambda s: (
            _BAND_RANK.get(s.latest_risk_band.value if s.latest_risk_band else None, 3),
            -(s.latest_score or 0.0),
            -(s.latest_screening_at.timestamp() if s.latest_screening_at else 0),
        ),
    )
