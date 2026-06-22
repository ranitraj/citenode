"""HelixDB v3 graph+vector store: dynamic queries over a local instance."""

import asyncio
from typing import Any

from helixdb import Client, NodeRef, Predicate, Projection, g, read_batch, write_batch

from verdict import config
from verdict.models import Edge, Paper, Subgraph

_PAPER_FIELDS = ("openalex_id", "doi", "title", "year", "abstract", "cited_by", "is_retracted", "venue")


class HelixGraphVectorStore:
    """GraphVectorStore backed by a local HelixDB v3 instance over dynamic queries.

    The helixdb client is synchronous; each call is offloaded to a worker thread
    so the event loop stays responsive. HelixDB traversal is single-threaded, so
    concurrent calls serialise at the engine.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    async def ensure_schema(self) -> None:
        """Create the paper vector index if it does not already exist.

        The index must exist before any paper is inserted; papers added without
        it are silently unsearchable. The call is idempotent.
        """
        batch = (
            write_batch()
            .var_as(
                "index", g().create_vector_index_nodes(config.HELIX_PAPER_LABEL, config.HELIX_EMBEDDING_FIELD, None)
            )
            .returning(["index"])
        )
        await self._write(batch, "ensure_schema")

    async def upsert_paper(self, paper: Paper, embedding: list[float]) -> None:
        """Store a paper node and its embedding, replacing any existing one.

        Parameters
        ----------
        paper : Paper
            The paper node to store.
        embedding : list[float]
            The paper's abstract embedding, kept for vector recall.
        """
        batch = (
            write_batch()
            .var_as("old", _paper_by_id(paper.openalex_id).drop())
            .var_as("new", g().add_n(config.HELIX_PAPER_LABEL, _paper_props(paper, embedding)))
            .returning(["new"])
        )
        await self._write(batch, "upsert_paper")

    async def upsert_edge(self, edge: Edge) -> None:
        """Store a directed edge between two existing paper nodes.

        Parameters
        ----------
        edge : Edge
            The edge to store; its endpoints are matched by ``openalex_id``.
        """
        batch = (
            write_batch()
            .var_as("src", _paper_by_id(edge.src))
            .var_as("dst", _paper_by_id(edge.dst))
            .var_as("edge", g().n(NodeRef.var("src")).add_e(edge.kind, NodeRef.var("dst")))
            .returning(["edge"])
        )
        await self._write(batch, "upsert_edge")

    async def recall_papers(self, query_vec: list[float], k: int) -> list[Paper]:
        """Return the k papers whose embeddings are nearest the query vector.

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
        batch = (
            read_batch()
            .var_as(
                "hits",
                g()
                .vector_search_nodes(config.HELIX_PAPER_LABEL, config.HELIX_EMBEDDING_FIELD, query_vec, k)
                .project([Projection.property(field) for field in _PAPER_FIELDS]),
            )
            .returning(["hits"])
        )
        result = await self._read(batch, "recall_papers")
        return [_to_paper(props) for props in result["hits"]["properties"]]

    async def evidence_neighbourhood(self, paper_id: str) -> Subgraph:
        """Return a paper's cited and citing neighbours with their cites edges.

        Parameters
        ----------
        paper_id : str
            The focal paper's openalex id.

        Returns
        -------
        Subgraph
            The neighbour papers and the cites edges touching the focal paper;
            empty when the paper is unknown.
        """
        fields = list(_PAPER_FIELDS)
        batch = (
            read_batch()
            .var_as("cited", _paper_by_id(paper_id).out("cites").dedup().value_map(fields))
            .var_as("citing", _paper_by_id(paper_id).in_("cites").dedup().value_map(fields))
            .returning(["cited", "citing"])
        )
        result = await self._read(batch, "evidence_neighbourhood")
        cited = [_to_paper(props) for props in result["cited"]["properties"]]
        citing = [_to_paper(props) for props in result["citing"]["properties"]]
        edges = [Edge(src=paper_id, dst=p.openalex_id, kind="cites") for p in cited]
        edges += [Edge(src=p.openalex_id, dst=paper_id, kind="cites") for p in citing]
        return Subgraph(papers=cited + citing, edges=edges)

    async def _read(self, batch: Any, name: str) -> Any:
        """Send a read batch to the instance and return its parsed response.

        Parameters
        ----------
        batch : Any
            The read batch to execute.
        name : str
            A query name carried for instance-side diagnostics.

        Returns
        -------
        Any
            The parsed JSON response.
        """
        request = batch.to_dynamic_request(query_name=name)
        return await asyncio.to_thread(lambda: self._client.query().dynamic(request).send())

    async def _write(self, batch: Any, name: str) -> Any:
        """Send a durable write batch to the instance and return its response.

        Parameters
        ----------
        batch : Any
            The write batch to execute.
        name : str
            A query name carried for instance-side diagnostics.

        Returns
        -------
        Any
            The parsed JSON response.
        """
        request = batch.to_dynamic_request(query_name=name)
        return await asyncio.to_thread(
            lambda: self._client.query().writer_only().should_await_durability(True).dynamic(request).send()
        )


def _paper_by_id(openalex_id: str) -> Any:
    """Build a traversal anchoring on the paper with the given openalex id.

    Parameters
    ----------
    openalex_id : str
        The paper's openalex id.

    Returns
    -------
    Any
        A traversal starting at the matching paper node.
    """
    return g().n_with_label(config.HELIX_PAPER_LABEL).where(Predicate.eq("openalex_id", openalex_id))


def _paper_props(paper: Paper, embedding: list[float]) -> dict[str, Any]:
    """Build the HelixDB property map for a paper node.

    Parameters
    ----------
    paper : Paper
        The paper to store.
    embedding : list[float]
        The abstract embedding stored under the vector field.

    Returns
    -------
    dict[str, Any]
        The property map; None-valued optional fields are omitted.
    """
    props: dict[str, Any] = {
        "openalex_id": paper.openalex_id,
        "title": paper.title,
        "abstract": paper.abstract,
        "year": paper.year,
        "cited_by": paper.cited_by,
        "is_retracted": paper.is_retracted,
        config.HELIX_EMBEDDING_FIELD: embedding,
    }
    if paper.doi is not None:
        props["doi"] = paper.doi
    if paper.venue is not None:
        props["venue"] = paper.venue
    return props


def _to_paper(props: dict[str, Any]) -> Paper:
    """Reconstruct a Paper from a HelixDB property map.

    Parameters
    ----------
    props : dict[str, Any]
        The node properties returned by a query.

    Returns
    -------
    Paper
        The reconstructed paper; absent optional fields become None.
    """
    return Paper(
        openalex_id=props["openalex_id"],
        doi=props.get("doi"),
        title=props["title"],
        year=props["year"],
        abstract=props["abstract"],
        cited_by=props["cited_by"],
        is_retracted=props["is_retracted"],
        venue=props.get("venue"),
    )
