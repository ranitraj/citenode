"""Tests for council member verdicts and the grounding guard."""

import pytest
from verdict.council.members import QuorumNotReached, apply_grounding_guard, draft_member_verdicts
from verdict.models import EvidenceItem, EvidenceSet, MemberVerdict, Stance, Verdict

from tests.factories import make_balance, make_paper
from tests.model_stubs import failing_model, member_verdict_model


def _evidence(stances: dict[str, Stance]) -> EvidenceSet:
    items = [
        EvidenceItem(paper=make_paper(paper_id), stance=stance, snippet="s", rationale="r")
        for paper_id, stance in stances.items()
    ]
    return EvidenceSet(items=items, balance=make_balance(0.0), coverage_note="n")


class _Provider:
    def __init__(self, models):
        self._models = models

    def member_models(self):
        """Return the stub member models."""
        return self._models


def _member(*, supporting: list[str], contradicting: list[str]) -> MemberVerdict:
    return MemberVerdict(
        verdict=Verdict.SUPPORTED, supporting_ids=supporting, contradicting_ids=contradicting, rationale="r"
    )


def test_grounding_keeps_citations_matching_the_derived_stance():
    evidence = _evidence({"P_sup": Stance.SUPPORTS, "P_con": Stance.CONTRADICTS})
    member = _member(supporting=["P_sup"], contradicting=["P_con"])

    grounded, dissent = apply_grounding_guard(member, evidence)

    assert grounded.supporting_ids == ["P_sup"]
    assert grounded.contradicting_ids == ["P_con"]
    assert not dissent


def test_grounding_drops_ungrounded_citations():
    evidence = _evidence({"P_sup": Stance.SUPPORTS})
    member = _member(supporting=["P_sup", "ghost"], contradicting=[])

    grounded, dissent = apply_grounding_guard(member, evidence)

    assert grounded.supporting_ids == ["P_sup"]
    assert not dissent


def test_grounding_flags_a_stance_mismatch_as_dissent():
    evidence = _evidence({"P": Stance.SUPPORTS})
    member = _member(supporting=[], contradicting=["P"])

    grounded, dissent = apply_grounding_guard(member, evidence)

    assert grounded.contradicting_ids == []
    assert dissent == ["P"]


async def test_draft_member_verdicts_grounds_each_member():
    evidence = _evidence({"P_sup": Stance.SUPPORTS, "P_con": Stance.CONTRADICTS})
    provider = _Provider(
        [
            member_verdict_model(supporting=["P_sup"], contradicting=["P_con"], model_name=f"m{index}")
            for index in range(4)
        ]
    )

    verdicts = await draft_member_verdicts("a claim", evidence, provider=provider)

    assert set(verdicts) == {"m0", "m1", "m2", "m3"}
    assert all(verdict.supporting_ids == ["P_sup"] for verdict in verdicts.values())


async def test_draft_member_verdicts_applies_the_grounding_guard():
    evidence = _evidence({"P": Stance.SUPPORTS})
    provider = _Provider(
        [member_verdict_model(supporting=["P", "ghost"], model_name=f"m{index}") for index in range(4)]
    )

    verdicts = await draft_member_verdicts("a claim", evidence, provider=provider)

    assert all(verdict.supporting_ids == ["P"] for verdict in verdicts.values())


async def test_draft_member_verdicts_survives_one_failed_member():
    evidence = _evidence({"P": Stance.SUPPORTS})
    provider = _Provider(
        [
            member_verdict_model(supporting=["P"], model_name="m0"),
            member_verdict_model(supporting=["P"], model_name="m1"),
            member_verdict_model(supporting=["P"], model_name="m2"),
            failing_model(model_name="m3"),
        ]
    )

    verdicts = await draft_member_verdicts("a claim", evidence, provider=provider)

    assert set(verdicts) == {"m0", "m1", "m2"}


async def test_draft_member_verdicts_raises_when_quorum_not_met():
    evidence = _evidence({"P": Stance.SUPPORTS})
    provider = _Provider(
        [
            member_verdict_model(supporting=["P"], model_name="m0"),
            member_verdict_model(supporting=["P"], model_name="m1"),
            failing_model(model_name="m2"),
            failing_model(model_name="m3"),
        ]
    )

    with pytest.raises(QuorumNotReached):
        await draft_member_verdicts("a claim", evidence, provider=provider)
