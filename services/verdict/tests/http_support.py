"""Shared httpx test helpers."""

from collections.abc import Callable

import httpx


def mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    """Build an httpx async client backed by a mock transport handler."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
