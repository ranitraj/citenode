"""Seed-and-expand corpus ingestion from a literature source into the store."""

import asyncio

from verdict import config
from verdict.embedding import paper_embedding_text
from verdict.models import Edge, EdgeKind, Paper, Work
from verdict.ports import Embedder, GraphVectorStore, LiteratureSource


async def ingest_corpus(query: str, *, source: LiteratureSource, store: GraphVectorStore, embedder: Embedder) -> int:
    """Seed-and-expand a corpus from the source and load it into the store.

    Searches the source for seed works, expands one hop through each seed's outgoing
    references and incoming citations (the latter surfaces refuting work, ADR 0007),
    then fetches, embeds, and upserts each unique work as a paper, adding CITES edges
    between papers that both made it into the corpus. The expansion is bounded by the
    ``INGEST_*`` limits in ``config``.

    Parameters
    ----------
    query : str
        The seed search query, typically the claim.
    source : LiteratureSource
        The literature source to search and expand.
    store : GraphVectorStore
        The store the papers and edges are written to.
    embedder : Embedder
        The embedder used to vectorize each paper's text.

    Returns
    -------
    int
        The number of papers ingested.
    """
    work_ids = await _gather_work_ids(query, source)
    fetched = await asyncio.gather(*(source.fetch_work(work_id) for work_id in work_ids), return_exceptions=True)
    works = [work for work in fetched if isinstance(work, Work)]
    papers = [_to_paper(work) for work in works]
    await _store_papers(store, papers, embedder)
    await _link_citations(store, works, {paper.openalex_id for paper in papers})
    return len(papers)


async def _gather_work_ids(query: str, source: LiteratureSource) -> list[str]:
    """Collect the ordered, unique work ids for a bounded seed-and-expand.

    Parameters
    ----------
    query : str
        The seed search query.
    source : LiteratureSource
        The literature source to search and expand.

    Returns
    -------
    list[str]
        Seed ids followed by their one-hop neighbours, de-duplicated and capped.
    """
    seeds = await source.search_seeds(query, config.INGEST_SEED_LIMIT)
    work_ids = [seed.openalex_id for seed in seeds]
    expansions = await asyncio.gather(*(_expand_seed(source, seed.openalex_id) for seed in seeds))
    for neighbour_ids in expansions:
        work_ids.extend(neighbour_ids)
    return list(dict.fromkeys(work_ids))[: config.INGEST_MAX_PAPERS]


async def _expand_seed(source: LiteratureSource, seed_id: str) -> list[str]:
    """Return a seed's one-hop neighbour ids: its references and its citers.

    Parameters
    ----------
    source : LiteratureSource
        The literature source to expand through.
    seed_id : str
        The seed work's id.

    Returns
    -------
    list[str]
        The ids of the seed's outgoing references and incoming citations.
    """
    references = await source.outgoing_refs(seed_id)
    citations = await source.incoming_citations(seed_id, config.INGEST_INCOMING_LIMIT)
    return [reference.openalex_id for reference in references] + [citation.openalex_id for citation in citations]


async def _store_papers(store: GraphVectorStore, papers: list[Paper], embedder: Embedder) -> None:
    """Embed the papers in one batch and upsert each into the store.

    Parameters
    ----------
    store : GraphVectorStore
        The store to write the papers to.
    papers : list[Paper]
        The papers to embed and store.
    embedder : Embedder
        The embedder used for the batch.
    """
    embeddings = await embedder.embed_batch([paper_embedding_text(paper) for paper in papers])
    for paper, embedding in zip(papers, embeddings, strict=True):
        await store.upsert_paper(paper, embedding)


async def _link_citations(store: GraphVectorStore, works: list[Work], ingested_ids: set[str]) -> None:
    """Add a CITES edge for each reference whose target was also ingested.

    Parameters
    ----------
    store : GraphVectorStore
        The store to write the edges to.
    works : list[Work]
        The ingested works carrying their referenced ids.
    ingested_ids : set[str]
        The ids of papers present in the corpus, to keep edges internal.
    """
    for work in works:
        for referenced_id in work.referenced_works:
            if referenced_id in ingested_ids:
                await store.upsert_edge(Edge(src=work.openalex_id, dst=referenced_id, kind=EdgeKind.CITES))


def _to_paper(work: Work) -> Paper:
    """Project a fetched work into the paper node stored in the graph.

    Parameters
    ----------
    work : Work
        The fetched work, with corpus-only fields dropped.

    Returns
    -------
    Paper
        The paper node carrying the work's stored fields.
    """
    return Paper(
        openalex_id=work.openalex_id,
        doi=work.doi,
        title=work.title,
        year=work.year,
        abstract=work.abstract,
        cited_by=work.cited_by,
        is_retracted=work.is_retracted,
        venue=work.venue,
    )
