"""Council member verdicts and the citation grounding guard."""

import asyncio

from pydantic_ai import Agent
from pydantic_ai.models import Model

from verdict.models import EvidenceSet, MemberVerdict, Stance
from verdict.ports import ModelProvider
from verdict.prompting import render_prompt


class QuorumNotReached(Exception):
    """Raised when fewer than the required number of council members succeed."""


async def draft_member_verdicts(
    claim: str, evidence: EvidenceSet, *, provider: ModelProvider
) -> dict[str, MemberVerdict]:
    """Draft grounded member verdicts concurrently, requiring an N-1 quorum.

    Runs each member model on the same evidence in parallel; a member that raises
    or fails validation is dropped, and the survivors pass the grounding guard. At
    least N-1 of N members must succeed, so one failure cannot sink a claim.

    Parameters
    ----------
    claim : str
        The claim under verification.
    evidence : EvidenceSet
        The shared evidence each member reasons over.
    provider : ModelProvider
        The provider whose member models draft the verdicts.

    Returns
    -------
    dict[str, MemberVerdict]
        The grounded verdict per member, keyed by model name.

    Raises
    ------
    QuorumNotReached
        If fewer than N-1 members succeed.
    """
    models = provider.member_models()
    drafts = await asyncio.gather(*(_draft_member(claim, evidence, model) for model in models), return_exceptions=True)
    verdicts = {
        model.model_name: draft
        for model, draft in zip(models, drafts, strict=True)
        if not isinstance(draft, BaseException)
    }
    if len(verdicts) < len(models) - 1:
        raise QuorumNotReached(f"only {len(verdicts)} of {len(models)} council members succeeded")
    return verdicts


def apply_grounding_guard(verdict: MemberVerdict, evidence: EvidenceSet) -> tuple[MemberVerdict, list[str]]:
    """Keep only the member citations grounded in the evidence with a matching stance.

    A citation survives only when its paper is a retrieved ``EvidenceItem`` and the
    list it appears in matches that paper's derived stance. Citations to papers
    outside the evidence are dropped; grounded citations whose stance is flipped are
    dropped from the counts and returned as dissent.

    Parameters
    ----------
    verdict : MemberVerdict
        The member's raw verdict with asserted citation ids.
    evidence : EvidenceSet
        The evidence whose items carry the derived stance per paper.

    Returns
    -------
    tuple[MemberVerdict, list[str]]
        The grounded verdict and the ids of grounded but stance-mismatched citations.
    """
    derived = {item.paper.openalex_id: item.stance for item in evidence.items}
    supporting, supporting_dissent = _partition(verdict.supporting_ids, Stance.SUPPORTS, derived)
    contradicting, contradicting_dissent = _partition(verdict.contradicting_ids, Stance.CONTRADICTS, derived)
    grounded = verdict.model_copy(update={"supporting_ids": supporting, "contradicting_ids": contradicting})
    return grounded, supporting_dissent + contradicting_dissent


async def _draft_member(claim: str, evidence: EvidenceSet, model: Model) -> MemberVerdict:
    """Draft one member's verdict from the evidence and apply the grounding guard.

    Parameters
    ----------
    claim : str
        The claim under verification.
    evidence : EvidenceSet
        The shared evidence.
    model : Model
        The member model that drafts the verdict.

    Returns
    -------
    MemberVerdict
        The member's grounded verdict.
    """
    agent = Agent(model=model, output_type=MemberVerdict, system_prompt=render_prompt("member_system.j2"))
    raw = (await agent.run(render_prompt("member_user.j2", claim=claim, evidence=evidence))).output
    grounded, _dissent = apply_grounding_guard(raw, evidence)
    return grounded


def _partition(cited_ids: list[str], asserted: Stance, derived: dict[str, Stance]) -> tuple[list[str], list[str]]:
    """Split cited ids into stance-matched citations and stance-mismatched dissent.

    Parameters
    ----------
    cited_ids : list[str]
        The paper ids the member cited for one asserted stance.
    asserted : Stance
        The stance implied by the list the ids appear in.
    derived : dict[str, Stance]
        The stance ``gather_evidence`` derived for each retrieved paper.

    Returns
    -------
    tuple[list[str], list[str]]
        The ids whose derived stance matches the assertion, and the grounded ids
        whose derived stance differs; ungrounded ids are dropped from both.
    """
    kept: list[str] = []
    dissent: list[str] = []
    for paper_id in cited_ids:
        actual = derived.get(paper_id)
        if actual is asserted:
            kept.append(paper_id)
        elif actual is not None:
            dissent.append(paper_id)
    return kept, dissent
