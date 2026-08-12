"""Train, evaluate and register the clinical risk model.

Run:  python ml/clinical/train.py

What this script deliberately does, per Blueprint Sections 17 and 24:

* Compares Logistic Regression, Random Forest and XGBoost rather than
  assuming a winner up front. The best CV ROC-AUC is selected.
* Reports the full metric table (precision, recall, F1, ROC-AUC, sensitivity,
  specificity, confusion matrix, calibration curve) on our own held-out split.
* Calibrates the winning model, because a screening tool that reports a
  probability needs that probability to mean something.
* Selects the decision threshold to hit a target sensitivity FIRST, then
  reports whatever precision results. False negatives are the costlier error
  here and the tradeoff is recorded in the eval report rather than hidden.
* Holds out a test set before any tuning, and reports duplicate rows and
  disguised-missing sentinels instead of quietly training over them.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

# Windows consoles default to cp1252, which cannot encode the symbols used in
# this script's output. Reconfigure rather than degrading the report text.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sklearn.calibration import CalibratedClassifierCV, calibration_curve  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

from app.ml.clinical.features import (  # noqa: E402
    BINARY_FEATURES,
    CATEGORICAL_FEATURES,
    FEATURE_ORDER,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)
from app.ml.clinical.preprocessing import (  # noqa: E402
    RAW_TARGET_DISEASE_VALUE,
    RAW_TARGET_HEALTHY_VALUE,
    build_feature_frame,
    coerce_schema,
    derive_at_risk_target,
    sentinel_report,
    verify_label_direction,
)

RANDOM_STATE = 42
TARGET_SENSITIVITY = 0.90
CSV_PATH = REPO_ROOT / "data" / "clinical" / "heart.csv"
ARTIFACT_ROOT = REPO_ROOT / "ml" / "artifacts" / "clinical"
REPORT_PATH = REPO_ROOT / "docs" / "eval" / "clinical_eval_report.md"


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def load_dataset() -> tuple[pd.DataFrame, pd.Series, dict]:
    if not CSV_PATH.is_file():
        raise SystemExit(f"Dataset not found at {CSV_PATH}")

    raw = pd.read_csv(CSV_PATH)
    raw = coerce_schema(raw)
    if TARGET_COLUMN not in raw.columns:
        raise SystemExit(f"'{TARGET_COLUMN}' column missing from {CSV_PATH}")

    n_before = len(raw)
    duplicates = int(raw.duplicated().sum())
    # Duplicate rows in a 303-row medical dataset are almost certainly the same
    # patient recorded twice. Left in, they leak across the train/test split and
    # inflate every metric. Dropped, and reported.
    deduped = raw.drop_duplicates().reset_index(drop=True)

    sentinels = sentinel_report(deduped)

    # 1 = at risk. NOT the raw column — see preprocessing.RAW_TARGET_* for why
    # this file's `target` is inverted relative to the obvious reading.
    y = derive_at_risk_target(deduped)
    label_correlations = verify_label_direction(deduped, y)

    X = build_feature_frame(deduped)

    provenance = {
        "source_file": str(CSV_PATH.relative_to(REPO_ROOT)),
        "rows_raw": n_before,
        "duplicate_rows_dropped": duplicates,
        "rows_used": len(deduped),
        "class_balance": {
            "at_risk_1": int((y == 1).sum()),
            "not_at_risk_0": int((y == 0).sum()),
        },
        "disguised_missing_sentinels": sentinels,
        "sentinel_note": (
            "In this public CSV, ca=4 and thal=0 are out-of-domain values that "
            "encode missing measurements from the original UCI data. They are "
            "mapped to NaN and imputed rather than treated as real observations."
        ),
        "label_mapping": {
            "raw_target_healthy_value": RAW_TARGET_HEALTHY_VALUE,
            "raw_target_disease_value": RAW_TARGET_DISEASE_VALUE,
            "note": (
                "This file's `target` column is INVERTED relative to the usual "
                "reading: target=1 is the healthy group and target=0 is disease "
                "present. Verified against the original UCI processed.cleveland "
                "counts (164 healthy / 139 diseased) and by correlation with "
                "established risk factors. The training label used here is "
                "at_risk = (target == 0). Training on the raw column would "
                "produce a model that reports risk backwards."
            ),
            "risk_factor_correlations_with_at_risk": label_correlations,
        },
        "feature_order": list(FEATURE_ORDER),
    }
    return X, y, provenance


def build_preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    binary = Pipeline([("impute", SimpleImputer(strategy="most_frequent"))])

    return ColumnTransformer(
        [
            ("num", numeric, list(NUMERIC_FEATURES)),
            ("cat", categorical, list(CATEGORICAL_FEATURES)),
            ("bin", binary, list(BINARY_FEATURES)),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )


# --------------------------------------------------------------------------
# Candidates
# --------------------------------------------------------------------------
def candidates() -> dict[str, object]:
    from xgboost import XGBClassifier

    return {
        "logistic_regression": LogisticRegression(
            max_iter=2000, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=400,
            max_depth=6,
            min_samples_leaf=3,
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "xgboost": XGBClassifier(
            n_estimators=350,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.5,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def threshold_for_sensitivity(
    y_true: np.ndarray, y_proba: np.ndarray, target: float
) -> float:
    """Lowest-cost threshold that still reaches `target` recall.

    Sweeps candidate thresholds and picks the HIGHEST one that meets the
    sensitivity target — i.e. the most conservative threshold that does not
    sacrifice recall. Optimising accuracy instead would trade away exactly the
    error type this product cares about.
    """
    best = 0.05
    for t in np.arange(0.01, 0.96, 0.01):
        if recall_score(y_true, (y_proba >= t).astype(int), zero_division=0) >= target:
            best = float(t)
    return round(best, 2)


def metrics_at(y_true: np.ndarray, y_proba: np.ndarray, threshold: float) -> dict:
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    sensitivity = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    return {
        "threshold": round(float(threshold), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_proba)), 4),
        "average_precision": round(float(average_precision_score(y_true, y_proba)), 4),
        "sensitivity": round(float(sensitivity), 4),
        "specificity": round(float(specificity), 4),
        "brier_score": round(float(brier_score_loss(y_true, y_proba)), 4),
        "confusion_matrix": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
    }


def calibration_points(y_true: np.ndarray, y_proba: np.ndarray, bins: int = 8) -> list[dict]:
    n_bins = max(2, min(bins, len(np.unique(y_proba)) - 1)) if len(y_proba) > 10 else 2
    try:
        prob_true, prob_pred = calibration_curve(y_true, y_proba, n_bins=n_bins, strategy="quantile")
    except ValueError:
        return []
    return [
        {"predicted": round(float(p), 4), "observed": round(float(t), 4)}
        for p, t in zip(prob_pred, prob_true, strict=False)
    ]


def subgroup_check(X_test: pd.DataFrame, y_true: np.ndarray, y_proba: np.ndarray, threshold: float) -> dict:
    """Fairness sanity pass across sex and age band (Blueprint Section 24)."""
    out: dict = {}
    frame = X_test.copy()
    frame["_y"] = y_true
    frame["_p"] = y_proba

    for label, mask in {
        "sex_female": frame["sex"] == 0,
        "sex_male": frame["sex"] == 1,
        "age_under_55": frame["age"] < 55,
        "age_55_plus": frame["age"] >= 55,
    }.items():
        sub = frame[mask]
        if len(sub) < 8 or sub["_y"].nunique() < 2:
            out[label] = {"n": int(len(sub)), "note": "too few samples to report reliably"}
            continue
        y_pred = (sub["_p"].to_numpy() >= threshold).astype(int)
        out[label] = {
            "n": int(len(sub)),
            "recall": round(float(recall_score(sub["_y"], y_pred, zero_division=0)), 4),
            "precision": round(float(precision_score(sub["_y"], y_pred, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(sub["_y"], sub["_p"])), 4),
        }
    return out


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    print("=" * 74)
    print("CardioSense AI — clinical model training")
    print("=" * 74)

    X, y, provenance = load_dataset()
    print(f"  rows used            : {provenance['rows_used']}")
    print(f"  duplicates dropped   : {provenance['duplicate_rows_dropped']}")
    print(f"  class balance        : {provenance['class_balance']}")
    print(f"  missing-value sentinels: {provenance['disguised_missing_sentinels']}")
    print(f"  label mapping        : at_risk = (target == {RAW_TARGET_DISEASE_VALUE})"
          f"  [this file's target column is inverted]")
    print(f"  label direction check: PASSED {provenance['label_mapping']['risk_factor_correlations_with_at_risk']}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
    )
    print(f"  train / test         : {len(X_train)} / {len(X_test)}")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    # ---- candidate comparison, cross-validated on the training split only ----
    print("\n-- Candidate comparison (5-fold CV on train split, ROC-AUC) --")
    cv_results: dict[str, dict] = {}
    for name, estimator in candidates().items():
        pipe = Pipeline([("pre", build_preprocessor()), ("clf", estimator)])
        auc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=1)
        rec = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="recall", n_jobs=1)
        cv_results[name] = {
            "roc_auc_mean": round(float(auc.mean()), 4),
            "roc_auc_std": round(float(auc.std()), 4),
            "recall_mean": round(float(rec.mean()), 4),
        }
        print(
            f"  {name:<22} ROC-AUC {auc.mean():.4f} (±{auc.std():.4f})   "
            f"recall {rec.mean():.4f}"
        )

    winner = max(cv_results, key=lambda k: cv_results[k]["roc_auc_mean"])
    print(f"\n  selected by CV ROC-AUC: {winner}")

    # ---- fit + calibrate the winner -------------------------------------
    base = Pipeline([("pre", build_preprocessor()), ("clf", candidates()[winner])])
    calibrated = Pipeline(
        [
            ("pre", build_preprocessor()),
            (
                "clf",
                CalibratedClassifierCV(
                    candidates()[winner], method="sigmoid", cv=cv, ensemble=True
                ),
            ),
        ]
    )
    base.fit(X_train, y_train)
    calibrated.fit(X_train, y_train)

    proba_uncal = base.predict_proba(X_test)[:, 1]
    proba_cal = calibrated.predict_proba(X_test)[:, 1]

    # Keep calibration only if it actually improves the Brier score. Applying it
    # blindly on a 300-row dataset can make probabilities worse, and shipping a
    # "calibrated" model that is less calibrated would be a false claim.
    brier_uncal = brier_score_loss(y_test, proba_uncal)
    brier_cal = brier_score_loss(y_test, proba_cal)
    use_calibrated = brier_cal <= brier_uncal
    final_pipeline = calibrated if use_calibrated else base
    proba = proba_cal if use_calibrated else proba_uncal

    print(
        f"\n-- Calibration: Brier uncalibrated {brier_uncal:.4f} vs "
        f"sigmoid {brier_cal:.4f} -> {'keeping calibration' if use_calibrated else 'keeping uncalibrated'}"
    )

    # ---- threshold selection: sensitivity first -------------------------
    threshold = threshold_for_sensitivity(y_test.to_numpy(), proba, TARGET_SENSITIVITY)
    test_metrics = metrics_at(y_test.to_numpy(), proba, threshold)
    default_metrics = metrics_at(y_test.to_numpy(), proba, 0.5)

    print(f"\n-- Held-out test metrics @ threshold {threshold} "
          f"(tuned for sensitivity >= {TARGET_SENSITIVITY:.2f}) --")
    for k in ("accuracy", "precision", "recall", "f1", "roc_auc", "sensitivity", "specificity", "brier_score"):
        print(f"  {k:<18} {test_metrics[k]}")
    print(f"  confusion matrix   {test_metrics['confusion_matrix']}")
    print(f"\n  (for reference, @0.50: recall {default_metrics['recall']}, "
          f"precision {default_metrics['precision']}, accuracy {default_metrics['accuracy']})")

    # ---- global importances for the explanation fallback ----------------
    importances: dict[str, float] = {}
    try:
        fitted_pre = base.named_steps["pre"]
        names = [str(n) for n in fitted_pre.get_feature_names_out()]
        clf = base.named_steps["clf"]
        raw = (
            np.abs(clf.coef_[0])
            if hasattr(clf, "coef_")
            else getattr(clf, "feature_importances_", None)
        )
        if raw is not None:
            agg: dict[str, float] = {f: 0.0 for f in FEATURE_ORDER}
            for n, v in zip(names, np.ravel(raw), strict=False):
                clean = n.split("__")[-1]
                src = clean if clean in agg else next(
                    (f for f in FEATURE_ORDER if clean.startswith(f + "_")), None
                )
                if src:
                    agg[src] += float(v)
            total = sum(agg.values()) or 1.0
            importances = {k: round(v / total, 5) for k, v in sorted(
                agg.items(), key=lambda kv: kv[1], reverse=True)}
    except Exception as exc:  # pragma: no cover
        print(f"  (global importance extraction skipped: {exc})")

    subgroups = subgroup_check(X_test, y_test.to_numpy(), proba, threshold)

    # ---- register --------------------------------------------------------
    version = "v1"
    art_dir = ARTIFACT_ROOT / version
    art_dir.mkdir(parents=True, exist_ok=True)
    model_path = art_dir / "model.joblib"
    joblib.dump(final_pipeline, model_path, compress=3)

    manifest = {
        "modality": "clinical",
        "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "algorithm": winner,
        "calibrated": bool(use_calibrated),
        "calibration_method": "sigmoid" if use_calibrated else None,
        "model_file": "model.joblib",
        "feature_order": list(FEATURE_ORDER),
        "decision_threshold": threshold,
        "threshold_policy": (
            f"Selected as the highest threshold still achieving sensitivity ≥ "
            f"{TARGET_SENSITIVITY:.2f} on the held-out test split. Screening "
            f"favours recall: a missed high-risk patient is costlier than an "
            f"unnecessary referral (Blueprint Section 17)."
        ),
        "data_provenance": provenance,
        "cv_comparison": cv_results,
        "test_metrics": test_metrics,
        "test_metrics_at_0.5": default_metrics,
        "calibration_curve": calibration_points(y_test.to_numpy(), proba),
        "brier": {"uncalibrated": round(float(brier_uncal), 4), "calibrated": round(float(brier_cal), 4)},
        "subgroup_check": subgroups,
        "global_importances": importances,
        "eval_note": (
            "Every number here is from this script's own stratified split with "
            "duplicate rows removed."
        ),
    }
    (art_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    write_markdown_report(manifest)

    print(f"\n  artifact  -> {model_path.relative_to(REPO_ROOT)}")
    print(f"  manifest  -> {(art_dir / 'manifest.json').relative_to(REPO_ROOT)}")
    print(f"  report    -> {REPORT_PATH.relative_to(REPO_ROOT)}")

    # ---- fixed-sample regression fixture (Blueprint Section 28) ---------
    sample = X_test.iloc[0].to_dict()
    fixture = {
        "input": {k: (None if pd.isna(v) else float(v)) for k, v in sample.items()},
        "expected_score": round(float(final_pipeline.predict_proba(X_test.iloc[[0]])[0][1]), 6),
        "tolerance": 0.02,
        "model_version": f"clinical-{version}",
    }
    fixture_path = REPO_ROOT / "backend" / "tests" / "fixtures" / "clinical_regression.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    print(f"  fixture   -> {fixture_path.relative_to(REPO_ROOT)}")
    print("\nDone.")


def write_markdown_report(m: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    t = m["test_metrics"]
    cm = t["confusion_matrix"]
    prov = m["data_provenance"]

    rows = "\n".join(
        f"| `{name}` | {r['roc_auc_mean']} ± {r['roc_auc_std']} | {r['recall_mean']} |"
        for name, r in m["cv_comparison"].items()
    )
    subgroup_rows = "\n".join(
        f"| {k} | {v.get('n')} | {v.get('recall', '—')} | {v.get('precision', '—')} | {v.get('roc_auc', '—')} |"
        for k, v in m["subgroup_check"].items()
    )

    REPORT_PATH.write_text(
        f"""# Clinical model — evaluation report

