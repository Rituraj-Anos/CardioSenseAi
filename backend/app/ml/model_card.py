"""Model card: surface the clinical model's real evaluation metrics.

Everything here is read from the trained artifact's manifest.json — the same
numbers produced by ml/clinical/train.py on the held-out split. Nothing is
hand-entered, so the Methodology page can never drift from the actual model.
"""

from __future__ import annotations

from typing import Any

from app.ml.clinical.features import FEATURE_LABELS
from app.ml.fusion.engine import BASE_WEIGHTS, FUSION_VERSION
from app.ml.registry import ModelNotAvailable, resolve


def build_model_card() -> dict[str, Any]:
    try:
        artifact = resolve("clinical")
    except ModelNotAvailable:
        return {"available": False, "reason": "No trained clinical model is registered."}

    m = artifact.manifest
    test = m.get("test_metrics", {})
    prov = m.get("data_provenance", {})

    return {
        "available": True,
        "model": {
            "modality": "clinical",
            "version": artifact.version,
            "algorithm": m.get("algorithm"),
            "calibrated": m.get("calibrated"),
            "decision_threshold": m.get("decision_threshold"),
            "threshold_policy": m.get("threshold_policy"),
            "created_at": m.get("created_at"),
        },
        "metrics": {
            "roc_auc": test.get("roc_auc"),
            "sensitivity": test.get("sensitivity"),
            "specificity": test.get("specificity"),
            "precision": test.get("precision"),
            "recall": test.get("recall"),
            "f1": test.get("f1"),
            "accuracy": test.get("accuracy"),
            "brier_score": test.get("brier_score"),
            "confusion_matrix": test.get("confusion_matrix"),
        },
        "metrics_at_0_5": m.get("test_metrics_at_0.5", {}),
        "calibration_curve": m.get("calibration_curve", []),
        "cv_comparison": m.get("cv_comparison", {}),
        "data": {
            "source_file": prov.get("source_file"),
            "rows_used": prov.get("rows_used"),
            "duplicates_dropped": prov.get("duplicate_rows_dropped"),
            "class_balance": prov.get("class_balance"),
            "label_note": (prov.get("label_mapping") or {}).get("note"),
        },
        "feature_importances": [
            {"feature": k, "label": FEATURE_LABELS.get(k, k), "importance": v}
            for k, v in (m.get("global_importances") or {}).items()
        ],
        "subgroup_check": m.get("subgroup_check", {}),
        "eval_note": m.get("eval_note"),
        "fusion": {"version": FUSION_VERSION, "base_weights": BASE_WEIGHTS},
    }
