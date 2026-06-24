"""End-to-end tests for verify_claim across the cheap and council paths."""

from unittest.mock import MagicMock

import pytest
from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.adapters.openrouter import OpenRouterModelProvider
from verdict.models import ClaimResult, Path, Stance, Verdict
from verdict.pipeline import CitenodeDeps, InternalCorpusLeakError, verify_claim

from tests.factories import make_paper
from tests.model_stubs import chairman_verdict_model, cheap_path_model, council_provider, member_ranker_model


class _Embedder:
    async def embed(self, _text: str) -> list[float]:
        """Return a fixed query/draft embedding."""
        return [1.0, 0.0]


def _deps(*, provider, store=None, corpus_is_internal=False) -> CitenodeDeps:
    return CitenodeDeps(
        store=store or InMemoryGraphVectorStore(),
        embedder=_Embedder(),
        text_embedder=_Embedder(),
        source=MagicMock(),
        provider=provider,
        k=5,
        escalation_threshold=0.1,
        corpus_is_internal=corpus_is_internal,
    )


async def _store_with(papers: dict[str, list[float]]) -> InMemoryGraphVectorStore:
    store = InMemoryGraphVectorStore()
    for paper_id, embedding in papers.items():
        await store.upsert_paper(make_paper(paper_id), embedding)
    return store


async def test_verify_claim_rejects_internal_corpus_on_openrouter_before_any_call():
    provider = OpenRouterModelProvider(
        api_key="dummy", cheap_model="x", member_models=["a", "b", "c", "d"], chairman_model="z"
    )

    with pytest.raises(InternalCorpusLeakError):
        await verify_claim("a claim", deps=_deps(provider=provider, corpus_is_internal=True))


async def test_verify_claim_returns_insufficient_for_a_non_checkable_claim():
    provider = council_provider(cheap=cheap_path_model(checkable=False))

    result = await verify_claim("Modern art is bad.", deps=_deps(provider=provider))

    assert result.verdict is Verdict.INSUFFICIENT
    assert result.path is Path.CHEAP
    assert result.supporting == []
    assert result.citations == []


async def test_verify_claim_takes_the_cheap_path_on_strong_one_sided_evidence():
    store = await _store_with({"P_sup": [1.0, 0.0]})
    provider = council_provider(cheap=cheap_path_model(verdict=Verdict.SUPPORTED))

    result = await verify_claim("a claim", deps=_deps(provider=provider, store=store))

    assert isinstance(result, ClaimResult)
    assert result.path is Path.CHEAP
    assert result.verdict is Verdict.SUPPORTED
    assert [item.paper.openalex_id for item in result.supporting] == ["P_sup"]
    assert [citation.openalex_id for citation in result.citations] == ["P_sup"]


async def test_verify_claim_escalates_to_the_council_on_contested_evidence():
    store = await _store_with({"P_sup": [1.0, 0.0], "P_con": [0.9, 0.1]})
    provider = council_provider(
        cheap=cheap_path_model(stances={"P_sup": Stance.SUPPORTS, "P_con": Stance.CONTRADICTS}),
        members=[
            member_ranker_model(
                verdict=Verdict.CONTESTED, supporting=["P_sup"], contradicting=["P_con"], model_name=f"m{index}"
            )
            for index in range(4)
        ],
        chairman=chairman_verdict_model(
            verdict=Verdict.CONTESTED,
            supporting=["P_sup"],
            contradicting=["P_con"],
            synthesis="evidence is mixed",
            dissent="a minority would refute",
        ),
    )

    result = await verify_claim("a claim", deps=_deps(provider=provider, store=store))

    assert result.path is Path.COUNCIL
    assert result.verdict is Verdict.CONTESTED
    assert result.dissent == "a minority would refute"
    assert [item.paper.openalex_id for item in result.supporting] == ["P_sup"]
    assert [item.paper.openalex_id for item in result.contradicting] == ["P_con"]
    assert {citation.openalex_id for citation in result.citations} == {"P_sup", "P_con"}


async def test_verify_claim_persists_nothing_between_runs():
    store = await _store_with({"P_sup": [1.0, 0.0]})
    deps = _deps(provider=council_provider(cheap=cheap_path_model()), store=store)

    first = await verify_claim("Claim one.", deps=deps)
    second = await verify_claim("Claim two.", deps=deps)

    assert first.claim == "Claim one."
    assert second.claim == "Claim two."
