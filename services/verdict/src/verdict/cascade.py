"""Cheap verification pass and the evidence-side escalation gate."""

from verdict.models import DraftVerdict, EvidenceSet, Verdict


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
