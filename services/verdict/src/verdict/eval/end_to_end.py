"""Run the end-to-end retrieval eval: gold-paper recall@k from the ingested corpus."""

from pydantic import BaseModel

from verdict import config
from verdict.eval.scifact import GoldClaim
from verdict.pipeline import CitenodeDeps
from verdict.retrieval import gather_candidates


class RecallSample(BaseModel):
    """One claim's retrieved paper ids alongside the gold paper ids it should surface."""

    claim_id: str
    retrieved_ids: list[str]
    gold_ids: list[str]


class RecallMetrics(BaseModel):
    """Mean gold-paper recall@k over the claims that carry gold evidence."""

    recall_at_k: float
    k: int
    n_total: int
    n_scored: int


async def run_recall_eval(gold: list[GoldClaim], *, deps: CitenodeDeps, k: int) -> list[RecallSample]:
    """Retrieve candidates per claim from the corpus and record gold-vs-retrieved ids.

    The gold abstracts are withheld from the per-claim input and must instead be
    surfaced by retrieval over the pre-ingested corpus in ``deps.store``, so the
    measure isolates retrieval from reasoning.

    Parameters
    ----------
    gold : list[GoldClaim]
        The gold claims whose cited abstracts are the retrieval targets.
    deps : CitenodeDeps
        The pipeline dependencies; its store holds the ingested corpus.
    k : int
        The number of candidates to retrieve per claim.

    Returns
    -------
    list[RecallSample]
        One sample per claim, in input order.
    """
    samples: list[RecallSample] = []
    for claim in gold:
        query_vec = await deps.embedder.embed(claim.claim)
        candidates = await gather_candidates(query_vec, store=deps.store, k=k, min_cited=config.FOUNDATION_MIN_CITED)
        samples.append(
            RecallSample(
                claim_id=claim.claim_id,
                retrieved_ids=[paper.openalex_id for paper in candidates],
                gold_ids=[abstract.doc_id for abstract in claim.abstracts],
            )
        )
    return samples


def score_recall(samples: list[RecallSample], *, k: int) -> RecallMetrics:
    """Average recall@k over the samples that have gold evidence to recall.

    Claims with no gold papers cannot be scored for recall and are excluded from the
    average; their count stays visible via ``n_total`` minus ``n_scored``.

    Parameters
    ----------
    samples : list[RecallSample]
        The per-claim retrieved-vs-gold ids.
    k : int
        The retrieval k these samples were drawn at, recorded for reporting.

    Returns
    -------
    RecallMetrics
        The mean recall@k and the scored/total counts.
    """
    scored = [sample for sample in samples if sample.gold_ids]
    mean = (
        sum(recall_at_k(sample.retrieved_ids, set(sample.gold_ids)) for sample in scored) / len(scored)
        if scored
        else 0.0
    )
    return RecallMetrics(recall_at_k=mean, k=k, n_total=len(samples), n_scored=len(scored))


def recall_at_k(retrieved_ids: list[str], gold_ids: set[str]) -> float:
    """Return the fraction of gold paper ids present among the retrieved ids.

    Parameters
    ----------
    retrieved_ids : list[str]
        The ids retrieved for the claim, already the top-k.
    gold_ids : set[str]
        The gold paper ids the retrieval should surface; assumed non-empty.

    Returns
    -------
    float
        The share of gold ids found in the retrieved set, or 0.0 when no gold ids.
    """
    if not gold_ids:
        return 0.0
    retrieved = set(retrieved_ids)
    return sum(1 for gold_id in gold_ids if gold_id in retrieved) / len(gold_ids)
