"""Clinical model tests: label direction, preprocessing, and a fixed-sample
regression check (Blueprint Section 28).

The label-direction test is the most important one in this file. It is the
guard against silently shipping a model whose risk score runs backwards.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.clinical.features import FEATURE_ORDER, display_value, label_for
from app.ml.clinical.predictor import get_clinical_predictor
from app.ml.clinical.preprocessing import (
    RAW_TARGET_DISEASE_VALUE,
    build_feature_frame,
    coerce_schema,
    derive_at_risk_target,
    normalise_sentinels,
    sentinel_report,
    verify_label_direction,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "data" / "clinical" / "heart.csv"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "clinical_regression.json"


@pytest.fixture(scope="module")
def raw_df() -> pd.DataFrame:
    if not CSV_PATH.is_file():
        pytest.skip("heart.csv not present")
    return coerce_schema(pd.read_csv(CSV_PATH))


# --------------------------------------------------------------------------
# Label semantics
# --------------------------------------------------------------------------
def test_derived_label_marks_disease_as_the_positive_class(raw_df):
    y = derive_at_risk_target(raw_df)
    assert set(y.unique()) <= {0, 1}
    # This file's raw target==0 rows are the diseased ones.
    assert int(y.sum()) == int((raw_df["target"] == RAW_TARGET_DISEASE_VALUE).sum())


def test_label_direction_check_passes_on_the_shipped_dataset(raw_df):
    correlations = verify_label_direction(raw_df, derive_at_risk_target(raw_df))
    # Established risk factors must correlate positively with being at risk.
    assert correlations["exang"] > 0
    assert correlations["oldpeak"] > 0
    assert correlations["ca"] > 0
    # A higher achievable peak heart rate is protective.
    assert correlations["thalach"] < 0


def test_label_direction_check_rejects_an_inverted_label(raw_df):
    """The guard must actually fire, not just pass on good data."""
    inverted = 1 - derive_at_risk_target(raw_df)
    with pytest.raises(ValueError, match="Label direction check failed"):
        verify_label_direction(raw_df, inverted)


# --------------------------------------------------------------------------
# Preprocessing
# --------------------------------------------------------------------------
def test_disguised_missing_values_are_detected(raw_df):
    report = sentinel_report(raw_df)
    # ca=4 and thal=0 are out-of-domain codes that mean "not measured".
    assert report["ca"] > 0
    assert report["thal"] > 0


def test_sentinels_become_nan_rather_than_being_treated_as_real_values(raw_df):
    cleaned = normalise_sentinels(raw_df)
    assert not (cleaned["ca"] == 4).any()
    assert not (cleaned["thal"] == 0).any()
    assert cleaned["ca"].isna().sum() == sentinel_report(raw_df)["ca"]


def test_feature_frame_has_contractual_column_order():
    frame = build_feature_frame(
        {
            "age": 55, "sex": 1, "cp": 0, "trestbps": 140, "chol": 240, "fbs": 0,
            "restecg": 1, "thalach": 140, "exang": 1, "oldpeak": 1.2, "slope": 1,
            "ca": 1, "thal": 3,
        }
    )
    assert list(frame.columns) == list(FEATURE_ORDER)
    assert len(frame) == 1


def test_missing_feature_column_fails_loudly():
    with pytest.raises(ValueError, match="missing expected feature columns"):
        build_feature_frame({"age": 55})


# --------------------------------------------------------------------------
# Curated label lookup (Blueprint Section 21)
# --------------------------------------------------------------------------
def test_every_feature_has_a_clinician_facing_label():
    for feature in FEATURE_ORDER:
        label = label_for(feature)
        assert label != feature, f"{feature} has no curated label"
        assert "_" not in label


def test_coded_values_render_as_words_not_numbers():
    assert display_value("cp", 0) == "Asymptomatic"
    assert display_value("cp", 3) == "Typical angina"
    assert display_value("thal", 2) == "Normal"
    assert display_value("thal", 3) == "Reversible defect"
    assert display_value("slope", 2) == "Upsloping"
    assert display_value("restecg", 1) == "Normal"
    assert display_value("sex", 1) == "Male"
    assert display_value("exang", 1) == "Yes"


def test_magnitudes_render_with_units():
    assert display_value("trestbps", 140) == "140 mm Hg"
    assert display_value("chol", 240) == "240 mg/dl"
    assert display_value("thalach", 150) == "150 bpm"
    assert display_value("oldpeak", 1.5) == "1.5 mm"
    assert display_value("age", 55) == "55 years"


def test_unrecorded_values_do_not_render_as_a_real_measurement():
    assert display_value("thal", 0) == "Not recorded"
    assert display_value("trestbps", None) == "—"


# --------------------------------------------------------------------------
# Model behaviour
# --------------------------------------------------------------------------
def test_model_artifact_is_loadable():
    predictor = get_clinical_predictor()
    assert predictor is not None, "Run: python ml/clinical/train.py"
    assert 0.0 < predictor.threshold < 1.0


def test_prediction_returns_probability_confidence_and_explanation():
    predictor = get_clinical_predictor()
    result = predictor.predict(
        {
            "age": 60, "sex": 1, "cp": 0, "trestbps": 150, "chol": 260, "fbs": 0,
            "restecg": 0, "thalach": 120, "exang": 1, "oldpeak": 2.0, "slope": 1,
            "ca": 2, "thal": 3,
        }
    )
    assert 0.0 <= result.score <= 1.0
    assert 0.0 <= result.confidence <= 1.0
    assert result.explanation_method == "shap"
    assert len(result.top_factors) >= 3
    assert sum(f["magnitude"] for f in result.top_factors) > 0


def test_model_ranks_a_high_risk_profile_above_a_low_risk_one():
    """Directional sanity check — the guard against an inverted model at the
    inference layer, complementing the training-time label check."""
    predictor = get_clinical_predictor()

    high_risk = {
        "age": 67, "sex": 1, "cp": 0, "trestbps": 160, "chol": 286, "fbs": 0,
        "restecg": 0, "thalach": 108, "exang": 1, "oldpeak": 1.5, "slope": 1,
        "ca": 3, "thal": 3,
    }
    low_risk = {
        "age": 41, "sex": 0, "cp": 2, "trestbps": 118, "chol": 190, "fbs": 0,
        "restecg": 1, "thalach": 172, "exang": 0, "oldpeak": 0.0, "slope": 2,
        "ca": 0, "thal": 2,
    }
    assert predictor.predict(high_risk).score > predictor.predict(low_risk).score


def test_explanation_directions_are_clinically_coherent():
    """Exercise-induced angina must push risk UP, never down."""
    predictor = get_clinical_predictor()
    result = predictor.predict(
        {
            "age": 62, "sex": 1, "cp": 0, "trestbps": 150, "chol": 250, "fbs": 0,
            "restecg": 0, "thalach": 110, "exang": 1, "oldpeak": 2.5, "slope": 1,
            "ca": 3, "thal": 3,
        }
    )
    factors = {f["feature"]: f for f in result.top_factors}
    for feature in ("ca", "oldpeak", "exang"):
        if feature in factors:
            assert factors[feature]["direction"] == "increases_risk", (
                f"{feature} was reported as reducing risk for a clearly "
                f"high-risk profile: {factors[feature]}"
            )


@pytest.mark.skipif(not FIXTURE_PATH.is_file(), reason="regression fixture not generated")
def test_fixed_sample_regression():
    """A known input must keep producing the same score within tolerance.

    Catches accidental changes to preprocessing, feature order, or the artifact
    that would otherwise pass every other test (Blueprint Section 28).
    """
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    predictor = get_clinical_predictor()

    features = {
        k: (np.nan if v is None else v) for k, v in fixture["input"].items()
    }
    score = predictor.predict(features).score
    assert score == pytest.approx(fixture["expected_score"], abs=fixture["tolerance"]), (
        f"Score drifted from {fixture['expected_score']} to {score}. If this is "
        f"an intended model change, retrain to regenerate the fixture."
    )
