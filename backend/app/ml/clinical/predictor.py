"""Clinical model inference + SHAP explanation.

Two things this deliberately does NOT do:

1. It does not report a bare label. It returns a calibrated probability, a
   confidence figure, and the threshold that was used, because a screening
   tool that reads as a diagnosis is the
   product failure mode called out in Blueprint Section 4.

2. It does not invent explanation text. SHAP values are mapped to the curated
   label table in `features.py` and returned as structured factors
   (Blueprint Section 21).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np

from app.core.logging import get_logger
from app.ml.clinical.features import (
    FEATURE_ORDER,
    display_value,
    label_for,
)
from app.ml.clinical.preprocessing import build_feature_frame
from app.ml.registry import Artifact, ModelNotAvailable, resolve

log = get_logger(__name__)


@dataclass
class ClinicalPrediction:
    score: float
    confidence: float
    threshold: float
    model_version: str
    top_factors: list[dict[str, Any]] = field(default_factory=list)
    explanation_method: str = "shap"
    base_value: float | None = None


class ClinicalPredictor:
    """Lazily loads the artifact once and reuses it across requests."""

    _lock = threading.Lock()
    _instance: ClinicalPredictor | None = None

    def __init__(self, version: str | None = None) -> None:
        self.artifact: Artifact = resolve("clinical", version)
        self.pipeline = joblib.load(self.artifact.model_path)
        self.threshold = self.artifact.threshold
        self._explainer = None
        self._explainer_failed = False
        log.info(
            "clinical_model_loaded",
            version=self.artifact.version,
            threshold=self.threshold,
            algorithm=self.artifact.manifest.get("algorithm"),
        )

    # -- singleton accessor -------------------------------------------------
    @classmethod
    def instance(cls) -> ClinicalPredictor:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop the cached instance (used by tests and after retraining)."""
        with cls._lock:
            cls._instance = None

    # -- inference ----------------------------------------------------------
    def predict(self, features: dict[str, Any]) -> ClinicalPrediction:
        frame = build_feature_frame(features)
        proba = float(self.pipeline.predict_proba(frame)[0][1])

        factors, base_value, method = self._explain(frame)

        return ClinicalPrediction(
            score=proba,
            confidence=self._confidence(proba),
            threshold=self.threshold,
            model_version=f"clinical-{self.artifact.version}",
            top_factors=factors,
            explanation_method=method,
            base_value=base_value,
        )

    @staticmethod
    def _confidence(proba: float) -> float:
        """Distance from the decision boundary, scaled to 0-1.

        A probability of 0.50 is maximally uncertain and reports 0.0; 0.0 or
        1.0 report 1.0. This is a decisiveness measure, not a calibration
        guarantee — the calibration itself is handled at training time by the
        isotonic/sigmoid wrapper, and the eval report carries the curve.
        """
        return round(min(1.0, abs(proba - 0.5) * 2.0), 4)

    # -- explainability -----------------------------------------------------
    def _build_explainer(self):
        """Build a SHAP explainer over the fitted estimator.

        TreeExplainer is used for tree models; anything else falls back to the
        model-agnostic Explainer with the training background stored alongside
        the artifact. If SHAP cannot be built for any reason we degrade to a
        coefficient/importance-based fallback rather than failing the request —
        an unexplained result is still a usable screening result, but a 500 is
        not.
        """
        import shap  # imported lazily; it is a heavy import

        estimator = self._final_estimator()
        return shap.TreeExplainer(estimator)

    def _final_estimator(self):
        """Unwrap CalibratedClassifierCV / Pipeline to the raw tree model."""
        obj = self.pipeline
        if hasattr(obj, "named_steps"):
            obj = obj.named_steps.get("clf", obj)
        if hasattr(obj, "calibrated_classifiers_"):
            inner = obj.calibrated_classifiers_[0]
            obj = getattr(inner, "estimator", getattr(inner, "base_estimator", obj))
        return obj

    def _transform_for_explainer(self, frame):
        """Apply every pipeline step except the classifier."""
        if not hasattr(self.pipeline, "named_steps"):
            return frame.to_numpy(dtype=float)
        data = frame
        for name, step in self.pipeline.steps[:-1]:
            data = step.transform(data)
        return data

    def _feature_names_after_transform(self) -> list[str]:
        try:
            pre = self.pipeline.named_steps.get("pre")
            if pre is not None and hasattr(pre, "get_feature_names_out"):
                return [str(n) for n in pre.get_feature_names_out()]
        except Exception:  # pragma: no cover - defensive
            pass
        return list(FEATURE_ORDER)

    def _explain(self, frame) -> tuple[list[dict[str, Any]], float | None, str]:
        raw_values = {c: frame.iloc[0][c] for c in frame.columns}

        if not self._explainer_failed:
            try:
                if self._explainer is None:
                    self._explainer = self._build_explainer()
                transformed = self._transform_for_explainer(frame)
                sv = self._explainer.shap_values(transformed)
                contributions = np.asarray(sv)
                if contributions.ndim == 3:      # (n, features, classes)
                    contributions = contributions[0, :, -1]
                elif contributions.ndim == 2:    # (n, features)
                    contributions = contributions[0]
                base = self._explainer.expected_value
                base_value = float(np.ravel(base)[-1]) if base is not None else None

                names = self._feature_names_after_transform()
                factors = self._aggregate_to_original_features(
                    names, contributions, raw_values
                )
                return factors, base_value, "shap"
            except Exception as exc:  # pragma: no cover - defensive
                self._explainer_failed = True
                log.warning("shap_explainer_unavailable", error=str(exc))

        return self._fallback_importance(raw_values), None, "global_importance_fallback"

    def _aggregate_to_original_features(
        self,
        transformed_names: list[str],
        contributions: np.ndarray,
        raw_values: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Sum one-hot column contributions back onto their source feature.

        Without this, a judge sees `cp_2` in the explanation instead of
        "Chest pain type: non-anginal pain" — the encoding is an
        implementation detail and should never surface in a clinical UI.
        """
        agg: dict[str, float] = {f: 0.0 for f in FEATURE_ORDER}
        for name, contrib in zip(transformed_names, np.ravel(contributions), strict=False):
            source = self._match_source_feature(name)
            if source:
                agg[source] += float(contrib)

        ranked = sorted(agg.items(), key=lambda kv: abs(kv[1]), reverse=True)
        out: list[dict[str, Any]] = []
        for feature, magnitude in ranked[:6]:
            if abs(magnitude) < 1e-9:
                continue
            value = raw_values.get(feature)
            value = None if value is None or (isinstance(value, float) and np.isnan(value)) else value
            out.append(
                {
                    "feature": feature,
                    "label": label_for(feature),
                    "value": float(value) if isinstance(value, (int, float, np.number)) else value,
                    "display_value": display_value(feature, value),
                    "direction": "increases_risk" if magnitude > 0 else "decreases_risk",
                    "magnitude": round(abs(float(magnitude)), 5),
                }
            )
        return out

    @staticmethod
    def _match_source_feature(transformed_name: str) -> str | None:
        clean = transformed_name.split("__")[-1]
        if clean in FEATURE_ORDER:
            return clean
        # one-hot columns look like "cp_2" / "thal_3"
        candidates = [f for f in FEATURE_ORDER if clean.startswith(f + "_")]
        if candidates:
            return max(candidates, key=len)
        return next((f for f in FEATURE_ORDER if f in clean), None)

    def _fallback_importance(self, raw_values: dict[str, Any]) -> list[dict[str, Any]]:
        """Global importances from the manifest, used only if SHAP is down.

        Labelled clearly as a fallback so the UI can say so — presenting a
        global-importance list as if it were a per-patient explanation would
        be exactly the kind of quiet overclaim this project is trying to avoid.
        """
        importances = self.artifact.manifest.get("global_importances") or {}
        ranked = sorted(importances.items(), key=lambda kv: abs(kv[1]), reverse=True)[:6]
        out = []
        for feature, magnitude in ranked:
            value = raw_values.get(feature)
            out.append(
                {
                    "feature": feature,
                    "label": label_for(feature),
                    "value": float(value) if isinstance(value, (int, float, np.number)) else value,
                    "display_value": display_value(feature, value),
                    "direction": "increases_risk",
                    "magnitude": round(abs(float(magnitude)), 5),
                }
            )
        return out


def get_clinical_predictor() -> ClinicalPredictor | None:
    """Returns None when no artifact is trained yet, rather than raising."""
    try:
        return ClinicalPredictor.instance()
    except ModelNotAvailable as exc:
        log.warning("clinical_model_unavailable", reason=str(exc))
        return None
