"""Cheap verification pass and the evidence-side escalation gate."""

from pydantic_ai import Agent
from pydantic_ai.models import Model

from verdict import config
from verdict.council.aggregate import confidence_from_lean
from verdict.models import CapReason, Confidence, DraftVerdict, EvidenceBalance, EvidenceSet, Verdict
from verdict.prompting import render_prompt


async def cheap_verdict(claim: str, evidence: EvidenceSet, *, model: Model) -> DraftVerdict:
    """Draft a single-model verdict for the claim from the gathered evidence.

    Parameters
    ----------
    claim : str
        The claim under verification.
    evidence : EvidenceSet
        The gathered evidence the verdict must be grounded in.
    model : Model
        The cheap model that reads the evidence and returns a draft verdict.

    Returns
    -------
    DraftVerdict
        The cheap pass's verdict, rationale, and self-reported uncertainty.
    """
    agent = Agent(model=model, output_type=DraftVerdict, system_prompt=render_prompt("cheap_verdict_system.j2"))
    prompt = render_prompt("cheap_verdict_user.j2", claim=claim, evidence=evidence)
    return (await agent.run(prompt)).output


def cheap_confidence(draft: DraftVerdict, balance: EvidenceBalance) -> Confidence:
    """Score cheap-pass confidence from the balance, capped by self-uncertainty.

    The band base comes from the evidence balance; the draft's self-reported
    uncertainty may only lower it, never raise it, since a model's own
    confidence is poorly calibrated upward.

    Parameters
    ----------
    draft : DraftVerdict
        The cheap pass's verdict, whose self-uncertainty may cap the band.
    balance : EvidenceBalance
        The evidence balance whose weighted lean sets the base band.

    Returns
    -------
    Confidence
        The score, discrete band, and a short basis string.
    """
    cap_reason = CapReason.HIGH_UNCERTAINTY if draft.self_uncertainty >= config.SELF_UNCERTAINTY_CAP_FLOOR else None
    return confidence_from_lean(balance.weighted_lean, cap_reason=cap_reason)


def should_escalate(evidence: EvidenceSet, draft: DraftVerdict, *, escalation_threshold: float) -> bool:
    """Decide whether a claim needs the council, from the evidence alone.

    The gate is evidence-side: it escalates when both stances are present, when
    the weighted lean is weaker than the threshold, when no on-topic evidence
    was found, or when the balance contradicts the cheap draft's verdict. The
    draft's self-reported uncertainty is advisory and never consulted here, so
    an over-confident cheap verdict cannot suppress escalation.

    Parameters
    ----------
    evidence : EvidenceSet
        The gathered evidence and its aggregate balance.
    draft : DraftVerdict
        The cheap pass's verdict.
    escalation_threshold : float
        The minimum absolute weighted lean below which the claim escalates.

    Returns
    -------
    bool
        True when the claim should escalate to the council.
    """
    balance = evidence.balance
    both_stances = balance.supports > 0 and balance.contradicts > 0
    weak_lean = abs(balance.weighted_lean) < escalation_threshold
    thin_coverage = balance.supports + balance.contradicts + balance.neutral == 0
    return (
        both_stances
        or weak_lean
        or thin_coverage
        or _balance_contradicts_verdict(draft.verdict, balance.weighted_lean)
    )


def _balance_contradicts_verdict(verdict: Verdict, weighted_lean: float) -> bool:
    """Return True when the evidence lean runs against the draft verdict.

    Parameters
    ----------
    verdict : Verdict
        The cheap draft's verdict.
    weighted_lean : float
        The signed evidence lean in [-1, 1].

    Returns
    -------
    bool
        True when a Supported verdict has a negative lean or a Refuted verdict
        has a positive lean; False otherwise.
    """
    if verdict is Verdict.SUPPORTED:
        return weighted_lean < 0
    if verdict is Verdict.REFUTED:
        return weighted_lean > 0
    return False
