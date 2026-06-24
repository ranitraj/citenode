"""Tests for the T11 reasoning-on-gold runner and its metrics."""

from verdict.eval.reasoning import Prediction, run_reasoning_eval, score_reasoning
from verdict.eval.scifact import GoldAbstract, GoldClaim
from verdict.models import Verdict

from tests.model_stubs import cheap_path_model, council_provider, make_deps


def _prediction(gold: Verdict, predicted: Verdict) -> Prediction:
    return Prediction(claim_id="c", gold=gold, predicted=predicted)


def test_score_reasoning_is_perfect_when_every_prediction_matches():
    predictions = [
        _prediction(Verdict.SUPPORTED, Verdict.SUPPORTED),
        _prediction(Verdict.REFUTED, Verdict.REFUTED),
        _prediction(Verdict.INSUFFICIENT, Verdict.INSUFFICIENT),
    ]

    metrics = score_reasoning(predictions)

    assert metrics.accuracy == 1.0
    assert metrics.n_scored == 3
    assert metrics.n_excluded == 0
    assert all(score.precision == 1.0 and score.recall == 1.0 for score in metrics.per_label.values())


def test_score_reasoning_excludes_contested_predictions_from_scoring():
    predictions = [
        _prediction(Verdict.SUPPORTED, Verdict.SUPPORTED),
        _prediction(Verdict.REFUTED, Verdict.CONTESTED),
    ]

    metrics = score_reasoning(predictions)

    assert metrics.n_total == 2
    assert metrics.n_scored == 1
    assert metrics.n_excluded == 1
    assert metrics.accuracy == 1.0


def test_score_reasoning_computes_per_label_precision_and_recall():
    predictions = [
        _prediction(Verdict.SUPPORTED, Verdict.SUPPORTED),
        _prediction(Verdict.SUPPORTED, Verdict.REFUTED),
        _prediction(Verdict.REFUTED, Verdict.REFUTED),
        _prediction(Verdict.INSUFFICIENT, Verdict.INSUFFICIENT),
    ]

    metrics = score_reasoning(predictions)

    assert metrics.accuracy == 0.75
    assert metrics.per_label[Verdict.SUPPORTED].precision == 1.0
    assert metrics.per_label[Verdict.SUPPORTED].recall == 0.5
    assert metrics.per_label[Verdict.REFUTED].precision == 0.5
    assert metrics.per_label[Verdict.REFUTED].recall == 1.0


async def test_run_reasoning_eval_predicts_a_verdict_per_gold_claim():
    gold = [
        GoldClaim(
            claim_id="42",
            claim="a claim",
            gold_verdict=Verdict.SUPPORTED,
            abstracts=[GoldAbstract(doc_id="d1", title="t", abstract="a supporting abstract")],
        )
    ]
    deps = make_deps(council_provider(cheap=cheap_path_model(verdict=Verdict.SUPPORTED)))

    predictions = await run_reasoning_eval(gold, deps=deps)

    assert len(predictions) == 1
    assert predictions[0].claim_id == "42"
    assert predictions[0].gold is Verdict.SUPPORTED
    assert predictions[0].predicted is Verdict.SUPPORTED
