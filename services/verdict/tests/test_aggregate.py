"""Tests for the pure council aggregation math."""

import math

import pytest
from verdict import config
from verdict.council.aggregate import (
    aggregate_rankings,
    compute_confidence,
    epistemic_uncertainty,
    has_disagreement,
    influence_recency_weight,
    kendalls_w,
    summarise_balance,
    weighted_lean,
)
from verdict.models import (
    AgreementSignals,
    EvidenceBalance,
    EvidenceItem,
    Stance,
)

from tests.factories import make_paper


def _item(stance: Stance, cited_by: int, year: int = config.CURRENT_YEAR) -> EvidenceItem:
    paper = make_paper(f"W-{stance}-{cited_by}-{year}", cited_by=cited_by, year=year)
    return EvidenceItem(paper=paper, stance=stance, snippet="s", rationale="r")


def _balance(lean: float) -> EvidenceBalance:
    return EvidenceBalance(supports=1, contradicts=0, neutral=0, off_topic=0, weighted_lean=lean)


# --- Kendall's W -----------------------------------------------------------


def test_kendalls_w_identical_rankings_is_one_and_not_low_information():
    rankings = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"]]
    w, low_info = kendalls_w(rankings)
    assert w == 1.0
    assert low_info is False  # k=3, n=3


def test_kendalls_w_reversed_rankings_is_low():
    w, _ = kendalls_w([["a", "b", "c"], ["c", "b", "a"]])
    assert w == 0.0


def test_kendalls_w_flags_low_information_for_small_panel():
    # Two rankers (k<3) → W is near-meaningless, flagged low_information.
    _, low_info = kendalls_w([["a", "b", "c"], ["a", "b", "c"]])
    assert low_info is True


def test_kendalls_w_returns_none_with_fewer_than_two_rankers():
    w, low_info = kendalls_w([["a", "b", "c"]])
    assert w is None
    assert low_info is True


# --- Epistemic uncertainty -------------------------------------------------


