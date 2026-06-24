"""Run T11 reasoning-on-gold and score verdict accuracy against SciFact labels."""

from dataclasses import replace

from pydantic import BaseModel

from verdict import config
from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.embedding import paper_embedding_text
from verdict.eval.scifact import GoldAbstract, GoldClaim
from verdict.models import Paper, Verdict
from verdict.pipeline import CitenodeDeps, verify_claim
from verdict.ports import Embedder

# The verdicts SciFact can label; citenode CONTESTED has no gold equivalent (ADR 0013).
_SCIFACT_VERDICTS = (Verdict.SUPPORTED, Verdict.REFUTED, Verdict.INSUFFICIENT)


class Prediction(BaseModel):
    """One gold claim's gold verdict alongside the verdict citenode produced."""

    claim_id: str
    gold: Verdict
    predicted: Verdict


class LabelScore(BaseModel):
    """Precision, recall, and gold support for a single verdict label."""

    precision: float
    recall: float
    support: int


class ReasoningMetrics(BaseModel):
    """Accuracy and per-label precision/recall over the scored predictions."""

    accuracy: float
    per_label: dict[Verdict, LabelScore]
    n_total: int
    n_scored: int
    n_excluded: int


async def run_reasoning_eval(gold: list[GoldClaim], *, deps: CitenodeDeps) -> list[Prediction]:
    """Verify each gold claim against only its gold abstracts and record the verdict.

    Each claim runs over a fresh in-memory store holding just its gold evidence, so the
    score isolates the stance and verdict reasoning from retrieval (T11). The provider
    and embedders from ``deps`` are reused; only the store is swapped per claim.

    Parameters
    ----------
    gold : list[GoldClaim]
        The gold claims with their evidence abstracts and gold verdicts.
    deps : CitenodeDeps
        The pipeline dependencies; its store is replaced per claim.

    Returns
    -------
    list[Prediction]
        One prediction per gold claim, in input order.
    """
    predictions: list[Prediction] = []
    for claim in gold:
        store = InMemoryGraphVectorStore()
        await _load_gold_store(store, claim.abstracts, deps.embedder)
        result = await verify_claim(claim.claim, deps=replace(deps, store=store))
        predictions.append(Prediction(claim_id=claim.claim_id, gold=claim.gold_verdict, predicted=result.verdict))
    return predictions


def score_reasoning(predictions: list[Prediction]) -> ReasoningMetrics:
    """Score accuracy and per-label precision/recall over the predictions.

    Predictions of CONTESTED are excluded from scoring because SciFact has no gold
    CONTESTED label; the excluded count is reported so the exclusion stays visible.

    Parameters
    ----------
    predictions : list[Prediction]
        The gold-vs-predicted verdicts to score.

    Returns
    -------
    ReasoningMetrics
        Accuracy, per-label precision/recall, and the scored/excluded counts.
    """
    scored = [prediction for prediction in predictions if prediction.predicted is not Verdict.CONTESTED]
    correct = sum(1 for prediction in scored if prediction.predicted is prediction.gold)
    accuracy = correct / len(scored) if scored else 0.0
    return ReasoningMetrics(
        accuracy=accuracy,
        per_label={label: _label_score(scored, label) for label in _SCIFACT_VERDICTS},
        n_total=len(predictions),
        n_scored=len(scored),
        n_excluded=len(predictions) - len(scored),
    )


async def _load_gold_store(store: InMemoryGraphVectorStore, abstracts: list[GoldAbstract], embedder: Embedder) -> None:
    """Load the gold abstracts into the store as embedded papers.

    Parameters
    ----------
    store : InMemoryGraphVectorStore
        The fresh per-claim store to populate.
    abstracts : list[GoldAbstract]
        The claim's gold evidence abstracts.
    embedder : Embedder
        The embedder used to embed each abstract for recall.
    """
    for abstract in abstracts:
        paper = _to_paper(abstract)
        embedding = await embedder.embed(paper_embedding_text(paper))
        await store.upsert_paper(paper, embedding)


def _to_paper(abstract: GoldAbstract) -> Paper:
    """Build a paper node from a gold abstract with uniform placeholder metadata.

    Parameters
    ----------
    abstract : GoldAbstract
        The gold abstract to convert.

    Returns
    -------
    Paper
        A paper node carrying the abstract's id, title, and text.
    """
    return Paper(
        openalex_id=abstract.doc_id,
        doi=None,
        title=abstract.title,
        year=config.EVAL_GOLD_PAPER_YEAR,
        abstract=abstract.abstract,
        cited_by=config.EVAL_GOLD_PAPER_CITED_BY,
        is_retracted=False,
        venue=None,
    )


def _label_score(scored: list[Prediction], label: Verdict) -> LabelScore:
    """Compute precision, recall, and support for one label over the scored predictions.

    Parameters
    ----------
    scored : list[Prediction]
        The predictions that were scored (CONTESTED already excluded).
    label : Verdict
        The verdict label to score.

    Returns
    -------
    LabelScore
        The label's precision, recall, and gold support; precision or recall is 0.0
        when its denominator is empty.
    """
    true_positives = sum(1 for prediction in scored if prediction.gold is label and prediction.predicted is label)
    predicted_count = sum(1 for prediction in scored if prediction.predicted is label)
    gold_count = sum(1 for prediction in scored if prediction.gold is label)
    return LabelScore(
        precision=true_positives / predicted_count if predicted_count else 0.0,
        recall=true_positives / gold_count if gold_count else 0.0,
        support=gold_count,
    )
