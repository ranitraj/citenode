"""Canonical text representation of a paper for embedding."""

from verdict.models import Paper


def paper_embedding_text(paper: Paper) -> str:
    """Return the title-and-abstract text used to embed a paper.

    Shared by corpus ingestion and the gold-evidence loader so every paper lands in
    the same embedding space regardless of where it entered the system.

    Parameters
    ----------
    paper : Paper
        The paper to represent.

    Returns
    -------
    str
        The paper's title and abstract joined for the embedder.
    """
    return f"{paper.title}\n\n{paper.abstract}"
