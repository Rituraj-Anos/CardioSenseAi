"""Health-worker dashboard and referral routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, select

from app.api.deps import (
    CurrentUser,
    DbSession,
    RequireHealthWorker,
    client_ip,
    get_owned_screening,
)
from app.models.entities import (
    FusionResult,
    Patient,
    Referral,
    RiskBand,
    Screening,
    ScreeningStatus,
    UserRole,
)
from app.models.schemas import (
    DashboardQueue,
    DashboardStats,
    ReferralCreate,
    ReferralOut,
)
from app.services import audit, patients as patient_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/queue", response_model=DashboardQueue)
def queue(
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> DashboardQueue:
    """Risk-sorted triage queue plus headline counts.

    Answers the question a health worker actually opens the app with: who do I
    need to see first.
    """
    scoped_patients = select(Patient.id)
    if user.role is not UserRole.admin:
        scoped_patients = scoped_patients.where(Patient.created_by == user.id)
    patient_ids = list(db.scalars(scoped_patients))

    total_patients = len(patient_ids)

    if patient_ids:
        screening_ids = select(Screening.id).where(Screening.patient_id.in_(patient_ids))
        total_screenings = int(
            db.scalar(
                select(func.count()).select_from(Screening).where(
                    Screening.patient_id.in_(patient_ids)
                )
            )
            or 0
        )
        band_counts = dict(
            db.execute(
                select(FusionResult.risk_band, func.count(FusionResult.id))
                .where(FusionResult.screening_id.in_(screening_ids))
                .group_by(FusionResult.risk_band)
            ).all()
        )
        pending_review = int(
            db.scalar(
                select(func.count())
                .select_from(Screening)
                .where(
                    Screening.patient_id.in_(patient_ids),
                    Screening.status == ScreeningStatus.analyzed,
                )
            )
            or 0
        )
        # A screening counts as multimodal only when more than one modality
        # actually contributed a score — not merely when a file was uploaded.
        multimodal = sum(
            1
            for row in db.scalars(
                select(FusionResult).where(FusionResult.screening_id.in_(screening_ids))
            )
            if len(row.modalities_used or []) > 1
        )
    else:
        total_screenings = pending_review = multimodal = 0
        band_counts = {}

    stats = DashboardStats(
        total_patients=total_patients,
        total_screenings=total_screenings,
        high_risk=int(band_counts.get(RiskBand.high, 0)),
        moderate_risk=int(band_counts.get(RiskBand.moderate, 0)),
        low_risk=int(band_counts.get(RiskBand.low, 0)),
        pending_review=pending_review,
        multimodal_screenings=multimodal,
    )

    summaries = patient_service.list_patients(db, user, limit=limit)
    return DashboardQueue(stats=stats, queue=patient_service.sort_by_risk(summaries))


@router.post("/referrals", response_model=ReferralOut, status_code=status.HTTP_201_CREATED)
def create_referral(
    payload: ReferralCreate, request: Request, db: DbSession, user: RequireHealthWorker
) -> Referral:
    screening = get_owned_screening(payload.screening_id, db, user)
    referral = Referral(
        screening_id=screening.id,
        created_by=user.id,
        refer_to=payload.refer_to,
        note=payload.note,
    )
    db.add(referral)
    db.flush()
    audit.record(
        db,
        user_id=user.id,
        action="referral.create",
        target_type="referral",
        target_id=referral.id,
        ip_address=client_ip(request),
        detail={"screening_id": str(screening.id)},
    )
    db.commit()
    db.refresh(referral)
    return referral


@router.get("/referrals", response_model=list[ReferralOut])
def list_referrals(db: DbSession, user: CurrentUser) -> list[Referral]:
    stmt = select(Referral).order_by(Referral.created_at.desc())
    if user.role is not UserRole.admin:
        stmt = stmt.where(Referral.created_by == user.id)
    return list(db.scalars(stmt))


@router.get("/dashboard/trends")
def trends(db: DbSession, user: CurrentUser, days: int = 30) -> dict:
    """Aggregates for the dashboard charts.

    All computed from real screening rows scoped to this worker — the charts
    reflect actual pipeline output, not sample data.
    """
    from datetime import UTC, datetime, timedelta

    scoped_patients = select(Patient.id)
    if user.role is not UserRole.admin:
        scoped_patients = scoped_patients.where(Patient.created_by == user.id)
    patient_ids = list(db.scalars(scoped_patients))

    if not patient_ids:
        return {"risk_distribution": [], "daily": [], "recent": []}

    screenings = list(
        db.scalars(
            select(Screening)
            .where(Screening.patient_id.in_(patient_ids))
            .order_by(Screening.created_at.desc())
        )
    )

    # Risk distribution across all analysed screenings.
    dist = {"low": 0, "moderate": 0, "high": 0}
    for s in screenings:
        if s.fusion is not None:
            dist[s.fusion.risk_band.value] += 1

    # Daily screening volume + high-risk count over the window.
    cutoff = datetime.now(UTC) - timedelta(days=days)
    buckets: dict[str, dict[str, int]] = {}
    for s in screenings:
        created = s.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created < cutoff:
            continue
        key = created.date().isoformat()
        b = buckets.setdefault(key, {"date": key, "screenings": 0, "high": 0})  # type: ignore
        b["screenings"] += 1
        if s.fusion is not None and s.fusion.risk_band.value == "high":
            b["high"] += 1

    daily = sorted(buckets.values(), key=lambda b: b["date"])

    # Recent activity feed.
    recent = []
    for s in screenings[:8]:
        if s.fusion is None:
            continue
        patient = db.get(Patient, s.patient_id)
        recent.append(
            {
                "screening_id": str(s.id),
                "patient_id": str(s.patient_id),
                "patient_name": patient.pii.full_name if patient else "Unknown",
                "risk_band": s.fusion.risk_band.value,
                "score": s.fusion.final_score,
                "created_at": s.created_at.isoformat(),
            }
        )

    return {
        "risk_distribution": [
            {"band": k, "count": v} for k, v in dist.items()
        ],
        "daily": daily,
        "recent": recent,
    }


@router.get("/dashboard/insights")
def insights(db: DbSession, user: CurrentUser) -> dict:
    """Cohort-level clinical aggregates, computed from real screening data.

    Powers the Insights page: prevalence of key risk factors, average vitals by
    risk band, and an age-band breakdown. Every number is derived from the
    worker's actual patients — no sample data.
    """
    from app.models.entities import ClinicalMeasurement

    scoped_patients = select(Patient.id)
    if user.role is not UserRole.admin:
        scoped_patients = scoped_patients.where(Patient.created_by == user.id)
    patient_ids = list(db.scalars(scoped_patients))
    if not patient_ids:
        return {"total": 0, "risk_factors": [], "by_age_band": [], "avg_by_band": []}

    # Join latest clinical measurements with their fusion result.
    rows = db.execute(
        select(ClinicalMeasurement, FusionResult)
        .join(Screening, Screening.id == ClinicalMeasurement.screening_id)
        .join(FusionResult, FusionResult.screening_id == Screening.id)
        .where(Screening.patient_id.in_(patient_ids))
    ).all()

    total = len(rows)
    if total == 0:
        return {"total": 0, "risk_factors": [], "by_age_band": [], "avg_by_band": []}

    # Prevalence of clinically meaningful risk factors.
    def pct(n: int) -> float:
        return round(100 * n / total, 1)

    risk_factors = [
        {"factor": "Hypertension (BP ≥ 140)", "prevalence": pct(sum(1 for c, _ in rows if c.trestbps >= 140))},
        {"factor": "High cholesterol (≥ 240)", "prevalence": pct(sum(1 for c, _ in rows if c.chol >= 240))},
        {"factor": "Elevated fasting sugar", "prevalence": pct(sum(1 for c, _ in rows if c.fbs == 1))},
        {"factor": "Exercise-induced angina", "prevalence": pct(sum(1 for c, _ in rows if c.exang == 1))},
        {"factor": "ST depression > 1.0", "prevalence": pct(sum(1 for c, _ in rows if c.oldpeak > 1.0))},
        {"factor": "Any major vessel finding", "prevalence": pct(sum(1 for c, _ in rows if c.ca > 0))},
    ]

    # Age-band breakdown with risk mix.
    bands = {"<45": [], "45-59": [], "60+": []}
    for c, f in rows:
        key = "<45" if c.age < 45 else ("45-59" if c.age < 60 else "60+")
        bands[key].append(f.risk_band.value)
    by_age_band = [
        {
            "band": k,
            "count": len(v),
            "high": v.count("high"),
            "moderate": v.count("moderate"),
            "low": v.count("low"),
        }
        for k, v in bands.items()
    ]

    # Average vitals by risk band (shows the model's inputs separate cleanly).
    avg_by_band = []
    for rb in ("low", "moderate", "high"):
        subset = [c for c, f in rows if f.risk_band.value == rb]
        if subset:
            avg_by_band.append(
                {
                    "band": rb,
                    "count": len(subset),
                    "avg_age": round(sum(c.age for c in subset) / len(subset), 1),
                    "avg_bp": round(sum(c.trestbps for c in subset) / len(subset), 1),
                    "avg_chol": round(sum(c.chol for c in subset) / len(subset), 1),
                    "avg_max_hr": round(sum(c.thalach for c in subset) / len(subset), 1),
                }
            )

    return {
        "total": total,
        "risk_factors": risk_factors,
        "by_age_band": by_age_band,
        "avg_by_band": avg_by_band,
    }
