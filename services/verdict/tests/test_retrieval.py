"""Tests for evidence retrieval: candidate gathering over the graph store."""

from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.models import Edge
from verdict.retrieval import gather_candidates

from tests.factories import make_paper


async def test_gather_candidates_unions_recall_foundations_and_neighbours():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("recall", cited_by=0), [1.0, 0.0])
    await store.upsert_paper(make_paper("neighbour", cited_by=0), [0.0, 1.0])
    await store.upsert_paper(make_paper("foundation", cited_by=100), [0.9, 0.1])
    await store.upsert_edge(Edge(src="recall", dst="neighbour", kind="cites"))

    candidates = await gather_candidates([1.0, 0.0], store=store, k=1, min_cited=50)

    ids = {p.openalex_id for p in candidates}
    assert {"recall", "neighbour", "foundation"} <= ids


async def test_gather_candidates_dedups_papers_seen_in_multiple_sources():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("both", cited_by=100), [1.0, 0.0])

    candidates = await gather_candidates([1.0, 0.0], store=store, k=5, min_cited=50)

    assert [p.openalex_id for p in candidates] == ["both"]


async def test_gather_candidates_drops_retracted_papers():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("ok", cited_by=0), [1.0, 0.0])
    await store.upsert_paper(make_paper("bad", cited_by=0, is_retracted=True), [0.99, 0.01])

    candidates = await gather_candidates([1.0, 0.0], store=store, k=5, min_cited=50)

    ids = {p.openalex_id for p in candidates}
    assert "ok" in ids
    assert "bad" not in ids
