"""Full council orchestration: members, peer ranking, signals, chairman, confidence."""

import asyncio
from collections import Counter

from verdict.council.aggregate import compute_confidence, epistemic_uncertainty, has_disagreement, kendalls_w
from verdict.council.chairman import synthesise_verdict
from verdict.council.members import draft_member_verdicts, ground_citations
from verdict.council.rank import peer_rank
from verdict.models import AgreementSignals, ChairmanVerdict, CouncilOutput, EvidenceSet, MemberVerdict, RankingOutput
from verdict.ports import ModelProvider, TextEmbedder

_DRAFT_EMBED_CHARS = 2000  # ADR 0016: cap each member draft before embedding for epistemic uncertainty.


async def run_council(
    claim: str, evidence: EvidenceSet, *, provider: ModelProvider, embedder: TextEmbedder
) -> CouncilOutput:
    """Run the full council: draft, peer-rank, synthesize, and score confidence.

    Members draft verdicts concurrently (an N-1 quorum tolerates one failure), peer-rank
    each other's anonymized drafts, and the rankings plus draft embeddings yield the
    agreement signals. The chairman synthesizes a final verdict from the drafts and those
    advisory signals; if the chairman fails, the council falls back to the member majority.
    Confidence comes from the evidence balance, capped by council disagreement.

    Parameters
    ----------
    claim : str
        The claim under verification.
    evidence : EvidenceSet
        The shared evidence the council reasons over.
    provider : ModelProvider
        The provider supplying the member and chairman models.
    embedder : TextEmbedder
        The prose embedder used for member-draft epistemic uncertainty.

    Returns
    -------
    CouncilOutput
        The members, agreement signals, chairman synthesis, and confidence.

    Raises
    ------
    QuorumNotReached
        If fewer than N-1 members succeed.
    """
    drafts = await draft_member_verdicts(claim, evidence, provider=provider)
    rankings = await peer_rank(claim, drafts, provider=provider)
    signals = await _agreement_signals(rankings, drafts, embedder)
    chairman = await _synthesise_or_fallback(claim, evidence, drafts, signals, provider=provider)
    confidence = compute_confidence(signals, evidence.balance)
    return CouncilOutput(members=drafts, signals=signals, chairman=chairman, confidence=confidence)


async def _agreement_signals(
    rankings: dict[str, RankingOutput], drafts: dict[str, MemberVerdict], embedder: TextEmbedder
) -> AgreementSignals:
    """Assemble the agreement signals from the peer rankings and draft embeddings.

    Parameters
    ----------
    rankings : dict[str, RankingOutput]
        The de-anonymized ranking per ranker.
    drafts : dict[str, MemberVerdict]
        The member verdicts whose rationales are embedded for epistemic uncertainty.
    embedder : TextEmbedder
        The prose embedder for the member drafts.

    Returns
    -------
    AgreementSignals
        Kendall's W and its low-information flag, epistemic uncertainty, and disagreement.
    """
    ranking_lists = [ranking.resolved_ranking for ranking in rankings.values()]
    weight, low_information = kendalls_w(ranking_lists)
    embeddings = await asyncio.gather(
        *(embedder.embed(draft.rationale[:_DRAFT_EMBED_CHARS]) for draft in drafts.values())
    )
    return AgreementSignals(
        kendalls_w=weight,
        eu=epistemic_uncertainty(list(embeddings)),
        has_disagreement=has_disagreement(ranking_lists),
        low_information=low_information,
    )


async def _synthesise_or_fallback(
    claim: str,
    evidence: EvidenceSet,
    drafts: dict[str, MemberVerdict],
    signals: AgreementSignals,
    *,
    provider: ModelProvider,
) -> ChairmanVerdict:
    """Synthesize the chairman verdict, falling back to the member majority on failure.

    Parameters
    ----------
    claim : str
        The claim under verification.
    evidence : EvidenceSet
        The shared evidence.
    drafts : dict[str, MemberVerdict]
        The member verdicts to reconcile.
    signals : AgreementSignals
        The advisory agreement signals.
    provider : ModelProvider
        The provider supplying the chairman model.

    Returns
    -------
    ChairmanVerdict
        The chairman's synthesis, or the member-majority fallback.
    """
    try:
        return await synthesise_verdict(claim, evidence, drafts, signals, provider=provider)
    except Exception:  # pylint: disable=broad-exception-caught
        return _member_majority(drafts, evidence)


def _member_majority(drafts: dict[str, MemberVerdict], evidence: EvidenceSet) -> ChairmanVerdict:
    """Build a fallback chairman verdict from the member majority and their citations.

    Parameters
    ----------
    drafts : dict[str, MemberVerdict]
        The grounded member verdicts.
    evidence : EvidenceSet
        The shared evidence, used to re-ground the pooled citations.

    Returns
    -------
    ChairmanVerdict
        The majority verdict over grounded, pooled citations, with no dissent.
    """
    verdict = Counter(draft.verdict for draft in drafts.values()).most_common(1)[0][0]
    supporting = sorted({paper_id for draft in drafts.values() for paper_id in draft.supporting_ids})
    contradicting = sorted({paper_id for draft in drafts.values() for paper_id in draft.contradicting_ids})
    grounded_supporting, grounded_contradicting, _flipped = ground_citations(supporting, contradicting, evidence)
    return ChairmanVerdict(
        verdict=verdict,
        supporting_ids=grounded_supporting,
        contradicting_ids=grounded_contradicting,
        synthesis="Chairman synthesis unavailable; reporting the member majority.",
        dissent=None,
    )
