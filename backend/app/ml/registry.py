"""Minimal model registry: a versioned folder plus a `manifest.json`.

Blueprint Section 22 explicitly scopes MLflow as `[FUTURE]` and calls a
versioned folder + manifest sufficient for the MVP. This is that.

Layout:
    ml/artifacts/
      clinical/
        latest -> pointer written into registry.json
        v1/
          model.joblib
          manifest.json
          eval_report.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class ModelNotAvailable(Exception):
    """Raised when a modality's artifact is absent.

    This is a first-class, expected condition, not a crash: the fusion engine
    treats an unavailable modality exactly like an absent one, which is the
    graceful-degradation contract from Blueprint Section 20.
    """


@dataclass(frozen=True)
class Artifact:
    modality: str
    version: str
    root: Path
    manifest: dict[str, Any]

    @property
    def model_path(self) -> Path:
        return self.root / self.manifest.get("model_file", "model.joblib")

    @property
    def threshold(self) -> float:
        return float(self.manifest.get("decision_threshold", 0.5))


def _modality_root(modality: str) -> Path:
    return settings.model_registry_root / modality


def available_versions(modality: str) -> list[str]:
    root = _modality_root(modality)
    if not root.is_dir():
        return []
    return sorted(
        (p.name for p in root.iterdir() if p.is_dir() and (p / "manifest.json").is_file()),
        key=lambda n: (len(n), n),
    )


def resolve(modality: str, version: str | None = None) -> Artifact:
    """Load an artifact's manifest. `version=None` resolves to the newest."""
    root = _modality_root(modality)
    versions = available_versions(modality)
    if not versions:
        raise ModelNotAvailable(
            f"No trained artifact for modality '{modality}' under {root}. "
            f"Train it first (see ml/{modality}/)."
        )
    chosen = version or versions[-1]
    if chosen not in versions:
        raise ModelNotAvailable(f"Version '{chosen}' not found for '{modality}'.")

    art_root = root / chosen
    manifest = json.loads((art_root / "manifest.json").read_text(encoding="utf-8"))
    return Artifact(modality=modality, version=chosen, root=art_root, manifest=manifest)


def write_manifest(modality: str, version: str, manifest: dict[str, Any]) -> Path:
    art_root = _modality_root(modality) / version
    art_root.mkdir(parents=True, exist_ok=True)
    path = art_root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    log.info("model_manifest_written", modality=modality, version=version, path=str(path))
    return path


def artifact_dir(modality: str, version: str) -> Path:
    d = _modality_root(modality) / version
    d.mkdir(parents=True, exist_ok=True)
    return d
