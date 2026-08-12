"""Pydantic request/response schemas (Blueprint Section 15).

Clinical input validation is enforced here, at the edge, with real
physiological ranges rather than "any int". Anything outside these ranges is
rejected with a 422 before it
can reach the model.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.entities import (
    Modality,
    ReferralStatus,
    RiskBand,
    ScreeningStatus,
    Sex,
    UserRole,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]
    full_name: Annotated[str, Field(min_length=1, max_length=160)]
    role: Literal[UserRole.patient, UserRole.health_worker] = UserRole.health_worker

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        from app.core.passwords import check_password

        result = check_password(v)
        if not result.ok:
            raise ValueError(" ".join(result.errors))
        return v


class PasswordCheckRequest(BaseModel):
    password: str
    email: EmailStr | None = None


class PasswordCheckResponse(BaseModel):
    ok: bool
    score: int
    errors: list[str]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime


# --------------------------------------------------------------------------
# Patients
# --------------------------------------------------------------------------
class PatientCreate(BaseModel):
    full_name: Annotated[str, Field(min_length=1, max_length=160)]
    contact: Annotated[str | None, Field(default=None, max_length=64)] = None
    dob: datetime | None = None
    address: Annotated[str | None, Field(default=None, max_length=500)] = None
    sex: Sex | None = None
    age_years: Annotated[int | None, Field(default=None, ge=0, le=120)] = None
    village_or_area: Annotated[str | None, Field(default=None, max_length=120)] = None
    notes: Annotated[str | None, Field(default=None, max_length=2000)] = None


class PatientOut(ORMModel):
    id: uuid.UUID
    full_name: str
    contact: str | None = None
    sex: Sex | None
    age_years: int | None
    village_or_area: str | None
    created_at: datetime


class PatientSummary(BaseModel):
    """Dashboard row — carries the latest screening's risk, if any."""

    id: uuid.UUID
    full_name: str
    sex: Sex | None
    age_years: int | None
    village_or_area: str | None
    screening_count: int
    latest_risk_band: RiskBand | None = None
    latest_score: float | None = None
    latest_screening_at: datetime | None = None
    latest_screening_id: uuid.UUID | None = None


# --------------------------------------------------------------------------
# Clinical intake — the validation surface that matters most
# --------------------------------------------------------------------------
class ClinicalInput(BaseModel):
    """UCI/Cleveland-style 13 features, range-checked.

    Ranges are physiological sanity bounds, intentionally a little wider than
    the training data's observed range so a real-but-unusual patient is not
    rejected — but narrow enough to catch transcription errors (a systolic
    BP of 1200, a cholesterol of 12).
    """

    model_config = ConfigDict(extra="forbid")

    age: Annotated[int, Field(ge=1, le=120, description="Age in years")]
    sex: Annotated[int, Field(ge=0, le=1, description="1 = male, 0 = female")]
    cp: Annotated[int, Field(ge=0, le=3, description="Chest pain type")]
    trestbps: Annotated[int, Field(ge=60, le=260, description="Resting systolic BP, mm Hg")]
    chol: Annotated[int, Field(ge=80, le=700, description="Serum cholesterol, mg/dl")]
    fbs: Annotated[int, Field(ge=0, le=1, description="Fasting blood sugar > 120 mg/dl")]
    restecg: Annotated[int, Field(ge=0, le=2, description="Resting ECG category")]
    thalach: Annotated[int, Field(ge=50, le=230, description="Max heart rate achieved")]
    exang: Annotated[int, Field(ge=0, le=1, description="Exercise-induced angina")]
    oldpeak: Annotated[float, Field(ge=0.0, le=10.0, description="ST depression")]
    slope: Annotated[int, Field(ge=0, le=2, description="ST segment slope")]
    ca: Annotated[int, Field(ge=0, le=4, description="Major vessels coloured by fluoroscopy")]
    thal: Annotated[int, Field(ge=0, le=3, description="Thalassemia category")]

    @field_validator("thalach")
    @classmethod
    def _plausible_max_hr(cls, v: int, info) -> int:
        age = (info.data or {}).get("age")
        if age and v > 220 - age * 0.5 + 40:
            # Not an error — a soft ceiling well above the age-predicted max.
            # Anything past this is almost certainly a data-entry slip.
            raise ValueError(
                f"Max heart rate {v} is implausibly high for age {age}; check the value."
            )
        return v


class ClinicalOut(ORMModel):
    age: int
    sex: int
    cp: int
    trestbps: int
    chol: int
    fbs: int
    restecg: int
    thalach: int
    exang: int
    oldpeak: float
    slope: int
    ca: int
    thal: int


# --------------------------------------------------------------------------
# Screenings, predictions, explanations, fusion
# --------------------------------------------------------------------------
class ScreeningCreate(BaseModel):
    patient_id: uuid.UUID


class ExplanationFactor(BaseModel):
    feature: str
    label: str
    value: float | int | str | None = None
    display_value: str | None = None
    direction: Literal["increases_risk", "decreases_risk"]
    magnitude: float


class ExplanationOut(BaseModel):
    method: str
    base_value: float | None = None
    top_factors: list[ExplanationFactor]


class PredictionOut(BaseModel):
    modality: Modality
    model_version: str
    score: float
    confidence: float
    threshold: float | None = None
    explanation: ExplanationOut | None = None


class RecordingMeta(BaseModel):
    present: bool
    sample_rate: int | None = None
    duration_seconds: float | None = None
    source: str | None = None
    leads: int | None = None


class ScreeningResult(BaseModel):
    screening_id: uuid.UUID
    patient_id: uuid.UUID
    status: ScreeningStatus
    created_at: datetime

    final_score: float
    risk_band: RiskBand
    confidence: float
    modalities_used: list[Modality]
    weights: dict[str, float]
    recommendation: str
    uncertainty_note: str
    fusion_version: str

    per_modality: list[PredictionOut]
    disclaimer: str


class ScreeningOut(ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: ScreeningStatus
    created_at: datetime


class ScreeningHistoryItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    status: ScreeningStatus
    risk_band: RiskBand | None = None
    final_score: float | None = None
    modalities_used: list[Modality] = []


class PatientDetail(BaseModel):
    patient: PatientOut
    screenings: list[ScreeningHistoryItem]


# --------------------------------------------------------------------------
# Referrals
# --------------------------------------------------------------------------
class ReferralCreate(BaseModel):
    screening_id: uuid.UUID
    refer_to: Annotated[str | None, Field(default=None, max_length=160)] = None
    note: Annotated[str | None, Field(default=None, max_length=2000)] = None


class ReferralOut(ORMModel):
    id: uuid.UUID
    screening_id: uuid.UUID
    status: ReferralStatus
    refer_to: str | None
    note: str | None
    created_at: datetime


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
class DashboardStats(BaseModel):
    total_patients: int
    total_screenings: int
    high_risk: int
    moderate_risk: int
    low_risk: int
    pending_review: int
    multimodal_screenings: int


class DashboardQueue(BaseModel):
    stats: DashboardStats
    queue: list[PatientSummary]
