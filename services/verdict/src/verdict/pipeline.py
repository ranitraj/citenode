"""End-to-end claim verification pipeline."""

from dataclasses import dataclass

from verdict.adapters.openrouter import OpenRouterModelProvider
from verdict.cascade import cheap_confidence, cheap_verdict, should_escalate
from verdict.council.aggregate import confidence_from_lean
from verdict.council.run import run_council
from verdict.models import (
    ClaimResult,
    CouncilOutput,
    DraftVerdict,
    EvidenceItem,
    EvidenceSet,
    Path,
    Stance,
    TriageResult,
    Verdict,
    WorkRef,
)
from verdict.ports import Embedder, GraphVectorStore, LiteratureSource, ModelProvider, TextEmbedder
from verdict.retrieval import gather_evidence
from verdict.triage import triage_claim


class InternalCorpusLeakError(Exception):
    """Raised when an internal corpus is wired against a public OpenRouter provider."""


@dataclass
class CitenodeDeps:
    """Per-run dependencies injected into the pipeline; nothing is persisted."""

    store: GraphVectorStore
    embedder: Embedder
    text_embedder: TextEmbedder
    source: LiteratureSource
    provider: ModelProvider
    k: int
    escalation_threshold: float
    corpus_is_internal: bool = False


async def verify_claim(claim: str, *, deps: CitenodeDeps) -> ClaimResult:
    """Verify a claim and return a 4-way verdict with calibrated confidence.

    Triages the claim, gathers connected literature, and takes the cheap single-model
    verdict; if the evidence is contested, thin, or weakly leaning, it escalates to the
    council. A non-checkable claim short-circuits to an Insufficient result without
    retrieval. The model provider must match the corpus boundary (ADR 0008).

    Parameters
    ----------
    claim : str
        The empirical claim to verify.
    deps : CitenodeDeps
        The per-run dependencies (store, embedders, source, model provider).

    Returns
    -------
    ClaimResult
        The verdict, confidence, evidence, and provenance for the claim.

    Raises
    ------
    InternalCorpusLeakError
        If an internal corpus is paired with an OpenRouter provider.
    """
    _guard_internal_corpus(deps)
    triage = await triage_claim(claim, model=deps.provider.cheap_model())
    if not triage.checkable:
        return _unverifiable_result(claim, triage)
    evidence = await gather_evidence(
        claim, store=deps.store, embedder=deps.embedder, model=deps.provider.cheap_model(), k=deps.k
    )
    draft = await cheap_verdict(claim, evidence, model=deps.provider.cheap_model())
    if not should_escalate(evidence, draft, escalation_threshold=deps.escalation_threshold):
        return _cheap_result(claim, triage, evidence, draft)
    council = await run_council(claim, evidence, provider=deps.provider, embedder=deps.text_embedder)
    return _council_result(claim, triage, evidence, council)


def _guard_internal_corpus(deps: CitenodeDeps) -> None:
    """Reject an internal corpus paired with an OpenRouter provider before any LLM call.

    Parameters
    ----------
    deps : CitenodeDeps
        The per-run dependencies whose corpus flag and provider are checked.

    Raises
    ------
    InternalCorpusLeakError
        If the corpus is internal and the provider is an OpenRouter provider.
    """
    # ADR 0008: internal document/code text must never reach the third-party OpenRouter router.
    if deps.corpus_is_internal and isinstance(deps.provider, OpenRouterModelProvider):
        raise InternalCorpusLeakError(
            "an internal corpus must not be wired to an OpenRouter provider; use the enterprise model provider."
        )


def _unverifiable_result(claim: str, triage: TriageResult) -> ClaimResult:
    """Build the result for a non-checkable claim, with no evidence gathered.

    Parameters
    ----------
    claim : str
        The claim that triage judged not checkable.
    triage : TriageResult
        The triage outcome carrying the refinement and reason.

    Returns
    -------
    ClaimResult
        An Insufficient result on the cheap path with no citations.
    """
    return ClaimResult(
        claim=claim,
        refined_claim=triage.refined_claim,
        verdict=Verdict.INSUFFICIENT,
        confidence=confidence_from_lean(0.0, cap_reason=None),
        supporting=[],
        contradicting=[],
        synthesis=triage.reason,
        dissent=None,
        path=Path.CHEAP,
        citations=[],
    )


