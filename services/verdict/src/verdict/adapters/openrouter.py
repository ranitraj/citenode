"""OpenRouter ModelProvider: role-keyed OpenAI-compatible models over OpenRouter."""

from collections.abc import Sequence

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openrouter import OpenRouterProvider

# Route only through providers that do not log or train on prompts (OpenRouter preference).
_PRIVATE_ROUTING: OpenAIChatModelSettings = {"extra_body": {"provider": {"data_collection": "deny"}}}


class OpenRouterModelProvider:
    """ModelProvider backed by OpenRouter, exposing role-keyed cross-family models.

    Every model is built with data collection denied, so providers that log or
    train on prompts are excluded from routing.
    """

    def __init__(self, *, api_key: str, cheap_model: str, member_models: Sequence[str], chairman_model: str) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key is required; set OPENROUTER_API_KEY in the environment.")
        self._provider = OpenRouterProvider(api_key=api_key)
        self._cheap_model = cheap_model
        self._member_models = list(member_models)
        self._chairman_model = chairman_model

    def cheap_model(self) -> Model:
        """Return the cheap single-pass model.

        Returns
        -------
        Model
            The model used for the cheap verdict.
        """
        return self._build(self._cheap_model)

    def member_models(self) -> list[Model]:
        """Return the cross-family council member models.

        Returns
        -------
        list[Model]
            The council member models.
        """
        return [self._build(name) for name in self._member_models]

    def chairman_model(self) -> Model:
        """Return the chairman synthesis model.

        Returns
        -------
        Model
            The model used for chairman synthesis.
        """
        return self._build(self._chairman_model)

    def _build(self, model_name: str) -> Model:
        """Build a privacy-routed OpenAI-compatible model for an OpenRouter id.

        Parameters
        ----------
        model_name : str
            The OpenRouter model identifier.

        Returns
        -------
        Model
            The configured model.
        """
        return OpenAIChatModel(model_name, provider=self._provider, settings=_PRIVATE_ROUTING)
