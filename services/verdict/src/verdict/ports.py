"""Swap-boundary ports the core, retrieval, and council depend on."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic_ai.models import Model

from verdict.models import Edge, Paper, Subgraph, Work, WorkRef


@runtime_checkable
class GraphVectorStore(Protocol):
    """Graph + vector store: vector recall plus citation-graph traversal."""

    async def upsert_paper(self, paper: Paper, embedding: list[float]) -> None:
        """Store a paper node and its embedding vector atomically.

        Parameters
        ----------
        paper : Paper
            The paper node to store.
        embedding : list[float]
            The paper's abstract embedding, kept for cosine recall.
        """

    async def upsert_edge(self, edge: Edge) -> None:
        """Store a directed edge between two nodes.

        Parameters
        ----------
        edge : Edge
            The edge to store.
        """

    async def recall_papers(self, query_vec: list[float], k: int) -> list[Paper]:
        """Return the papers whose embeddings are nearest the query vector.

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

    async def evidence_neighbourhood(self, paper_id: str) -> Subgraph:
        """Return a paper's cited, citing, and topic neighbours with their edges.

        Parameters
        ----------
        paper_id : str
            The focal paper's id.

        Returns
        -------
        Subgraph
            The neighbour papers and the edges touching the focal paper.
        """

    async def foundations_for_query(self, query_vec: list[float], k: int, min_cited: int) -> Subgraph:
        """Return the most-cited papers near the query, filtered by citation count.

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


@runtime_checkable
class Embedder(Protocol):
    """Paper embedder over title + abstract for vector recall."""

    async def embed(self, text: str) -> list[float]:
        """Embed a single text into a vector.

        Parameters
        ----------
        text : str
            The text to embed.

        Returns
        -------
        list[float]
            The embedding vector.
        """

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors.

        Parameters
        ----------
        texts : Sequence[str]
            The texts to embed.

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, in order.
        """


@runtime_checkable
class TextEmbedder(Protocol):
    """General prose embedder for council member-draft epistemic uncertainty."""

    async def embed(self, text: str) -> list[float]:
        """Embed a prose draft into a vector.

        Parameters
        ----------
        text : str
            The prose to embed.

        Returns
        -------
        list[float]
            The embedding vector.
        """


@runtime_checkable
class LiteratureSource(Protocol):
    """Corpus adapter: seed search, work fetch, and citation expansion."""

    async def search_seeds(self, query: str, limit: int) -> list[WorkRef]:
        """Return seed works matching a claim query.

        Parameters
        ----------
        query : str
            The claim or search query.
        limit : int
            The maximum number of seed works to return.

        Returns
        -------
        list[WorkRef]
            References to the matching seed works.
        """

    async def fetch_work(self, work_id: str) -> Work:
        """Fetch a single work with its abstract and metadata.

        Parameters
        ----------
        work_id : str
            The source identifier of the work.

        Returns
        -------
        Work
            The fetched work.
        """

    async def outgoing_refs(self, work_id: str) -> list[WorkRef]:
        """Return the works a given work cites.

        Parameters
        ----------
        work_id : str
            The citing work's identifier.

        Returns
        -------
        list[WorkRef]
            References to the cited works.
        """

    async def incoming_citations(self, work_id: str, limit: int) -> list[WorkRef]:
        """Return works that cite a given work.

        Parameters
        ----------
        work_id : str
            The cited work's identifier.
        limit : int
            The maximum number of citing works to return.

        Returns
        -------
        list[WorkRef]
            References to the citing works.
        """


@runtime_checkable
class ModelProvider(Protocol):
    """Role-keyed LLM provider: cheap pass, council members, chairman."""

    def cheap_model(self) -> Model:
        """Return the cheap single-pass model.

        Returns
        -------
        Model
            The model used for the cheap verdict.
        """

    def member_models(self) -> list[Model]:
        """Return the cross-family council member models.

        Returns
        -------
        list[Model]
            The council member models.
        """

    def chairman_model(self) -> Model:
        """Return the chairman synthesis model.

        Returns
        -------
        Model
            The model used for chairman synthesis.
        """
