"""Tests for the OpenRouter model provider and env-sourced settings."""

from collections.abc import Sequence

import pytest
from verdict.adapters.openrouter import OpenRouterModelProvider
from verdict.config import Settings


def _provider(*, api_key: str = "sk-test", members: Sequence[str] = ("m1:free", "m2:free", "m3:free", "m4:free")):
    return OpenRouterModelProvider(
        api_key=api_key, cheap_model="cheap:free", member_models=members, chairman_model="chair:free"
    )


def test_provider_returns_role_keyed_models():
    provider = _provider()

    assert provider.cheap_model().model_name == "cheap:free"
    assert [model.model_name for model in provider.member_models()] == ["m1:free", "m2:free", "m3:free", "m4:free"]
    assert provider.chairman_model().model_name == "chair:free"


def test_provider_denies_data_collection_on_every_model():
    provider = _provider()
    models = [provider.cheap_model(), provider.chairman_model(), *provider.member_models()]

    for model in models:
        assert model.settings["extra_body"] == {"provider": {"data_collection": "deny"}}


def test_provider_requires_an_api_key():
    with pytest.raises(ValueError, match="API key"):
        _provider(api_key="")


def test_settings_read_the_openrouter_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-env")

    assert Settings().openrouter_api_key == "sk-from-env"
