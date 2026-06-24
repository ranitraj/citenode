"""Ablate the citation graph against vector-only recall, gated on a recall floor."""

from enum import StrEnum

from pydantic import BaseModel

from verdict import config
from verdict.eval.end_to_end import RecallSample, mean_recall
from verdict.eval.scifact import GoldClaim
from verdict.models import Paper
from verdict.pipeline import CitenodeDeps
from verdict.retrieval import gather_candidates


class AblationOutcome(StrEnum):
    """Whether the ablation delta can be trusted given the retrieval recall."""

    CONCLUSIVE = "conclusive"
    INCONCLUSIVE = "inconclusive"


class AblationResult(BaseModel):
    """Graph-on vs vector-only recall, their delta, and whether it clears the floor."""

    graph_recall: float
    vector_recall: float
    delta: float
    outcome: AblationOutcome


async def run_ablation_eval(
    gold: list[GoldClaim], *, deps: CitenodeDeps, k: int, recall_floor: float = config.ABLATION_RECALL_FLOOR
) -> AblationResult:
    """Retrieve each claim both with the graph and vector-only, then score the ablation.

    For every claim the graph path (vector recall plus citation-graph expansion) and the
    vector-only path (vector recall alone) retrieve from the same corpus; the delta in
    gold-paper recall measures what the graph adds.

    Parameters
    ----------
    gold : list[GoldClaim]
        The gold claims whose cited abstracts are the retrieval targets.
    deps : CitenodeDeps
        The pipeline dependencies; its store holds the ingested corpus.
    k : int
        The number of candidates to retrieve per claim on each path.
    recall_floor : float
        The graph recall@k below which the delta is inconclusive.

    Returns
    -------
    AblationResult
        The two recalls, their delta, and the conclusiveness outcome.
    """
    graph_samples: list[RecallSample] = []
    vector_samples: list[RecallSample] = []
    for claim in gold:
        query_vec = await deps.embedder.embed(claim.claim)
        graph = await gather_candidates(query_vec, store=deps.store, k=k, min_cited=config.FOUNDATION_MIN_CITED)
        vector = await deps.store.recall_papers(query_vec, k)
        gold_ids = [abstract.doc_id for abstract in claim.abstracts]
        graph_samples.append(_sample(claim.claim_id, graph, gold_ids))
        vector_samples.append(_sample(claim.claim_id, vector, gold_ids))
    return score_ablation(graph_samples, vector_samples, recall_floor=recall_floor)


def score_ablation(
    graph_samples: list[RecallSample],
    vector_samples: list[RecallSample],
    *,
    recall_floor: float = config.ABLATION_RECALL_FLOOR,
) -> AblationResult:
    """Score the graph-vs-vector recall delta, marking it inconclusive below the floor.

    A delta is only interpretable when retrieval works at all: if the graph recall@k
    stays under the floor, the result is inconclusive and cannot motivate a redesign.

    Parameters
    ----------
    graph_samples : list[RecallSample]
        The retrieved-vs-gold ids from the graph path.
    vector_samples : list[RecallSample]
        The retrieved-vs-gold ids from the vector-only path.
    recall_floor : float
        The graph recall@k below which the delta is inconclusive.

    Returns
    -------
    AblationResult
        The two recalls, their delta, and the conclusiveness outcome.
    """
    graph_recall = mean_recall(graph_samples)
    vector_recall = mean_recall(vector_samples)
    outcome = AblationOutcome.CONCLUSIVE if graph_recall >= recall_floor else AblationOutcome.INCONCLUSIVE
    return AblationResult(
        graph_recall=graph_recall, vector_recall=vector_recall, delta=graph_recall - vector_recall, outcome=outcome
    )


def _sample(claim_id: str, papers: list[Paper], gold_ids: list[str]) -> RecallSample:
    """Build a recall sample from retrieved papers and the claim's gold ids.

    Parameters
    ----------
    claim_id : str
        The claim's id.
    papers : list[Paper]
        The retrieved papers, in rank order.
    gold_ids : list[str]
        The gold paper ids the retrieval should surface.

    Returns
    -------
    RecallSample
        The retrieved-vs-gold ids for the claim.
    """
    return RecallSample(claim_id=claim_id, retrieved_ids=[paper.openalex_id for paper in papers], gold_ids=gold_ids)
