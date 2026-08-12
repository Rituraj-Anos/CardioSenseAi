"""Lab-report auto-fill orchestrator.

Flow:
  image  ->  document_parser (OCR + geometric layout reconstruction)
         ->  field_mapping (synonym tables + value normalisers)
         ->  per-field {value, matched} contract

The result pre-fills the existing editable Clinical Measurements form (the
"auto" badge fields). Nothing is auto-submitted to the risk model — the health
worker reviews every value first, and that review step already exists in the UI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.ml.clinical.document_parser import (
    parse_document,
    structure_available,
    warm_up,
)
from app.ml.clinical.field_mapping import FIELD_ORDER, map_fields

log = get_logger(__name__)


@dataclass
class ExtractionResult:
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    raw_text: str = ""
    engine: str = ""
    engine_available: bool = True
    engine_note: str = ""
    elapsed_ms: int = 0

    def as_payload(self) -> dict[str, Any]:
        # `extracted` keeps the shape the existing frontend already consumes
        # (dict of field -> {value, confidence, source_text}); `fields` adds the
        # explicit {value, matched} contract for every one of the 13 fields.
        extracted = {
            name: {
                "value": info["value"],
                "confidence": info.get("confidence", 0.0),
                "source_text": info.get("source_value", ""),
            }
            for name, info in self.fields.items()
            if info["matched"]
        }
        return {
            "engine": self.engine,
            "engine_available": self.engine_available,
            "engine_note": self.engine_note,
            "elapsed_ms": self.elapsed_ms,
            "extracted": extracted,
            "fields": self.fields,  # {field: {value, matched}} for all 13
            "missing_fields": self.missing,
            "found_count": len(extracted),
            "raw_text_preview": self.raw_text[:1200],
        }


def extract_from_image(path: str | Path) -> ExtractionResult:
    start = time.perf_counter()
    pairs, engine, raw = parse_document(path)

    if not pairs and engine == "tesseract-fallback" and not raw:
        return ExtractionResult(
            engine=engine,
            engine_available=False,
            engine_note=(
                "No document-parsing engine was available and the image could not "
                "be read. Enter the values manually."
            ),
            missing=list(FIELD_ORDER),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )

    mapped = map_fields(pairs)
    fields_payload = {
        name: {
            "value": mf.value,
            "matched": mf.matched,
            "source_label": mf.source_label,
            "source_value": mf.source_value,
            "confidence": round(mf.confidence, 2),
        }
        for name, mf in mapped.items()
    }
    missing = [name for name, mf in mapped.items() if not mf.matched]
    elapsed = int((time.perf_counter() - start) * 1000)

    matched_count = len(FIELD_ORDER) - len(missing)
    log.info(
        "report_extracted",
        engine=engine,
        matched=matched_count,
        missing=len(missing),
        elapsed_ms=elapsed,
    )

    note = ""
    if engine == "tesseract-fallback":
        note = (
            "The document reader is running in a reduced mode; table-heavy "
            "reports may extract fewer fields. Please verify the values below."
        )

    return ExtractionResult(
        fields=fields_payload,
        missing=missing,
        raw_text=raw,
        engine=engine,
        engine_available=True,
        engine_note=note,
        elapsed_ms=elapsed,
    )


# Re-exported so the app startup can warm the model.
__all__ = ["ExtractionResult", "extract_from_image", "structure_available", "warm_up"]
