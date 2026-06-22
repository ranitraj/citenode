"""Tests for the TEI-backed embeddings adapter."""

import json

import httpx
import pytest
from verdict.adapters.embeddings import EmbeddingServiceClient
from verdict.ports import Embedder, TextEmbedder

BASE_URL = "http://embeddings.test"


def _mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_embed_posts_single_input_and_returns_vector():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=[[0.1, 0.2, 0.3]])

    embedder = EmbeddingServiceClient(BASE_URL, http_client=_mock_client(handler))
    vector = await embedder.embed("deep learning works")

    assert vector == [0.1, 0.2, 0.3]
    assert seen["url"] == f"{BASE_URL}/embed"
    assert seen["body"] == {"inputs": "deep learning works"}


async def test_embed_batch_posts_list_and_preserves_order():
    def handler(request):
        inputs = json.loads(request.content)["inputs"]
        return httpx.Response(200, json=[[float(i)] for i, _ in enumerate(inputs)])

    embedder = EmbeddingServiceClient(BASE_URL, http_client=_mock_client(handler))
    vectors = await embedder.embed_batch(["a", "b", "c"])

    assert vectors == [[0.0], [1.0], [2.0]]


async def test_satisfies_both_embedder_ports():
    embedder = EmbeddingServiceClient(BASE_URL, http_client=_mock_client(lambda _r: httpx.Response(200, json=[[0.0]])))

    assert isinstance(embedder, Embedder)
    assert isinstance(embedder, TextEmbedder)


async def test_server_error_propagates():
    embedder = EmbeddingServiceClient(BASE_URL, http_client=_mock_client(lambda _r: httpx.Response(503)))

    with pytest.raises(httpx.HTTPStatusError):
        await embedder.embed("x")
