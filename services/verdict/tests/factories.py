"""Shared object factories for tests."""

from verdict.models import EvidenceBalance, Paper


def make_paper(openalex_id: str, *, cited_by: int = 10, year: int = 2020, is_retracted: bool = False) -> Paper:
    """Build a Paper with sensible test defaults."""
    return Paper(
        openalex_id=openalex_id,
        doi=None,
        title=openalex_id,
        year=year,
        abstract="a",
        cited_by=cited_by,
        is_retracted=is_retracted,
        venue=None,
    )


def make_balance(
    lean: float, *, supports: int = 1, contradicts: int = 0, neutral: int = 0, off_topic: int = 0
) -> EvidenceBalance:
    """Build an EvidenceBalance with the given lean and sensible count defaults."""
    return EvidenceBalance(
        supports=supports, contradicts=contradicts, neutral=neutral, off_topic=off_topic, weighted_lean=lean
    )