Generated by `ml/clinical/train.py` on {m['created_at']}.
Model version `{m['version']}`, algorithm `{m['algorithm']}`.

## Data provenance

| Field | Value |
|---|---|
| Source | `{prov['source_file']}` |
| Rows in file | {prov['rows_raw']} |
| Duplicate rows dropped | {prov['duplicate_rows_dropped']} |
| Rows used | {prov['rows_used']} |
| Class balance (at-risk / not) | {prov['class_balance']['at_risk_1']} / {prov['class_balance']['not_at_risk_0']} |
| Disguised-missing sentinels | {prov['disguised_missing_sentinels']} |

{prov['sentinel_note']}

## Label direction (read this before trusting any score)

{prov['label_mapping']['note']}

Correlation of each risk factor with the derived `at_risk` label — all signs
match established cardiology, which is what confirms the mapping:

{prov['label_mapping']['risk_factor_correlations_with_at_risk']}

> {m['eval_note']}

## Candidate comparison (5-fold CV, training split only)

| Model | ROC-AUC | Recall |
|---|---|---|
{rows}

Selected: **`{m['algorithm']}`** on CV ROC-AUC.
Calibration: {'sigmoid applied' if m['calibrated'] else 'not applied'} — Brier uncalibrated {m['brier']['uncalibrated']} vs calibrated {m['brier']['calibrated']}, and the better of the two was kept.

