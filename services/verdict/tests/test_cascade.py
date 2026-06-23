"""Tests for the cheap-pass cascade: confidence, escalation gate, and cheap verdict."""

import pytest
from verdict import config
from verdict.cascade import cheap_confidence, cheap_verdict, should_escalate
from verdict.models import DraftVerdict, EvidenceItem, EvidenceSet, Stance, Verdict

from tests.factories import make_balance, make_paper
from tests.model_stubs import draft_verdict_model


def _evidence(*, supports: int, contradicts: int, neutral: int, off_topic: int, lean: float) -> EvidenceSet:
    balance = make_balance(lean, supports=supports, contradicts=contradicts, neutral=neutral, off_topic=off_topic)
    return EvidenceSet(items=[], balance=balance, coverage_note="note")


def _draft(verdict: Verdict, *, self_uncertainty: float = 0.1) -> DraftVerdict:
    return DraftVerdict(verdict=verdict, rationale="r", self_uncertainty=self_uncertainty)


def test_should_escalate_is_false_for_one_sided_strong_evidence():
    evidence = _evidence(supports=5, contradicts=0, neutral=0, off_topic=0, lean=0.9)

    assert should_escalate(evidence, _draft(Verdict.SUPPORTED), escalation_threshold=0.1) is False


def test_should_escalate_is_true_when_both_stances_are_present():
    evidence = _evidence(supports=3, contradicts=2, neutral=0, off_topic=0, lean=0.2)

    assert should_escalate(evidence, _draft(Verdict.SUPPORTED), escalation_threshold=0.1) is True


def test_should_escalate_is_true_when_the_lean_is_below_threshold():
    evidence = _evidence(supports=2, contradicts=0, neutral=0, off_topic=0, lean=0.05)

    assert should_escalate(evidence, _draft(Verdict.SUPPORTED), escalation_threshold=0.1) is True


def test_should_escalate_is_true_when_the_balance_disagrees_with_the_draft():
    evidence = _evidence(supports=0, contradicts=4, neutral=0, off_topic=0, lean=-0.8)

    assert should_escalate(evidence, _draft(Verdict.SUPPORTED), escalation_threshold=0.1) is True


def test_should_escalate_is_true_when_coverage_is_thin():
    evidence = _evidence(supports=0, contradicts=0, neutral=0, off_topic=3, lean=0.0)

    assert should_escalate(evidence, _draft(Verdict.INSUFFICIENT), escalation_threshold=0.1) is True


def test_should_escalate_ignores_a_confident_self_uncertainty():
    evidence = _evidence(supports=5, contradicts=0, neutral=0, off_topic=0, lean=0.9)

    assert (
        should_escalate(evidence, _draft(Verdict.SUPPORTED, self_uncertainty=0.99), escalation_threshold=0.1) is False
    )


def test_cheap_confidence_is_high_for_a_strong_balance_and_low_uncertainty():
    confidence = cheap_confidence(_draft(Verdict.SUPPORTED, self_uncertainty=0.1), make_balance(lean=0.9))

    assert confidence.band == "high"
    assert confidence.score == pytest.approx(0.9)


def test_cheap_confidence_caps_one_band_at_high_self_uncertainty():
    confidence = cheap_confidence(
        _draft(Verdict.SUPPORTED, self_uncertainty=config.SELF_UNCERTAINTY_CAP_FLOOR), make_balance(lean=0.9)
    )

    assert confidence.band == "moderate"


def test_cheap_confidence_uncertainty_only_lowers_never_below_low():
    confidence = cheap_confidence(_draft(Verdict.SUPPORTED, self_uncertainty=0.99), make_balance(lean=0.1))

    assert confidence.band == "low"


async def test_cheap_verdict_returns_a_draft_verdict():
    evidence = _evidence(supports=2, contradicts=0, neutral=0, off_topic=0, lean=0.8)

    draft = await cheap_verdict("a claim", evidence, model=draft_verdict_model(Verdict.SUPPORTED))

    assert isinstance(draft, DraftVerdict)
    assert draft.verdict is Verdict.SUPPORTED
    assert draft.self_uncertainty == pytest.approx(0.2)


async def test_cheap_verdict_renders_the_evidence_into_the_prompt():
    item = EvidenceItem(paper=make_paper("W1"), stance=Stance.SUPPORTS, snippet="MARKER_SNIPPET", rationale="r")
    evidence = EvidenceSet(items=[item], balance=make_balance(lean=0.5), coverage_note="note")
    model = draft_verdict_model(Verdict.SUPPORTED, marker="MARKER_SNIPPET", fallback=Verdict.INSUFFICIENT)

    draft = await cheap_verdict("a claim", evidence, model=model)

    assert draft.verdict is Verdict.SUPPORTED
