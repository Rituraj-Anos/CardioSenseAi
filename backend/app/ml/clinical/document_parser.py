"""Document parsing for lab-report auto-fill.

Uses an OCR engine (text detection + recognition) to read positioned text
boxes from a report image, followed by our own geometric row/column
reconstruction that recovers the label/value structure of a table without a
heavy full-document pipeline — fast enough to run inline on upload.

The engine loads once (module singleton) and is warmed at app startup so the
first real upload doesn't pay the graph-compilation cost.
"""

from __future__ import annotations

import os
import re
import shutil
import threading
from pathlib import Path

# paddlepaddle 3.3.1's oneDNN path crashes on Windows CPU
# ("ConvertPirAttribute2RuntimeAttribute not support"). Disable before import.
os.environ.setdefault("FLAGS_use_mkldnn", "0")

from app.core.logging import get_logger

log = get_logger(__name__)

Pair = tuple[str, list[str]]

# Resize longest side to this before OCR. Phone photos can be 4000px+, which is
# both slow and no more accurate than a sensible working resolution.
MAX_SIDE = 1600


class _OCREngine:
    _lock = threading.Lock()
    _instance: "_OCREngine | None" = None
    _load_failed = False

    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        # Mobile PP-OCRv5 det+rec: the accuracy/speed sweet spot on CPU.
        # textline orientation on → helps rotated/skewed phone photos; doc
        # orientation/unwarping off → they add latency for little gain here.
        self.ocr = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            enable_mkldnn=False,
        )
        log.info("paddleocr_loaded")

    @classmethod
    def get(cls) -> "_OCREngine | None":
        if cls._instance is None and not cls._load_failed:
            with cls._lock:
                if cls._instance is None and not cls._load_failed:
                    try:
                        cls._instance = cls()
                    except Exception as exc:  # pragma: no cover - env dependent
                        cls._load_failed = True
                        log.warning("paddleocr_unavailable", error=str(exc))
        return cls._instance


def structure_available() -> bool:
    return _OCREngine.get() is not None


def warm_up() -> bool:
    """Load + run one tiny inference so the first real upload isn't the slow one."""
    engine = _OCREngine.get()
    if engine is None:
        return False
    try:
        from PIL import Image
        import numpy as np

        dummy = np.array(Image.new("RGB", (320, 120), "white"))
        engine.ocr.predict(dummy)
        log.info("paddleocr_warmed")
    except Exception as exc:  # pragma: no cover
        log.warning("paddleocr_warm_failed", error=str(exc))
    return True


# --------------------------------------------------------------------------
# Parse
# --------------------------------------------------------------------------
def parse_document(path: str | Path) -> tuple[list[Pair], str, str]:
    """Return (pairs, engine_name, debug_text)."""
    engine = _OCREngine.get()
    if engine is not None:
        try:
            boxes = _run_paddle(engine, path)
            pairs = _reconstruct(boxes)
            debug = " | ".join(t for t, _, _, _ in boxes)
            return pairs, "pp-ocrv5", debug
        except Exception as exc:  # pragma: no cover - runtime issues
            log.warning("paddle_predict_failed", error=str(exc))

    text = _tesseract_text(path)
    return _pairs_from_text(text), "tesseract-fallback", text


# each box: (text, cx_left, cy_center, height)
Box = tuple[str, float, float, float]


def _deskew(image):
    """Best-effort deskew for angled phone photos.

    Estimates the dominant text angle from the binarised page and rotates it
    upright. Bounded to small angles so we never make a straight page worse;
    large rotations (portrait/landscape flips) are left to PP-OCRv5's textline
    orientation model. This directly targets the skew case flagged in testing —
    it improves it but does not fully solve heavy skew, which is reported.
    """
    try:
        import cv2
        import numpy as np

        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=120, minLineLength=min(image.width // 4, 250), maxLineGap=20
        )
        if lines is None:
            return image
        angles = []
        for x1, y1, x2, y2 in lines[:, 0, :]:
            a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(a) < 25:  # near-horizontal text/rule lines only
                angles.append(a)
        if len(angles) < 5:
            return image
        angle = float(np.median(angles))
        if abs(angle) < 0.6:
            return image
        from PIL import Image as _Image

        return image.rotate(
            angle, expand=True, fillcolor=(255, 255, 255), resample=_Image.BICUBIC
        )
    except Exception:  # pragma: no cover - opencv edge cases
        return image


