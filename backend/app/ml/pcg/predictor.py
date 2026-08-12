"""PCG inference wrapper.

Loads the trained heart-sound artifact (classical MFCC-based classifier) and
scores a recording. If no artifact is registered, `predict()` raises
ModelNotAvailable and the fusion engine simply excludes the modality — a
missing model is never treated as a normal finding.

Explanations are feature-importance based (the model is classical, not a CNN),
mapped to plain-language descriptors and clearly labelled as such.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.core.logging import get_logger
from app.ml.pcg.features import extract_features
from app.ml.pcg.signal import (
    PCGValidationError,
    estimate_heart_rate,
    load_and_validate,
)
from app.ml.registry import Artifact, ModelNotAvailable, resolve

log = get_logger(__name__)

# Plain-language descriptors for the feature families that drive the model.
_FEATURE_LABELS = {
    "mfcc": "Timbre / spectral shape of the heart sound",
    "spectral_centroid": "Brightness of the sound",
    "spectral_bandwidth": "Spread of frequencies",
    "spectral_rolloff": "High-frequency content",
    "zcr": "Noisiness / high-frequency crossings",
    "rms": "Loudness variation",
    "in_band_energy_ratio": "Energy within the heart-sound band",
    "heart_rate": "Heart rate",
}


def _label_for(feature: str) -> str:
    for key, label in _FEATURE_LABELS.items():
        if feature.startswith(key):
            return label
    return feature


@dataclass
class PCGPrediction:
    score: float
    confidence: float
    threshold: float
    model_version: str
    top_factors: list[dict[str, Any]] = field(default_factory=list)
    explanation_method: str = "feature_importance"


@dataclass
class PCGAnalysis:
    duration_seconds: float
    sample_rate: int
    original_sample_rate: int
    heart_rate_bpm: float | None
    quality: dict[str, float]
    usable: bool
    quality_note: str


def analyse_recording(path: str | Path) -> PCGAnalysis:
    """Validate + describe a recording (no model needed)."""
    sig = load_and_validate(path)
    hr = estimate_heart_rate(sig.audio, sig.sample_rate)
    q = sig.quality
    problems = []
    if q["in_band_energy_ratio"] < 0.25:
        problems.append("most energy sits outside the heart-sound band (likely ambient noise)")
    if q["clipping_ratio"] > 0.01:
        problems.append("the recording is clipping")
    if q["rms"] < 0.01:
        problems.append("the signal level is very low")
    if hr is None:
        problems.append("no reliable cardiac cycle detected")
    usable = not problems
    return PCGAnalysis(
        duration_seconds=sig.duration_seconds,
        sample_rate=sig.sample_rate,
        original_sample_rate=sig.original_sample_rate,
        heart_rate_bpm=hr,
        quality=q,
        usable=usable,
        quality_note="Signal quality looks adequate for analysis."
        if usable
        else "Quality concerns: " + "; ".join(problems) + ".",
    )


class PCGPredictor:
    _lock = threading.Lock()
    _instance: "PCGPredictor | None" = None

    def __init__(self) -> None:
        self.artifact: Artifact = resolve("pcg")
        self.pipeline = joblib.load(self.artifact.model_path)
        self.threshold = self.artifact.threshold
        self._importances = self.artifact.manifest.get("global_importances", {})
        log.info("pcg_model_loaded", version=self.artifact.version,
                 algorithm=self.artifact.manifest.get("algorithm"))

    @classmethod
    def instance(cls) -> "PCGPredictor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def predict(self, path: str | Path) -> PCGPrediction:
        sig = load_and_validate(path)
        feats = extract_features(sig).reshape(1, -1)
        proba = float(self.pipeline.predict_proba(feats)[0][1])
        confidence = round(min(1.0, abs(proba - 0.5) * 2.0), 4)

        # Top contributing feature families (global importance; deduped to labels).
        seen: dict[str, float] = {}
        for feature, imp in self._importances.items():
            label = _label_for(feature)
            seen[label] = seen.get(label, 0.0) + float(imp)
        top = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:4]
        factors = [
            {
                "feature": "pcg",
                "label": label,
                "value": None,
                "display_value": "",
                "direction": "increases_risk" if proba >= self.threshold else "decreases_risk",
                "magnitude": round(mag, 4),
            }
            for label, mag in top
        ]
        return PCGPrediction(
            score=proba,
            confidence=confidence,
            threshold=self.threshold,
            model_version=f"pcg-{self.artifact.version}",
            top_factors=factors,
        )


def predict(path: str | Path) -> PCGPrediction:
    return PCGPredictor.instance().predict(path)


def is_available() -> bool:
    try:
        resolve("pcg")
        return True
    except ModelNotAvailable:
        return False


__all__ = [
    "PCGAnalysis", "PCGPrediction", "PCGValidationError",
    "analyse_recording", "is_available", "predict",
]
