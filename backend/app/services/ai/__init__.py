import logging

from app.core.config import get_settings
from app.services.ai.base import AIProvider

log = logging.getLogger(__name__)
_provider: AIProvider | None = None
_built = False


def get_ai_provider() -> AIProvider | None:
    """The AI provider chosen in .env (AI_PROVIDER), or None when the helper is switched off or not set up."""
    global _provider, _built
    if not _built:
        settings = get_settings()
        if settings.ai_provider == "anthropic":
            if settings.anthropic_api_key:
                from app.services.ai.anthropic import AnthropicProvider

                _provider = AnthropicProvider(
                    api_key=settings.anthropic_api_key,
                    model=settings.ai_model,
                    base_url=settings.ai_base_url,
                    timeout_seconds=settings.ai_timeout_seconds,
                )
            else:
                log.error("AI_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty. The AI helper stays off.")
        elif settings.ai_provider == "demo":
            from app.services.ai.demo import DemoProvider

            _provider = DemoProvider()
        elif settings.ai_provider != "none":
            log.error("Unknown AI_PROVIDER '%s'. Use none, demo or anthropic. The AI helper stays off.", settings.ai_provider)
        _built = True
    return _provider
