"""Tests for anonymized council peer-ranking."""

from verdict.council.rank import peer_rank
from verdict.models import MemberVerdict, Verdict

from tests.model_stubs import council_provider, failing_model, ranking_by_marker, text_function_model


def _drafts(names: list[str]) -> dict[str, MemberVerdict]:
    return {
        name: MemberVerdict(verdict=Verdict.SUPPORTED, supporting_ids=[], contradicting_ids=[], rationale=name)
        for name in names
    }


def _ranker_by_marker(name: str) -> object:
    return text_function_model(ranking_by_marker, model_name=name)


def _ranker_text(name: str, text: str) -> object:
    return text_function_model(lambda _prompt: text, model_name=name)


async def test_peer_rank_de_anonymises_each_ranker_into_model_order():
    drafts = _drafts(["m0", "m1", "m2", "m3"])
    provider = council_provider(members=[_ranker_by_marker(f"r{index}") for index in range(4)])

    rankings = await peer_rank("a claim", drafts, provider=provider)

    assert set(rankings) == {"r0", "r1", "r2", "r3"}
    assert all(ranking.resolved_ranking == ["m0", "m1", "m2", "m3"] for ranking in rankings.values())


async def test_peer_rank_drops_a_ranker_with_a_malformed_ranking():
    drafts = _drafts(["m0", "m1", "m2", "m3"])
    provider = council_provider(members=[_ranker_by_marker("r0"), _ranker_text("r1", "I will not rank these.")])

    rankings = await peer_rank("a claim", drafts, provider=provider)

    assert set(rankings) == {"r0"}


async def test_peer_rank_drops_a_ranker_that_errors():
    drafts = _drafts(["m0", "m1", "m2", "m3"])
    provider = council_provider(members=[_ranker_by_marker("r0"), failing_model(model_name="r1")])

    rankings = await peer_rank("a claim", drafts, provider=provider)

    assert set(rankings) == {"r0"}


async def test_peer_rank_ignores_hallucinated_response_labels():
    drafts = _drafts(["m0", "m1"])
    provider = council_provider(members=[_ranker_text("r0", "FINAL RANKING:\n1. Response A\n2. Response Z\n")])

    rankings = await peer_rank("a claim", drafts, provider=provider)

    assert rankings["r0"].resolved_ranking == [next(iter(rankings["r0"].resolved_ranking))]
    assert rankings["r0"].resolved_ranking[0] in {"m0", "m1"}
