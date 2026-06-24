"""Shared pydantic-ai model stubs for tests."""

import re
from collections.abc import Callable
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from verdict.models import Stance, Verdict
from verdict.ports import ModelProvider


def user_text(messages: list[ModelMessage]) -> str:
    """Return the text of the latest user prompt in a message history.

    Parameters
    ----------
    messages : list[ModelMessage]
        The message history passed to the model.

    Returns
    -------
    str
        The latest user prompt's text, or an empty string when none is found.
    """
    for message in reversed(messages):
        for part in message.parts:
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                return part.content
    return ""


def structured_function_model(
    decide: Callable[[str], dict[str, Any]], *, model_name: str | None = None
) -> FunctionModel:
    """Build a model that emits one structured output per run from the prompt.

    Parameters
    ----------
    decide : Callable[[str], dict[str, Any]]
        Maps the latest user prompt text to the output tool's argument dict.
    model_name : str | None
        An identity for the model, used where callers key results by model name.

    Returns
    -------
    FunctionModel
        A model returning the output tool call built from ``decide``.
    """

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        args = decide(user_text(messages))
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=args)])

    return FunctionModel(respond, model_name=model_name)


def text_function_model(decide: Callable[[str], str], *, model_name: str | None = None) -> FunctionModel:
    """Build a model that emits one plain-text response per run from the prompt.

    Parameters
    ----------
    decide : Callable[[str], str]
        Maps the latest user prompt text to the model's text reply.
    model_name : str | None
        An identity for the model, used where callers key results by model name.

    Returns
    -------
    FunctionModel
        A model returning the text built from ``decide``.
    """

    def respond(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=decide(user_text(messages)))])

    return FunctionModel(respond, model_name=model_name)


def draft_verdict_model(
    verdict: Verdict,
    *,
    marker: str | None = None,
    fallback: Verdict = Verdict.INSUFFICIENT,
    model_name: str | None = None,
) -> FunctionModel:
    """Build a model returning ``verdict`` when ``marker`` is in the prompt, else ``fallback``.

    Parameters
    ----------
    verdict : Verdict
        The verdict to return on a match.
    marker : str | None
        Text that must appear in the prompt to return ``verdict``; ``None`` always matches.
    fallback : Verdict
        The verdict returned when ``marker`` is set but absent from the prompt.
    model_name : str | None
        An identity for the model.

    Returns
    -------
    FunctionModel
        A model emitting a ``DraftVerdict`` argument dict.
    """

    def decide(prompt: str) -> dict[str, Any]:
        chosen = verdict if marker is None or marker in prompt else fallback
        return {"verdict": chosen.value, "rationale": "because", "self_uncertainty": 0.2}

    return structured_function_model(decide, model_name=model_name)


def member_verdict_model(
    *, supporting: list[str], contradicting: list[str] | None = None, model_name: str | None = None
) -> FunctionModel:
    """Build a council member that cites ``supporting`` and ``contradicting`` ids.

    Parameters
    ----------
    supporting : list[str]
        The ids the member asserts support the claim.
    contradicting : list[str] | None
        The ids the member asserts contradict the claim.
    model_name : str | None
        An identity for the model, used where results are keyed by model name.

    Returns
    -------
    FunctionModel
        A model emitting a ``MemberVerdict`` argument dict.
    """

    def decide(_prompt: str) -> dict[str, Any]:
        return {
            "verdict": Verdict.SUPPORTED.value,
            "supporting_ids": supporting,
            "contradicting_ids": contradicting or [],
            "rationale": "r",
        }

    return structured_function_model(decide, model_name=model_name)


