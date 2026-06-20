"""End-to-end claim verification pipeline."""

from dataclasses import dataclass

from pydantic_ai import Agent
from pydantic_ai.models import Model

from verdict.council.aggregate import compute_confidence
from verdict.models import (
    AgreementSignals,
    ClaimResult,
    DraftVerdict,
    EvidenceBalance,
    EvidenceSet,
    Path,
    TriageResult,
)
from verdict.ports import (
    Embedder,
    GraphVectorStore,
    LiteratureSource,
    ModelProvider,
    TextEmbedder,
)


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

    This is the walking-skeleton wiring: the stage helpers are throwaway
    pass-throughs that the real triage, retrieval, cascade, and council stages
    replace later. It proves a well-formed ``ClaimResult`` threads end-to-end.

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
    """
    triage = _stub_triage()
    evidence = await _stub_gather(deps)
    draft = await _stub_cheap_verdict(claim, deps.provider.cheap_model())
    confidence = compute_confidence(_no_council_signals(), evidence.balance)
    return ClaimResult(
        claim=claim,
        refined_claim=triage.refined_claim,
        verdict=draft.verdict,
        confidence=confidence,
        supporting=[],
        contradicting=[],
        synthesis=draft.rationale,
        dissent=None,
        path=Path.CHEAP,
        citations=[],
    )


def _stub_triage() -> TriageResult:
    """Pass-through triage that treats every claim as checkable.

    Returns
    -------
    TriageResult
        A checkable result with no refinement.
    """
    return TriageResult(checkable=True, refined_claim=None, reason="walking skeleton stub")


async def _stub_gather(deps: CitenodeDeps) -> EvidenceSet:
    """Exercise the store seam and return a canned, lopsided evidence set.

    Parameters
    ----------
    deps : CitenodeDeps
        The per-run dependencies, whose store is queried.

    Returns
    -------
    EvidenceSet
        A stub evidence set with a one-sided balance.
    """
    await deps.store.recall_papers([1.0, 0.0], deps.k)
    balance = EvidenceBalance(supports=1, contradicts=0, neutral=0, off_topic=0, weighted_lean=1.0)
    return EvidenceSet(items=[], balance=balance, coverage_note="walking skeleton stub")


async def _stub_cheap_verdict(claim: str, model: Model) -> DraftVerdict:
    """Draft a cheap verdict through the model seam.

    Parameters
    ----------
    claim : str
        The claim to draft a verdict for.
    model : Model
        The model to run (a TestModel in tests).

    Returns
    -------
    DraftVerdict
        The drafted verdict.
    """
    agent = Agent(model=model, output_type=DraftVerdict)
    result = await agent.run(claim)
    return result.output


def _no_council_signals() -> AgreementSignals:
    """Return placeholder agreement signals for the cheap path.

    Returns
    -------
    AgreementSignals
        Signals indicating no council ran.
    """
    return AgreementSignals(kendalls_w=None, eu=None, has_disagreement=False, low_information=True)
