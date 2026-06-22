"""Integration tests for the HelixDB v3 graph+vector store (needs a live instance)."""

import asyncio

import httpx
import pytest
from helixdb import Client, g, write_batch
from verdict import config
from verdict.adapters.helix_store import HelixGraphVectorStore
from verdict.models import Edge, Paper

SEED = Paper(
    openalex_id="W_seed",
    doi="10.1/seed",
    title="Seed",
    year=2020,
    abstract="seed abstract",
    cited_by=100,
    is_retracted=False,
    venue="Nature",
)
OTHER = Paper(
    openalex_id="W_other",
    doi=None,
    title="Other",
    year=2019,
    abstract="other abstract",
    cited_by=5,
    is_retracted=False,
    venue=None,
)


def _instance_up() -> bool:
    """Return True if the local HelixDB query endpoint answers."""
    try:
        return httpx.get(f"{config.HELIX_URL}/v1/query", timeout=2.0).status_code == 405
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(not _instance_up(), reason="HelixDB instance not running")


async def test_recall_returns_nearest_first():
    store = await _fresh_store()
    await store.upsert_paper(SEED, [1.0, 0.0, 0.0])
    await store.upsert_paper(OTHER, [0.0, 1.0, 0.0])

    papers = await store.recall_papers([0.9, 0.1, 0.0], 2)

    assert [p.openalex_id for p in papers] == ["W_seed", "W_other"]
    assert papers[0] == SEED


async def test_recall_round_trips_null_doi_and_venue():
    store = await _fresh_store()
    await store.upsert_paper(OTHER, [0.0, 1.0, 0.0])

    (paper,) = await store.recall_papers([0.0, 1.0, 0.0], 1)

    assert paper == OTHER


async def test_upsert_replaces_the_existing_paper():
    store = await _fresh_store()
    await store.upsert_paper(SEED, [1.0, 0.0, 0.0])
    await store.upsert_paper(SEED.model_copy(update={"title": "Seed v2"}), [1.0, 0.0, 0.0])

    papers = await store.recall_papers([1.0, 0.0, 0.0], 5)

    assert len(papers) == 1
    assert papers[0].title == "Seed v2"


async def test_evidence_neighbourhood_returns_cited_and_citing():
    store = await _fresh_store()
    for oid, vec in (("W_a", [1.0, 0.0, 0.0]), ("W_b", [0.0, 1.0, 0.0]), ("W_c", [0.0, 0.0, 1.0])):
        await store.upsert_paper(_paper(oid), vec)
    await store.upsert_edge(Edge(src="W_a", dst="W_b", kind="cites"))
    await store.upsert_edge(Edge(src="W_c", dst="W_a", kind="cites"))

    sub = await store.evidence_neighbourhood("W_a")

    assert {p.openalex_id for p in sub.papers} == {"W_b", "W_c"}
    assert Edge(src="W_a", dst="W_b", kind="cites") in sub.edges
    assert Edge(src="W_c", dst="W_a", kind="cites") in sub.edges


async def test_evidence_neighbourhood_of_unknown_paper_is_empty():
    store = await _fresh_store()

    sub = await store.evidence_neighbourhood("W_missing")

    assert sub.papers == []
    assert sub.edges == []


async def test_upsert_edge_is_idempotent_in_neighbourhood():
    store = await _fresh_store()
    await store.upsert_paper(_paper("W_a"), [1.0, 0.0, 0.0])
    await store.upsert_paper(_paper("W_b"), [0.0, 1.0, 0.0])
    await store.upsert_edge(Edge(src="W_a", dst="W_b", kind="cites"))
    await store.upsert_edge(Edge(src="W_a", dst="W_b", kind="cites"))

    sub = await store.evidence_neighbourhood("W_a")

    assert [p.openalex_id for p in sub.papers] == ["W_b"]
    assert sub.edges == [Edge(src="W_a", dst="W_b", kind="cites")]


def _paper(openalex_id: str) -> Paper:
    """Return a minimal paper with the given openalex id."""
    return SEED.model_copy(update={"openalex_id": openalex_id})


async def _fresh_store() -> HelixGraphVectorStore:
    """Return a store against an empty graph: index ensured, all papers dropped."""
    store = HelixGraphVectorStore(Client(config.HELIX_URL))
    await store.ensure_schema()
    drop = write_batch().var_as("d", g().n_with_label(config.HELIX_PAPER_LABEL).drop()).returning(["d"])
    await asyncio.to_thread(
        lambda: Client(config.HELIX_URL)
        .query()
        .writer_only()
        .should_await_durability(True)
        .dynamic(drop.to_dynamic_request())
        .send()
    )
    return store