def _cheap_result(claim: str, triage: TriageResult, evidence: EvidenceSet, draft: DraftVerdict) -> ClaimResult:
    """Build the result for a claim resolved by the cheap pass.

    Parameters
    ----------
    claim : str
        The verified claim.
    triage : TriageResult
        The triage outcome carrying the refinement.
    evidence : EvidenceSet
        The gathered evidence, partitioned into the shown citations.
    draft : DraftVerdict
        The cheap pass's verdict.

    Returns
    -------
    ClaimResult
        The cheap-path result with confidence from the evidence balance.
    """
    supporting, contradicting = _partition_evidence(evidence)
    return ClaimResult(
        claim=claim,
        refined_claim=triage.refined_claim,
        verdict=draft.verdict,
        confidence=cheap_confidence(draft, evidence.balance),
        supporting=supporting,
        contradicting=contradicting,
        synthesis=draft.rationale,
        dissent=None,
        path=Path.CHEAP,
        citations=_citations(supporting, contradicting),
    )


def _council_result(claim: str, triage: TriageResult, evidence: EvidenceSet, council: CouncilOutput) -> ClaimResult:
    """Build the result for a claim escalated to and resolved by the council.

    Parameters
    ----------
    claim : str
        The verified claim.
    triage : TriageResult
        The triage outcome carrying the refinement.
    evidence : EvidenceSet
        The gathered evidence the chairman's citations are drawn from.
    council : CouncilOutput
        The council's chairman synthesis, signals, and confidence.

    Returns
    -------
    ClaimResult
        The council-path result with the chairman's verdict, dissent, and confidence.
    """
    chairman = council.chairman
    supporting = _items_for_ids(evidence, chairman.supporting_ids)
    contradicting = _items_for_ids(evidence, chairman.contradicting_ids)
    return ClaimResult(
        claim=claim,
        refined_claim=triage.refined_claim,
        verdict=chairman.verdict,
        confidence=council.confidence,
        supporting=supporting,
        contradicting=contradicting,
        synthesis=chairman.synthesis,
        dissent=chairman.dissent,
        path=Path.COUNCIL,
        citations=_citations(supporting, contradicting),
    )


def _partition_evidence(evidence: EvidenceSet) -> tuple[list[EvidenceItem], list[EvidenceItem]]:
    """Split the evidence items into supporting and contradicting by derived stance.

    Parameters
    ----------
    evidence : EvidenceSet
        The gathered evidence.

    Returns
    -------
    tuple[list[EvidenceItem], list[EvidenceItem]]
        The supporting items and the contradicting items; neutral and off-topic are dropped.
    """
    supporting = [item for item in evidence.items if item.stance is Stance.SUPPORTS]
    contradicting = [item for item in evidence.items if item.stance is Stance.CONTRADICTS]
    return supporting, contradicting


def _items_for_ids(evidence: EvidenceSet, paper_ids: list[str]) -> list[EvidenceItem]:
    """Select the evidence items named by a chairman's grounded citation ids.

    Parameters
    ----------
    evidence : EvidenceSet
        The gathered evidence.
    paper_ids : list[str]
        The grounded citation ids, in the chairman's order.

    Returns
    -------
    list[EvidenceItem]
        The evidence items for those ids, in id order.
    """
    by_id = {item.paper.openalex_id: item for item in evidence.items}
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]


def _citations(supporting: list[EvidenceItem], contradicting: list[EvidenceItem]) -> list[WorkRef]:
    """Build de-duplicated work references from the cited evidence items.

    Parameters
    ----------
    supporting : list[EvidenceItem]
        The supporting evidence items.
    contradicting : list[EvidenceItem]
        The contradicting evidence items.

    Returns
    -------
    list[WorkRef]
        One reference per cited paper, de-duplicated by id and kept in first-seen order.
    """
    seen: set[str] = set()
    citations: list[WorkRef] = []
    for item in [*supporting, *contradicting]:
        paper_id = item.paper.openalex_id
        if paper_id not in seen:
            seen.add(paper_id)
            citations.append(WorkRef(openalex_id=paper_id, doi=item.paper.doi))
    return citations
