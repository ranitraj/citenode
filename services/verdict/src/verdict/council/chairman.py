"""Chairman synthesis of the member drafts into one final verdict."""

from pydantic_ai import Agent

from verdict.council.members import ground_citations
from verdict.models import AgreementSignals, ChairmanVerdict, EvidenceSet, MemberVerdict
from verdict.ports import ModelProvider
from verdict.prompting import render_prompt


async def synthesise_verdict(
    claim: str,
    evidence: EvidenceSet,
    drafts: dict[str, MemberVerdict],
    signals: AgreementSignals,
    *,
    provider: ModelProvider,
) -> ChairmanVerdict:
    """Reconcile the member drafts into one grounded chairman verdict.

    The chairman reads the evidence, the member drafts, and the advisory agreement
    signals, then emits a single verdict with a synthesis and the strongest dissent.
    Its citations pass the same grounding guard as the members': ungrounded or
    stance-mismatched ids are dropped before the verdict is returned.

    Parameters
    ----------
    claim : str
        The claim under verification.
    evidence : EvidenceSet
        The shared evidence the council reasoned over.
    drafts : dict[str, MemberVerdict]
        The grounded member verdicts to reconcile, keyed by model name.
    signals : AgreementSignals
        The advisory inter-member agreement signals.
    provider : ModelProvider
        The provider whose chairman model performs the synthesis.

    Returns
    -------
    ChairmanVerdict
        The reconciled, grounded verdict with its synthesis and dissent.
    """
    agent = Agent(
        model=provider.chairman_model(),
        output_type=ChairmanVerdict,
        system_prompt=render_prompt("chairman_system.j2"),
    )
    prompt = render_prompt(
        "chairman_user.j2", claim=claim, evidence=evidence, drafts=list(drafts.values()), signals=signals
    )
    raw = (await agent.run(prompt)).output
    supporting, contradicting, _flipped = ground_citations(raw.supporting_ids, raw.contradicting_ids, evidence)
    return raw.model_copy(update={"supporting_ids": supporting, "contradicting_ids": contradicting})
