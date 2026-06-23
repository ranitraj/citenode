"""Tests for council member verdicts and the grounding guard."""

from verdict.council.members import ground_member_verdict
from verdict.models import EvidenceItem, EvidenceSet, MemberVerdict, Stance, Verdict

from tests.factories import make_balance, make_paper


def _evidence(stances: dict[str, Stance]) -> EvidenceSet:
    items = [
        EvidenceItem(paper=make_paper(paper_id), stance=stance, snippet="s", rationale="r")
        for paper_id, stance in stances.items()
    ]
    return EvidenceSet(items=items, balance=make_balance(0.0), coverage_note="n")


def _member(*, supporting: list[str], contradicting: list[str]) -> MemberVerdict:
    return MemberVerdict(
        verdict=Verdict.SUPPORTED, supporting_ids=supporting, contradicting_ids=contradicting, rationale="r"
    )


def test_grounding_keeps_citations_matching_the_derived_stance():
    evidence = _evidence({"P_sup": Stance.SUPPORTS, "P_con": Stance.CONTRADICTS})
    member = _member(supporting=["P_sup"], contradicting=["P_con"])

    grounded, dissent = ground_member_verdict(member, evidence)

    assert grounded.supporting_ids == ["P_sup"]
    assert grounded.contradicting_ids == ["P_con"]
    assert not dissent


def test_grounding_drops_ungrounded_citations():
    evidence = _evidence({"P_sup": Stance.SUPPORTS})
    member = _member(supporting=["P_sup", "ghost"], contradicting=[])

    grounded, dissent = ground_member_verdict(member, evidence)

    assert grounded.supporting_ids == ["P_sup"]
    assert not dissent


def test_grounding_flags_a_stance_mismatch_as_dissent():
    evidence = _evidence({"P": Stance.SUPPORTS})
    member = _member(supporting=[], contradicting=["P"])

    grounded, dissent = ground_member_verdict(member, evidence)

    assert grounded.contradicting_ids == []
    assert dissent == ["P"]
