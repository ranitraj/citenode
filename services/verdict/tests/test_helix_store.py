"""HelixDB-specific tests: recall@k ordering, field round-trip, upsert and edge semantics."""

import pytest
from verdict.models import Edge, Paper

from tests.factories import make_paper
from tests.helix_support import fresh_helix_store, helix_instance_up

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

pytestmark = pytest.mark.skipif(not helix_instance_up(), reason="HelixDB instance not running")


async def test_recall_at_k_returns_planted_nearest_first():
    store = await fresh_helix_store()
    await store.upsert_paper(SEED, [1.0, 0.0, 0.0])
    await store.upsert_paper(OTHER, [0.0, 1.0, 0.0])

    papers = await store.recall_papers([0.9, 0.1, 0.0], 2)

    assert [p.openalex_id for p in papers] == ["W_seed", "W_other"]
    assert papers[0] == SEED


async def test_recall_round_trips_null_doi_and_venue():
    store = await fresh_helix_store()
    await store.upsert_paper(OTHER, [0.0, 1.0, 0.0])

    (paper,) = await store.recall_papers([0.0, 1.0, 0.0], 1)

    assert paper == OTHER


async def test_upsert_replaces_the_existing_paper():
    store = await fresh_helix_store()
    await store.upsert_paper(SEED, [1.0, 0.0, 0.0])
    await store.upsert_paper(SEED.model_copy(update={"title": "Seed v2"}), [1.0, 0.0, 0.0])

    papers = await store.recall_papers([1.0, 0.0, 0.0], 5)

    assert len(papers) == 1
    assert papers[0].title == "Seed v2"


async def test_upsert_edge_is_idempotent_in_neighbourhood():
    store = await fresh_helix_store()
    await store.upsert_paper(make_paper("W_a"), [1.0, 0.0, 0.0])
    await store.upsert_paper(make_paper("W_b"), [0.0, 1.0, 0.0])
    await store.upsert_edge(Edge(src="W_a", dst="W_b", kind="cites"))
    await store.upsert_edge(Edge(src="W_a", dst="W_b", kind="cites"))

    sub = await store.evidence_neighbourhood("W_a")

    assert [p.openalex_id for p in sub.papers] == ["W_b"]
    assert sub.edges == [Edge(src="W_a", dst="W_b", kind="cites")]
