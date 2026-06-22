"""Shared helpers for HelixDB integration tests."""

import asyncio

import httpx
from helixdb import Client, g, write_batch
from verdict import config
from verdict.adapters.helix_store import HelixGraphVectorStore


def helix_instance_up() -> bool:
    """Return True if the local HelixDB query endpoint answers."""
    try:
        return httpx.get(f"{config.HELIX_URL}/v1/query", timeout=2.0).status_code == 405
    except httpx.HTTPError:
        return False


async def fresh_helix_store() -> HelixGraphVectorStore:
    """Return a store against an empty graph: index ensured, all papers dropped."""
    store = HelixGraphVectorStore(Client(config.HELIX_URL))
    await store.ensure_schema()
    drop = write_batch().var_as("d", g().n_with_label(config.HELIX_PAPER_LABEL).drop()).returning(["d"])
    await asyncio.to_thread(
        lambda: Client(config.HELIX_URL)
        .query()
        .writer_only()
        .should_await_durability(True)
        .dynamic(drop.to_dynamic_request())
        .send()
    )
    return store