def test_epistemic_uncertainty_is_zero_for_identical_drafts():
    assert epistemic_uncertainty([[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]) == 0.0


def test_epistemic_uncertainty_is_one_for_orthogonal_drafts():
    assert epistemic_uncertainty([[1.0, 0.0], [0.0, 1.0]]) == 1.0


def test_epistemic_uncertainty_is_none_with_a_single_draft():
    assert epistemic_uncertainty([[1.0, 0.0]]) is None


# --- has_disagreement ------------------------------------------------------


def test_has_disagreement_false_when_top_pick_is_shared():
    assert has_disagreement([["a", "b"], ["a", "c"]]) is False


def test_has_disagreement_true_when_top_picks_differ():
    assert has_disagreement([["a", "b"], ["b", "a"]]) is True


# --- aggregate_rankings (average-rank, not Borda) --------------------------


def test_aggregate_rankings_orders_by_average_rank():
    aggs = aggregate_rankings([["a", "b", "c"], ["b", "a", "c"]])
    by_model = {agg.model: agg for agg in aggs}
    assert by_model["a"].average_rank == 1.5
    assert by_model["b"].average_rank == 1.5
    assert by_model["c"].average_rank == 3.0
    # Sorted best (lowest average rank) first; worst last.
    assert aggs[0].average_rank <= aggs[-1].average_rank
    assert aggs[-1].model == "c"


def test_aggregate_rankings_counts_only_rankers_that_placed_a_model():
    aggs = aggregate_rankings([["a", "b"], ["a", "b", "c"]])
    by_model = {agg.model: agg for agg in aggs}
    assert by_model["c"].rankings_count == 1
    assert by_model["c"].average_rank == 3.0
    assert by_model["a"].rankings_count == 2


# --- weighted_lean ---------------------------------------------------------


def test_weighted_lean_is_plus_one_for_all_supporting():
    assert weighted_lean([_item(Stance.SUPPORTS, 10)]) == pytest.approx(1.0)


def test_weighted_lean_is_minus_one_for_all_contradicting():
    assert weighted_lean([_item(Stance.CONTRADICTS, 10)]) == pytest.approx(-1.0)


def test_weighted_lean_is_zero_for_balanced_equal_weight_evidence():
    items = [_item(Stance.SUPPORTS, 10), _item(Stance.CONTRADICTS, 10)]
    assert weighted_lean(items) == pytest.approx(0.0)


def test_weighted_lean_counts_neutral_in_denominator_not_numerator():
    # One support + one equal-weight neutral → numerator=w, denominator=2w → 0.5.
    items = [_item(Stance.SUPPORTS, 10), _item(Stance.NEUTRAL, 10)]
    assert weighted_lean(items) == pytest.approx(0.5)


def test_weighted_lean_excludes_off_topic_from_the_balance():
    # A heavy off-topic paper must not move the lean.
    items = [_item(Stance.SUPPORTS, 10), _item(Stance.OFF_TOPIC, 1_000_000)]
    assert weighted_lean(items) == pytest.approx(1.0)


def test_weighted_lean_is_zero_when_no_on_topic_evidence():
    assert weighted_lean([_item(Stance.OFF_TOPIC, 10)]) == pytest.approx(0.0)


def test_weighted_lean_weights_influence_by_log1p_cited_by():
    # Same year (recency=1); the lean is the log1p(cited_by) influence balance.
    support = _item(Stance.SUPPORTS, 20)
    contra = _item(Stance.CONTRADICTS, 4)
    w_s, w_c = math.log1p(20), math.log1p(4)
    expected = (w_s - w_c) / (w_s + w_c)
    assert weighted_lean([support, contra]) == pytest.approx(expected)


def test_weighted_lean_halves_weight_for_one_half_life_older_evidence():
    # Equal cited_by → log1p cancels; only the recency factor (0.5) remains.
    recent = _item(Stance.SUPPORTS, 100, year=config.CURRENT_YEAR)
    older = _item(Stance.CONTRADICTS, 100, year=config.CURRENT_YEAR - config.RECENCY_HALF_LIFE_YEARS)
    expected = (1.0 - 0.5) / (1.0 + 0.5)
    assert weighted_lean([recent, older]) == pytest.approx(expected)


def test_summarise_balance_counts_each_stance_bucket():
    items = [
        _item(Stance.SUPPORTS, 10),
        _item(Stance.SUPPORTS, 10),
        _item(Stance.CONTRADICTS, 10),
        _item(Stance.NEUTRAL, 10),
        _item(Stance.OFF_TOPIC, 10),
    ]

    balance = summarise_balance(items)

    assert (balance.supports, balance.contradicts, balance.neutral, balance.off_topic) == (2, 1, 1, 1)


def test_summarise_balance_carries_the_weighted_lean():
    items = [_item(Stance.SUPPORTS, 10), _item(Stance.OFF_TOPIC, 1_000_000)]

    balance = summarise_balance(items)

    assert balance.weighted_lean == pytest.approx(weighted_lean(items))


def test_summarise_balance_of_no_items_is_all_zero():
    balance = summarise_balance([])

    assert balance == EvidenceBalance(supports=0, contradicts=0, neutral=0, off_topic=0, weighted_lean=0.0)


def test_influence_recency_weight_is_log1p_cited_by_at_current_year():
    assert influence_recency_weight(20, config.CURRENT_YEAR) == pytest.approx(math.log1p(20))


def test_influence_recency_weight_halves_after_one_half_life():
    older = influence_recency_weight(20, config.CURRENT_YEAR - config.RECENCY_HALF_LIFE_YEARS)
    assert older == pytest.approx(math.log1p(20) * 0.5)


# --- compute_confidence (balance base; disagreement only caps) -------------


def _signals(*, w: float | None, disagree: bool, low_info: bool, eu: float | None = 0.1) -> AgreementSignals:
    return AgreementSignals(kendalls_w=w, eu=eu, has_disagreement=disagree, low_information=low_info)


def test_compute_confidence_high_balance_high_agreement_stays_high():
    conf = compute_confidence(_signals(w=0.9, disagree=False, low_info=False), _balance(0.8))
    assert conf.band == "high"
    assert conf.score == pytest.approx(0.8)


def test_compute_confidence_uses_absolute_lean_so_refuting_evidence_can_be_high():
    conf = compute_confidence(_signals(w=0.9, disagree=False, low_info=False), _balance(-0.7))
    assert conf.band == "high"
    assert conf.score == pytest.approx(0.7)


def test_compute_confidence_low_w_caps_high_band_down_one_step():
    conf = compute_confidence(_signals(w=0.2, disagree=False, low_info=False), _balance(0.8))
    assert conf.band == "moderate"


def test_compute_confidence_low_information_disables_the_w_cap():
    # At small N, W is meaningless → it must not cap the band.
    conf = compute_confidence(_signals(w=0.2, disagree=False, low_info=True), _balance(0.8))
    assert conf.band == "high"


def test_compute_confidence_disagreement_caps_even_with_high_w():
    conf = compute_confidence(_signals(w=0.95, disagree=True, low_info=False), _balance(0.8))
    assert conf.band == "moderate"


def test_compute_confidence_disagreement_caps_even_when_low_information():
    # low_information disables the W cap but not the has_disagreement cap.
    conf = compute_confidence(_signals(w=0.2, disagree=True, low_info=True), _balance(0.8))
    assert conf.band == "moderate"


def test_compute_confidence_never_raises_a_mixed_balance_to_high():
    conf = compute_confidence(_signals(w=0.99, disagree=False, low_info=False), _balance(0.4))
    assert conf.band == "moderate"


def test_compute_confidence_cap_never_drops_below_low():
    conf = compute_confidence(_signals(w=0.1, disagree=True, low_info=False), _balance(0.1))
    assert conf.band == "low"
