"""Shared FastAPI dependencies: DB session, current user, RBAC guards.

Blueprint Section 16: RBAC enforced via dependency guards on every route, plus
per-creator row-level scoping. Facility-based scoping is `[FUTURE]`; a health
worker seeing only the patients they created is enough for this build and is
enforced here rather than trusted to each route handler.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import TokenError, decode_token
from app.models.entities import Patient, Screening, User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    try:
        payload = decode_token(credentials.credentials, "access")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise _UNAUTHORIZED from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or missing."
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Route guard: allow only the listed roles. Admin always passes."""

    allowed = set(roles) | {UserRole.admin}

    def _guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This action requires one of: "
                    f"{', '.join(sorted(r.value for r in roles))}."
                ),
            )
        return user

    return _guard


RequireHealthWorker = Annotated[User, Depends(require_roles(UserRole.health_worker))]


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


# --------------------------------------------------------------------------
# Row-level scoping helpers
# --------------------------------------------------------------------------
def get_owned_patient(patient_id: uuid.UUID, db: Session, user: User) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    if user.role is not UserRole.admin and patient.created_by != user.id:
        # 404 rather than 403 on purpose: confirming a record exists but is
        # someone else's still leaks that the record exists.
        raise HTTPException(status_code=404, detail="Patient not found.")
    return patient


def get_owned_screening(screening_id: uuid.UUID, db: Session, user: User) -> Screening:
    screening = db.get(Screening, screening_id)
    if screening is None:
        raise HTTPException(status_code=404, detail="Screening not found.")
    if user.role is not UserRole.admin:
        patient = db.get(Patient, screening.patient_id)
        if patient is None or patient.created_by != user.id:
            raise HTTPException(status_code=404, detail="Screening not found.")
    return screening
