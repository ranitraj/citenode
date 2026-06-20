"""Walking-skeleton test: verify_claim threads a ClaimResult end-to-end on stubs."""

from unittest.mock import MagicMock

from pydantic_ai.models.test import TestModel
from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.models import ClaimResult, Path, Verdict
from verdict.pipeline import CitenodeDeps, verify_claim


def _make_deps() -> CitenodeDeps:
    provider = MagicMock()
    provider.cheap_model.return_value = TestModel()
    return CitenodeDeps(
        store=InMemoryGraphVectorStore(),
        embedder=MagicMock(),
        text_embedder=MagicMock(),
        source=MagicMock(),
        provider=provider,
        k=5,
        escalation_threshold=0.1,
    )


async def test_verify_claim_threads_a_cheap_claim_result_end_to_end():
    result = await verify_claim("Transformers improved machine translation.", deps=_make_deps())
    assert isinstance(result, ClaimResult)
    assert result.path is Path.CHEAP
    assert result.verdict in set(Verdict)
    assert 0.0 <= result.confidence.score <= 1.0
    assert result.claim == "Transformers improved machine translation."


async def test_verify_claim_persists_nothing_between_runs():
    deps = _make_deps()
    first = await verify_claim("Claim one.", deps=deps)
    second = await verify_claim("Claim two.", deps=deps)
    assert first.claim == "Claim one."
    assert second.claim == "Claim two."
