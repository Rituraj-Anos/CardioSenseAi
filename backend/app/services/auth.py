"""Authentication service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import hash_password, needs_rehash, verify_password
from app.models.entities import User, UserRole
from app.models.schemas import RegisterRequest

log = get_logger(__name__)

# Account lockout policy.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == _normalise_email(email)))


def register_user(db: Session, payload: RegisterRequest) -> User:
    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(
        email=_normalise_email(payload.email),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=UserRole(payload.role),
        password_changed_at=datetime.now(UTC),
    )
    db.add(user)
    db.flush()
    log.info("user_registered", user_id=str(user.id), role=user.role.value)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    """Verify credentials with brute-force protection.

    - Wrong email and wrong password return the same error, and the password
      hash is still verified against a dummy when the user is absent, so
      response timing doesn't reveal which emails are registered.
    - Repeated failures on a real account trigger a temporary lockout.
    """
    user = get_user_by_email(db, email)

    if user is None:
        # Constant-ish work on the miss path.
        verify_password(password, hash_password("dummy-timing-equaliser"))
        raise _invalid_credentials()

    now = datetime.now(UTC)

    # Locked out?
    if user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        if locked_until > now:
            mins = max(1, int((locked_until - now).total_seconds() // 60) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account temporarily locked after too many attempts. Try again in {mins} minute(s).",
            )

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
            log.warning("account_locked", user_id=str(user.id))
            # Persist the lock even though we're about to raise — the endpoint
            # commits only on success, so failure state must be committed here.
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.",
            )
        db.commit()
        log.info("login_failed", user_id=str(user.id), attempts=user.failed_login_attempts)
        raise _invalid_credentials(remaining=MAX_FAILED_ATTEMPTS - user.failed_login_attempts)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")

    # Success: reset counters, record login.
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        log.info("password_hash_upgraded", user_id=str(user.id))

    db.flush()
    return user


def _invalid_credentials(remaining: int | None = None) -> HTTPException:
    detail = "Incorrect email or password."
    if remaining is not None and remaining <= 2:
        detail += f" {remaining} attempt(s) left before the account is locked."
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