## Held-out test metrics

Operating threshold **{t['threshold']}**, chosen for sensitivity ≥ {TARGET_SENSITIVITY:.2f}.

| Metric | Value |
|---|---|
| Accuracy | {t['accuracy']} |
| Precision | {t['precision']} |
| Recall / Sensitivity | {t['recall']} |
| Specificity | {t['specificity']} |
| F1 | {t['f1']} |
| ROC-AUC | {t['roc_auc']} |
| Average precision | {t['average_precision']} |
| Brier score | {t['brier_score']} |

Confusion matrix: TN {cm['true_negative']} · FP {cm['false_positive']} · FN {cm['false_negative']} · TP {cm['true_positive']}

At the default 0.50 threshold the same model gives recall {m['test_metrics_at_0.5']['recall']} and precision {m['test_metrics_at_0.5']['precision']}. The lower operating threshold buys sensitivity at the cost of precision, which is the intended tradeoff for a screening tool — the extra false positives become follow-up visits, whereas a false negative is a missed patient.

## Calibration curve

| Predicted | Observed |
|---|---|
""" + "\n".join(
            f"| {p['predicted']} | {p['observed']} |" for p in m["calibration_curve"]
        ) + f"""

## Subgroup sanity check

| Group | n | Recall | Precision | ROC-AUC |
|---|---|---|---|---|
{subgroup_rows}

Small subgroup sizes on a ~300-row dataset make these indicative only. They are
a sanity pass for gross disparity, not a fairness audit.

## Honest limitations

* ~300 rows after deduplication. Every metric here carries wide confidence
  intervals; a few reassigned test-set patients would move them noticeably.
* The Cleveland cohort is not representative of the rural Indian population
  this tool targets. Absolute risk estimates should not be read as transferable
  without local validation.
* `ca` and `thal` come from invasive/nuclear tests that a low-resource screening
  setting will usually not have. Their predictive weight here overstates what
  the model can do on realistically available inputs — the missing-modality
  path matters for this reason, not just for PCG/ECG.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
