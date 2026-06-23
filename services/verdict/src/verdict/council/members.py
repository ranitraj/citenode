"""Council member verdicts and the citation grounding guard."""

from verdict.models import EvidenceSet, MemberVerdict, Stance


def ground_member_verdict(verdict: MemberVerdict, evidence: EvidenceSet) -> tuple[MemberVerdict, list[str]]:
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
