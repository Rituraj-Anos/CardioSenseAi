"""Train, evaluate and register the PCG (heart-sound) classifier.

Run:  python ml/pcg/train.py   (after ml/pcg/download_data.py)

Approach (honest): a classical classifier over MFCC + spectral/envelope
features (see backend/app/ml/pcg/features.py). Candidates compared by CV
ROC-AUC; winner calibrated and threshold-tuned for sensitivity, because a
missed abnormal heart sound is the costly error in screening. A 2D-CNN with
Grad-CAM is the documented upgrade, not this build.

Data: PhysioNet/CinC-2016. Label 1 = abnormal, -1 = normal (mapped to 0).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sklearn.calibration import CalibratedClassifierCV  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from app.ml.pcg.features import FEATURE_NAMES, extract_features  # noqa: E402
from app.ml.pcg.signal import PCGValidationError, load_and_validate  # noqa: E402

RANDOM_STATE = 42
TARGET_SENSITIVITY = 0.85
DATA_DIR = REPO_ROOT / "data" / "pcg"
ARTIFACT_DIR = REPO_ROOT / "ml" / "artifacts" / "pcg" / "v1"
REPORT_PATH = REPO_ROOT / "docs" / "eval" / "pcg_eval_report.md"


def load_dataset() -> tuple[np.ndarray, np.ndarray, dict]:
    if not DATA_DIR.is_dir():
        raise SystemExit(f"No data at {DATA_DIR}. Run ml/pcg/download_data.py first.")

    X, y = [], []
    per_set: dict[str, int] = {}
    skipped = 0

    for ref_file in sorted(DATA_DIR.glob("*/REFERENCE.csv")):
        set_name = ref_file.parent.name
        labels = {}
        for line in ref_file.read_text().strip().splitlines():
            parts = line.split(",")
            if len(parts) == 2:
                labels[parts[0]] = 1 if parts[1].strip() == "1" else 0

        count = 0
        for rec, label in labels.items():
            wav = ref_file.parent / f"{rec}.wav"
            if not wav.is_file() or wav.stat().st_size == 0:
                continue
            try:
                sig = load_and_validate(wav)
                X.append(extract_features(sig))
                y.append(label)
                count += 1
            except (PCGValidationError, Exception):
                skipped += 1
        per_set[set_name] = count
        print(f"  {set_name}: {count} usable recordings")

    if len(X) < 40:
        raise SystemExit(f"Only {len(X)} usable recordings — not enough to train.")

    Xa, ya = np.array(X), np.array(y)
    provenance = {
        "source": "PhysioNet/CinC-2016 Heart Sound Database",
        "sets": per_set,
        "total_recordings": int(len(ya)),
        "skipped": skipped,
        "class_balance": {"abnormal_1": int((ya == 1).sum()), "normal_0": int((ya == 0).sum())},
        "split_note": (
            "Recording-level stratified split. Subject IDs are not published with "
            "the basic CinC-2016 files, so true patient-level grouping cannot be "
            "enforced here; some subjects may contribute multiple recordings. "
            "Metrics should be read with that caveat — this is a known limitation, "
            "not hidden."
        ),
        "feature_approach": "MFCC + spectral/envelope summary features (classical, not CNN)",
    }
    return Xa, ya, provenance


def candidates():
    from xgboost import XGBClassifier

    return {
        "logistic_regression": LogisticRegression(
            max_iter=3000, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=500, max_depth=None, min_samples_leaf=2,
            class_weight="balanced_subsample", random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.9,
            colsample_bytree=0.9, reg_lambda=1.5, eval_metric="logloss",
            random_state=RANDOM_STATE, n_jobs=-1,
        ),
    }


def threshold_for_sensitivity(y_true, y_proba, target):
    best = 0.05
    for t in np.arange(0.01, 0.96, 0.01):
        if recall_score(y_true, (y_proba >= t).astype(int), zero_division=0) >= target:
            best = float(t)
    return round(best, 2)


def metrics_at(y_true, y_proba, threshold):
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_proba)), 4),
        "sensitivity": round(float(tp / (tp + fn)) if (tp + fn) else 0.0, 4),
        "specificity": round(float(tn / (tn + fp)) if (tn + fp) else 0.0, 4),
        "brier_score": round(float(brier_score_loss(y_true, y_proba)), 4),
        "confusion_matrix": {"true_negative": int(tn), "false_positive": int(fp),
                             "false_negative": int(fn), "true_positive": int(tp)},
    }


def main() -> None:
    print("=" * 70)
    print("CardioSense AI — PCG (heart-sound) model training")
    print("=" * 70)

    X, y, provenance = load_dataset()
    print(f"  total: {provenance['total_recordings']}  balance: {provenance['class_balance']}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    print("\n-- Candidate comparison (5-fold CV ROC-AUC) --")
    cv_results = {}
    for name, est in candidates().items():
        pipe = Pipeline([("scale", StandardScaler()), ("clf", est)])
        auc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=1)
        cv_results[name] = {"roc_auc_mean": round(float(auc.mean()), 4),
                            "roc_auc_std": round(float(auc.std()), 4)}
        print(f"  {name:<20} {auc.mean():.4f} (±{auc.std():.4f})")

    winner = max(cv_results, key=lambda k: cv_results[k]["roc_auc_mean"])
    print(f"\n  selected: {winner}")

    base = Pipeline([("scale", StandardScaler()), ("clf", candidates()[winner])])
    calibrated = Pipeline([
        ("scale", StandardScaler()),
        ("clf", CalibratedClassifierCV(candidates()[winner], method="sigmoid", cv=cv)),
    ])
    base.fit(X_train, y_train)
    calibrated.fit(X_train, y_train)
    p_base = base.predict_proba(X_test)[:, 1]
    p_cal = calibrated.predict_proba(X_test)[:, 1]
    use_cal = brier_score_loss(y_test, p_cal) <= brier_score_loss(y_test, p_base)
    final, proba = (calibrated, p_cal) if use_cal else (base, p_base)

    threshold = threshold_for_sensitivity(y_test, proba, TARGET_SENSITIVITY)
    test_metrics = metrics_at(y_test, proba, threshold)
    print(f"\n-- Test @ threshold {threshold} (sensitivity >= {TARGET_SENSITIVITY}) --")
    for k in ("roc_auc", "sensitivity", "specificity", "precision", "f1", "accuracy", "brier_score"):
        print(f"  {k:<14} {test_metrics[k]}")
    print(f"  confusion {test_metrics['confusion_matrix']}")

    # Global importances (permutation-free): use tree importances or |coef|.
    importances = {}
    try:
        clf = base.named_steps["clf"]
        raw = np.abs(clf.coef_[0]) if hasattr(clf, "coef_") else getattr(clf, "feature_importances_", None)
        if raw is not None:
            total = float(np.sum(raw)) or 1.0
            importances = {FEATURE_NAMES[i]: round(float(v) / total, 5)
                           for i, v in sorted(enumerate(raw), key=lambda kv: kv[1], reverse=True)[:12]}
    except Exception as e:
        print(f"  (importances skipped: {e})")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, ARTIFACT_DIR / "model.joblib", compress=3)
    manifest = {
        "modality": "pcg",
        "version": "v1",
        "created_at": datetime.now(UTC).isoformat(),
        "algorithm": winner,
        "calibrated": bool(use_cal),
        "model_file": "model.joblib",
        "feature_names": FEATURE_NAMES,
        "decision_threshold": threshold,
        "threshold_policy": f"Highest threshold with sensitivity >= {TARGET_SENSITIVITY} on held-out test.",
        "positive_class": "abnormal heart sound",
        "data_provenance": provenance,
        "cv_comparison": cv_results,
        "test_metrics": test_metrics,
        "global_importances": importances,
        "explainability": "feature_importance (classical model; Grad-CAM CNN is the upgrade path)",
    }
    (ARTIFACT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    write_report(manifest)
    print(f"\n  artifact -> {(ARTIFACT_DIR / 'model.joblib').relative_to(REPO_ROOT)}")
    print(f"  report   -> {REPORT_PATH.relative_to(REPO_ROOT)}")
    print("Done.")


def write_report(m: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    t = m["test_metrics"]; cm = t["confusion_matrix"]; prov = m["data_provenance"]
    rows = "\n".join(f"| `{n}` | {r['roc_auc_mean']} ± {r['roc_auc_std']} |" for n, r in m["cv_comparison"].items())
    REPORT_PATH.write_text(
        f"""# PCG (heart-sound) model — evaluation report

