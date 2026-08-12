"""Late (decision-level) fusion — Blueprint Section 20.

Each available modality contributes a calibrated probability. Only modalities
that actually ran are combined, and the weights are renormalised over the
present set. That renormalisation is the entire graceful-degradation
mechanism: a clinical-only screening is not a partial result, it is a valid
result computed at full clinical weight.

Two deliberate design choices worth defending out loud:

* Weights are fixed and declared, not learned. A learned meta-learner needs a
  training set where all three modalities are paired per patient, which this
  project does not have. Blueprint Section 20 scopes that as `[FUTURE]`, and
  shipping a learned combiner trained on a handful of paired records would be
  a worse answer that merely looks more sophisticated.

* Confidence drops when modalities disagree. Averaging two confident but
  opposing signals into one confident answer would hide precisely the
  uncertainty this product is supposed to surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

FUSION_VERSION: Final[str] = "late-fusion-v1"

# Base weights over the full modality set. Clinical carries the most weight
# because it is the only modality with a validated model on this dataset and
# the only one guaranteed to be present.
BASE_WEIGHTS: Final[dict[str, float]] = {
    "clinical": 0.50,
    "pcg": 0.25,
    "ecg": 0.25,
}

# Risk bands. Tuned toward recall (Blueprint Section 17): the moderate band
# starts low on purpose, because a missed high-risk patient is a worse outcome
# than an unnecessary referral. This asymmetry is stated in the UI, not buried.
BAND_MODERATE_MIN: Final[float] = 0.30
BAND_HIGH_MIN: Final[float] = 0.60

DISCLAIMER: Final[str] = (
    "CardioSense AI is a screening aid, not a diagnosis. It estimates risk from "
    "the data provided and can be wrong in both directions. Only a qualified "
    "clinician can diagnose or rule out heart disease."
)


@dataclass
class ModalityScore:
    modality: str
    score: float
    confidence: float


@dataclass
class FusionOutcome:
    final_score: float
    risk_band: str
    confidence: float
    modalities_used: list[str]
    weights: dict[str, float] = field(default_factory=dict)
    recommendation: str = ""
    uncertainty_note: str = ""
    fusion_version: str = FUSION_VERSION
    disclaimer: str = DISCLAIMER


def _renormalise(present: list[str]) -> dict[str, float]:
    subset = {m: BASE_WEIGHTS[m] for m in present if m in BASE_WEIGHTS}
    total = sum(subset.values())
    if total <= 0:
        # Equal split for any modality set not covered by BASE_WEIGHTS.
        equal = 1.0 / max(len(present), 1)
        return {m: round(equal, 4) for m in present}
    return {m: round(w / total, 4) for m, w in subset.items()}


def _band(score: float) -> str:
    if score >= BAND_HIGH_MIN:
        return "high"
    if score >= BAND_MODERATE_MIN:
        return "moderate"
    return "low"


def _disagreement_penalty(scores: list[float]) -> float:
    """0.0 when modalities agree, up to 1.0 when they maximally disagree."""
    if len(scores) < 2:
        return 0.0
    return float(max(scores) - min(scores))


def _recommendation(band: str, modalities: list[str], confidence: float) -> str:
    single = len(modalities) == 1
    if band == "high":
        base = (
            "See a doctor promptly. This screening suggests a raised likelihood "
            "of cardiovascular disease that should be assessed clinically."
        )
    elif band == "moderate":
        base = (
            "Arrange a follow-up with a health worker or doctor. The result is "
            "not clearly low-risk and warrants a closer look."
        )
    else:
        base = (
            "No raised risk detected in this screening. Continue routine "
            "self-monitoring and repeat screening if symptoms appear."
        )

    if single and modalities == ["clinical"]:
        base += (
            " This assessment used clinical measurements only; adding a heart-sound "
            "or ECG recording would give a more complete picture."
        )
    if confidence < 0.35:
        base += (
            " Confidence in this result is low, so treat it as a prompt to gather "
            "more information rather than as a conclusion."
        )
    return base


def _uncertainty_note(
    modalities: list[str], confidence: float, disagreement: float
) -> str:
    parts = [
        f"Based on {len(modalities)} of 3 possible modalities "
        f"({', '.join(modalities)}).",
        f"Model confidence: {confidence:.0%}.",
    ]
    if disagreement >= 0.30:
        parts.append(
            f"The available modalities disagreed noticeably (spread of "
            f"{disagreement:.0%} between the highest and lowest signal), which "
            f"has been reflected as reduced confidence rather than averaged away."
        )
    missing = [m for m in BASE_WEIGHTS if m not in modalities]
    if missing:
        parts.append(
            f"Not assessed: {', '.join(missing)}. Absent modalities were excluded "
            f"and the remaining weights renormalised — they were not treated as "
            f"normal findings."
        )
    return " ".join(parts)


def fuse(scores: list[ModalityScore]) -> FusionOutcome:
    """Combine whatever modalities are present into one calibrated result."""
    if not scores:
        raise ValueError("Fusion requires at least one modality score.")

    present = [s.modality for s in scores]
    weights = _renormalise(present)

    final = sum(s.score * weights.get(s.modality, 0.0) for s in scores)
    final = float(min(max(final, 0.0), 1.0))

    mean_conf = sum(s.confidence for s in scores) / len(scores)
    disagreement = _disagreement_penalty([s.score for s in scores])
    # Disagreement erodes confidence; a single modality carries no disagreement
    # term but also gets no multi-modality confidence bonus.
    confidence = float(max(0.0, min(1.0, mean_conf * (1.0 - 0.5 * disagreement))))
    confidence = round(confidence, 4)

    band = _band(final)

    return FusionOutcome(
        final_score=round(final, 4),
        risk_band=band,
        confidence=confidence,
        modalities_used=present,
        weights=weights,
        recommendation=_recommendation(band, present, confidence),
        uncertainty_note=_uncertainty_note(present, confidence, disagreement),
    )
