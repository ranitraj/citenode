"""Shared pydantic-ai model stubs for tests."""

from collections.abc import Callable
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


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