def chairman_verdict_model(
    *,
    verdict: Verdict,
    supporting: list[str] | None = None,
    contradicting: list[str] | None = None,
    synthesis: str = "synthesis",
    dissent: str | None = None,
) -> FunctionModel:
    """Build a chairman that emits a synthesis verdict over the member drafts.

    Parameters
    ----------
    verdict : Verdict
        The reconciled verdict to return.
    supporting : list[str] | None
        The ids the chairman cites as supporting the claim.
    contradicting : list[str] | None
        The ids the chairman cites as contradicting the claim.
    synthesis : str
        The chairman's prose synthesis.
    dissent : str | None
        The minority report, or ``None`` when the members did not meaningfully disagree.

    Returns
    -------
    FunctionModel
        A model emitting a ``ChairmanVerdict`` argument dict.
    """

    def decide(_prompt: str) -> dict[str, Any]:
        return {
            "verdict": verdict.value,
            "supporting_ids": supporting or [],
            "contradicting_ids": contradicting or [],
            "synthesis": synthesis,
            "dissent": dissent,
        }

    return structured_function_model(decide)


def ranking_by_marker(prompt: str) -> str:
    """Build a ``FINAL RANKING`` block ordering the ``Response`` labels by their m-marker.

    Each labeled draft carries an ``m<digit>`` marker (its member's rationale); the
    labels are ordered by that marker so every ranker returns the same ordering,
    making the peer ranking deterministic regardless of the per-ranker shuffle.

    Parameters
    ----------
    prompt : str
        The rendered rank-stage user prompt.

    Returns
    -------
    str
        A ``FINAL RANKING:`` block, or one with no lines when no markers are found.
    """
    headers = list(re.finditer(r"Response ([A-Z]):", prompt))
    markers: dict[str, str] = {}
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(prompt)
        found = re.search(r"m\d", prompt[header.end() : end])
        if found:
            markers[header.group(1)] = found.group(0)
    ordered = sorted(markers, key=lambda label: markers[label])
    lines = "\n".join(f"{position}. Response {label}" for position, label in enumerate(ordered, start=1))
    return f"FINAL RANKING:\n{lines}\n"


def member_ranker_model(
    *,
    supporting: list[str] | None = None,
    contradicting: list[str] | None = None,
    verdict: Verdict = Verdict.SUPPORTED,
    model_name: str | None = None,
) -> FunctionModel:
    """Build a council model that drafts a member verdict and ranks by marker.

    Used where members also act as rankers: with output tools present it emits a
    ``MemberVerdict`` whose rationale is the model name (its ranking marker); with no
    output tools it returns a marker-ordered ``FINAL RANKING`` block.

    Parameters
    ----------
    supporting : list[str] | None
        The ids this member cites as supporting the claim.
    contradicting : list[str] | None
        The ids this member cites as contradicting the claim.
    verdict : Verdict
        The member's verdict.
    model_name : str | None
        The model identity, also used as the rationale marker for ranking.

    Returns
    -------
    FunctionModel
        A model that drafts as a member and ranks as a peer.
    """

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if info.output_tools:
            args = {
                "verdict": verdict.value,
                "supporting_ids": supporting or [],
                "contradicting_ids": contradicting or [],
                "rationale": model_name or "",
            }
            return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=args)])
        return ModelResponse(parts=[TextPart(content=ranking_by_marker(user_text(messages)))])

    return FunctionModel(respond, model_name=model_name)


def triage_model(
    *, checkable: bool, refined: str | None = None, marker: str | None = None, model_name: str | None = None
) -> FunctionModel:
    """Build a triage model, keyed on an optional prompt marker.

    Parameters
    ----------
    checkable : bool
        Whether the claim is checkable; downgraded to ``False`` when ``marker`` is absent.
    refined : str | None
        A sharper rewrite to return, or ``None``.
    marker : str | None
        Text that must appear in the prompt to keep ``checkable``; ``None`` always matches.
    model_name : str | None
        An identity for the model.

    Returns
    -------
    FunctionModel
        A model emitting a ``TriageResult`` argument dict.
    """

    def decide(prompt: str) -> dict[str, Any]:
        is_checkable = checkable if marker is None or marker in prompt else False
        return {"checkable": is_checkable, "refined_claim": refined, "reason": "because"}

    return structured_function_model(decide, model_name=model_name)


