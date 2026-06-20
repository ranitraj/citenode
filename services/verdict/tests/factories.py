"""Shared object factories for tests."""

from verdict.models import Paper


def make_paper(openalex_id: str, *, cited_by: int = 10, year: int = 2020) -> Paper:
    """Build a Paper with sensible test defaults."""
    return Paper(
        openalex_id=openalex_id,
        doi=None,
        title=openalex_id,
        year=year,
        abstract="a",
        cited_by=cited_by,
        is_retracted=False,
        venue=None,
    )
