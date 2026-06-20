"""In-memory graph+vector store for infra-free tests."""

from verdict.models import Edge, Paper, Subgraph
from verdict.vectors import cosine_similarity


class InMemoryGraphVectorStore:
    """Brute-force cosine recall plus dict-backed edges, with no external engine."""

    def __init__(self) -> None:
        self._papers: dict[str, Paper] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._edges: list[Edge] = []

    async def upsert_paper(self, paper: Paper, embedding: list[float]) -> None:
        """Store a paper node and its embedding vector.

        Parameters
        ----------
        paper : Paper
            The paper node to store.
        embedding : list[float]
            The paper's abstract embedding, kept for cosine recall.
        """
        self._papers[paper.openalex_id] = paper
        self._embeddings[paper.openalex_id] = embedding

    async def upsert_edge(self, edge: Edge) -> None:
        """Store a directed edge, de-duplicated.

        Parameters
        ----------
        edge : Edge
            The edge to store.
        """
        if edge not in self._edges:
            self._edges.append(edge)

    async def recall_papers(self, query_vec: list[float], k: int) -> list[Paper]:
        """Return the k papers whose embeddings are nearest the query by cosine.

        Parameters
        ----------
        query_vec : list[float]
            The query embedding.
        k : int
            The maximum number of papers to return.

        Returns
        -------
        list[Paper]
            Up to k papers, most similar first.
        """
        ranked = self._rank_by_cosine(query_vec, list(self._papers))
        return [self._papers[pid] for pid, _ in ranked[:k]]

    async def evidence_neighbourhood(self, paper_id: str) -> Subgraph:
        """Return a paper's cited, citing, and topic neighbours with their edges.

        Parameters
        ----------
        paper_id : str
            The focal paper's id.

        Returns
        -------
        Subgraph
            The neighbour papers and the edges touching the focal paper; empty
            when the paper is unknown.
        """
        if paper_id not in self._papers:
            return Subgraph(papers=[], edges=[])
        edges = [e for e in self._edges if paper_id in (e.src, e.dst)]
        neighbour_ids = ({e.src for e in edges} | {e.dst for e in edges}) - {paper_id}
        papers = [self._papers[pid] for pid in neighbour_ids if pid in self._papers]
        return Subgraph(papers=papers, edges=edges)

    async def foundations_for_query(self, query_vec: list[float], k: int, min_cited: int) -> Subgraph:
        """Return the most-cited papers near the query, filtered by min_cited.

        Parameters
        ----------
        query_vec : list[float]
            The query embedding.
        k : int
            The maximum number of foundational papers to return.
        min_cited : int
            The minimum citation count a paper must have to qualify.

        Returns
        -------
        Subgraph
            The qualifying papers nearest the query and the edges among them.
        """
        eligible = [pid for pid, p in self._papers.items() if p.cited_by >= min_cited]
        ranked = self._rank_by_cosine(query_vec, eligible)
        papers = [self._papers[pid] for pid, _ in ranked[:k]]
        kept = {p.openalex_id for p in papers}
        edges = [e for e in self._edges if e.src in kept and e.dst in kept]
        return Subgraph(papers=papers, edges=edges)

    def _rank_by_cosine(self, query_vec: list[float], ids: list[str]) -> list[tuple[str, float]]:
        """Rank paper ids by descending cosine similarity to the query vector.

        Parameters
        ----------
        query_vec : list[float]
            The query embedding.
        ids : list[str]
            The candidate paper ids to score.

        Returns
        -------
        list[tuple[str, float]]
            (paper id, similarity) pairs sorted by descending similarity.
        """
        scored = [(pid, cosine_similarity(query_vec, self._embeddings[pid])) for pid in ids]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored
