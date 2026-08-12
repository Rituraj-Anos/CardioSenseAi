"""ECG inference wrapper.

Loads the trained ECG artifact (classical rhythm/morphology classifier) and
scores a single-lead waveform. Without an artifact, `predict()` raises
ModelNotAvailable and fusion excludes the modality — never treated as normal.

`analyse_*` helpers describe the waveform (rhythm summary) with or without a
model, and are safe to show because they measure the signal rather than predict
from it.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib

from app.core.logging import get_logger
from app.ml.ecg.features import extract_features
from app.ml.ecg.signal import (
    ECGSignal,
    ECGValidationError,
    from_upload,
    from_wfdb,
    rhythm_summary,
)
from app.ml.registry import Artifact, ModelNotAvailable, resolve

log = get_logger(__name__)

_FEATURE_LABELS = {
    "heart_rate_bpm": "Heart rate",
    "mean_rr": "Average beat interval",
    "sdnn": "Beat-to-beat variability (SDNN)",
    "rmssd": "Short-term variability (RMSSD)",
    "rr_irregularity": "Rhythm irregularity",
    "pnn50": "Proportion of large interval changes",
    "qrs_amp_mean": "QRS amplitude",
    "qrs_amp_std": "QRS amplitude variation",
    "signal_std": "Signal variation",
    "signal_ptp": "Signal peak-to-peak",
    "beat_rate_per_s": "Beat rate",
    "rr_range": "Interval spread",
}


@dataclass
class ECGPrediction:
    score: float
    confidence: float
    threshold: float
    model_version: str
    top_factors: list[dict[str, Any]] = field(default_factory=list)
    explanation_method: str = "feature_importance"


@dataclass
class ECGAnalysis:
    duration_seconds: float
    sample_rate: int
    lead_name: str
    rhythm: dict[str, Any]
    metadata: dict[str, Any]
    usable: bool
    quality_note: str


def analyse_signal(ecg: ECGSignal) -> ECGAnalysis:
    rhythm = rhythm_summary(ecg)
    hr = rhythm.get("heart_rate_bpm")
    problems = []
    if hr is None:
        problems.append("no reliable QRS complexes detected")
    elif not (30 <= hr <= 220):
        problems.append(f"detected rate ({hr} bpm) is implausible")
    if rhythm.get("beats_detected", 0) < 5:
        problems.append("too few beats for a meaningful summary")
    usable = not problems
    return ECGAnalysis(
        duration_seconds=ecg.duration_seconds,
        sample_rate=ecg.sample_rate,
        lead_name=ecg.lead_name,
        rhythm=rhythm,
        metadata=ecg.metadata,
        usable=usable,
        quality_note="Waveform looks usable for analysis."
        if usable
        else "Quality concerns: " + "; ".join(problems) + ".",
    )


def analyse_upload(path: str | Path, sample_rate: int | None = None) -> ECGAnalysis:
    return analyse_signal(from_upload(path, sample_rate))


def analyse_physionet_record(record: str, pn_dir: str = "mitdb") -> ECGAnalysis:
    return analyse_signal(from_wfdb(record, pn_dir=pn_dir))


class ECGPredictor:
    _lock = threading.Lock()
    _instance: "ECGPredictor | None" = None

    def __init__(self) -> None:
        self.artifact: Artifact = resolve("ecg")
        self.pipeline = joblib.load(self.artifact.model_path)
        self.threshold = self.artifact.threshold
        self._importances = self.artifact.manifest.get("global_importances", {})
        log.info("ecg_model_loaded", version=self.artifact.version,
                 algorithm=self.artifact.manifest.get("algorithm"))

    @classmethod
    def instance(cls) -> "ECGPredictor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def predict(self, ecg: ECGSignal) -> ECGPrediction:
        feats = extract_features(ecg).reshape(1, -1)
        proba = float(self.pipeline.predict_proba(feats)[0][1])
        confidence = round(min(1.0, abs(proba - 0.5) * 2.0), 4)
        top = sorted(self._importances.items(), key=lambda kv: kv[1], reverse=True)[:4]
        factors = [
            {
                "feature": "ecg",
                "label": _FEATURE_LABELS.get(name, name),
                "value": None,
                "display_value": "",
                "direction": "increases_risk" if proba >= self.threshold else "decreases_risk",
                "magnitude": round(float(mag), 4),
            }
            for name, mag in top
        ]
        return ECGPrediction(
            score=proba,
            confidence=confidence,
            threshold=self.threshold,
            model_version=f"ecg-{self.artifact.version}",
            top_factors=factors,
        )


def predict(ecg: ECGSignal) -> ECGPrediction:
    return ECGPredictor.instance().predict(ecg)


def is_available() -> bool:
    try:
        resolve("ecg")
        return True
    except ModelNotAvailable:
        return False


__all__ = [
    "ECGAnalysis", "ECGPrediction", "ECGValidationError",
    "analyse_physionet_record", "analyse_signal", "analyse_upload",
    "is_available", "predict",
]
