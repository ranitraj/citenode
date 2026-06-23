"""Tests for chairman synthesis and its citation grounding."""

from verdict.council.chairman import synthesise_verdict
from verdict.models import (
    AgreementSignals,
    ChairmanVerdict,
    EvidenceItem,
    EvidenceSet,
    MemberVerdict,
    Stance,
    Verdict,
)

from tests.factories import make_balance, make_paper
from tests.model_stubs import chairman_verdict_model


def _evidence(stances: dict[str, Stance]) -> EvidenceSet:
    items = [
        EvidenceItem(paper=make_paper(paper_id), stance=stance, snippet="s", rationale="r")
        for paper_id, stance in stances.items()
    ]
    return EvidenceSet(items=items, balance=make_balance(0.0), coverage_note="n")


def _drafts(names: list[str]) -> dict[str, MemberVerdict]:
    return {
        name: MemberVerdict(verdict=Verdict.SUPPORTED, supporting_ids=[], contradicting_ids=[], rationale=name)
        for name in names
    }


def _signals() -> AgreementSignals:
    return AgreementSignals(kendalls_w=0.8, eu=0.1, has_disagreement=False, low_information=False)


class _Provider:
    def __init__(self, model):
        self._model = model

    def chairman_model(self):
        """Return the stub chairman model."""
        return self._model


async def test_synthesise_verdict_returns_a_grounded_chairman_verdict():
    evidence = _evidence({"P_sup": Stance.SUPPORTS, "P_con": Stance.CONTRADICTS})
    provider = _Provider(
        chairman_verdict_model(
            verdict=Verdict.CONTESTED,
            supporting=["P_sup"],
            contradicting=["P_con"],
            synthesis="weighed both sides",
            dissent="a member would refute",
        )
    )

    result = await synthesise_verdict("a claim", evidence, _drafts(["m0", "m1"]), _signals(), provider=provider)

    assert isinstance(result, ChairmanVerdict)
    assert result.verdict is Verdict.CONTESTED
    assert result.supporting_ids == ["P_sup"]
    assert result.contradicting_ids == ["P_con"]
    assert result.synthesis == "weighed both sides"
    assert result.dissent == "a member would refute"


async def test_synthesise_verdict_drops_ungrounded_citations():
    evidence = _evidence({"P_sup": Stance.SUPPORTS})
    provider = _Provider(chairman_verdict_model(verdict=Verdict.SUPPORTED, supporting=["P_sup", "ghost"]))

    result = await synthesise_verdict("a claim", evidence, _drafts(["m0"]), _signals(), provider=provider)

    assert result.supporting_ids == ["P_sup"]


async def test_synthesise_verdict_drops_stance_mismatched_citations():
    evidence = _evidence({"P": Stance.SUPPORTS})
    provider = _Provider(chairman_verdict_model(verdict=Verdict.REFUTED, contradicting=["P"]))

    result = await synthesise_verdict("a claim", evidence, _drafts(["m0"]), _signals(), provider=provider)

    assert result.contradicting_ids == []


async def test_synthesise_verdict_keeps_dissent_none_when_absent():
    evidence = _evidence({"P": Stance.SUPPORTS})
    provider = _Provider(chairman_verdict_model(verdict=Verdict.SUPPORTED, supporting=["P"], dissent=None))

    result = await synthesise_verdict("a claim", evidence, _drafts(["m0"]), _signals(), provider=provider)

    assert result.dissent is None
