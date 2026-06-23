"""Tests for anonymized council peer-ranking."""

import re

from verdict.council.rank import peer_rank
from verdict.models import MemberVerdict, Verdict

from tests.model_stubs import failing_model, text_function_model


def _drafts(names: list[str]) -> dict[str, MemberVerdict]:
    return {
        name: MemberVerdict(verdict=Verdict.SUPPORTED, supporting_ids=[], contradicting_ids=[], rationale=name)
        for name in names
    }


class _Provider:
    def __init__(self, rankers):
        self._rankers = rankers

    def member_models(self):
        """Return the stub ranker models."""
        return self._rankers


def _label_markers(prompt: str) -> dict[str, str]:
    headers = list(re.finditer(r"Response ([A-Z]):", prompt))
    markers: dict[str, str] = {}
    for index, header in enumerate(headers):
        start = header.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(prompt)
        found = re.search(r"m\d", prompt[start:end])
        if found:
            markers[header.group(1)] = found.group(0)
    return markers


def _ranker_by_marker(name: str) -> object:
    def decide(prompt: str) -> str:
        markers = _label_markers(prompt)
        ordered = sorted(markers, key=lambda label: markers[label])
        lines = "\n".join(f"{position}. Response {label}" for position, label in enumerate(ordered, start=1))
        return f"CRITERIA SCORES:\nResponse A: Faithfulness=4/5\n\nFINAL RANKING:\n{lines}\n"

    return text_function_model(decide, model_name=name)


def _ranker_text(name: str, text: str) -> object:
    return text_function_model(lambda _prompt: text, model_name=name)


async def test_peer_rank_de_anonymises_each_ranker_into_model_order():
    drafts = _drafts(["m0", "m1", "m2", "m3"])
    provider = _Provider([_ranker_by_marker(f"r{index}") for index in range(4)])

    rankings = await peer_rank("a claim", drafts, provider=provider)

    assert set(rankings) == {"r0", "r1", "r2", "r3"}
    assert all(ranking.resolved_ranking == ["m0", "m1", "m2", "m3"] for ranking in rankings.values())


async def test_peer_rank_drops_a_ranker_with_a_malformed_ranking():
    drafts = _drafts(["m0", "m1", "m2", "m3"])
    provider = _Provider([_ranker_by_marker("r0"), _ranker_text("r1", "I will not rank these.")])

    rankings = await peer_rank("a claim", drafts, provider=provider)

    assert set(rankings) == {"r0"}


async def test_peer_rank_drops_a_ranker_that_errors():
    drafts = _drafts(["m0", "m1", "m2", "m3"])
    provider = _Provider([_ranker_by_marker("r0"), failing_model(model_name="r1")])

    rankings = await peer_rank("a claim", drafts, provider=provider)

    assert set(rankings) == {"r0"}


async def test_peer_rank_ignores_hallucinated_response_labels():
    drafts = _drafts(["m0", "m1"])
    provider = _Provider([_ranker_text("r0", "FINAL RANKING:\n1. Response A\n2. Response Z\n")])

    rankings = await peer_rank("a claim", drafts, provider=provider)

    assert rankings["r0"].resolved_ranking == [next(iter(rankings["r0"].resolved_ranking))]
    assert rankings["r0"].resolved_ranking[0] in {"m0", "m1"}
