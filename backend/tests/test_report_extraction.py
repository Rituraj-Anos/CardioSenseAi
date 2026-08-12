"""Field-mapping layer tests.

These test the mapping + normalisation directly against (label, value) pairs —
the engine-agnostic core — so they run without the OCR engine present. The
document parser is validated separately with a live image harness
(scripts/eval_report_extraction.py), not in the unit suite, because it needs
model weights and is slow.
"""

from __future__ import annotations

from app.ml.clinical.field_mapping import FIELD_ORDER, map_fields, match_field


def _matched(pairs):
    m = map_fields(pairs)
    return {k: v.value for k, v in m.items() if v.matched}


# --------------------------------------------------------------------------
# Label matching + synonyms
# --------------------------------------------------------------------------
def test_common_synonyms_map_to_the_right_field():
    assert match_field("Resting Blood Pressure") == "trestbps"
    assert match_field("BP (Systolic)") == "trestbps"
    assert match_field("Blood Pressure") == "trestbps"
    assert match_field("Serum Cholesterol") == "chol"
    assert match_field("Total Cholesterol") == "chol"
    assert match_field("Fasting Blood Sugar") == "fbs"
    assert match_field("Peak Heart Rate Achieved") == "thalach"
    assert match_field("Max HR") == "thalach"
    assert match_field("Exercise-Induced Angina") == "exang"
    assert match_field("ST Depression (Oldpeak)") == "oldpeak"
    assert match_field("ST Segment Slope") == "slope"
    assert match_field("Major Vessels (Fluoroscopy)") == "ca"
    assert match_field("Thallium Stress Test") == "thal"
    assert match_field("Resting ECG Finding") == "restecg"


def test_blood_sugar_is_not_captured_by_blood_pressure_synonym():
    # The "longest synonym wins" rule must keep these distinct.
    assert match_field("Fasting Blood Sugar") == "fbs"
    assert match_field("Resting Blood Pressure") == "trestbps"


def test_unrelated_label_matches_nothing():
    assert match_field("Referring Physician") is None
    assert match_field("Report Date") is None
    assert match_field("Reference Range") is None


# --------------------------------------------------------------------------
# Value normalisation
# --------------------------------------------------------------------------
def test_numeric_values_normalise_and_range_check():
    v = _matched(
        [
            ("Resting Blood Pressure", ["158 mm Hg"]),
            ("Serum Cholesterol", ["284 mg/dL"]),
            ("Peak Heart Rate Achieved", ["118 bpm"]),
            ("ST Depression (Oldpeak)", ["2.8 mm"]),
            ("Major Vessels", ["2"]),
        ]
    )
    assert v["trestbps"] == 158
    assert v["chol"] == 284
    assert v["thalach"] == 118
    assert v["oldpeak"] == 2.8
    assert v["ca"] == 2


def test_reference_range_column_is_not_read_as_the_result():
    # A full table row: label, RESULT, REFERENCE RANGE, FLAG.
    v = _matched([("Resting Blood Pressure", ["158 mm Hg", "90 - 120 mm Hg", "HIGH"])])
    assert v["trestbps"] == 158  # not 90 from the reference range


def test_categorical_values_map_to_verified_encodings():
    v = _matched(
        [
            ("Chest Pain Type", ["Typical angina"]),
            ("Resting ECG Finding", ["Left ventricular hypertrophy"]),
            ("ST Segment Slope", ["Downsloping"]),
            ("Thallium Stress Test", ["Reversible defect"]),
        ]
    )
    assert v["cp"] == 3       # typical angina
    assert v["restecg"] == 0  # LVH
    assert v["slope"] == 0    # downsloping
    assert v["thal"] == 3     # reversible defect


def test_sex_and_yes_no_fields():
    v = _matched(
        [
            ("Sex", ["Male"]),
            ("Exercise-Induced Angina", ["Yes"]),
        ]
    )
    assert v["sex"] == 1
    assert v["exang"] == 1


def test_fasting_sugar_numeric_threshold_and_flag_word():
    assert _matched([("Fasting Blood Sugar", ["138 mg/dL"])])["fbs"] == 1
    assert _matched([("Fasting Blood Sugar", ["95 mg/dL"])])["fbs"] == 0
    assert _matched([("Fasting Blood Sugar", ["High"])])["fbs"] == 1


def test_full_sunrise_diagnostics_layout_all_thirteen():
    """The exact layout from the reported failing sample (tabular lab report)."""
    pairs = [
        ("Age", ["58 years"]),
        ("Sex", ["Male"]),
        ("Resting Blood Pressure", ["158 mm Hg", "90 - 120 mm Hg", "HIGH"]),
        ("Serum Cholesterol", ["284 mg/dL", "< 200 mg/dL", "HIGH"]),
        ("Fasting Blood Sugar", ["138 mg/dL", "< 100 mg/dL (>120 flagged)", "HIGH"]),
        ("Chest Pain Type", ["Typical angina", "-", "Normal"]),
        ("Resting ECG Finding", ["Left ventricular hypertrophy", "-", "HIGH"]),
        ("Peak Heart Rate Achieved", ["118 bpm", "220 - age (approx.)", "Normal"]),
        ("Exercise-Induced Angina", ["Yes", "-", "Normal"]),
        ("ST Depression (Oldpeak)", ["2.8 mm", "< 1.0 mm", "HIGH"]),
        ("ST Segment Slope", ["Downsloping", "-", "HIGH"]),
        ("Major Vessels (Fluoroscopy)", ["2", "0 - 3", "HIGH"]),
        ("Thallium Stress Test", ["Reversible defect", "-", "HIGH"]),
    ]
    mapped = map_fields(pairs)
    matched = {k: v.value for k, v in mapped.items() if v.matched}
    assert set(matched) == set(FIELD_ORDER), f"missing: {set(FIELD_ORDER) - set(matched)}"
    assert matched == {
        "age": 58, "sex": 1, "cp": 3, "trestbps": 158, "chol": 284, "fbs": 1,
        "restecg": 0, "thalach": 118, "exang": 1, "oldpeak": 2.8, "slope": 0,
        "ca": 2, "thal": 3,
    }


def test_partial_report_reports_unmatched_as_missing():
    mapped = map_fields([("Age", ["44 years"]), ("Serum Cholesterol", ["210 mg/dL"])])
    assert mapped["age"].matched and mapped["age"].value == 44
    assert mapped["chol"].matched
    assert not mapped["thalach"].matched
    assert mapped["thalach"].value is None


def test_every_field_present_in_output_contract():
    mapped = map_fields([])
    assert set(mapped) == set(FIELD_ORDER)
    assert all(not mf.matched and mf.value is None for mf in mapped.values())
