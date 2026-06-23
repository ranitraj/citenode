"""Pure aggregation math for the council: concordance, divergence, and confidence."""

import math

from verdict import config
from verdict.models import (
    AgreementSignals,
    CapReason,
    Confidence,
    ConfidenceBand,
    EvidenceBalance,
    EvidenceItem,
    RankAgg,
    Stance,
)
from verdict.vectors import cosine_similarity

_BANDS = (ConfidenceBand.LOW, ConfidenceBand.MODERATE, ConfidenceBand.HIGH)


def kendalls_w(rankings: list[list[str]]) -> tuple[float | None, bool]:
    """Compute Kendall's W (coefficient of concordance) over member rankings.

    Parameters
    ----------
    rankings : list[list[str]]
        One full ordering per ranker, best to worst, by model name.

    Returns
    -------
    tuple[float | None, bool]
        The concordance `W` in [0, 1] rounded to 3 dp (or None when fewer than
        two rankers or models), and `low_information` (True when k < 3 or n < 3,
        where W is near-meaningless).
    """
    ranked = [r for r in rankings if r]
    k = len(ranked)
    models = sorted({m for r in ranked for m in r})
    n = len(models)
    low_information = k < 3 or n < 3

    if k < 2 or n < 2:
        return None, low_information

    rank_sums = [_rank_sum(model, ranked, n) for model in models]
    mean = sum(rank_sums) / n
    s = sum((rs - mean) ** 2 for rs in rank_sums)
    denom = k**2 * (n**3 - n)
    w = 0.0 if denom <= 0 else min(12 * s / denom, 1.0)
    return round(w, 3), low_information


def has_disagreement(rankings: list[list[str]]) -> bool:
    """Return True when the rankers do not share a single top pick.

    Parameters
    ----------
    rankings : list[list[str]]
        One ordering per ranker, best to worst.

    Returns
    -------
    bool
        True when more than one distinct model appears in the top position.
    """
    top_picks = {r[0] for r in rankings if r}
    return len(top_picks) > 1


