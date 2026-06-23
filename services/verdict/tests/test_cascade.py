"""Tests for the cheap-pass cascade: evidence-side escalation gate."""

from verdict.cascade import should_escalate
from verdict.models import DraftVerdict, EvidenceBalance, EvidenceSet, Verdict


def _evidence(*, supports: int, contradicts: int, neutral: int, off_topic: int, lean: float) -> EvidenceSet:
    balance = EvidenceBalance(
        supports=supports, contradicts=contradicts, neutral=neutral, off_topic=off_topic, weighted_lean=lean
    )
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
