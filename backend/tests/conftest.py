"""Test fixtures.

Each test module gets a fresh SQLite file so tests cannot leak state into each
other, and the app's `get_db` dependency is overridden to use it.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Force the test environment (not setdefault) so a leaked APP_ENV from the
# launching shell can't turn on rate limiting / demo provisioning mid-suite.
os.environ["APP_ENV"] = "test"
os.environ["PROVISION_DEMO_DATA"] = "false"
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-anywhere-real-0123456789")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402

API = settings.api_v1_prefix


@pytest.fixture
def db_engine() -> Generator:
    tmpdir = tempfile.mkdtemp(prefix="cardiosense-test-")
    db_path = Path(tmpdir) / "test.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(db_engine) -> Generator[TestClient, None, None]:
    TestingSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Register + log in a health worker, return an Authorization header."""
    client.post(
        f"{API}/auth/register",
        json={
            "email": "asha.worker@example.org",
            "password": "Correct-Horse-9!",
            "full_name": "Asha Worker",
            "role": "health_worker",
        },
    )
    res = client.post(
        f"{API}/auth/login",
        json={"email": "asha.worker@example.org", "password": "Correct-Horse-9!"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def normal_vitals() -> dict:
    """A low-risk-leaning clinical record."""
    return {
        "age": 41, "sex": 0, "cp": 1, "trestbps": 118, "chol": 190, "fbs": 0,
        "restecg": 0, "thalach": 172, "exang": 0, "oldpeak": 0.0, "slope": 2,
        "ca": 0, "thal": 1,
    }


@pytest.fixture
def concerning_vitals() -> dict:
    """A higher-risk-leaning clinical record."""
    return {
        "age": 67, "sex": 1, "cp": 0, "trestbps": 160, "chol": 286, "fbs": 0,
        "restecg": 2, "thalach": 108, "exang": 1, "oldpeak": 1.5, "slope": 1,
        "ca": 3, "thal": 2,
    }