def epistemic_uncertainty(member_embeddings: list[list[float]]) -> float | None:
    """Compute epistemic uncertainty as 1 minus the mean pairwise cosine.

    Parameters
    ----------
    member_embeddings : list[list[float]]
        Embedded member draft texts (prose), one vector per member.

    Returns
    -------
    float | None
        `1 - mean(pairwise cosine)` rounded to 4 dp, or None when fewer than
        two non-empty drafts are available.
    """
    vectors = [v for v in member_embeddings if v]
    if len(vectors) < 2:
        return None
    sims = [cosine_similarity(vectors[i], vectors[j]) for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
    return round(1 - sum(sims) / len(sims), 4)


def aggregate_rankings(rankings: list[list[str]]) -> list[RankAgg]:
    """Aggregate member rankings by average rank (not Borda), best first.

    Parameters
    ----------
    rankings : list[list[str]]
        One ordering per ranker, best to worst.

    Returns
    -------
    list[RankAgg]
        One entry per model with its mean 1-indexed position and the count of
        rankers that placed it, sorted ascending by average rank.
    """
    positions: dict[str, list[int]] = {}
    for ranking in rankings:
        for index, model in enumerate(ranking):
            positions.setdefault(model, []).append(index + 1)

    aggs = [
        RankAgg(
            model=model,
            average_rank=sum(places) / len(places),
            rankings_count=len(places),
        )
        for model, places in positions.items()
    ]
    return sorted(aggs, key=lambda agg: agg.average_rank)


def weighted_lean(items: list[EvidenceItem]) -> float:
    """Compute the signed, influence- and recency-weighted evidence balance.

    Parameters
    ----------
    items : list[EvidenceItem]
        The per-paper evidence; OFF_TOPIC items are excluded from the balance
        and NEUTRAL items count toward the denominator only.

    Returns
    -------
    float
        `(supports_weight - contradicts_weight) / total_weight` in [-1, 1], or
        0.0 when there is no on-topic, non-zero-weight evidence.
    """
    numerator = 0.0
    denominator = 0.0
    for item in items:
        if item.stance is Stance.OFF_TOPIC:
            continue
        weight = influence_recency_weight(item.paper.cited_by, item.paper.year)
        denominator += weight
        if item.stance is Stance.SUPPORTS:
            numerator += weight
        elif item.stance is Stance.CONTRADICTS:
            numerator -= weight

    if denominator <= 0:
        return 0.0
    return numerator / denominator


def influence_recency_weight(cited_by: int, year: int) -> float:
    """Weight a paper by influence discounted for age.

    Parameters
    ----------
    cited_by : int
        The paper's citation count.
    year : int
        The paper's publication year.

    Returns
    -------
    float
        ``log1p(cited_by)`` scaled by a recency half-life factor.
    """
    age = config.CURRENT_YEAR - year
    recency_factor: float = 0.5 ** (age / config.RECENCY_HALF_LIFE_YEARS)
    return math.log1p(cited_by) * recency_factor


def summarise_balance(items: list[EvidenceItem]) -> EvidenceBalance:
    """Tally per-paper stances into an EvidenceBalance with the signed lean.

    Parameters
    ----------
    items : list[EvidenceItem]
        The per-paper evidence to summarise.

    Returns
    -------
    EvidenceBalance
        Per-stance counts and the influence-weighted lean over the items.
    """
    counts = {stance: 0 for stance in Stance}
    for item in items:
        counts[item.stance] += 1
    return EvidenceBalance(
        supports=counts[Stance.SUPPORTS],
        contradicts=counts[Stance.CONTRADICTS],
        neutral=counts[Stance.NEUTRAL],
        off_topic=counts[Stance.OFF_TOPIC],
        weighted_lean=weighted_lean(items),
    )


def compute_confidence(signals: AgreementSignals, balance: EvidenceBalance) -> Confidence:
    """Derive confidence from the evidence balance, capped by council disagreement.

    The band base comes from `|balance.weighted_lean|`; council disagreement may
    only lower it by one step, never raise it. The cap fires on `has_disagreement`
    or a low Kendall's W, but a low-information W is ignored.

    Parameters
    ----------
    signals : AgreementSignals
        The council agreement signals (Kendall's W, EU, disagreement flags).
    balance : EvidenceBalance
        The evidence balance whose `weighted_lean` sets the base band.

    Returns
    -------
    Confidence
        The score, discrete band, and a short basis string.
    """
    score = abs(balance.weighted_lean)
    base_index = _base_band_index(score)

    w_caps = (
        signals.kendalls_w is not None
        and signals.kendalls_w < config.KENDALLS_W_UNSETTLED_FLOOR
        and not signals.low_information
    )
    unsettled = signals.has_disagreement or w_caps
    index = max(0, base_index - 1) if unsettled else base_index

    basis = f"balance |lean|={score:.2f}"
    if unsettled:
        reason = CapReason.COUNCIL_DISAGREEMENT if signals.has_disagreement else CapReason.LOW_CONCORDANCE
        basis += f", capped one band ({reason})"
    return Confidence(score=score, band=_BANDS[index], basis=basis)


def _rank_sum(model: str, rankings: list[list[str]], absent_position: int) -> int:
    """Sum a model's 1-indexed positions across rankers.

    Parameters
    ----------
    model : str
        The model whose positions are summed.
    rankings : list[list[str]]
        The per-ranker orderings.
    absent_position : int
        The position to use where a ranker omitted the model.

    Returns
    -------
    int
        The summed 1-indexed positions.
    """
    return sum(ranking.index(model) + 1 if model in ranking else absent_position for ranking in rankings)


def _base_band_index(score: float) -> int:
    """Map a confidence score to its base band index.

    Parameters
    ----------
    score : float
        The absolute weighted lean in [0, 1].

    Returns
    -------
    int
        0 for low, 1 for moderate, 2 for high.
    """
    if score >= config.CONFIDENCE_HIGH_MIN:
        return 2
    if score >= config.CONFIDENCE_MODERATE_MIN:
        return 1
    return 0
