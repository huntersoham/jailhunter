"""
JailHunter Provider Abstraction Layer
Defines the contract every provider must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelResponse:
    """Normalised response from any provider."""

    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    response_time_ms: int = 0
    raw: Optional[dict] = field(default=None, repr=False)

    @property
    def is_empty(self) -> bool:
        """True when the model returned nothing useful."""
        return not self.content.strip()

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class BaseProvider(ABC):
    """Abstract base class for all JailHunter model providers."""

    #: Human-readable provider identifier
    name: str = "base"

    @abstractmethod
    async def send(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ModelResponse:
        """
        Send a prompt to the model and return a normalised response.

        Args:
            prompt:        User-turn content.
            model:         Model name/ID.
            system_prompt: Optional system-turn content.
            max_tokens:    Maximum tokens in the response.
            temperature:   Sampling temperature.

        Returns:
            ModelResponse with content and metadata.

        Raises:
            RuntimeError: On non-recoverable API errors.
            ConnectionError: When the provider endpoint is unreachable.
        """

    @abstractmethod
    async def check_connection(self) -> tuple[bool, str]:
        """
        Verify the provider is reachable and configured correctly.

        Returns:
            (ok: bool, message: str)
            ok=True  → provider ready
            ok=False → message explains the problem
        """
