"""Auth hardening tests: password policy, strength endpoint, account lockout."""

from __future__ import annotations

from app.core.config import settings

API = settings.api_v1_prefix


def _register(client, email, password):
    return client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": "T", "role": "health_worker"},
    )


def test_password_policy_endpoint_lists_requirements(client):
    body = client.get(f"{API}/auth/password-policy").json()
    assert body["min_length"] == 10
    assert any("symbol" in r.lower() for r in body["requirements"])


def test_check_password_scores_and_reports_errors(client):
    weak = client.post(f"{API}/auth/check-password", json={"password": "abc"}).json()
    assert weak["ok"] is False
    assert weak["score"] <= 1
    assert weak["errors"]

    strong = client.post(f"{API}/auth/check-password", json={"password": "Str0ng-Pass!word"}).json()
    assert strong["ok"] is True
    assert strong["score"] >= 3


def test_registration_rejects_password_without_uppercase(client):
    r = _register(client, "nouppercase@example.org", "lowercase-1!")
    assert r.status_code == 422


def test_registration_rejects_password_without_symbol(client):
    r = _register(client, "nosymbol@example.org", "NoSymbol123")
    assert r.status_code == 422


def test_registration_rejects_common_password(client):
    r = _register(client, "common@example.org", "Password123")
    # "password123" is on the common list (case-insensitive) — but this has a
    # capital P + digits; ensure a genuinely common one is caught.
    r2 = _register(client, "common2@example.org", "password123")
    assert r2.status_code == 422


def test_strong_password_is_accepted(client):
    r = _register(client, "strong@example.org", "Str0ng-Pass!word")
    assert r.status_code == 201


def test_account_locks_after_repeated_failures(client):
    email = "lockme@example.org"
    assert _register(client, email, "Str0ng-Pass!word").status_code == 201

    # 5 wrong attempts → lock.
    codes = []
    for _ in range(5):
        codes.append(
            client.post(f"{API}/auth/login", json={"email": email, "password": "Wrong-Pass!1"}).status_code
        )
    # The 5th failure locks the account (429).
    assert codes[-1] == 429

    # Even the correct password is now refused while locked.
    locked = client.post(f"{API}/auth/login", json={"email": email, "password": "Str0ng-Pass!word"})
    assert locked.status_code == 429
    assert "lock" in locked.json()["detail"].lower()


def test_successful_login_resets_failure_counter(client):
    email = "resetme@example.org"
    _register(client, email, "Str0ng-Pass!word")
    # a few failures, but below the lock threshold
    for _ in range(3):
        client.post(f"{API}/auth/login", json={"email": email, "password": "Wrong-Pass!1"})
    ok = client.post(f"{API}/auth/login", json={"email": email, "password": "Str0ng-Pass!word"})
    assert ok.status_code == 200
    # counter reset → can fail 4 more times without locking
    for _ in range(4):
        r = client.post(f"{API}/auth/login", json={"email": email, "password": "Wrong-Pass!1"})
        assert r.status_code == 401
