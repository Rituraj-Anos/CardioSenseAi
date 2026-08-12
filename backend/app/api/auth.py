"""Auth routes: register, login, refresh, logout, me.

The refresh token is set as an httpOnly cookie rather than returned in the JSON
body (Blueprint Section 16), so JavaScript on the page cannot read it and an XSS
bug cannot walk away with a long-lived credential.
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app.api.deps import CurrentUser, DbSession, client_ip
from app.core.config import settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.passwords import POLICY_DESCRIPTION, check_password
from app.core.ratelimit import rate_limit
from app.models.entities import User, UserRole
from app.models.schemas import (
    LoginRequest,
    PasswordCheckRequest,
    PasswordCheckResponse,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import audit
from app.services.auth import authenticate, register_user
from app.services.demo_data import provision_demo_cohort

router = APIRouter(prefix="/auth", tags=["auth"])

# Brute-force / abuse guards on the sensitive endpoints.
_login_limit = rate_limit("login", limit=10, window_seconds=60)
_register_limit = rate_limit("register", limit=5, window_seconds=300)

REFRESH_COOKIE = "cardiosense_refresh"


def _set_refresh_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=create_refresh_token(str(user.id)),
        httponly=True,
        secure=not settings.is_dev,   # requires HTTPS outside development
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=f"{settings.api_v1_prefix}/auth",
    )


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role.value),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/password-policy")
def password_policy() -> dict:
    """Expose the policy so the client meter and the server agree on the rules."""
    return POLICY_DESCRIPTION


@router.post("/check-password", response_model=PasswordCheckResponse)
def check_password_endpoint(payload: PasswordCheckRequest) -> PasswordCheckResponse:
    """Live strength check for the register form (no account is created)."""
    r = check_password(payload.password, email=payload.email)
    return PasswordCheckResponse(ok=r.ok, score=r.score, errors=r.errors)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_register_limit)],
)
def register(payload: RegisterRequest, request: Request, db: DbSession) -> User:
    user = register_user(db, payload)
    audit.record(
        db,
        user_id=user.id,
        action="user.register",
        target_type="user",
        target_id=user.id,
        ip_address=client_ip(request),
        detail={"role": user.role.value},
    )
    db.commit()
    db.refresh(user)

    # Populate a realistic starter cohort so the new account's dashboard,
    # insights and queue are alive from the first login (health workers only).
    if settings.provision_demo_data and user.role is UserRole.health_worker:
        try:
            provision_demo_cohort(db, user)
            db.commit()
        except Exception:  # provisioning must never block account creation
            db.rollback()

    return user


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_login_limit)])
def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession
) -> TokenResponse:
    user = authenticate(db, payload.email, payload.password)
    audit.record(
        db,
        user_id=user.id,
        action="user.login",
        target_type="user",
        target_id=user.id,
        ip_address=client_ip(request),
    )
    db.commit()
    _set_refresh_cookie(response, user)
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: DbSession,
    cardiosense_refresh: str | None = Cookie(default=None),
) -> TokenResponse:
    if not cardiosense_refresh:
        raise HTTPException(status_code=401, detail="No refresh token present.")
    try:
        payload = decode_token(cardiosense_refresh, "refresh")
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    import uuid as _uuid

    user = db.get(User, _uuid.UUID(str(payload["sub"])))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or missing.")

    _set_refresh_cookie(response, user)
    return _token_response(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=f"{settings.api_v1_prefix}/auth")
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
