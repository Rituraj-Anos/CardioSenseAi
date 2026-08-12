"""Field-mapping layer for lab-report auto-fill.

This is the substantive new code (not just calling an OCR library). It takes the
structure-preserving output of a document parser — a list of (label, value)
candidate pairs recovered from tables and key/value blocks — and maps them onto
the 13 fields of the clinical_measurements schema.

Two things make this non-trivial and worth doing carefully:

1. Real diagnostic labs phrase labels differently ("Resting BP" vs "Blood
   Pressure" vs "BP (Systolic)"). So each field carries a table of synonyms and
   we match by the LONGEST matching synonym, which stops "fasting blood sugar"
   from being captured by a short "blood" match meant for blood pressure.

2. Values arrive as free text ("158 mm Hg", "Typical angina", "Yes",
   "Reversible defect") and must be normalised to the model's encodings — the
   SAME encodings verified against the original UCI data, not the (wrong)
   encodings in most Kaggle column docs.

Output contract per field: {value, matched}. Unmatched fields return
value=None, matched=False, so they flow into the existing editable auto-fill
UI (the "auto" badge fields) for the health worker to complete — nothing is
ever auto-submitted to the risk model.

KNOWN CONSTRAINT (documented, not hidden): the synonym table is expected to be
iterated as new report formats are encountered. It is intentionally data, not
control flow, so extending it is a one-line change per synonym.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class MappedField:
    value: float | int | None
    matched: bool
    source_label: str = ""
    source_value: str = ""
    confidence: float = 0.0


FIELD_ORDER = (
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal",
)

# --------------------------------------------------------------------------
# Label synonyms per field. Lowercased; matched as normalised substrings.
# Order within a list doesn't matter — the matcher scores by matched length.
# --------------------------------------------------------------------------
FIELD_SYNONYMS: dict[str, list[str]] = {
    "age": ["age", "patient age", "age (years)", "age/sex"],
    "sex": ["sex", "gender", "sex/gender"],
    "cp": [
        "chest pain type", "chest pain", "type of chest pain", "angina type",
        "cp type", "chest pain (type)", "cp",
    ],
    "trestbps": [
        "resting blood pressure", "resting bp", "blood pressure (systolic)",
        "bp (systolic)", "systolic blood pressure", "systolic bp",
        "resting bp (systolic)", "blood pressure at rest", "resting systolic bp",
        "blood pressure", "bp",
    ],
    "chol": [
        "serum cholesterol", "total cholesterol", "cholesterol (total)",
        "s. cholesterol", "cholesterol", "serum chol", "chol",
    ],
    "fbs": [
        "fasting blood sugar", "fasting blood glucose", "fasting plasma glucose",
        "fasting glucose", "blood sugar (fasting)", "fasting sugar", "fbs",
    ],
    "restecg": [
        "resting ecg finding", "resting ecg result", "resting ecg",
        "resting electrocardiogram", "rest ecg", "ecg (resting)",
        "resting electrocardiographic results", "resting ekg",
    ],
    "thalach": [
        "peak heart rate achieved", "maximum heart rate achieved",
        "peak heart rate", "maximum heart rate", "max heart rate", "max hr",
        "maximum hr", "peak hr", "thalach", "heart rate (peak)",
    ],
    "exang": [
        "exercise-induced angina", "exercise induced angina", "exercise angina",
        "angina on exertion", "exertional angina", "exercise-related angina",
        "exang",
    ],
    "oldpeak": [
        "st depression (oldpeak)", "st depression induced by exercise",
        "st-segment depression", "st segment depression", "st depression",
        "oldpeak", "st dep",
    ],
    "slope": [
        "st segment slope", "st-segment slope", "slope of peak exercise st segment",
        "peak exercise st slope", "st slope", "slope",
    ],
    "ca": [
        "number of major vessels", "major vessels (fluoroscopy)",
        "major vessels colored by fluoroscopy", "vessels colored by fluoroscopy",
        "major vessels", "number of vessels", "ca",
    ],
    "thal": [
        "thallium stress test", "thallium stress-test result", "thallium scan",
        "thalassemia", "thallium", "thal result", "thal",
    ],
}

# Normalised synonym -> field, sorted so the longest synonym wins on overlap.
_SYNONYM_INDEX: list[tuple[str, str]] = sorted(
    ((re.sub(r"[^a-z0-9 ]", " ", syn).strip(), field)
     for field, syns in FIELD_SYNONYMS.items()
     for syn in syns),
    key=lambda kv: len(kv[0]),
    reverse=True,
)


def _normalise_label(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", label.lower())).strip()


def match_field(label: str) -> str | None:
    """Return the schema field a report label maps to, or None.

    Matches by the longest synonym that appears as a whole-word phrase in the
    (normalised) label, so more specific labels beat generic ones.
    """
    norm = _normalise_label(label)
    if not norm:
        return None
    for synonym, field in _SYNONYM_INDEX:
        # whole-phrase, word-boundary match
        if re.search(rf"(?:^|\s){re.escape(synonym)}(?:\s|$)", norm):
            return field
    return None


# --------------------------------------------------------------------------
# Value normalisers. Return None when the text can't be trusted for that field.
# Encodings match app.ml.clinical.features (verified against UCI).
# --------------------------------------------------------------------------
def _first_number(text: str, lo: float, hi: float, allow_float: bool = False) -> float | None:
    # First standalone number; the leftmost value in a "158 / 90" pair.
    m = re.search(r"(?<!\d)(\d{1,3}(?:\.\d+)?)(?!\d)", text)
    if not m:
        return None
    val = float(m.group(1)) if allow_float else int(round(float(m.group(1))))
    return val if lo <= val <= hi else None


def _category(text: str, mapping: dict[int, list[str]]) -> int | None:
    t = _normalise_label(text)
    # Prefer the longest matching phrase to avoid "normal" catching inside a
    # longer phrase, etc.
    best: tuple[int, int] | None = None  # (matched_len, value)
    for value, phrases in mapping.items():
        for phrase in phrases:
            if phrase in t and (best is None or len(phrase) > best[0]):
                best = (len(phrase), value)
    return best[1] if best else None


def _norm_age(v: str) -> int | None:
    return _first_number(v, 1, 120)


def _norm_sex(v: str) -> int | None:
    t = _normalise_label(v)
    if re.search(r"\b(male|m)\b", t) and not re.search(r"\bfemale\b", t):
        return 1
    if re.search(r"\b(female|f)\b", t):
        return 0
    return None


def _norm_trestbps(v: str) -> int | None:
    return _first_number(v, 60, 260)


def _norm_chol(v: str) -> int | None:
    return _first_number(v, 80, 700)


def _norm_fbs(v: str) -> int | None:
    t = _normalise_label(v)
    if re.search(r"\b(yes|high|elevated|positive|true)\b", t):
        return 1
    if re.search(r"\b(no|normal|negative|false)\b", t):
        return 0
    num = _first_number(v, 30, 600, allow_float=True)
    if num is not None:
        return 1 if num > 120 else 0
    return None


def _norm_restecg(v: str) -> int | None:
    return _category(
        v,
        {
            2: ["st t wave abnormality", "st t abnormality", "st t", "st-t"],
            0: ["left ventricular hypertrophy", "lv hypertrophy", "hypertrophy", "lvh"],
            1: ["normal"],
        },
    )


def _norm_thalach(v: str) -> int | None:
    return _first_number(v, 50, 230)


def _norm_exang(v: str) -> int | None:
    t = _normalise_label(v)
    if re.search(r"\b(yes|present|positive|true)\b", t):
        return 1
    if re.search(r"\b(no|absent|negative|false|none)\b", t):
        return 0
    return None


def _norm_oldpeak(v: str) -> float | None:
    return _first_number(v, 0, 10, allow_float=True)


def _norm_slope(v: str) -> int | None:
    return _category(
        v,
        {2: ["upsloping", "up sloping", "up slope"], 1: ["flat"], 0: ["downsloping", "down sloping", "down slope"]},
    )


def _norm_ca(v: str) -> int | None:
    return _first_number(v, 0, 3)


def _norm_thal(v: str) -> int | None:
    return _category(
        v,
        {
            3: ["reversible defect", "reversable defect", "reversible"],
            1: ["fixed defect", "fixed"],
            2: ["normal"],
        },
    )


NORMALISERS: dict[str, Callable[[str], float | int | None]] = {
    "age": _norm_age, "sex": _norm_sex, "cp": lambda v: _category(
        v, {3: ["typical angina"], 1: ["atypical angina"], 2: ["non anginal", "non-anginal", "nonanginal"], 0: ["asymptomatic"]}
    ),
    "trestbps": _norm_trestbps, "chol": _norm_chol, "fbs": _norm_fbs,
    "restecg": _norm_restecg, "thalach": _norm_thalach, "exang": _norm_exang,
    "oldpeak": _norm_oldpeak, "slope": _norm_slope, "ca": _norm_ca, "thal": _norm_thal,
}


def map_fields(pairs: list[tuple[str, list[str]]]) -> dict[str, MappedField]:
    """Map (label, [candidate value cells]) pairs onto the schema.

    `pairs` carries a list of candidate value strings per label so a table row
    like `Resting BP | 158 mm Hg | 90-120 mm Hg | HIGH` can offer every cell;
    the leftmost cell that normalises for the matched field wins, which keeps a
    reference-range column from being read as the result.
    """
    result: dict[str, MappedField] = {
        f: MappedField(value=None, matched=False) for f in FIELD_ORDER
    }

    for label, value_cells in pairs:
        field = match_field(label)
        if field is None or result[field].matched:
            continue
        normaliser = NORMALISERS[field]
        for cell in value_cells:
            value = normaliser(cell)
            if value is not None:
                result[field] = MappedField(
                    value=value,
                    matched=True,
                    source_label=label.strip()[:60],
                    source_value=cell.strip()[:60],
                    confidence=0.9,
                )
                break

    _infer_combined_sex(pairs, result)
    return result


def _infer_combined_sex(pairs: list[tuple[str, list[str]]], result: dict[str, MappedField]) -> None:
    """Labs often print sex inside a combined field, e.g. 'Age / Sex: 58 / Male'.

    When sex wasn't matched from its own label, look for a standalone male/female
    token in the value cells of a label that mentions sex/gender — but never
    from a free-floating word elsewhere, to avoid false positives.
    """
    if result["sex"].matched:
        return
    for label, cells in pairs:
        norm_label = _normalise_label(label)
        if "sex" not in norm_label and "gender" not in norm_label:
            continue
        for cell in cells:
            sex = _norm_sex(cell)
            if sex is not None:
                result["sex"] = MappedField(
                    value=sex, matched=True, source_label=label.strip()[:60],
                    source_value=cell.strip()[:60], confidence=0.75,
                )
                return
