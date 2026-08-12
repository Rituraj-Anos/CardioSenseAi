"""ORM entities — Blueprint Section 14.

Design rules encoded here:
  * PII lives in its own table (`patient_pii`) so it can carry tighter access
    control than clinical data, and so ML/audit paths reference `patient_id`
    only (Blueprint Section 25, data minimisation).
  * Raw signal bytes are never stored in the database. `pcg_recordings` and
    `ecg_recordings` hold a storage path plus metadata only.
  * One `model_predictions` row per modality that actually ran, and a
    `fusion_results` row recording *which* modalities contributed — that
    record is what makes the graceful-degradation story auditable rather
    than just asserted (Blueprint Section 20).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    JSONB,
    GUID,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class UserRole(str, enum.Enum):
    patient = "patient"
    health_worker = "health_worker"
    admin = "admin"


class ScreeningStatus(str, enum.Enum):
    draft = "draft"           # created, no clinical data yet
    ready = "ready"           # has at least clinical data, not yet analysed
    analyzed = "analyzed"     # inference + fusion complete
    reviewed = "reviewed"     # a health worker has signed off


class Modality(str, enum.Enum):
    clinical = "clinical"
    pcg = "pcg"
    ecg = "ecg"


class RiskBand(str, enum.Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class ReferralStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    completed = "completed"
    cancelled = "cancelled"


class Sex(str, enum.Enum):
    female = "female"
    male = "male"


def _enum(py_enum, name: str):
    """Store enums by value (not by Python member name) for stable migrations."""
    return SAEnum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------
class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(160))
    role: Mapped[UserRole] = mapped_column(
        _enum(UserRole, "user_role"), default=UserRole.health_worker, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Brute-force protection: track failures and lock an account temporarily
    # after too many. Reset on a successful login.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patients_created: Mapped[list[Patient]] = relationship(
        back_populates="creator", foreign_keys="Patient.created_by"
    )


# --------------------------------------------------------------------------
# Patient + isolated PII
# --------------------------------------------------------------------------
class PatientPII(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Directly identifying data. Kept apart from clinical records on purpose."""

    __tablename__ = "patient_pii"

    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(64))
    dob: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    address: Mapped[str | None] = mapped_column(Text)

    patient: Mapped[Patient] = relationship(back_populates="pii", uselist=False)


class Patient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patients"

    pii_ref: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("patient_pii.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # De-identified demographics needed for screening logic live here, not in PII.
    sex: Mapped[Sex | None] = mapped_column(_enum(Sex, "sex"))
    age_years: Mapped[int | None] = mapped_column(Integer)
    village_or_area: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)

    pii: Mapped[PatientPII] = relationship(back_populates="patient")
    creator: Mapped[User] = relationship(
        back_populates="patients_created", foreign_keys=[created_by]
    )
    screenings: Mapped[list[Screening]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", order_by="Screening.created_at.desc()"
    )


