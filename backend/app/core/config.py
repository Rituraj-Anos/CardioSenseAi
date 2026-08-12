"""Application configuration.

All values come from the environment (Blueprint Section 25: no hard-coded
secrets, ever). Defaults here are development-only and deliberately safe:
the app refuses to boot in a non-development environment while SECRET_KEY
still holds its placeholder value.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent

_PLACEHOLDER_SECRET = "replace-me-with-a-64-byte-urlsafe-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_env: str = "development"
    app_name: str = "CardioSense AI"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # ---- Security ----
    secret_key: str = _PLACEHOLDER_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # ---- Database ----
    database_url: str = "sqlite+pysqlite:///./cardiosense.db"

    # ---- Storage ----
    storage_backend: str = "local"
    storage_local_path: str = "./storage"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # ---- CORS ----
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Uploads ----
    max_upload_mb: int = Field(default=25, ge=1, le=200)

    # ---- Demo experience ----
    # When true, a new health-worker account is provisioned with a realistic
    # starter cohort so the dashboard/insights are populated immediately rather
    # than showing empty states on first login.
    provision_demo_data: bool = True

    # ---- Monitoring ----
    sentry_dsn: str | None = None

    @field_validator("app_env")
    @classmethod
    def _normalise_env(cls, v: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        v = v.strip().lower()
        if v not in allowed:
            raise ValueError(f"app_env must be one of {sorted(allowed)}, got {v!r}")
        return v

    @model_validator(mode="after")
    def _reject_placeholder_secret_outside_dev(self) -> Settings:
        if self.app_env in {"staging", "production"} and (
            self.secret_key == _PLACEHOLDER_SECRET or len(self.secret_key) < 32
        ):
            raise ValueError(
                "SECRET_KEY must be set to a strong random value "
                f"(>=32 chars) when APP_ENV={self.app_env}."
            )
        return self

    @property
    def is_dev(self) -> bool:
        return self.app_env in {"development", "test"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def storage_root(self) -> Path:
        p = Path(self.storage_local_path)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def model_registry_root(self) -> Path:
        """Versioned model folders + manifest.json (Blueprint Section 22)."""
        return REPO_ROOT / "ml" / "artifacts"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
