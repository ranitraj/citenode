"""Tests for evidence retrieval: candidate gathering over the graph store."""

from unittest.mock import AsyncMock

from pydantic_ai.models.function import FunctionModel
from verdict import config
from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.models import Edge, EvidenceItem, EvidenceSet, Stance
from verdict.retrieval import gather_candidates, gather_evidence, score_stances

from tests.factories import make_paper
from tests.model_stubs import structured_function_model


def _embedder(vector: list[float]) -> AsyncMock:
    """Build a stub embedder whose embed coroutine returns a fixed vector."""
    embedder = AsyncMock()
    embedder.embed.return_value = vector
    return embedder


def _stance_for(title_to_stance: dict[str, Stance]) -> FunctionModel:
    """Build a model that returns a stance keyed on the paper title in the prompt."""

    def decide(prompt: str) -> dict[str, object]:
        stance = next((s for title, s in title_to_stance.items() if title in prompt), Stance.NEUTRAL)
        return {"stance": stance.value, "snippet": "snip", "rationale": "why"}

    return structured_function_model(decide)


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


async def test_score_stances_returns_one_evidence_item_per_paper():
    papers = [make_paper("P1"), make_paper("P2")]
    model = _stance_for({"P1": Stance.SUPPORTS, "P2": Stance.SUPPORTS})

    items = await score_stances("a claim", papers, model=model)

    assert len(items) == 2
    assert all(isinstance(item, EvidenceItem) for item in items)
    assert [item.paper.openalex_id for item in items] == ["P1", "P2"]


async def test_score_stances_judges_each_paper_independently():
    papers = [make_paper("PRO"), make_paper("CON"), make_paper("OFF")]
    model = _stance_for({"PRO": Stance.SUPPORTS, "CON": Stance.CONTRADICTS, "OFF": Stance.OFF_TOPIC})

    items = await score_stances("a claim", papers, model=model)

    by_id = {item.paper.openalex_id: item.stance for item in items}
    assert by_id == {"PRO": Stance.SUPPORTS, "CON": Stance.CONTRADICTS, "OFF": Stance.OFF_TOPIC}


async def test_score_stances_carries_the_llm_snippet_and_rationale():
    model = _stance_for({"P1": Stance.SUPPORTS})

    (item,) = await score_stances("a claim", [make_paper("P1")], model=model)

    assert item.snippet == "snip"
    assert item.rationale == "why"


async def test_score_stances_of_no_papers_is_empty():
    model = _stance_for({})

    assert await score_stances("a claim", [], model=model) == []


async def test_gather_evidence_builds_an_evidence_set_from_recalled_papers():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("PRO"), [1.0, 0.0])
    await store.upsert_paper(make_paper("CON"), [0.9, 0.1])
    model = _stance_for({"PRO": Stance.SUPPORTS, "CON": Stance.CONTRADICTS})

    evidence = await gather_evidence("a claim", store=store, embedder=_embedder([1.0, 0.0]), model=model, k=5)

    assert isinstance(evidence, EvidenceSet)
    assert {item.paper.openalex_id for item in evidence.items} == {"PRO", "CON"}
    assert evidence.balance.supports == 1
    assert evidence.balance.contradicts == 1


async def test_gather_evidence_with_no_candidates_is_empty_with_a_coverage_note():
    evidence = await gather_evidence(
        "a claim", store=InMemoryGraphVectorStore(), embedder=_embedder([1.0, 0.0]), model=_stance_for({}), k=5
    )

    assert evidence.items == []
    assert evidence.balance.supports == 0
    assert evidence.balance.weighted_lean == 0.0
    assert evidence.coverage_note != ""


async def test_gather_evidence_excludes_retracted_papers():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("ok"), [1.0, 0.0])
    await store.upsert_paper(make_paper("bad", is_retracted=True), [0.99, 0.01])
    model = _stance_for({"ok": Stance.SUPPORTS, "bad": Stance.SUPPORTS})

    evidence = await gather_evidence("a claim", store=store, embedder=_embedder([1.0, 0.0]), model=model, k=5)

    assert {item.paper.openalex_id for item in evidence.items} == {"ok"}


async def test_gather_evidence_scores_only_the_top_weighted_papers_within_budget(monkeypatch):
    monkeypatch.setattr(config, "MAX_STANCE_CALLS", 2)
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("high", cited_by=1000), [1.0, 0.0])
    await store.upsert_paper(make_paper("mid", cited_by=100), [1.0, 0.0])
    await store.upsert_paper(make_paper("low", cited_by=1), [1.0, 0.0])
    model = _stance_for({"high": Stance.SUPPORTS, "mid": Stance.SUPPORTS, "low": Stance.SUPPORTS})

    evidence = await gather_evidence("a claim", store=store, embedder=_embedder([1.0, 0.0]), model=model, k=5)

    assert {item.paper.openalex_id for item in evidence.items} == {"high", "mid"}


async def test_gather_evidence_notes_truncation_in_coverage_note(monkeypatch):
    monkeypatch.setattr(config, "MAX_STANCE_CALLS", 2)
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("high", cited_by=1000), [1.0, 0.0])
    await store.upsert_paper(make_paper("mid", cited_by=100), [1.0, 0.0])
    await store.upsert_paper(make_paper("low", cited_by=1), [1.0, 0.0])
    model = _stance_for({"high": Stance.SUPPORTS, "mid": Stance.SUPPORTS, "low": Stance.SUPPORTS})

    evidence = await gather_evidence("a claim", store=store, embedder=_embedder([1.0, 0.0]), model=model, k=5)

    assert "not scored" in evidence.coverage_note
