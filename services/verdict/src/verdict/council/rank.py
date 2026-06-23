"""Anonymized council peer-ranking of member drafts."""

import asyncio
import random
import re
import string

from pydantic_ai import Agent
from pydantic_ai.models import Model

from verdict.models import MemberVerdict, RankingOutput
from verdict.ports import ModelProvider
from verdict.prompting import render_prompt

_RANKING_HEADER = "FINAL RANKING:"
_RANKING_LINE = re.compile(r"\d+\.\s*Response\s+([A-Z])")


async def peer_rank(
    claim: str, drafts: dict[str, MemberVerdict], *, provider: ModelProvider
) -> dict[str, RankingOutput]:
    """Peer-rank the member drafts, de-anonymizing each ranker into a model ordering.

    Each ranker sees the drafts under freshly shuffled ``Response`` labels to defeat
    position bias, emits the regex-parsed ``FINAL RANKING:`` text contract, and its
    ordering is mapped back to model names through that ranker's own label map. A
    ranker that raises or whose ranking does not parse is dropped, so a single weak
    model cannot stall the stage.

    Parameters
    ----------
    claim : str
        The claim the drafts verdicts address.
    drafts : dict[str, MemberVerdict]
        The member verdicts to rank, keyed by member model name.
    provider : ModelProvider
        The provider whose member models act as the rankers.

    Returns
    -------
    dict[str, RankingOutput]
        The de-anonymized ranking per ranker that produced a parseable ordering,
        keyed by ranker model name.
    """
    rankers = provider.member_models()
    results = await asyncio.gather(*(_rank_one(claim, drafts, ranker) for ranker in rankers), return_exceptions=True)
    return {
        ranker.model_name: ranking
        for ranker, ranking in zip(rankers, results, strict=True)
        if isinstance(ranking, RankingOutput) and ranking.resolved_ranking
    }


async def _rank_one(claim: str, drafts: dict[str, MemberVerdict], ranker: Model) -> RankingOutput:
    """Run one ranker over the shuffled drafts and resolve its ranking to model names.

    Parameters
    ----------
    claim : str
        The claim the drafts address.
    drafts : dict[str, MemberVerdict]
        The member verdicts to rank, keyed by member model name.
    ranker : Model
        The model producing this ranking.

    Returns
    -------
    RankingOutput
        The de-anonymized ordering; empty when the ranker's output does not parse.
    """
    responses, label_to_model = _anonymise(drafts)
    agent = Agent(model=ranker, system_prompt=render_prompt("rank_system.j2"))
    text = (await agent.run(render_prompt("rank_user.j2", claim=claim, responses=responses))).output
    return RankingOutput(resolved_ranking=_resolve_ranking(text, label_to_model))


def _anonymise(drafts: dict[str, MemberVerdict]) -> tuple[list[dict[str, object]], dict[str, str]]:
    """Shuffle the drafts under fresh ``Response`` labels, hiding model identity.

    Parameters
    ----------
    drafts : dict[str, MemberVerdict]
        The member verdicts, keyed by model name.

    Returns
    -------
    tuple[list[dict[str, object]], dict[str, str]]
        The labeled drafts to render (label and verdict only) and the label-to-model
        map used to de-anonymize the ranking.
    """
    items = list(drafts.items())
    random.shuffle(items)
    responses: list[dict[str, object]] = []
    label_to_model: dict[str, str] = {}
    for label, (model_name, verdict) in zip(string.ascii_uppercase, items, strict=False):
        label_to_model[label] = model_name
        responses.append({"label": label, "verdict": verdict})
    return responses, label_to_model


def _resolve_ranking(text: str, label_to_model: dict[str, str]) -> list[str]:
    """Parse the ``FINAL RANKING:`` block and map its labels back to model names.

    Parameters
    ----------
    text : str
        The ranker's raw text response.
    label_to_model : dict[str, str]
        This ranker's label-to-model map.

    Returns
    -------
    list[str]
        The ranked model names best to worst; empty when no ranking block is found.
        Unknown labels are ignored and duplicate labels keep their first position.
    """
    _, header, body = text.partition(_RANKING_HEADER)
    if not header:
        return []
    resolved: list[str] = []
    for label in _RANKING_LINE.findall(body):
        model_name = label_to_model.get(label)
        if model_name is not None and model_name not in resolved:
            resolved.append(model_name)
    return resolved
