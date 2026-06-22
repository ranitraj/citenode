"""Embeddings adapter: one model serves papers, query, and prose over HTTP."""

from collections.abc import Sequence

import httpx

from verdict import config


class EmbeddingServiceClient:
    """Embedder backed by a Text Embeddings Inference (TEI) service over HTTP.

    Backs both the ``Embedder`` and ``TextEmbedder`` ports: one model, one vector
    space for papers, the query, and Council prose. The caller owns the HTTP client.
    """

    def __init__(self, base_url: str, *, http_client: httpx.AsyncClient) -> None:
        self._embed_endpoint = f"{base_url}{config.EMBEDDINGS_EMBED_PATH}"
        self._http_client = http_client

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
        vectors = await self._request_embeddings(text)
        return vectors[0]

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
        return await self._request_embeddings(list(texts))

    async def _request_embeddings(self, inputs: str | list[str]) -> list[list[float]]:
        """POST inputs to the embeddings endpoint and return its vectors.

        Parameters
        ----------
        inputs : str | list[str]
            A single text or a batch of texts.

        Returns
        -------
        list[list[float]]
            One vector per input, as returned by the service.

        Raises
        ------
        httpx.HTTPStatusError
            If the service returns a non-success status.
        """
        response = await self._http_client.post(self._embed_endpoint, json={"inputs": inputs})
        response.raise_for_status()
        vectors: list[list[float]] = response.json()
        return vectors
