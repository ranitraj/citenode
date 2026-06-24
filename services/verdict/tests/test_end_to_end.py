"""Tests for the end-to-end retrieval recall@k eval."""

from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.eval.end_to_end import RecallSample, recall_at_k, run_recall_eval, score_recall
from verdict.eval.scifact import GoldAbstract, GoldClaim
from verdict.models import Verdict

from tests.factories import make_paper
from tests.model_stubs import council_provider, make_deps


def _sample(claim_id: str, *, retrieved: list[str], gold: list[str]) -> RecallSample:
    return RecallSample(claim_id=claim_id, retrieved_ids=retrieved, gold_ids=gold)


def test_recall_at_k_is_one_when_all_gold_papers_are_retrieved():
    assert recall_at_k(["A", "B", "C"], {"A", "B"}) == 1.0


def test_recall_at_k_is_the_fraction_of_gold_papers_found():
    assert recall_at_k(["A", "X"], {"A", "B"}) == 0.5
    assert recall_at_k(["X", "Y"], {"A"}) == 0.0


def test_score_recall_averages_over_claims_with_gold_only():
    samples = [
        _sample("1", retrieved=["A", "B"], gold=["A", "B"]),
        _sample("2", retrieved=["A", "X"], gold=["A", "B"]),
        _sample("3", retrieved=["Z"], gold=[]),
    ]

    metrics = score_recall(samples, k=5)

    assert metrics.recall_at_k == 0.75
    assert metrics.n_total == 3
    assert metrics.n_scored == 2
    assert metrics.k == 5


async def test_run_recall_eval_measures_gold_recall_from_the_corpus():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("W1"), [1.0, 0.0])
    await store.upsert_paper(make_paper("D1"), [1.0, 0.0])
    gold = [
        GoldClaim(
            claim_id="1",
            claim="a claim",
            gold_verdict=Verdict.SUPPORTED,
            abstracts=[GoldAbstract(doc_id="W1", title="t", abstract="a")],
        )
    ]
    deps = make_deps(council_provider(), store=store)

    samples = await run_recall_eval(gold, deps=deps, k=5)

    assert len(samples) == 1
    assert samples[0].gold_ids == ["W1"]
    assert "W1" in samples[0].retrieved_ids
