"""Password policy — one source of truth for strength rules.

Used by the registration schema (reject weak passwords) and exposed to the
frontend so the live strength meter and the server agree on the rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MIN_LENGTH = 10
MAX_LENGTH = 128

# A small blocklist of obviously weak choices. A real deployment would check
# against a breached-password corpus (e.g. HaveIBeenPwned k-anonymity); this is
# a pragmatic subset that catches the common ones.
_COMMON = {
    "password", "password1", "password12", "password123", "passw0rd",
    "12345678", "123456789", "1234567890", "qwerty123", "letmein123",
    "welcome123", "admin123", "cardiosense", "changeme123", "iloveyou1",
}


@dataclass
class PasswordCheck:
    ok: bool
    errors: list[str]
    score: int  # 0-4 strength


def check_password(password: str, *, email: str | None = None) -> PasswordCheck:
    errors: list[str] = []
    p = password or ""

    if len(p) < MIN_LENGTH:
        errors.append(f"Use at least {MIN_LENGTH} characters.")
    if len(p) > MAX_LENGTH:
        errors.append(f"Keep it under {MAX_LENGTH} characters.")
    if not re.search(r"[a-z]", p):
        errors.append("Add a lowercase letter.")
    if not re.search(r"[A-Z]", p):
        errors.append("Add an uppercase letter.")
    if not re.search(r"\d", p):
        errors.append("Add a number.")
    if not re.search(r"[^A-Za-z0-9]", p):
        errors.append("Add a symbol (e.g. ! ? @ #).")
    if p.lower() in _COMMON:
        errors.append("That password is too common.")
    if email and p and email.split("@")[0].lower() in p.lower() and len(email.split("@")[0]) >= 3:
        errors.append("Don't include your email name in the password.")

    return PasswordCheck(ok=not errors, errors=errors, score=_score(p))


def _score(p: str) -> int:
    """Rough 0-4 strength score for the UI meter."""
    if not p:
        return 0
    score = 0
    if len(p) >= MIN_LENGTH:
        score += 1
    if len(p) >= 14:
        score += 1
    classes = sum(
        bool(re.search(pat, p)) for pat in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]")
    )
    score += max(0, classes - 1)
    return min(4, score)


POLICY_DESCRIPTION = {
    "min_length": MIN_LENGTH,
    "requirements": [
        "At least 10 characters",
        "Upper and lowercase letters",
        "At least one number",
        "At least one symbol",
    ],
}
