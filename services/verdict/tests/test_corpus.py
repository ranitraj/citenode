"""Tests for seed-and-expand corpus ingestion into the store."""

from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.ingest.corpus import ingest_corpus
from verdict.models import EdgeKind, Work, WorkRef

from tests.model_stubs import StubEmbedder


def _work(work_id: str, *, refs: list[str] | None = None) -> Work:
    return Work(
        openalex_id=work_id,
        doi=None,
        title=f"title {work_id}",
        year=2020,
        abstract=f"abstract {work_id}",
        cited_by=5,
        is_retracted=False,
        venue=None,
        topics=[],
        referenced_works=refs or [],
    )


def _ref(work_id: str) -> WorkRef:
    return WorkRef(openalex_id=work_id, doi=None)


class _Source:
    def __init__(self, *, seeds, works, refs, cites):
        self._seeds = seeds
        self._works = works
        self._refs = refs
        self._cites = cites

    async def search_seeds(self, _query: str, limit: int) -> list[WorkRef]:
        """Return the stub seed references."""
        return self._seeds[:limit]

    async def fetch_work(self, work_id: str) -> Work:
        """Return the stub work for an id."""
        return self._works[work_id]

    async def outgoing_refs(self, work_id: str) -> list[WorkRef]:
        """Return the stub outgoing references for a work."""
        return self._refs.get(work_id, [])

    async def incoming_citations(self, work_id: str, limit: int) -> list[WorkRef]:
        """Return the stub incoming citations for a work."""
        return self._cites.get(work_id, [])[:limit]


async def test_ingest_corpus_populates_papers_and_citation_edges():
    source = _Source(
        seeds=[_ref("W1"), _ref("W2")],
        works={"W1": _work("W1", refs=["W3"]), "W2": _work("W2"), "W3": _work("W3"), "W4": _work("W4", refs=["W1"])},
        refs={"W1": [_ref("W3")]},
        cites={"W1": [_ref("W4")]},
    )
    store = InMemoryGraphVectorStore()

    count = await ingest_corpus("a query", source=source, store=store, embedder=StubEmbedder())

    assert count == 4
    papers = await store.recall_papers([1.0, 0.0], 10)
    assert {paper.openalex_id for paper in papers} == {"W1", "W2", "W3", "W4"}
    neighbourhood = await store.evidence_neighbourhood("W1")
    assert any(edge.src == "W1" and edge.dst == "W3" and edge.kind is EdgeKind.CITES for edge in neighbourhood.edges)


async def test_ingest_corpus_adds_an_edge_only_when_both_papers_are_ingested():
    source = _Source(
        seeds=[_ref("W1")],
        works={"W1": _work("W1", refs=["W_absent"])},
        refs={},
        cites={},
    )
    store = InMemoryGraphVectorStore()

    count = await ingest_corpus("a query", source=source, store=store, embedder=StubEmbedder())

    assert count == 1
    neighbourhood = await store.evidence_neighbourhood("W1")
    assert neighbourhood.edges == []