# --------------------------------------------------------------------------
# Screening event
# --------------------------------------------------------------------------
class Screening(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "screenings"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ScreeningStatus] = mapped_column(
        _enum(ScreeningStatus, "screening_status"), default=ScreeningStatus.draft, nullable=False
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped[Patient] = relationship(back_populates="screenings")
    clinical: Mapped[ClinicalMeasurement | None] = relationship(
        back_populates="screening", cascade="all, delete-orphan", uselist=False
    )
    pcg: Mapped[PCGRecording | None] = relationship(
        back_populates="screening", cascade="all, delete-orphan", uselist=False
    )
    ecg: Mapped[ECGRecording | None] = relationship(
        back_populates="screening", cascade="all, delete-orphan", uselist=False
    )
    predictions: Mapped[list[ModelPrediction]] = relationship(
        back_populates="screening", cascade="all, delete-orphan"
    )
    fusion: Mapped[FusionResult | None] = relationship(
        back_populates="screening", cascade="all, delete-orphan", uselist=False
    )
    referrals: Mapped[list[Referral]] = relationship(
        back_populates="screening", cascade="all, delete-orphan"
    )


class ClinicalMeasurement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The 13 UCI/Cleveland-style features, stored with explicit names.

    Column names mirror the dataset's feature names so training and serving
    share one vocabulary (Blueprint Section 22: avoid train/serve skew).
    Human-readable labels are applied at the presentation layer via a curated
    lookup, never generated (Blueprint Section 21).
    """

    __tablename__ = "clinical_measurements"

    screening_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("screenings.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    age: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[int] = mapped_column(Integer, nullable=False)            # 1=male, 0=female
    cp: Mapped[int] = mapped_column(Integer, nullable=False)             # chest pain type 0-3
    trestbps: Mapped[int] = mapped_column(Integer, nullable=False)       # resting BP mm Hg
    chol: Mapped[int] = mapped_column(Integer, nullable=False)           # serum cholesterol mg/dl
    fbs: Mapped[int] = mapped_column(Integer, nullable=False)            # fasting blood sugar >120
    restecg: Mapped[int] = mapped_column(Integer, nullable=False)        # resting ECG category 0-2
    thalach: Mapped[int] = mapped_column(Integer, nullable=False)        # max heart rate achieved
    exang: Mapped[int] = mapped_column(Integer, nullable=False)          # exercise-induced angina
    oldpeak: Mapped[float] = mapped_column(Float, nullable=False)        # ST depression
    slope: Mapped[int] = mapped_column(Integer, nullable=False)          # ST slope 0-2
    ca: Mapped[int] = mapped_column(Integer, nullable=False)             # major vessels 0-4
    thal: Mapped[int] = mapped_column(Integer, nullable=False)           # thalassemia 0-3

    screening: Mapped[Screening] = relationship(back_populates="clinical")


class PCGRecording(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pcg_recordings"

    screening_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("screenings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(64), default="upload", nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)

    screening: Mapped[Screening] = relationship(back_populates="pcg")


class ECGRecording(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ingestion contract mirrors the HAL from Blueprint Section 27:
    {signal, sample_rate, metadata} — the model never learns which device
    produced the signal."""

    __tablename__ = "ecg_recordings"

    screening_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("screenings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    leads: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lead_names: Mapped[list | None] = mapped_column(JSONB)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="upload", nullable=False)
    device_metadata: Mapped[dict | None] = mapped_column(JSONB)

    screening: Mapped[Screening] = relationship(back_populates="ecg")


class ModelPrediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_predictions"
    __table_args__ = (UniqueConstraint("screening_id", "modality", name="uq_prediction_per_modality"),)

    screening_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("screenings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modality: Mapped[Modality] = mapped_column(_enum(Modality, "modality"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)        # calibrated P(at risk)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)   # 0-1
    threshold: Mapped[float | None] = mapped_column(Float)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    screening: Mapped[Screening] = relationship(back_populates="predictions")
    explanation: Mapped[Explanation | None] = relationship(
        back_populates="prediction", cascade="all, delete-orphan", uselist=False
    )


class Explanation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured only — never free-text model-generated reasoning
    (Blueprint Section 21)."""

    __tablename__ = "explanations"

    prediction_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("model_predictions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    method: Mapped[str] = mapped_column(String(64), nullable=False)  # shap | grad_cam | ...
    top_factors: Mapped[list] = mapped_column(JSONB, nullable=False)
    base_value: Mapped[float | None] = mapped_column(Float)

    prediction: Mapped[ModelPrediction] = relationship(back_populates="explanation")


class FusionResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fusion_results"

    screening_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("screenings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_band: Mapped[RiskBand] = mapped_column(_enum(RiskBand, "risk_band"), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    modalities_used: Mapped[list] = mapped_column(JSONB, nullable=False)
    weights: Mapped[dict | None] = mapped_column(JSONB)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty_note: Mapped[str] = mapped_column(Text, nullable=False)
    fusion_version: Mapped[str] = mapped_column(String(64), nullable=False)

    screening: Mapped[Screening] = relationship(back_populates="fusion")


class Referral(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "referrals"

    screening_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("screenings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ReferralStatus] = mapped_column(
        _enum(ReferralStatus, "referral_status"), default=ReferralStatus.pending, nullable=False
    )
    refer_to: Mapped[str | None] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(Text)

    screening: Mapped[Screening] = relationship(back_populates="referrals")


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Who accessed or changed what (Blueprint Section 25). Append-only."""

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
