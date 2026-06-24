"""Score confidence calibration (ECE, Brier) and council panel independence (n_eff)."""

import math
from collections import defaultdict
from itertools import combinations

from pydantic import BaseModel

from verdict import config


class CalibrationSample(BaseModel):
    """One verdict's confidence score and whether it matched the gold label."""

    confidence: float
    correct: bool


class CalibrationMetrics(BaseModel):
    """Calibration over the scored verdicts: expected calibration error and Brier score."""

    ece: float
    brier: float
    n: int


class PanelDiagnostic(BaseModel):
    """The council's effective independent votes against the member count and floor."""

    n_eff: float
    n_members: int
    meets_floor: bool


def score_calibration(samples: list[CalibrationSample], *, bins: int = config.CALIBRATION_BINS) -> CalibrationMetrics:
    """Bundle the expected calibration error and Brier score over the samples.

    Parameters
    ----------
    samples : list[CalibrationSample]
        The confidence-vs-correctness pairs to score.
    bins : int
        The number of equal-width confidence bins for the calibration error.

    Returns
    -------
    CalibrationMetrics
        The calibration error, Brier score, and sample count.
    """
    return CalibrationMetrics(
        ece=expected_calibration_error(samples, bins=bins), brier=brier_score(samples), n=len(samples)
    )


def brier_score(samples: list[CalibrationSample]) -> float:
    """Return the mean squared error between confidence and the binary outcome.

    Parameters
    ----------
    samples : list[CalibrationSample]
        The confidence-vs-correctness pairs.

    Returns
    -------
    float
        The mean squared error in [0, 1], or 0.0 when there are no samples.
    """
    if not samples:
        return 0.0
    return sum((sample.confidence - float(sample.correct)) ** 2 for sample in samples) / len(samples)


def expected_calibration_error(samples: list[CalibrationSample], *, bins: int = config.CALIBRATION_BINS) -> float:
    """Return the bin-weighted gap between confidence and accuracy.

    Samples are grouped into equal-width confidence bins; each bin contributes the
    absolute gap between its mean confidence and its accuracy, weighted by its share
    of the samples.

    Parameters
    ----------
    samples : list[CalibrationSample]
        The confidence-vs-correctness pairs.
    bins : int
        The number of equal-width confidence bins over [0, 1].

    Returns
    -------
    float
        The expected calibration error in [0, 1], or 0.0 when there are no samples.
    """
    if not samples:
        return 0.0
    grouped: dict[int, list[CalibrationSample]] = defaultdict(list)
    for sample in samples:
        grouped[min(int(sample.confidence * bins), bins - 1)].append(sample)
    error = 0.0
    for group in grouped.values():
        accuracy = sum(1 for sample in group if sample.correct) / len(group)
        confidence = sum(sample.confidence for sample in group) / len(group)
        error += (len(group) / len(samples)) * abs(accuracy - confidence)
    return error


def panel_diagnostic(member_correct: dict[str, list[bool]]) -> PanelDiagnostic:
    """Report the council's effective independent votes and whether it clears the floor.

    Parameters
    ----------
    member_correct : dict[str, list[bool]]
        Per member, whether its verdict matched gold on each claim, in claim order.

    Returns
    -------
    PanelDiagnostic
        The effective-vote count, member count, and whether n_eff/N clears the floor.
    """
    n_members = len(member_correct)
    n_eff = effective_votes(member_correct)
    meets_floor = n_members > 0 and n_eff / n_members >= config.PANEL_INDEPENDENCE_FLOOR
    return PanelDiagnostic(n_eff=n_eff, n_members=n_members, meets_floor=meets_floor)


def effective_votes(member_correct: dict[str, list[bool]]) -> float:
    """Return the panel's effective independent votes from correlated member errors.

    Uses the standard effective-sample-size-under-correlation form
    ``n_eff = N / (1 + (N-1) * mean_correlation)`` over the members' per-claim
    correctness vectors: independent members give n_eff ~ N, perfectly correlated
    members collapse to 1. Negative mean correlation is floored at 0, capping n_eff at N.

    Parameters
    ----------
    member_correct : dict[str, list[bool]]
        Per member, whether its verdict matched gold on each claim, in claim order.

    Returns
    -------
    float
        The effective number of independent votes in [1, N].
    """
    members = list(member_correct.values())
    n_members = len(members)
    if n_members < 2:
        return float(n_members)
    correlations = [_pearson(first, second) for first, second in combinations(members, 2)]
    mean_correlation = max(0.0, sum(correlations) / len(correlations))
    return n_members / (1 + (n_members - 1) * mean_correlation)


def _pearson(first: list[bool], second: list[bool]) -> float:
    """Return the Pearson correlation of two correctness vectors, 0.0 if either is constant.

    Parameters
    ----------
    first : list[bool]
        One member's per-claim correctness.
    second : list[bool]
        Another member's per-claim correctness.

    Returns
    -------
    float
        The Pearson correlation in [-1, 1], or 0.0 when a vector has no variance.
    """
    left = [float(value) for value in first]
    right = [float(value) for value in second]
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    covariance = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right, strict=True))
    deviation_left = math.sqrt(sum((a - mean_left) ** 2 for a in left))
    deviation_right = math.sqrt(sum((b - mean_right) ** 2 for b in right))
    if deviation_left == 0 or deviation_right == 0:
        return 0.0
    return covariance / (deviation_left * deviation_right)
