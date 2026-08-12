"""Canonical clinical feature vocabulary.

Single source of truth shared by the training script (`ml/clinical/train.py`)
and the live predictor, so the column order and encoding can never drift
between train and serve (Blueprint Section 22).

The label lookup here is the curated mapping demanded by Blueprint Section 21:
raw feature names are translated to clinician-friendly text through *this
table only*. Nothing generates medical language dynamically — that is exactly
how a system ends up asserting reasoning the model never used.
"""

from __future__ import annotations

from typing import Final

# Order is contractual. The model's input matrix is built in exactly this
# order at train time and at serve time.
FEATURE_ORDER: Final[tuple[str, ...]] = (
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalach",
    "exang",
    "oldpeak",
    "slope",
    "ca",
    "thal",
)

TARGET_COLUMN: Final[str] = "target"

# Features that are categorical codes, not magnitudes. Treated as categories
# during preprocessing rather than scaled as if 'chest pain type 3' were
# three times 'chest pain type 1'.
CATEGORICAL_FEATURES: Final[tuple[str, ...]] = ("cp", "restecg", "slope", "thal")
BINARY_FEATURES: Final[tuple[str, ...]] = ("sex", "fbs", "exang")
NUMERIC_FEATURES: Final[tuple[str, ...]] = (
    "age",
    "trestbps",
    "chol",
    "thalach",
    "oldpeak",
    "ca",
)

# Clinician-facing labels. Curated, not generated.
FEATURE_LABELS: Final[dict[str, str]] = {
    "age": "Age",
    "sex": "Sex",
    "cp": "Chest pain type",
    "trestbps": "Resting blood pressure",
    "chol": "Serum cholesterol",
    "fbs": "Fasting blood sugar",
    "restecg": "Resting ECG finding",
    "thalach": "Peak heart rate reached",
    "exang": "Angina brought on by exertion",
    "oldpeak": "ST-segment depression",
    "slope": "ST-segment slope during exercise",
    "ca": "Major vessels seen on fluoroscopy",
    "thal": "Thallium stress-test result",
}

# Human-readable values for coded features. Also curated.
# Human-readable values for coded features. Also curated.
#
# IMPORTANT: these mappings were derived by matching the per-value counts in the
# circulated `heart.csv` against the original UCI `processed.cleveland.data`,
# not from the dataset's column descriptions — which are wrong for this file.
# Four of the five categorical columns are remapped relative to UCI:
#
#   cp:      kaggle 0<-uci 4, 1<-uci 2, 2<-uci 3, 3<-uci 1
#   restecg: kaggle 0<-uci 2, 1<-uci 0, 2<-uci 1
#   slope:   kaggle 0<-uci 3, 1<-uci 2, 2<-uci 1
#   thal:    kaggle 1<-uci 6, 2<-uci 3, 3<-uci 7, 0 = missing
#
# Each mapping is corroborated by the resulting disease rates being clinically
# coherent (e.g. thal=2 "normal" has the lowest disease rate at 22%, thal=3
# "reversible defect" the highest at 76%). See docs/DATA_NOTES.md.
VALUE_LABELS: Final[dict[str, dict[int, str]]] = {
    "sex": {0: "Female", 1: "Male"},
    "cp": {
        0: "Asymptomatic",
        1: "Atypical angina",
        2: "Non-anginal pain",
        3: "Typical angina",
    },
    "fbs": {0: "≤ 120 mg/dl", 1: "> 120 mg/dl"},
    "restecg": {
        0: "Left ventricular hypertrophy",
        1: "Normal",
        2: "ST-T wave abnormality",
    },
    "exang": {0: "No", 1: "Yes"},
    "slope": {0: "Downsloping", 1: "Flat", 2: "Upsloping"},
    "thal": {
        0: "Not recorded",
        1: "Fixed defect",
        2: "Normal",
        3: "Reversible defect",
    },
}

UNITS: Final[dict[str, str]] = {
    "age": "years",
    "trestbps": "mm Hg",
    "chol": "mg/dl",
    "thalach": "bpm",
    "oldpeak": "mm",
}


def label_for(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature)


def display_value(feature: str, value: float | int | None) -> str:
    """Render a feature value for display. Coded features go through
    VALUE_LABELS; magnitudes get their unit appended."""
    if value is None:
        return "—"
    if feature in VALUE_LABELS:
        try:
            return VALUE_LABELS[feature][int(value)]
        except (KeyError, ValueError, TypeError):
            return str(value)
    if feature == "ca":
        return f"{int(value)}"
    unit = UNITS.get(feature)
    if isinstance(value, float) and not float(value).is_integer():
        rendered = f"{value:.1f}"
    else:
        rendered = f"{int(value)}"
    return f"{rendered} {unit}" if unit else rendered
