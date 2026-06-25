"""Tests for the Ollama-backed embeddings adapter."""

import json

import httpx
import pytest
from verdict.adapters.ollama_embeddings import OllamaEmbedder
from verdict.ports import Embedder, TextEmbedder

from tests.http_support import mock_client

BASE_URL = "http://ollama.test"
MODEL = "qwen3-embedding:0.6b"


def _embedder(handler):
    return OllamaEmbedder(BASE_URL, http_client=mock_client(handler), model=MODEL)


async def test_embed_posts_model_and_single_input_and_returns_vector():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})

    vector = await _embedder(handler).embed("deep learning works")

    assert vector == [0.1, 0.2, 0.3]
    assert seen["url"] == f"{BASE_URL}/api/embed"
    assert seen["body"] == {"model": MODEL, "input": "deep learning works"}


async def test_embed_batch_posts_list_and_preserves_order():
    def handler(request):
        inputs = json.loads(request.content)["input"]
        return httpx.Response(200, json={"embeddings": [[float(index)] for index, _ in enumerate(inputs)]})

    vectors = await _embedder(handler).embed_batch(["a", "b", "c"])

    assert vectors == [[0.0], [1.0], [2.0]]


async def test_satisfies_both_embedder_ports():
    embedder = _embedder(lambda _r: httpx.Response(200, json={"embeddings": [[0.0]]}))

    assert isinstance(embedder, Embedder)
    assert isinstance(embedder, TextEmbedder)


async def test_server_error_propagates():
    embedder = _embedder(lambda _r: httpx.Response(503))

    with pytest.raises(httpx.HTTPStatusError):
        await embedder.embed("x")
