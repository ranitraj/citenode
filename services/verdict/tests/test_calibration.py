"""Tests for confidence calibration and council panel-independence metrics."""

import pytest
from verdict.eval.calibration import (
    CalibrationSample,
    brier_score,
    effective_votes,
    expected_calibration_error,
    panel_diagnostic,
    score_calibration,
)


def _sample(confidence: float, correct: bool) -> CalibrationSample:
    return CalibrationSample(confidence=confidence, correct=correct)


def test_brier_score_is_zero_for_perfectly_confident_correct_calls():
    samples = [_sample(1.0, True), _sample(0.0, False)]
    assert brier_score(samples) == 0.0  # confidence = outcome → squared error 0


def test_brier_score_is_one_for_perfectly_confident_wrong_calls():
    samples = [_sample(1.0, False), _sample(0.0, True)]
    assert brier_score(samples) == 1.0  # confidence = 1 - outcome → squared error 1


def test_expected_calibration_error_is_zero_when_confidence_matches_accuracy():
    samples = [_sample(1.0, True) for _ in range(10)] + [_sample(0.0, False) for _ in range(10)]
    assert expected_calibration_error(samples, bins=10) == 0.0  # each bin's accuracy = its confidence


def test_expected_calibration_error_is_high_when_overconfident():
    samples = [_sample(1.0, True), _sample(1.0, False)]
    assert expected_calibration_error(samples, bins=10) == 0.5  # conf=1.0, accuracy=0.5 → |0.5 - 1.0|


def test_score_calibration_bundles_ece_brier_and_count():
    metrics = score_calibration([_sample(1.0, True), _sample(0.0, False)], bins=10)
    assert metrics.ece == 0.0
    assert metrics.brier == 0.0
    assert metrics.n == 2


def test_effective_votes_collapses_to_one_for_identical_members():
    members = {"m1": [True, False, True], "m2": [True, False, True], "m3": [True, False, True]}
    assert effective_votes(members) == pytest.approx(1.0)  # corr=1 → n_eff = N/(1+(N-1)) = 1


def test_effective_votes_is_full_for_uncorrelated_members():
    members = {"m1": [True, True, False, False], "m2": [True, False, True, False]}
    assert effective_votes(members) == 2.0  # orthogonal → corr=0 → n_eff = N


def test_panel_diagnostic_flags_independence_below_the_floor():
    members = {"m1": [True, False], "m2": [True, False], "m3": [True, False]}
    diagnostic = panel_diagnostic(members)
    assert diagnostic.n_eff == pytest.approx(1.0)  # 3 identical → n_eff=1; 1/3 < 0.5 floor
    assert diagnostic.n_members == 3
    assert diagnostic.meets_floor is False
