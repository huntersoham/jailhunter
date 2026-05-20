"""
JailHunter Provider Abstraction Layer
Base interface for all AI model providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelResponse:
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: dict | None = None

    @property
    def is_empty(self) -> bool:
        return not self.content.strip()


class BaseProvider(ABC):
    """Abstract base for all model providers."""

    name: str = "base"

    @abstractmethod
    async def send(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ModelResponse:
        """Send a prompt and return a ModelResponse."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and reachable."""