def _run_paddle(engine: "_OCREngine", path: str | Path) -> list[Box]:
    import numpy as np
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if max(image.size) > MAX_SIDE:
        scale = MAX_SIDE / max(image.size)
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    image = _deskew(image)

    results = engine.ocr.predict(np.array(image))
    if not results:
        return []
    res = results[0]
    texts = res.get("rec_texts") or res.get("rec_text") or []
    polys = res.get("rec_polys") or res.get("dt_polys") or res.get("rec_boxes") or []

    boxes: list[Box] = []
    for text, poly in zip(texts, polys):
        if not text or not str(text).strip():
            continue
        pts = np.asarray(poly, dtype=float).reshape(-1, 2)
        ys, xs = pts[:, 1], pts[:, 0]
        boxes.append((str(text).strip(), float(xs.min()), float(ys.mean()), float(ys.max() - ys.min())))
    return boxes


# --------------------------------------------------------------------------
# Geometric reconstruction: cluster boxes into rows, then emit pairs.
# --------------------------------------------------------------------------
def _reconstruct(boxes: list[Box]) -> list[Pair]:
    if not boxes:
        return []

    median_h = sorted(b[3] for b in boxes)[len(boxes) // 2] or 12.0
    tol = max(6.0, median_h * 0.6)

    # Cluster by center-y into rows.
    rows: list[list[Box]] = []
    for box in sorted(boxes, key=lambda b: b[2]):
        placed = False
        for row in rows:
            if abs(row[0][2] - box[2]) <= tol:
                row.append(box)
                placed = True
                break
        if not placed:
            rows.append([box])

    pairs: list[Pair] = []
    for row in rows:
        row.sort(key=lambda b: b[1])  # left-to-right
        cells = [b[0] for b in row]

        # (A) Table interpretation: first cell is the label, the rest are value
        # candidates (RESULT, REFERENCE RANGE, FLAG ...). map_fields picks the
        # leftmost cell that normalises, so the reference-range column is ignored.
        if len(cells) >= 2:
            pairs.append((cells[0], cells[1:]))

        # (B) Key/value interpretation: join the row and split on colons, which
        # handles single-line forms ("Resting BP: 158  Chol: 284") and combined
        # header grids ("Age: 58  Sex: Male").
        joined = "  ".join(cells)
        pairs.extend(_pairs_from_text(joined))

    return _dedupe(pairs)


def _pairs_from_text(text: str) -> list[Pair]:
    """Recover 'Label: value' pairs, including several per physical line."""
    prose = re.sub(r"<[^>]+>", " ", text)
    kv = re.compile(
        r"([A-Za-z][A-Za-z0-9 /()\-\.]{1,38}?)\s*:\s*"
        r"(.+?)(?=\s+[A-Za-z][A-Za-z0-9 /()\-\.]{1,38}?\s*:|$)"
    )
    pairs: list[Pair] = []
    for raw in prose.splitlines():
        line = raw.strip().lstrip("#").strip()
        if not line or ":" not in line:
            continue
        for m in kv.finditer(line):
            label = " ".join(m.group(1).split()[-4:])
            value = m.group(2).strip(" .-")
            if label and value:
                pairs.append((label, [value]))
    return pairs


def _dedupe(pairs: list[Pair]) -> list[Pair]:
    seen: set[tuple[str, str]] = set()
    out: list[Pair] = []
    for label, values in pairs:
        key = (re.sub(r"\s+", " ", label.lower()).strip(), "|".join(values))
        if key[0] and key not in seen:
            seen.add(key)
            out.append((label, values))
    return out


# --------------------------------------------------------------------------
# Tesseract fallback
# --------------------------------------------------------------------------
def _tesseract_available() -> bool:
    import pytesseract

    if shutil.which("tesseract"):
        return True
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(candidate).is_file():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True
    return False


def _tesseract_text(path: str | Path) -> str:
    if not _tesseract_available():
        return ""
    import pytesseract
    from PIL import Image, ImageOps

    image = ImageOps.autocontrast(ImageOps.grayscale(Image.open(path)))
    if max(image.size) < 1600:
        scale = 1600 / max(image.size)
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    try:
        return pytesseract.image_to_string(image)
    except Exception:  # pragma: no cover
        return ""
