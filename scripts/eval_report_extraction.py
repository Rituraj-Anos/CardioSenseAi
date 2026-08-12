"""Live validation harness for lab-report auto-fill.

Generates several DIFFERENT report layouts (not one template), plus a
rotated/skewed variant, runs the real OCR extraction pipeline, and reports
field-level accuracy (X/13 matched) per layout.

Run:  python scripts/eval_report_extraction.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.ml.clinical.document_parser import structure_available  # noqa: E402
from app.ml.clinical.field_mapping import FIELD_ORDER  # noqa: E402
from app.ml.clinical.report_extraction import extract_from_image  # noqa: E402

OUT = Path(__file__).resolve().parent / "_eval_images"
OUT.mkdir(exist_ok=True)

# Ground truth shared across layouts (same patient, different report styles).
TRUTH = {
    "age": 58, "sex": 1, "cp": 3, "trestbps": 158, "chol": 284, "fbs": 1,
    "restecg": 0, "thalach": 118, "exang": 1, "oldpeak": 2.8, "slope": 0,
    "ca": 2, "thal": 3,
}


def _font(size: int, bold: bool = False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def layout_table(path: Path) -> None:
    """A 4-column clinical table (like the reported failing sample)."""
    img = Image.new("RGB", (1024, 720), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 40), "SUNRISE DIAGNOSTICS & CARDIAC CARE CENTRE", fill="#0E6E64", font=_font(30, True))
    d.text((60, 120), "Patient: Rajesh Banerjee    Age: 58 years    Sex: Male", fill="black", font=_font(20))
    rows = [
        ("PARAMETER", "RESULT", "REFERENCE RANGE", "FLAG"),
        ("Resting Blood Pressure", "158 mm Hg", "90 - 120 mm Hg", "HIGH"),
        ("Serum Cholesterol", "284 mg/dL", "< 200 mg/dL", "HIGH"),
        ("Fasting Blood Sugar", "138 mg/dL", "< 100 mg/dL", "HIGH"),
        ("Chest Pain Type", "Typical angina", "-", "Normal"),
        ("Resting ECG Finding", "Left ventricular hypertrophy", "-", "HIGH"),
        ("Peak Heart Rate Achieved", "118 bpm", "220 - age", "Normal"),
        ("Exercise-Induced Angina", "Yes", "-", "Normal"),
        ("ST Depression (Oldpeak)", "2.8 mm", "< 1.0 mm", "HIGH"),
        ("ST Segment Slope", "Downsloping", "-", "HIGH"),
        ("Major Vessels (Fluoroscopy)", "2", "0 - 3", "HIGH"),
        ("Thallium Stress Test", "Reversible defect", "-", "HIGH"),
    ]
    y = 180
    cols = [60, 430, 660, 880]
    for r, row in enumerate(rows):
        f = _font(18, r == 0)
        for c, cell in zip(cols, row):
            d.text((c, y), cell, fill="black", font=f)
        d.line((60, y + 32, 980, y + 32), fill="#E4E7EC")
        y += 44
    img.save(path)


def layout_two_column(path: Path) -> None:
    """A key/value two-column form, different wording."""
    img = Image.new("RGB", (900, 760), "white")
    d = ImageDraw.Draw(img)
    d.text((50, 40), "CityCare Labs — Cardiac Risk Profile", fill="#08403A", font=_font(26, True))
    kv = [
        ("Age / Sex", "58 / Male"),
        ("BP (Systolic)", "158 mmHg"),
        ("Total Cholesterol", "284 mg/dL"),
        ("Fasting Glucose", "138 mg/dL"),
        ("Type of Chest Pain", "Typical angina"),
        ("Resting Electrocardiogram", "LV hypertrophy"),
        ("Max Heart Rate", "118 /min"),
        ("Exertional Angina", "Present"),
        ("ST-Segment Depression", "2.8"),
        ("Slope of Peak Exercise ST Segment", "Down sloping"),
        ("No. of Major Vessels", "2"),
        ("Thallium Scan", "Reversible defect"),
    ]
    y = 120
    for k, v in kv:
        d.text((50, y), f"{k}:", fill="#475467", font=_font(19))
        d.text((520, y), v, fill="black", font=_font(19, True))
        y += 48
    img.save(path)


def layout_compact(path: Path) -> None:
    """A denser report with abbreviations."""
    img = Image.new("RGB", (960, 640), "white")
    d = ImageDraw.Draw(img)
    d.text((40, 30), "Rural Health Mission — Screening Slip", fill="#0E6E64", font=_font(24, True))
    rows = [
        ("Age", "58 yrs", "Sex", "M"),
        ("Resting BP", "158", "Chol", "284"),
        ("FBS", "138 mg/dl", "Rest ECG", "ST-T wave abnormality"),
        ("Peak HR", "118", "Exang", "Yes"),
        ("Oldpeak", "2.8", "ST Slope", "Flat"),
        ("Major Vessels", "2", "Thal", "Reversible defect"),
        ("Chest Pain", "Asymptomatic", "", ""),
    ]
    y = 110
    for a, b, c, e in rows:
        d.text((40, y), f"{a}: {b}", fill="black", font=_font(20))
        if c:
            d.text((520, y), f"{c}: {e}", fill="black", font=_font(20))
        y += 54
    img.save(path)


def score(path: Path, name: str, truth: dict) -> None:
    t0 = time.perf_counter()
    res = extract_from_image(path)
    dt = int((time.perf_counter() - t0) * 1000)
    matched = {k: v["value"] for k, v in res.fields.items() if v["matched"]}
    correct = sum(1 for k, val in matched.items() if k in truth and val == truth[k])
    wrong = {k: (matched[k], truth.get(k)) for k in matched if truth.get(k) != matched[k]}
    print(f"\n=== {name} === engine={res.engine} {dt} ms")
    print(f"  matched {len(matched)}/13, correct {correct}/13")
    if wrong:
        print(f"  mismatches (got, expected): {wrong}")
    missing = [f for f in FIELD_ORDER if f not in matched]
    if missing:
        print(f"  unmatched (need manual entry): {missing}")


def main() -> None:
    print("OCR engine available:", structure_available())

    clean = OUT / "table.png"
    layout_table(clean)
    layout_two_column(OUT / "twocol.png")
    layout_compact(OUT / "compact.png")

    # Rotated / skewed phone-photo simulation.
    skewed = OUT / "table_skewed.png"
    Image.open(clean).rotate(-7, expand=True, fillcolor="white").save(skewed)

    score(clean, "Layout A: 4-column clinical table", TRUTH)
    score(OUT / "twocol.png", "Layout B: two-column key/value form", TRUTH)
    score(OUT / "compact.png", "Layout C: compact abbreviated slip",
          {**TRUTH, "cp": 0, "slope": 1, "restecg": 2})  # this layout states different categoricals
    score(skewed, "Layout A rotated -7 deg (skew test)", TRUTH)


if __name__ == "__main__":
    main()