def stance_model(title_to_stance: dict[str, Stance], *, model_name: str | None = None) -> FunctionModel:
    """Build a model that returns a stance keyed on the paper title in the prompt.

    Parameters
    ----------
    title_to_stance : dict[str, Stance]
        Maps a paper title substring to the stance to return; defaults to neutral on no match.
    model_name : str | None
        An identity for the model.

    Returns
    -------
    FunctionModel
        A model emitting a ``StanceJudgement`` argument dict.
    """

    def decide(prompt: str) -> dict[str, Any]:
        stance = next((value for title, value in title_to_stance.items() if title in prompt), Stance.NEUTRAL)
        return {"stance": stance.value, "snippet": "snip", "rationale": "why"}

    return structured_function_model(decide, model_name=model_name)


def cheap_path_model(
    *,
    checkable: bool = True,
    stances: dict[str, Stance] | None = None,
    verdict: Verdict = Verdict.SUPPORTED,
    model_name: str | None = None,
) -> FunctionModel:
    """Build the cheap-path model that backs triage, stance scoring, and the cheap verdict.

    A single cheap model serves three pipeline stages; this stub inspects the requested
    output schema and returns the matching structured output: a triage result, a per-paper
    stance (keyed on the paper title present in the prompt), or a cheap draft verdict.

    Parameters
    ----------
    checkable : bool
        The triage checkability to return.
    stances : dict[str, Stance] | None
        A title-substring to stance map for stance scoring; defaults to supports.
    verdict : Verdict
        The cheap draft verdict to return.
    model_name : str | None
        An identity for the model.

    Returns
    -------
    FunctionModel
        A model that adapts its output to the calling stage's schema.
    """

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        properties = info.output_tools[0].parameters_json_schema.get("properties", {})
        if "checkable" in properties:
            args: dict[str, Any] = {"checkable": checkable, "refined_claim": None, "reason": "r"}
        elif "stance" in properties:
            prompt = user_text(messages)
            stance = next((value for title, value in (stances or {}).items() if title in prompt), Stance.SUPPORTS)
            args = {"stance": stance.value, "snippet": "snip", "rationale": "r"}
        else:
            args = {"verdict": verdict.value, "rationale": "r", "self_uncertainty": 0.1}
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=args)])

    return FunctionModel(respond, model_name=model_name)


def failing_model(*, model_name: str | None = None) -> FunctionModel:
    """Build a model whose every run raises, for quorum and fallback tests.

    Parameters
    ----------
    model_name : str | None
        An identity for the model.

    Returns
    -------
    FunctionModel
        A model that raises ``RuntimeError`` on each run.
    """

    def decide(_prompt: str) -> dict[str, Any]:
        raise RuntimeError("model crashed")

    return structured_function_model(decide, model_name=model_name)


def council_provider(
    *, cheap: Model | None = None, members: list[Model] | None = None, chairman: Model | None = None
) -> ModelProvider:
    """Build a provider stub exposing the cheap, member, and chairman models.

    Parameters
    ----------
    cheap : Model | None
        The cheap-path model (triage, stance, cheap verdict); requesting it without
        one configured raises.
    members : list[Model] | None
        The council member models, which also act as the rankers.
    chairman : Model | None
        The chairman model; requesting it without one configured raises.

    Returns
    -------
    ModelProvider
        A provider stub for the cheap pass and the council stages.
    """

    class _Provider:
        def cheap_model(self) -> Model:
            """Return the stub cheap model, or raise when none is configured."""
            if cheap is None:
                raise RuntimeError("council provider stub has no cheap model")
            return cheap

        def member_models(self) -> list[Model]:
            """Return the stub member models."""
            return members or []

        def chairman_model(self) -> Model:
            """Return the stub chairman model, or raise when none is configured."""
            if chairman is None:
                raise RuntimeError("council provider stub has no chairman model")
            return chairman

    return _Provider()
