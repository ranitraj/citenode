"""Tests for the full council orchestration."""

from verdict.council.run import run_council
from verdict.models import (
    ConfidenceBand,
    CouncilOutput,
    EvidenceItem,
    EvidenceSet,
    Stance,
    Verdict,
)

from tests.factories import make_balance, make_paper
from tests.model_stubs import (
    StubEmbedder,
    chairman_verdict_model,
    council_provider,
    failing_model,
    member_ranker_model,
)


def _evidence(stances: dict[str, Stance], *, lean: float) -> EvidenceSet:
    items = [
        EvidenceItem(paper=make_paper(paper_id), stance=stance, snippet="s", rationale="r")
        for paper_id, stance in stances.items()
    ]
    return EvidenceSet(items=items, balance=make_balance(lean, supports=len(items)), coverage_note="n")


async def test_run_council_produces_a_full_council_output():
    evidence = _evidence({"P_sup": Stance.SUPPORTS}, lean=0.9)
    provider = council_provider(
        members=[member_ranker_model(supporting=["P_sup"], model_name=f"m{index}") for index in range(4)],
        chairman=chairman_verdict_model(verdict=Verdict.SUPPORTED, supporting=["P_sup"], synthesis="clear support"),
    )

    out = await run_council("a claim", evidence, provider=provider, embedder=StubEmbedder())

    assert isinstance(out, CouncilOutput)
    assert set(out.members) == {"m0", "m1", "m2", "m3"}
    assert out.chairman.verdict is Verdict.SUPPORTED
    assert out.chairman.supporting_ids == ["P_sup"]
    assert out.signals.has_disagreement is False
    assert out.confidence.band is ConfidenceBand.HIGH


async def test_run_council_survives_one_failed_member():
    evidence = _evidence({"P_sup": Stance.SUPPORTS}, lean=0.8)
    provider = council_provider(
        members=[
            member_ranker_model(supporting=["P_sup"], model_name="m0"),
            member_ranker_model(supporting=["P_sup"], model_name="m1"),
            member_ranker_model(supporting=["P_sup"], model_name="m2"),
            failing_model(model_name="m3"),
        ],
        chairman=chairman_verdict_model(verdict=Verdict.SUPPORTED, supporting=["P_sup"]),
    )

    out = await run_council("a claim", evidence, provider=provider, embedder=StubEmbedder())

    assert set(out.members) == {"m0", "m1", "m2"}
    assert out.chairman.verdict is Verdict.SUPPORTED


async def test_run_council_falls_back_to_member_majority_when_chairman_fails():
    evidence = _evidence({"P_sup": Stance.SUPPORTS}, lean=0.8)
    provider = council_provider(
        members=[
            member_ranker_model(verdict=Verdict.SUPPORTED, supporting=["P_sup"], model_name=f"m{index}")
            for index in range(4)
        ],
        chairman=failing_model(model_name="chair"),
    )

    out = await run_council("a claim", evidence, provider=provider, embedder=StubEmbedder())

    assert out.chairman.verdict is Verdict.SUPPORTED
    assert out.chairman.supporting_ids == ["P_sup"]
    assert out.chairman.dissent is None
