"""Typed domain models for the claim-verification pipeline."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Reusable type-level invariants (each used across several models, declared once).
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegInt = Annotated[int, Field(ge=0)]


class Stance(StrEnum):
    """A paper's stance toward the claim, derived by an LLM reading its abstract."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"
    OFF_TOPIC = "off_topic"


class Verdict(StrEnum):
    """The 4-way claim verdict returned to the caller."""

    SUPPORTED = "supported"
    CONTESTED = "contested"
    REFUTED = "refuted"
    INSUFFICIENT = "insufficient"


class Path(StrEnum):
    """Which branch of the cascade produced the result."""

    CHEAP = "cheap"
    COUNCIL = "council"


class EdgeKind(StrEnum):
    """The directed relation an edge encodes between two graph nodes."""

    CITES = "cites"
    ABOUT = "about"


class ConfidenceBand(StrEnum):
    """The discrete confidence band, ordered from least to most confident."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class CapReason(StrEnum):
    """Why a confidence band was capped one step lower than the evidence base."""

    COUNCIL_DISAGREEMENT = "council_disagreement"
    LOW_CONCORDANCE = "low_concordance"
    HIGH_UNCERTAINTY = "high_self_reported_uncertainty"


class _Model(BaseModel):
    """Frozen base with strict field validation for every domain value object."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class WorkRef(_Model):
    """A lightweight reference to a source work."""

    openalex_id: str
    doi: str | None


class Work(_Model):
    """A raw work fetched from the literature source, before graph ingestion."""

    openalex_id: str
    doi: str | None
    title: str
    year: int
    abstract: str
    cited_by: NonNegInt
    is_retracted: bool
    venue: str | None
    topics: list[str]
    referenced_works: list[str]


class Paper(_Model):
    """A paper node stored in and read back from the graph store."""

    openalex_id: str
    doi: str | None
    title: str
    year: int
    abstract: str
    cited_by: NonNegInt
    is_retracted: bool
    venue: str | None


class Edge(_Model):
    """A directed relation between two graph nodes."""

    src: str
    dst: str
    kind: EdgeKind


class Subgraph(_Model):
    """A bundle of papers and the edges reconstructed from a graph traversal."""

    papers: list[Paper]
    edges: list[Edge]


class StanceJudgement(_Model):
    """An LLM's stance reading of one paper's abstract against the claim."""

    stance: Stance = Field(description="The paper's 4-way stance toward the claim.")
    snippet: str = Field(description="A short quote from the abstract grounding the stance.")
    rationale: str = Field(description="Why the abstract takes this stance toward the claim.")


class EvidenceItem(_Model):
    """One paper's LLM-derived stance toward the claim."""

    paper: Paper
    stance: Stance
    snippet: str
    rationale: str


class EvidenceBalance(_Model):
    """Aggregate stance counts plus the signed, weighted lean of the evidence."""

    supports: NonNegInt
    contradicts: NonNegInt
    neutral: NonNegInt
    off_topic: NonNegInt
    weighted_lean: Annotated[float, Field(ge=-1.0, le=1.0)]


class EvidenceSet(_Model):
    """The full evidence gathered for a claim, with a coverage note."""

    items: list[EvidenceItem]
    balance: EvidenceBalance
    coverage_note: str


class TriageResult(_Model):
    """The triage gate's decision on whether a claim is checkable."""

    checkable: bool = Field(description="True only if the claim is an empirical, evidence-checkable statement.")
    refined_claim: str | None = Field(
        description="A sharper, checkable rewrite of the claim, or null if none is needed."
    )
    reason: str = Field(description="Why the claim is or is not checkable.")


class DraftVerdict(_Model):
    """The cheap pass's single-model verdict and self-reported uncertainty."""

    verdict: Verdict = Field(description="The 4-way verdict from the cheap pass.")
    rationale: str = Field(description="Short justification grounded in the evidence.")
    self_uncertainty: UnitInterval = Field(
        description="The model's own uncertainty in [0,1]; advisory, may only lower confidence."
    )


class MemberVerdict(_Model):
    """One council member's verdict with its grounded citation ids."""

    verdict: Verdict = Field(description="This member's 4-way verdict.")
    supporting_ids: list[str] = Field(description="OpenAlex ids of retrieved papers that support the claim.")
    contradicting_ids: list[str] = Field(description="OpenAlex ids of retrieved papers that contradict the claim.")
    rationale: str = Field(description="Justification citing only retrieved papers.")


class RankingOutput(_Model):
    """A ranker's de-anonymized member ordering, best to worst."""

    resolved_ranking: list[str]


class RankAgg(_Model):
    """A member's aggregate position across all rankers."""

    model: str
    average_rank: float
    rankings_count: NonNegInt


class AgreementSignals(_Model):
    """Inter-member agreement signals feeding the confidence cap."""

    kendalls_w: UnitInterval | None
    eu: UnitInterval | None
    has_disagreement: bool
    low_information: bool


class Confidence(_Model):
    """A calibrated confidence score with its discrete band and basis."""

    score: UnitInterval
    band: ConfidenceBand
    basis: str


class ChairmanVerdict(_Model):
    """The chairman's reconciled verdict, grounded citations, synthesis, and dissent."""

    verdict: Verdict = Field(description="The single verdict reconciled from the member drafts.")
    supporting_ids: list[str] = Field(description="Grounded ids of retrieved papers that support the claim.")
    contradicting_ids: list[str] = Field(description="Grounded ids of retrieved papers that contradict the claim.")
    synthesis: str = Field(description="Prose synthesis of the verdict; required, never null.")
    dissent: str | None = Field(description="The strongest minority report, or null when members agreed.")


class CouncilOutput(_Model):
    """The council stage's full result: members, agreement signals, chairman synthesis, and confidence."""

    members: dict[str, MemberVerdict]
    signals: AgreementSignals
    chairman: ChairmanVerdict
    confidence: Confidence


class ClaimResult(_Model):
    """The final result returned for a verified claim, on either path."""

    claim: str
    refined_claim: str | None
    verdict: Verdict
    confidence: Confidence
    supporting: list[EvidenceItem]
    contradicting: list[EvidenceItem]
    synthesis: str
    dissent: str | None
    path: Path
    citations: list[WorkRef]
