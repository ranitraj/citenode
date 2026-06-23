"""Evidence retrieval: gather connected literature for a claim from the graph store."""

from pydantic_ai import Agent
from pydantic_ai.models import Model

from verdict import config
from verdict.council.aggregate import influence_recency_weight, summarise_balance
from verdict.models import EvidenceItem, EvidenceSet, Paper, Stance, StanceJudgement
from verdict.ports import Embedder, GraphVectorStore
from verdict.prompting import render_prompt


async def gather_evidence(
    claim: str, *, store: GraphVectorStore, embedder: Embedder, model: Model, k: int
) -> EvidenceSet:
    """Gather the claim's connected literature and score each paper's stance.

    Parameters
    ----------
    claim : str
        The claim under verification.
    store : GraphVectorStore
        The graph+vector store to retrieve candidates from.
    embedder : Embedder
        The embedder that turns the claim into a query vector.
    model : Model
        The model that judges each candidate's stance.
    k : int
        The recall breadth passed to candidate gathering.

    Returns
    -------
    EvidenceSet
        The scored evidence items, their aggregate balance, and a coverage note.
    """
    query_vec = await embedder.embed(claim)
    candidates = await gather_candidates(query_vec, store=store, k=k, min_cited=config.FOUNDATION_MIN_CITED)
    papers, dropped = _within_stance_budget(candidates)
    items = await score_stances(claim, papers, model=model)
    return EvidenceSet(items=items, balance=summarise_balance(items), coverage_note=_coverage_note(items, dropped))


async def gather_candidates(query_vec: list[float], *, store: GraphVectorStore, k: int, min_cited: int) -> list[Paper]:
    """Gather candidate papers for a claim from vector recall and the citation graph.

    Unions nearest-neighbour recall, the foundational (highly-cited) papers near
    the query, and the citation neighbourhood of each recalled seed, then drops
    retractions and de-duplicates by openalex id, recalled papers first.

    Parameters
    ----------
    query_vec : list[float]
        The claim embedding.
    store : GraphVectorStore
        The graph+vector store to query.
    k : int
        The recall breadth for both nearest-neighbour and foundational queries.
    min_cited : int
        The minimum citation count for a paper to count as foundational.

    Returns
    -------
    list[Paper]
        The unique, non-retracted candidate papers.
    """
    recalled = await store.recall_papers(query_vec, k)
    foundations = await store.foundations_for_query(query_vec, k, min_cited)
    candidates = [*recalled, *foundations.papers]
    for seed in recalled:
        neighbourhood = await store.evidence_neighbourhood(seed.openalex_id)
        candidates.extend(neighbourhood.papers)
    return _unique_unretracted(candidates)


async def score_stances(claim: str, papers: list[Paper], *, model: Model) -> list[EvidenceItem]:
    """Score each candidate paper's stance toward the claim with an LLM.

    Parameters
    ----------
    claim : str
        The claim under verification.
    papers : list[Paper]
        The candidate papers to judge.
    model : Model
        The model that reads each abstract and returns a stance judgement.

    Returns
    -------
    list[EvidenceItem]
        One evidence item per paper, in input order, carrying the model's stance.
    """
    agent = Agent(model=model, output_type=StanceJudgement, system_prompt=render_prompt("stance_system.j2"))
    items: list[EvidenceItem] = []
    for paper in papers:
        prompt = render_prompt("stance_user.j2", claim=claim, title=paper.title, abstract=paper.abstract)
        judgement = (await agent.run(prompt)).output
        items.append(
            EvidenceItem(
                paper=paper,
                stance=judgement.stance,
                snippet=judgement.snippet,
                rationale=judgement.rationale,
            )
        )
    return items


def _within_stance_budget(papers: list[Paper]) -> tuple[list[Paper], int]:
    """Keep the highest-weighted papers within the per-claim stance-call budget.

    Parameters
    ----------
    papers : list[Paper]
        The candidate papers to score.

    Returns
    -------
    tuple[list[Paper], int]
        The papers to score (all of them when under budget) and the count
        dropped, lowest influence-recency weight first.
    """
    if len(papers) <= config.MAX_STANCE_CALLS:
        return papers, 0
    ranked = sorted(papers, key=lambda paper: influence_recency_weight(paper.cited_by, paper.year), reverse=True)
    return ranked[: config.MAX_STANCE_CALLS], len(papers) - config.MAX_STANCE_CALLS


def _coverage_note(items: list[EvidenceItem], dropped: int) -> str:
    """Describe how much usable evidence was gathered for the claim.

    Parameters
    ----------
    items : list[EvidenceItem]
        The scored evidence items.
    dropped : int
        The number of candidate papers left unscored by the stance-call budget.

    Returns
    -------
    str
        A short human-readable coverage summary.
    """
    if not items:
        return "No papers were retrieved for this claim."
    on_topic = sum(1 for item in items if item.stance is not Stance.OFF_TOPIC)
    note = f"Scored {len(items)} retrieved papers; {on_topic} on-topic."
    if dropped:
        note += f" {dropped} lower-weighted papers were not scored (call budget)."
    return note


def _unique_unretracted(papers: list[Paper]) -> list[Paper]:
    """Drop retracted papers and de-duplicate by openalex id, preserving order.

    Parameters
    ----------
    papers : list[Paper]
        The papers to filter, in priority order.

    Returns
    -------
    list[Paper]
        The first occurrence of each non-retracted paper, in input order.
    """
    seen: set[str] = set()
    result: list[Paper] = []
    for paper in papers:
        if paper.is_retracted or paper.openalex_id in seen:
            continue
        seen.add(paper.openalex_id)
        result.append(paper)
    return result
