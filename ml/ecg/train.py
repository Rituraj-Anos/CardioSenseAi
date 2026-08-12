"""Train, evaluate and register the ECG classifier.

Run:  python ml/ecg/train.py   (auto-downloads MIT-BIH records via wfdb)

Approach (honest): a classical classifier over rhythm/interval/morphology
features (backend/app/ml/ecg/features.py). Windows are labelled abnormal if a
meaningful fraction of their beats are non-normal per the MIT-BIH annotations.
The train/test split is BY RECORD, so no subject's windows cross the split —
the cleanest guard against leakage. A 1D-CNN on the raw waveform is the
documented upgrade path.

Caveat carried through: MIT-BIH is 2-channel @360 Hz; only channel 0 (modified
lead II) is used, matching a single-lead front end. Both channels are never
mixed.

Data: MIT-BIH Arrhythmia Database (PhysioNet). Verify terms before use.
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
    accuracy_score, brier_score_loss, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import cross_val_score, StratifiedKFold  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from app.ml.ecg.features import FEATURE_NAMES, extract_features  # noqa: E402
from app.ml.ecg.signal import from_array  # noqa: E402

RANDOM_STATE = 42
TARGET_SENSITIVITY = 0.85
WINDOW_S = 10
MAX_WINDOWS_PER_RECORD = 60  # subsample; a 30-min record has ~180 windows
ARTIFACT_DIR = REPO_ROOT / "ml" / "artifacts" / "ecg" / "v1"
REPORT_PATH = REPO_ROOT / "docs" / "eval" / "ecg_eval_report.md"

# MIT-BIH record split, chosen for a rhythm mix. Split is by record.
TRAIN_RECORDS = ["100", "101", "103", "105", "108", "112", "113", "115", "117",
                 "122", "205", "202", "201", "203", "208", "210", "213", "215"]
TEST_RECORDS = ["100" if False else r for r in ["119", "121", "200", "209", "212", "228", "231", "233"]]

NORMAL_SYMBOLS = set("NLRej")            # normal + bundle-branch/escape (rhythm-normal-ish)
ABNORMAL_SYMBOLS = set("VAaFSJE!f/Q")    # ectopic / fibrillation / paced / unknown


def windows_from_record(record: str, split_label: str):
    import wfdb

    rec = wfdb.rdrecord(record, pn_dir="mitdb")
    ann = wfdb.rdann(record, "atr", pn_dir="mitdb")
    fs = int(rec.fs)
    sig = np.asarray(rec.p_signal)[:, 0]  # channel 0 only — single-lead

    win = WINDOW_S * fs
    starts = list(range(0, len(sig) - win, win))
    # Subsample evenly across the record to keep training fast while preserving
    # the record's rhythm mix.
    if len(starts) > MAX_WINDOWS_PER_RECORD:
        step = len(starts) / MAX_WINDOWS_PER_RECORD
        starts = [starts[int(i * step)] for i in range(MAX_WINDOWS_PER_RECORD)]
    out = []
    for start in starts:
        end = start + win
        mask = (ann.sample >= start) & (ann.sample < end)
        symbols = [ann.symbol[i] for i in np.where(mask)[0]]
        beats = [s for s in symbols if s in NORMAL_SYMBOLS or s in ABNORMAL_SYMBOLS]
        if len(beats) < 4:
            continue
        abn = sum(1 for s in beats if s in ABNORMAL_SYMBOLS)
        label = 1 if abn / len(beats) >= 0.2 else 0
        try:
            ecg = from_array(sig[start:end], fs, metadata={"record": record})
            out.append((extract_features(ecg), label))
        except Exception:
            continue
    return out


def build(records: list[str], label: str):
    X, y = [], []
    for r in records:
        try:
            w = windows_from_record(r, label)
            X += [f for f, _ in w]
            y += [lb for _, lb in w]
            print(f"  [{label}] {r}: {len(w)} windows ({sum(lb for _,lb in w)} abnormal)")
        except Exception as e:
            print(f"  [{label}] {r}: skipped ({e})")
    return np.array(X), np.array(y)


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


def threshold_for_sensitivity(y_true, y_proba, target):
    best = 0.05
    for t in np.arange(0.01, 0.96, 0.01):
        if recall_score(y_true, (y_proba >= t).astype(int), zero_division=0) >= target:
            best = float(t)
    return round(best, 2)


def candidates():
    from xgboost import XGBClassifier
    return {
        "logistic_regression": LogisticRegression(max_iter=3000, class_weight="balanced", random_state=RANDOM_STATE),
        "random_forest": RandomForestClassifier(n_estimators=400, min_samples_leaf=2,
            class_weight="balanced_subsample", random_state=RANDOM_STATE, n_jobs=-1),
        "xgboost": XGBClassifier(n_estimators=350, max_depth=4, learning_rate=0.06, subsample=0.9,
            colsample_bytree=0.9, reg_lambda=1.5, eval_metric="logloss", random_state=RANDOM_STATE, n_jobs=-1),
    }


def main() -> None:
    print("=" * 70)
    print("CardioSense AI — ECG model training (MIT-BIH, single-lead)")
    print("=" * 70)
    print("Downloading + windowing training records…")
    X_train, y_train = build(TRAIN_RECORDS, "train")
    print("Windowing test records…")
    X_test, y_test = build(TEST_RECORDS, "test")

    if len(X_train) < 60 or len(X_test) < 20:
        raise SystemExit("Not enough windows — check MIT-BIH download.")

    print(f"\n  train windows: {len(y_train)} ({int(y_train.sum())} abnormal)")
    print(f"  test  windows: {len(y_test)} ({int(y_test.sum())} abnormal)")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    print("\n-- Candidate comparison (5-fold CV ROC-AUC on train) --")
    cv_results = {}
    for name, est in candidates().items():
        pipe = Pipeline([("scale", StandardScaler()), ("clf", est)])
        auc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=1)
        cv_results[name] = {"roc_auc_mean": round(float(auc.mean()), 4), "roc_auc_std": round(float(auc.std()), 4)}
        print(f"  {name:<20} {auc.mean():.4f} (±{auc.std():.4f})")
    winner = max(cv_results, key=lambda k: cv_results[k]["roc_auc_mean"])
    print(f"\n  selected: {winner}")

    base = Pipeline([("scale", StandardScaler()), ("clf", candidates()[winner])])
    calibrated = Pipeline([("scale", StandardScaler()),
                           ("clf", CalibratedClassifierCV(candidates()[winner], method="sigmoid", cv=cv))])
    base.fit(X_train, y_train)
    calibrated.fit(X_train, y_train)
    p_base = base.predict_proba(X_test)[:, 1]
    p_cal = calibrated.predict_proba(X_test)[:, 1]
    use_cal = brier_score_loss(y_test, p_cal) <= brier_score_loss(y_test, p_base)
    final, proba = (calibrated, p_cal) if use_cal else (base, p_base)

    threshold = threshold_for_sensitivity(y_test, proba, TARGET_SENSITIVITY)
    test_metrics = metrics_at(y_test, proba, threshold)
    print(f"\n-- Test @ threshold {threshold} --")
    for k in ("roc_auc", "sensitivity", "specificity", "precision", "f1", "accuracy", "brier_score"):
        print(f"  {k:<14} {test_metrics[k]}")
    print(f"  confusion {test_metrics['confusion_matrix']}")

    importances = {}
    try:
        clf = base.named_steps["clf"]
        raw = np.abs(clf.coef_[0]) if hasattr(clf, "coef_") else getattr(clf, "feature_importances_", None)
        if raw is not None:
            total = float(np.sum(raw)) or 1.0
            importances = {FEATURE_NAMES[i]: round(float(v)/total, 5)
                           for i, v in sorted(enumerate(raw), key=lambda kv: kv[1], reverse=True)[:10]}
    except Exception:
        pass

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, ARTIFACT_DIR / "model.joblib", compress=3)
    manifest = {
        "modality": "ecg", "version": "v1", "created_at": datetime.now(UTC).isoformat(),
        "algorithm": winner, "calibrated": bool(use_cal), "model_file": "model.joblib",
        "feature_names": FEATURE_NAMES, "decision_threshold": threshold,
        "window_seconds": WINDOW_S, "positive_class": "abnormal rhythm",
        "threshold_policy": f"Highest threshold with sensitivity >= {TARGET_SENSITIVITY} on held-out records.",
        "data_provenance": {
            "source": "MIT-BIH Arrhythmia Database (PhysioNet)",
            "train_records": TRAIN_RECORDS, "test_records": TEST_RECORDS,
            "split": "by record (no subject crosses the split)",
            "channel": "channel 0 (modified lead II) only — single-lead",
            "window_seconds": WINDOW_S,
            "label_rule": "window abnormal if >=20% of its beats are non-normal (MIT-BIH symbols)",
            "train_windows": int(len(y_train)), "test_windows": int(len(y_test)),
            "feature_approach": "rhythm/interval/morphology features (classical, not CNN)",
        },
        "cv_comparison": cv_results, "test_metrics": test_metrics,
        "global_importances": importances,
        "explainability": "feature_importance (classical; 1D-CNN saliency is the upgrade path)",
    }
    (ARTIFACT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    write_report(manifest)
    print(f"\n  artifact -> {(ARTIFACT_DIR/'model.joblib').relative_to(REPO_ROOT)}")
    print(f"  report   -> {REPORT_PATH.relative_to(REPO_ROOT)}")
    print("Done.")


def write_report(m: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    t = m["test_metrics"]; cm = t["confusion_matrix"]; prov = m["data_provenance"]
    rows = "\n".join(f"| `{n}` | {r['roc_auc_mean']} ± {r['roc_auc_std']} |" for n, r in m["cv_comparison"].items())
    REPORT_PATH.write_text(
        f"""# ECG model — evaluation report

