"""Conformance suite: behaviours every GraphVectorStore adapter must agree on.

Asserts exact-agreement behaviours only (node presence/absence, reconstructed
edges, retraction carry-through), not ranking equivalence, since HelixDB recall
is approximate.
"""

from collections.abc import Awaitable, Callable

import pytest
from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.models import Edge
from verdict.ports import GraphVectorStore

from tests.factories import make_paper
from tests.helix_support import fresh_helix_store, helix_instance_up

StoreFactory = Callable[[], Awaitable[GraphVectorStore]]


async def _new_inmemory() -> GraphVectorStore:
    """Return a fresh in-memory store."""
    return InMemoryGraphVectorStore()


async def _new_helix() -> GraphVectorStore:
    """Return a fresh HelixDB store, skipping when no instance is running."""
    if not helix_instance_up():
        pytest.skip("HelixDB instance not running")
    return await fresh_helix_store()


pytestmark = pytest.mark.parametrize("make_store", [_new_inmemory, _new_helix])


async def test_empty_store_recalls_nothing(make_store: StoreFactory):
    store = await make_store()

    assert await store.recall_papers([1.0, 0.0, 0.0], 5) == []


async def test_recall_returns_an_upserted_paper(make_store: StoreFactory):
    store = await make_store()
    paper = make_paper("W1")
    await store.upsert_paper(paper, [1.0, 0.0, 0.0])

    assert await store.recall_papers([1.0, 0.0, 0.0], 1) == [paper]


async def test_retraction_carries_through(make_store: StoreFactory):
    store = await make_store()
    await store.upsert_paper(make_paper("W1", is_retracted=True), [1.0, 0.0, 0.0])

    (paper,) = await store.recall_papers([1.0, 0.0, 0.0], 1)

    assert paper.is_retracted is True


async def test_evidence_neighbourhood_reconstructs_cited_and_citing(make_store: StoreFactory):
    store = await make_store()
    await store.upsert_paper(make_paper("W_a"), [1.0, 0.0, 0.0])
    await store.upsert_paper(make_paper("W_b"), [0.0, 1.0, 0.0])
    await store.upsert_paper(make_paper("W_c"), [0.0, 0.0, 1.0])
    await store.upsert_edge(Edge(src="W_a", dst="W_b", kind="cites"))
    await store.upsert_edge(Edge(src="W_c", dst="W_a", kind="cites"))

    sub = await store.evidence_neighbourhood("W_a")

    assert {p.openalex_id for p in sub.papers} == {"W_b", "W_c"}
    assert Edge(src="W_a", dst="W_b", kind="cites") in sub.edges
    assert Edge(src="W_c", dst="W_a", kind="cites") in sub.edges


async def test_evidence_neighbourhood_of_unknown_paper_is_empty(make_store: StoreFactory):
    store = await make_store()

    sub = await store.evidence_neighbourhood("W_missing")

    assert sub.papers == []
    assert sub.edges == []


async def test_foundations_filters_sub_threshold_and_links_kept(make_store: StoreFactory):
    store = await make_store()
    await store.upsert_paper(make_paper("W_keep1", cited_by=50), [1.0, 0.0, 0.0])
    await store.upsert_paper(make_paper("W_keep2", cited_by=30), [0.9, 0.1, 0.0])
    await store.upsert_paper(make_paper("W_drop", cited_by=1), [0.8, 0.2, 0.0])
    await store.upsert_edge(Edge(src="W_keep1", dst="W_keep2", kind="cites"))
    await store.upsert_edge(Edge(src="W_keep1", dst="W_drop", kind="cites"))

    sub = await store.foundations_for_query([1.0, 0.0, 0.0], 5, 10)

    assert {p.openalex_id for p in sub.papers} == {"W_keep1", "W_keep2"}
    assert Edge(src="W_keep1", dst="W_keep2", kind="cites") in sub.edges
    assert all(edge.dst != "W_drop" for edge in sub.edges)
