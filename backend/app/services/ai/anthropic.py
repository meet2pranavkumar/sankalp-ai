"""Client for the Claude API (Messages API, https://docs.anthropic.com/en/api/messages)."""
import httpx

from app.services.ai.base import ProviderError, ProviderResult

API_VERSION = "2023-06-01"


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
        timeout_seconds: float = 30,
        client: httpx.Client | None = None,
    ):
        self._model = model
        self._http = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"x-api-key": api_key, "anthropic-version": API_VERSION},
            timeout=timeout_seconds,
        )

    def complete(self, system: str, user: str, max_tokens: int) -> ProviderResult:
        body = {
            "model": self._model,
            "max_tokens": max_tokens,
            "temperature": 0.3,  # a little variety, but steady advice
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        try:
            res = self._http.post("/v1/messages", json=body)
        except httpx.TimeoutException:
            raise ProviderError("The AI helper took too long to answer. Please try again.") from None
        except httpx.HTTPError:
            raise ProviderError("The AI helper cannot be reached right now. Please try again later.") from None

        # None of the messages below contain the key, the request, or the service's own error text.
        if res.status_code in (401, 403):
            raise ProviderError("The AI service did not accept the school's key. Please tell your teacher.")
        if res.status_code == 429 or res.status_code == 529:
            raise ProviderError("The AI helper is very busy. Please try again in a minute.")
        if res.status_code >= 500:
            raise ProviderError("The AI service has a problem right now. Please try again later.")
        if res.status_code != 200:
            raise ProviderError("The AI helper could not handle this request.")

        try:
            data = res.json()
            text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()
            usage = data.get("usage") or {}
        except (ValueError, AttributeError):
            raise ProviderError("The AI helper sent an answer we could not read.") from None
        if not text:
            raise ProviderError("The AI helper sent an empty answer. Please try again.")
        return ProviderResult(text=text, input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))
