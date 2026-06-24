"""Tests for the verdict domain models."""

import pytest
from pydantic import ValidationError
from verdict.models import (
    AgreementSignals,
    ChairmanVerdict,
    ClaimResult,
    Confidence,
    ConfidenceBand,
    CouncilOutput,
    DraftVerdict,
    Edge,
    EvidenceBalance,
    EvidenceItem,
    EvidenceSet,
    MemberVerdict,
    Paper,
    Path,
    RankAgg,
    RankingOutput,
    Stance,
    Subgraph,
    TriageResult,
    Verdict,
    Work,
    WorkRef,
)


def _paper(pid: str = "W1") -> Paper:
    return Paper(
        openalex_id=pid,
        doi=None,
        title="A study",
        year=2020,
        abstract="An abstract.",
        cited_by=10,
        is_retracted=False,
        venue="Nature",
    )


def test_enums_round_trip_through_their_string_values():
    assert Stance("supports") is Stance.SUPPORTS
    assert Stance("off_topic") is Stance.OFF_TOPIC
    assert Verdict("contested") is Verdict.CONTESTED
    assert Path("council") is Path.COUNCIL
    # StrEnum members compare equal to their raw string value.
    assert Verdict.REFUTED == "refuted"


def test_work_carries_topics_and_referenced_works_pre_graph():
    work = Work(
        openalex_id="W1",
        doi="10.1/x",
        title="t",
        year=2021,
        abstract="a",
        cited_by=3,
        is_retracted=True,
        venue=None,
        topics=["nlp", "ir"],
        referenced_works=["W2", "W3"],
    )
    assert work.is_retracted is True
    assert work.referenced_works == ["W2", "W3"]


def test_paper_node_rejects_pre_graph_only_fields():
    # Paper is the stored node; topics/referenced_works live on Work, not Paper.
    # extra="forbid" must reject them so the two shapes can't be confused.
    with pytest.raises(ValidationError):
        Paper(
            openalex_id="W1",
            doi=None,
            title="t",
            year=2020,
            abstract="a",
            cited_by=1,
            is_retracted=False,
            venue=None,
            topics=["nlp"],  # extra → forbidden
        )


def test_subgraph_carries_typed_edges():
    sub = Subgraph(
        papers=[_paper("W1"), _paper("W2")],
        edges=[Edge(src="W1", dst="W2", kind="cites")],
    )
    assert sub.edges[0].kind == "cites"


def test_edge_kind_is_constrained_to_known_relations():
    with pytest.raises(ValidationError):
        Edge(src="W1", dst="W2", kind="wrote")


def test_evidence_balance_keeps_off_topic_separate_from_stance_counts():
    # OFF_TOPIC is tracked in its own field, never folded into the three stance
    # counts that feed the verdict.
    balance = EvidenceBalance(supports=3, contradicts=1, neutral=2, off_topic=5, weighted_lean=0.4)
    assert balance.off_topic == 5
    assert balance.supports + balance.contradicts + balance.neutral == 6


def test_evidence_set_bundles_items_balance_and_coverage_note():
    item = EvidenceItem(paper=_paper(), stance=Stance.SUPPORTS, snippet="s", rationale="r")
    ev = EvidenceSet(
        items=[item],
        balance=EvidenceBalance(supports=1, contradicts=0, neutral=0, off_topic=0, weighted_lean=1.0),
        coverage_note="3 abstracts missing, 5 off-topic",
    )
    assert ev.items[0].stance is Stance.SUPPORTS
    assert "off-topic" in ev.coverage_note


def test_member_verdict_holds_grounded_citation_ids_only():
    mv = MemberVerdict(
        verdict=Verdict.SUPPORTED,
        supporting_ids=["W1", "W2"],
        contradicting_ids=[],
        rationale="r",
    )
    assert mv.supporting_ids == ["W1", "W2"]


def test_ranking_output_exposes_resolved_ranking_and_round_trips():
    ro = RankingOutput(resolved_ranking=["m2", "m1", "m3"])
    assert RankingOutput.model_validate(ro.model_dump()).resolved_ranking == [
        "m2",
        "m1",
        "m3",
    ]


def test_rank_agg_tracks_average_rank_and_rankings_count():
    agg = RankAgg(model="m1", average_rank=1.5, rankings_count=2)
    assert agg.rankings_count == 2


def test_agreement_signals_carries_low_information_flag_and_nullable_w():
    signals = AgreementSignals(kendalls_w=None, eu=0.1, has_disagreement=False, low_information=True)
    restored = AgreementSignals.model_validate(signals.model_dump())
    assert restored.low_information is True
    assert restored.kendalls_w is None


def test_council_output_bundles_members_signals_and_chairman():
    out = CouncilOutput(
        members={
            "m1": MemberVerdict(
                verdict=Verdict.SUPPORTED,
                supporting_ids=["W1"],
                contradicting_ids=[],
                rationale="r",
            )
        },
        signals=AgreementSignals(kendalls_w=0.8, eu=0.1, has_disagreement=False, low_information=False),
        chairman=ChairmanVerdict(
            verdict=Verdict.SUPPORTED, supporting_ids=["W1"], contradicting_ids=[], synthesis="s", dissent=None
        ),
        confidence=Confidence(score=0.8, band=ConfidenceBand.HIGH, basis="b"),
    )
    assert out.chairman.verdict is Verdict.SUPPORTED
    assert out.confidence.band is ConfidenceBand.HIGH


def test_claim_result_requires_confidence_on_both_paths():
    confidence = Confidence(score=0.8, band="high", basis="balance")
    base = {
        "claim": "c",
        "refined_claim": None,
        "verdict": Verdict.SUPPORTED,
        "supporting": [],
        "contradicting": [],
        "synthesis": "s",
        "dissent": None,
        "citations": [WorkRef(openalex_id="W1", doi=None)],
    }
    # Confidence present is valid on either path.
    ClaimResult(**base, confidence=confidence, path=Path.CHEAP)
    ClaimResult(**base, confidence=confidence, path=Path.COUNCIL)
    # Omitting confidence is rejected (it is required, not optional).
    with pytest.raises(ValidationError):
        ClaimResult(**base, path=Path.CHEAP)


def test_triage_and_draft_verdict_round_trip():
    triage = TriageResult(checkable=False, refined_claim=None, reason="too vague")
    draft = DraftVerdict(verdict=Verdict.INSUFFICIENT, rationale="r", self_uncertainty=0.7)
    assert triage.checkable is False
    assert draft.self_uncertainty == 0.7