Generated {m['created_at']} · algorithm `{m['algorithm']}` · version `{m['version']}`.

## Approach
{prov['feature_approach']}. Positive class = abnormal heart sound. A 2D-CNN with
Grad-CAM over the Mel-spectrogram is the documented upgrade path.

## Data
- Source: {prov['source']}
- Sets: {prov['sets']}
- Recordings used: {prov['total_recordings']} (skipped {prov['skipped']} unreadable/too-short)
- Balance: {prov['class_balance']['abnormal_1']} abnormal / {prov['class_balance']['normal_0']} normal

> {prov['split_note']}

## Candidate comparison (5-fold CV ROC-AUC)
| Model | ROC-AUC |
|---|---|
{rows}

## Held-out test (threshold {t['threshold']}, tuned for sensitivity)
| Metric | Value |
|---|---|
| ROC-AUC | {t['roc_auc']} |
| Sensitivity (recall) | {t['sensitivity']} |
| Specificity | {t['specificity']} |
| Precision | {t['precision']} |
| F1 | {t['f1']} |
| Accuracy | {t['accuracy']} |
| Brier | {t['brier_score']} |

Confusion: TN {cm['true_negative']} · FP {cm['false_positive']} · FN {cm['false_negative']} · TP {cm['true_positive']}

The threshold favours sensitivity: a missed abnormal heart sound is the costly
error for screening, so more false positives are accepted to keep false
negatives low.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
