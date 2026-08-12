"""Shared preprocessing for the clinical model.

Imported by BOTH `ml/clinical/train.py` and the live predictor. That sharing is
the whole point: it is the mechanism that prevents train/serve skew
(Blueprint Section 22), so keep it dependency-light and free of any
training-only or request-only concerns.

One real data-quality issue is handled here rather than silently ignored.
In the widely circulated 303-row `heart.csv`, the original UCI dataset's
missing values for `ca` and `thal` were not dropped — they were re-encoded as
`ca = 4` and `thal = 0`. Both are out-of-range for their documented domains
(`ca` is 0–3 vessels, `thal` is 1–3). Treating them as ordinary values teaches
the model that a nonexistent measurement is a real one, so they are mapped to
an explicit "not recorded" marker and flagged, not quietly passed through.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.clinical.features import (
    CATEGORICAL_FEATURES,
    FEATURE_ORDER,
    TARGET_COLUMN,
)

# Sentinel encodings present in the public CSV that actually mean "missing".
SENTINEL_MISSING: dict[str, set[int]] = {
    "ca": {4},
    "thal": {0},
}

# --------------------------------------------------------------------------
# Label semantics — the single most dangerous detail in this dataset
# --------------------------------------------------------------------------
# In this widely circulated `heart.csv`, `target == 1` means NO disease and
# `target == 0` means disease present. That is inverted from how almost every
# tutorial and notebook using this file reads it.
#
# Verified two independent ways:
#   1. Against the original UCI `processed.cleveland.data`: UCI has 164 healthy
#      (num == 0) and 139 diseased; this file has 165 rows at target == 1 and
#      138 at target == 0.
#   2. By correlation with established risk factors. The target == 1 group is
#      younger, has far less exercise-induced angina (0.14 vs 0.55), less ST
#      depression (0.58 vs 1.59), fewer diseased vessels (0.36 vs 1.17) and a
#      HIGHER peak heart rate (158 vs 139). Those are all healthy-group traits.
#
# Training on the raw column as if 1 meant "at risk" produces a model whose
# "risk score" is actually a wellness score. In a screening tool that inversion
# is worse than having no model at all, so the mapping is made explicit here and
# guarded by `verify_label_direction` below.
RAW_TARGET_HEALTHY_VALUE: int = 1
RAW_TARGET_DISEASE_VALUE: int = 0

# Sign that each feature's correlation with the at-risk label must have.
# Derived from established cardiology, not from this dataset.
_EXPECTED_RISK_CORRELATION_SIGN: dict[str, int] = {
    "exang": +1,     # exercise-induced angina indicates disease
    "oldpeak": +1,   # greater ST depression indicates ischaemia
    "ca": +1,        # more diseased vessels
    "thalach": -1,   # a higher achievable peak heart rate is healthier
    "age": +1,
}


def derive_at_risk_target(df: pd.DataFrame) -> pd.Series:
    """Map the raw `target` column to 1 = at risk, 0 = not at risk."""
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"'{TARGET_COLUMN}' column is required to derive labels.")
    raw = pd.to_numeric(df[TARGET_COLUMN], errors="coerce")
    return (raw == RAW_TARGET_DISEASE_VALUE).astype(int)


def verify_label_direction(df: pd.DataFrame, y_at_risk: pd.Series) -> dict[str, float]:
    """Fail loudly if the derived label does not behave like a disease label.

    This exists so that a swapped dataset revision, a re-download from a
    different source, or a well-meaning edit to the mapping above cannot quietly
    invert every risk score the product reports. Cheap check, catastrophic bug.
    """
    correlations: dict[str, float] = {}
    violations: list[str] = []

    for feature, expected_sign in _EXPECTED_RISK_CORRELATION_SIGN.items():
        if feature not in df.columns:
            continue
        corr = float(pd.to_numeric(df[feature], errors="coerce").corr(y_at_risk))
        correlations[feature] = round(corr, 4)
        # Ignore near-zero correlations; only a confident wrong sign is a failure.
        if abs(corr) > 0.15 and (corr > 0) != (expected_sign > 0):
            violations.append(
                f"{feature}: expected {'positive' if expected_sign > 0 else 'negative'} "
                f"correlation with being at risk, got {corr:+.3f}"
            )

    if violations:
        raise ValueError(
            "Label direction check failed — the target may be inverted for this "
            "dataset revision. Refusing to train a model that would report risk "
            "backwards.\n  " + "\n  ".join(violations)
        )
    return correlations


def coerce_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Verify the expected columns exist and are numeric. Fails loudly."""
    missing = [c for c in FEATURE_ORDER if c not in df.columns]
    if missing:
        raise ValueError(f"heart.csv is missing expected feature columns: {missing}")

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for col in FEATURE_ORDER:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if TARGET_COLUMN in out.columns:
        out[TARGET_COLUMN] = pd.to_numeric(out[TARGET_COLUMN], errors="coerce").astype("Int64")
    return out


def sentinel_report(df: pd.DataFrame) -> dict[str, int]:
    """Count rows carrying a disguised-missing sentinel, per column."""
    return {
        col: int(df[col].isin(list(values)).sum())
        for col, values in SENTINEL_MISSING.items()
        if col in df.columns
    }


def normalise_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    """Map disguised-missing sentinels to NaN so the imputer handles them
    as what they actually are."""
    out = df.copy()
    for col, values in SENTINEL_MISSING.items():
        if col in out.columns:
            out.loc[out[col].isin(list(values)), col] = np.nan
    return out


def build_feature_frame(records: dict | list[dict] | pd.DataFrame) -> pd.DataFrame:
    """Turn raw input into the model's exact input frame.

    Accepts a single dict (one live request), a list of dicts, or a DataFrame,
    and always returns columns in `FEATURE_ORDER` with sentinels normalised.
    """
    if isinstance(records, dict):
        frame = pd.DataFrame([records])
    elif isinstance(records, list):
        frame = pd.DataFrame(records)
    else:
        frame = records.copy()

    frame = coerce_schema(frame)
    frame = normalise_sentinels(frame)
    return frame.loc[:, list(FEATURE_ORDER)]


def categorical_indices() -> list[int]:
    """Positional indices of categorical features within FEATURE_ORDER."""
    return [FEATURE_ORDER.index(c) for c in CATEGORICAL_FEATURES]
