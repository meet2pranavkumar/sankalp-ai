"""How the AI provider is chosen from the settings in .env."""
import logging

import pytest

from app.core.config import get_settings
from app.routers.ai import ai_provider_dependency
from app.services import ai as ai_module
from app.services.ai.anthropic import AnthropicProvider
from app.services.ai.demo import DemoProvider


@pytest.fixture()
def fresh(monkeypatch):
    """Forget any provider built earlier, and put the cache back afterwards."""
    monkeypatch.setattr(ai_module, "_built", False)
    monkeypatch.setattr(ai_module, "_provider", None)
    return get_settings()


def test_none_means_off(fresh, monkeypatch):
    monkeypatch.setattr(fresh, "ai_provider", "none")
    assert ai_module.get_ai_provider() is None


def test_demo_gives_the_example_provider(fresh, monkeypatch):
    monkeypatch.setattr(fresh, "ai_provider", "demo")
    assert isinstance(ai_module.get_ai_provider(), DemoProvider)


def test_anthropic_with_a_key_builds_the_real_client_from_the_settings(fresh, monkeypatch):
    monkeypatch.setattr(fresh, "ai_provider", "anthropic")
    monkeypatch.setattr(fresh, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(fresh, "ai_model", "claude-test-9")
    monkeypatch.setattr(fresh, "ai_base_url", "https://example.test/")
    provider = ai_module.get_ai_provider()
    assert isinstance(provider, AnthropicProvider)
    assert provider._model == "claude-test-9"
    assert str(provider._http.base_url).rstrip("/") == "https://example.test"
    assert provider._http.headers["x-api-key"] == "sk-ant-test"


def test_anthropic_without_a_key_stays_off_and_says_why(fresh, monkeypatch, caplog):
    monkeypatch.setattr(fresh, "ai_provider", "anthropic")
    monkeypatch.setattr(fresh, "anthropic_api_key", None)
    with caplog.at_level(logging.ERROR):
        assert ai_module.get_ai_provider() is None
    assert "ANTHROPIC_API_KEY is empty" in caplog.text


def test_a_misspelled_provider_stays_off_and_says_why(fresh, monkeypatch, caplog):
    monkeypatch.setattr(fresh, "ai_provider", "antropic")
    with caplog.at_level(logging.ERROR):
        assert ai_module.get_ai_provider() is None
    assert "Unknown AI_PROVIDER 'antropic'" in caplog.text


def test_the_provider_is_built_only_once(fresh, monkeypatch):
    monkeypatch.setattr(fresh, "ai_provider", "demo")
    first = ai_module.get_ai_provider()
    monkeypatch.setattr(fresh, "ai_provider", "none")  # a later change does not matter until the server restarts
    assert ai_module.get_ai_provider() is first


def test_the_web_route_uses_the_same_choice(fresh, monkeypatch):
    monkeypatch.setattr(fresh, "ai_provider", "demo")
    assert isinstance(ai_provider_dependency(), DemoProvider)


def test_the_secret_key_never_appears_in_the_logs(fresh, monkeypatch, caplog):
    """Even with the most detailed logging on, and a request that fails, the key must not be written anywhere."""
    from app.services.ai.base import ProviderError

    monkeypatch.setattr(fresh, "ai_provider", "anthropic")
    monkeypatch.setattr(fresh, "anthropic_api_key", "sk-ant-SECRET-VALUE")
    monkeypatch.setattr(fresh, "ai_base_url", "http://127.0.0.1:1")  # nothing listens here, so the request fails at once
    caplog.set_level(logging.DEBUG)
    provider = ai_module.get_ai_provider()
    with pytest.raises(ProviderError) as err:
        provider.complete("system", "user", 10)
    assert "sk-ant-SECRET-VALUE" not in caplog.text
    assert "sk-ant-SECRET-VALUE" not in str(err.value)
