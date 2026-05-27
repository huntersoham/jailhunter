"""
JailHunter Provider Registry
Factory function and public exports for all model providers.
"""

from __future__ import annotations

from .base_provider import BaseProvider, ModelResponse
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


def get_provider(name: str, **kwargs: object) -> BaseProvider:
    """
    Instantiate and return a configured provider by name.

    Args:
        name:     Provider identifier: 'openai' or 'ollama'.
        **kwargs: Passed directly to the provider constructor.

    Returns:
        Configured BaseProvider instance.

    Raises:
        ValueError: Unknown provider name, or missing required arguments.

    Examples:
        >>> get_provider("ollama")
        >>> get_provider("openai", api_key="sk-...")
        >>> get_provider("openai", api_key="x", base_url="http://localhost:1234/v1")
    """
    _registry: dict[str, type[BaseProvider]] = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }

    key = name.strip().lower()
    provider_cls = _registry.get(key)

    if provider_cls is None:
        available = ", ".join(_registry.keys())
        raise ValueError(
            f"Unknown provider '{name}'. "
            f"Available: {available}"
        )

    try:
        return provider_cls(**kwargs)  # type: ignore[arg-type]
    except TypeError as exc:
        # Convert cryptic TypeError from missing constructor args to clear ValueError
        raise ValueError(
            f"Failed to initialise '{name}' provider: {exc}\n"
            "  Hint: OpenAI requires --api-key or OPENAI_API_KEY env var."
        ) from exc


__all__ = [
    "BaseProvider",
    "ModelResponse",
    "OllamaProvider",
    "OpenAIProvider",
    "get_provider",
]
