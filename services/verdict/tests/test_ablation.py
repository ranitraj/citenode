"""Tests for the graph-vs-vector retrieval ablation."""

from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.eval.ablation import AblationOutcome, run_ablation_eval, score_ablation
from verdict.eval.end_to_end import RecallSample

from tests.factories import make_gold_claim, make_paper
from tests.model_stubs import council_provider, make_deps


def _sample(retrieved: list[str], gold: list[str]) -> RecallSample:
    return RecallSample(claim_id="c", retrieved_ids=retrieved, gold_ids=gold)


def test_score_ablation_reports_a_positive_delta_when_the_graph_recalls_more():
    graph = [_sample(["W1", "W2"], ["W1", "W2"])]  # graph recall 1.0
    vector = [_sample(["W1"], ["W1", "W2"])]  # vector recall 0.5
    result = score_ablation(graph, vector, recall_floor=0.5)
    assert result.delta == 0.5  # 1.0 - 0.5
    assert result.outcome is AblationOutcome.CONCLUSIVE  # graph recall 1.0 >= floor


def test_score_ablation_is_inconclusive_below_the_recall_floor():
    graph = [_sample(["X"], ["W1", "W2"])]  # graph recall 0.0 < floor
    vector = [_sample([], ["W1", "W2"])]
    result = score_ablation(graph, vector, recall_floor=0.5)
    assert result.outcome is AblationOutcome.INCONCLUSIVE


async def test_run_ablation_eval_scores_both_retrieval_paths():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("W1"), [1.0, 0.0])
    gold = [make_gold_claim()]
    deps = make_deps(council_provider(), store=store)

    result = await run_ablation_eval(gold, deps=deps, k=5, recall_floor=0.5)

    assert result.graph_recall == 1.0
    assert result.vector_recall == 1.0
    assert result.outcome is AblationOutcome.CONCLUSIVE
