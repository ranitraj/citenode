"""Ollama embeddings adapter over a local server's /api/embed endpoint."""

from collections.abc import Sequence

import httpx


class OllamaEmbedder:
    """Embedder backed by a local Ollama server, for the Embedder and TextEmbedder ports."""

    def __init__(self, base_url: str, *, http_client: httpx.AsyncClient, model: str) -> None:
        self._embed_endpoint = f"{base_url}/api/embed"
        self._http_client = http_client
        self._model = model

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
        """POST inputs to the embed endpoint and return its vectors.

        Parameters
        ----------
        inputs : str | list[str]
            A single text or a batch of texts.

        Returns
        -------
        list[list[float]]
            One vector per input, as returned by the server.

        Raises
        ------
        httpx.HTTPStatusError
            If the server returns a non-success status.
        """
        response = await self._http_client.post(self._embed_endpoint, json={"model": self._model, "input": inputs})
        response.raise_for_status()
        vectors: list[list[float]] = response.json()["embeddings"]
        return vectors
