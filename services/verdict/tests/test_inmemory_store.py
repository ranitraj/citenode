"""Tests for the in-memory graph+vector store used by infra-free tests."""

from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.models import Edge

from tests.factories import make_paper


async def test_recall_papers_returns_nearest_by_cosine():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("P1"), [1.0, 0.0, 0.0])
    await store.upsert_paper(make_paper("P2"), [0.0, 1.0, 0.0])
    await store.upsert_paper(make_paper("P3"), [0.9, 0.1, 0.0])
    hits = await store.recall_papers([1.0, 0.0, 0.0], k=2)
    assert [p.openalex_id for p in hits] == ["P1", "P3"]


async def test_recall_papers_caps_results_at_k():
    store = InMemoryGraphVectorStore()
    for i in range(5):
        await store.upsert_paper(make_paper(f"P{i}"), [1.0, i / 10, 0.0])
    hits = await store.recall_papers([1.0, 0.0, 0.0], k=3)
    assert len(hits) == 3


async def test_evidence_neighbourhood_reconstructs_cited_citing_and_topic_edges():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("focal"), [1.0, 0.0])
    await store.upsert_paper(make_paper("cited"), [0.0, 1.0])
    await store.upsert_paper(make_paper("citing"), [1.0, 1.0])
    await store.upsert_edge(Edge(src="focal", dst="cited", kind="cites"))
    await store.upsert_edge(Edge(src="citing", dst="focal", kind="cites"))
    await store.upsert_edge(Edge(src="focal", dst="T1", kind="about"))

    sub = await store.evidence_neighbourhood("focal")
    ids = {p.openalex_id for p in sub.papers}
    assert {"cited", "citing"} <= ids
    assert Edge(src="focal", dst="cited", kind="cites") in sub.edges
    assert Edge(src="citing", dst="focal", kind="cites") in sub.edges
    assert Edge(src="focal", dst="T1", kind="about") in sub.edges


async def test_evidence_neighbourhood_of_unknown_paper_is_empty():
    store = InMemoryGraphVectorStore()
    sub = await store.evidence_neighbourhood("missing")
    assert sub.papers == []
    assert sub.edges == []


async def test_foundations_for_query_respects_min_cited():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("high", cited_by=100), [1.0, 0.0])
    await store.upsert_paper(make_paper("low", cited_by=5), [1.0, 0.0])
    sub = await store.foundations_for_query([1.0, 0.0], k=5, min_cited=50)
    ids = {p.openalex_id for p in sub.papers}
    assert "high" in ids
    assert "low" not in ids


async def test_empty_store_recall_returns_no_results():
    store = InMemoryGraphVectorStore()
    assert await store.recall_papers([1.0, 0.0, 0.0], k=5) == []
