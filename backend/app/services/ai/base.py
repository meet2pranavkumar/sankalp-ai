"""The AI helper is a plug: anything with complete() can write a hint."""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderError(Exception):
    """The AI service failed. The message is safe to show to a student: it never contains keys or internal details."""


class AIProvider(Protocol):
    def complete(self, system: str, user: str, max_tokens: int) -> ProviderResult: ...
