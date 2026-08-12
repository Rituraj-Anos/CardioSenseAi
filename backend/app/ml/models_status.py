"""Runtime report of which modalities can contribute a score.

The frontend reads this so an unavailable modality is labelled as unavailable
rather than rendered as an empty/normal result. Making capability visible is
cheaper than explaining it after a judge has already misread the screen.
"""

from __future__ import annotations

from typing import Any

from app.ml.clinical.predictor import get_clinical_predictor
from app.ml.ecg import predictor as ecg_predictor
from app.ml.fusion.engine import BASE_WEIGHTS, DISCLAIMER, FUSION_VERSION
from app.ml.pcg import predictor as pcg_predictor


def modality_status() -> dict[str, Any]:
    clinical = get_clinical_predictor()

    modalities: dict[str, Any] = {
        "clinical": {
            "available": clinical is not None,
            "model_version": clinical.artifact.version if clinical else None,
            "algorithm": clinical.artifact.manifest.get("algorithm") if clinical else None,
            "decision_threshold": clinical.threshold if clinical else None,
            "explainability": "shap" if clinical else None,
            "reason": None if clinical else "No trained clinical artifact is registered.",
        },
        "pcg": {
            "available": pcg_predictor.is_available(),
            "model_version": None,
            "signal_pipeline": True,
            "explainability": "grad_cam" if pcg_predictor.is_available() else None,
            "reason": (
                None
                if pcg_predictor.is_available()
                else "Signal validation, filtering and quality checks run, but no "
                     "heart-sound classifier is trained yet. Recordings are stored "
                     "and excluded from fusion rather than scored."
            ),
        },
        "ecg": {
            "available": ecg_predictor.is_available(),
            "model_version": None,
            "signal_pipeline": True,
            "explainability": "saliency" if ecg_predictor.is_available() else None,
            "reason": (
                None
                if ecg_predictor.is_available()
                else "Filtering, R-peak detection and rhythm summary run, but no ECG "
                     "classifier is trained yet. Waveforms are stored and excluded "
                     "from fusion rather than scored."
            ),
        },
    }

    active = [m for m, v in modalities.items() if v["available"]]

    return {
        "modalities": modalities,
        "active_modalities": active,
        "fusion": {
            "version": FUSION_VERSION,
            "strategy": "late (decision-level) fusion with weight renormalisation",
            "base_weights": BASE_WEIGHTS,
            "note": (
                "Absent or unavailable modalities are excluded and the remaining "
                "weights renormalised. A missing modality is never treated as a "
                "normal finding."
            ),
        },
        "disclaimer": DISCLAIMER,
    }
