"""Fusion engine unit tests — Blueprint Section 38 requires all four modality
combinations to be tested and to produce sane, differently-weighted output."""

from __future__ import annotations

import pytest

from app.ml.fusion.engine import (
    BASE_WEIGHTS,
    ModalityScore,
    fuse,
)


def test_clinical_only_runs_at_full_weight():
    out = fuse([ModalityScore("clinical", 0.8, 0.6)])
    assert out.weights == {"clinical": 1.0}
    assert out.final_score == pytest.approx(0.8, abs=1e-6)
    assert out.modalities_used == ["clinical"]


def test_clinical_plus_pcg_renormalises_weights():
    out = fuse([ModalityScore("clinical", 0.8, 0.9), ModalityScore("pcg", 0.8, 0.9)])
    # 0.50 / 0.25 base -> 0.667 / 0.333 renormalised
    assert out.weights["clinical"] == pytest.approx(0.6667, abs=1e-3)
    assert out.weights["pcg"] == pytest.approx(0.3333, abs=1e-3)
    assert sum(out.weights.values()) == pytest.approx(1.0, abs=1e-3)


def test_clinical_plus_ecg_renormalises_weights():
    out = fuse([ModalityScore("clinical", 0.4, 0.8), ModalityScore("ecg", 0.4, 0.8)])
    assert out.weights["clinical"] == pytest.approx(0.6667, abs=1e-3)
    assert out.weights["ecg"] == pytest.approx(0.3333, abs=1e-3)


def test_full_multimodal_uses_base_weights():
    out = fuse(
        [
            ModalityScore("clinical", 0.5, 0.5),
            ModalityScore("pcg", 0.5, 0.5),
            ModalityScore("ecg", 0.5, 0.5),
        ]
    )
    assert out.weights == pytest.approx(BASE_WEIGHTS, abs=1e-3)
    assert sum(out.weights.values()) == pytest.approx(1.0, abs=1e-3)


@pytest.mark.parametrize(
    "modalities",
    [
        ["clinical"],
        ["clinical", "pcg"],
        ["clinical", "ecg"],
        ["clinical", "pcg", "ecg"],
    ],
)
def test_all_four_combinations_produce_valid_output(modalities):
    out = fuse([ModalityScore(m, 0.55, 0.7) for m in modalities])
    assert 0.0 <= out.final_score <= 1.0
    assert out.risk_band in {"low", "moderate", "high"}
    assert 0.0 <= out.confidence <= 1.0
    assert out.modalities_used == modalities
    assert sum(out.weights.values()) == pytest.approx(1.0, abs=1e-3)
    assert out.recommendation
    assert out.uncertainty_note


def test_weights_always_sum_to_one_across_every_subset():
    for subset in (["clinical"], ["pcg"], ["ecg"], ["pcg", "ecg"], ["clinical", "pcg"]):
        out = fuse([ModalityScore(m, 0.5, 0.5) for m in subset])
        assert sum(out.weights.values()) == pytest.approx(1.0, abs=1e-6), subset


def test_risk_bands_map_to_expected_ranges():
    assert fuse([ModalityScore("clinical", 0.10, 0.9)]).risk_band == "low"
    assert fuse([ModalityScore("clinical", 0.45, 0.9)]).risk_band == "moderate"
    assert fuse([ModalityScore("clinical", 0.85, 0.9)]).risk_band == "high"


def test_disagreement_between_modalities_reduces_confidence():
    """Two confident but opposing signals must not average into confidence."""
    agreeing = fuse(
        [ModalityScore("clinical", 0.85, 0.9), ModalityScore("pcg", 0.85, 0.9)]
    )
    disagreeing = fuse(
        [ModalityScore("clinical", 0.90, 0.9), ModalityScore("pcg", 0.10, 0.9)]
    )
    assert disagreeing.confidence < agreeing.confidence
    assert "disagreed" in disagreeing.uncertainty_note


def test_missing_modalities_are_named_and_not_treated_as_normal():
    out = fuse([ModalityScore("clinical", 0.5, 0.8)])
    note = out.uncertainty_note
    assert "1 of 3" in note
    assert "pcg" in note and "ecg" in note
    assert "not treated as" in note.lower() or "not assessed" in note.lower()


def test_clinical_only_recommendation_mentions_the_missing_modalities():
    out = fuse([ModalityScore("clinical", 0.20, 0.9)])
    assert "clinical measurements only" in out.recommendation


def test_low_confidence_is_surfaced_in_the_recommendation():
    out = fuse([ModalityScore("clinical", 0.52, 0.04)])
    assert "confidence in this result is low" in out.recommendation.lower()


def test_high_band_recommendation_advises_seeing_a_doctor():
    out = fuse([ModalityScore("clinical", 0.92, 0.9)])
    assert "doctor" in out.recommendation.lower()


def test_empty_input_is_an_error_not_a_zero_risk_result():
    """A screening with no signal behind it must never look like low risk."""
    with pytest.raises(ValueError):
        fuse([])


def test_disclaimer_is_always_attached():
    out = fuse([ModalityScore("clinical", 0.5, 0.5)])
    assert "not a diagnosis" in out.disclaimer.lower()