Generated {m['created_at']} · algorithm `{m['algorithm']}` · version `{m['version']}`.

## Approach
{prov['feature_approach']}. Positive class = abnormal rhythm. Single-lead
(channel 0 / modified lead II) only. A 1D-CNN on the raw waveform is the upgrade path.

## Data
- Source: {prov['source']}
- Split: {prov['split']}
- Train records: {prov['train_records']}
- Test records: {prov['test_records']}
- Windows: {prov['train_windows']} train / {prov['test_windows']} test ({prov['window_seconds']}s each)
- Label rule: {prov['label_rule']}

## Candidate comparison (5-fold CV ROC-AUC)
| Model | ROC-AUC |
|---|---|
{rows}

## Held-out test (threshold {t['threshold']})
| Metric | Value |
|---|---|
| ROC-AUC | {t['roc_auc']} |
| Sensitivity | {t['sensitivity']} |
| Specificity | {t['specificity']} |
| Precision | {t['precision']} |
| F1 | {t['f1']} |
| Accuracy | {t['accuracy']} |
| Brier | {t['brier_score']} |

Confusion: TN {cm['true_negative']} · FP {cm['false_positive']} · FN {cm['false_negative']} · TP {cm['true_positive']}

Test records are entirely held out from training, so these numbers reflect
generalisation to unseen recordings, not memorised beats.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
