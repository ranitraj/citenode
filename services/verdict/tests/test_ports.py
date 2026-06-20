"""Tests that the swap-boundary ports define the expected contracts."""

from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.ports import Embedder, GraphVectorStore, TextEmbedder


class _ProseOnly:
    async def embed(self, text: str) -> list[float]:
        """Return a trivial embedding of the text."""
        return [float(len(text))]


def test_inmemory_store_satisfies_the_graph_vector_store_port():
    assert isinstance(InMemoryGraphVectorStore(), GraphVectorStore)


def test_text_embedder_is_narrower_than_the_paper_embedder():
    prose = _ProseOnly()
    assert isinstance(prose, TextEmbedder)
    assert not isinstance(prose, Embedder)
