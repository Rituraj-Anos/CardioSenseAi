"""Audit logging service (Blueprint Section 25).

A real table, written on every state change and every clinical-data read —
not an afterthought. `detail` is restricted to non-PII fields by convention;
`app.core.logging` scrubs the same key names on the log stream so the two
paths agree.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.entities import AuditLog

log = get_logger(__name__)

_FORBIDDEN_DETAIL_KEYS = {"name", "full_name", "contact", "phone", "email", "dob", "address"}


def record(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    ip_address: str | None = None,
    detail: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditLog:
    safe_detail = None
    if detail:
        safe_detail = {
            k: ("[redacted]" if k.lower() in _FORBIDDEN_DETAIL_KEYS else v)
            for k, v in detail.items()
        }

    entry = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip_address=ip_address,
        detail=safe_detail,
        timestamp=datetime.now(UTC),
    )
    db.add(entry)
    if commit:
        db.commit()
    log.info("audit", action=action, target_type=target_type, target_id=str(target_id))
    return entry
