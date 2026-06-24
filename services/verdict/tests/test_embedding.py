"""Tests for the shared paper embedding-text representation."""

from verdict.embedding import paper_embedding_text
from verdict.models import Paper


def _paper(title: str, abstract: str) -> Paper:
    return Paper(
        openalex_id="W1",
        doi=None,
        title=title,
        year=2020,
        abstract=abstract,
        cited_by=0,
        is_retracted=False,
        venue=None,
    )


def test_paper_embedding_text_joins_title_and_abstract_with_a_blank_line():
    text = paper_embedding_text(_paper("A Title", "An abstract."))

    assert text == "A Title\n\nAn abstract."
