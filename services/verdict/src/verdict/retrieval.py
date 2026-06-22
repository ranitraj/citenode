"""Evidence retrieval: gather connected literature for a claim from the graph store."""

from verdict.models import Paper
from verdict.ports import GraphVectorStore


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
