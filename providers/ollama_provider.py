"""
JailHunter Ollama Provider
Connects to a locally running `ollama serve` instance.

Supports llama3, mistral, qwen, and any model pulled via `ollama pull <name>`.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import aiohttp

from .base_provider import BaseProvider, ModelResponse

logger = logging.getLogger("jailhunter.providers.ollama")


class OllamaProvider(BaseProvider):
    """
    Provider for locally hosted models via Ollama.

    Usage:
        provider = OllamaProvider()                             # default localhost
        provider = OllamaProvider(base_url="http://host:11434") # custom host
    """

    name: str = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ) -> None:
        """
        Args:
            base_url: Base URL of the running Ollama server.
            timeout:  Total request timeout in seconds. Local models can be slow
                      to generate so this defaults to 120s.
        """
        # Defensive: strip trailing slash so URL building is always correct
        self.base_url: str = (base_url or "http://localhost:11434").rstrip("/")
        self.timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(total=timeout)

    # ─────────────────────────────────────────────────────────────────────────
    #  Connection diagnostics
    # ─────────────────────────────────────────────────────────────────────────

    async def check_connection(self) -> tuple[bool, str]:
        """
        Ping the Ollama server and verify it is running.

        Returns:
            (True, "Ollama reachable, N models available")
            (False, "<human-readable error explaining what to do>")
        """
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                async with session.get(f"{self.base_url}/api/tags") as resp:
                    if resp.status != 200:
                        return (
                            False,
                            f"Ollama returned HTTP {resp.status}. "
                            f"Is `ollama serve` running at {self.base_url}?",
                        )
                    data = await resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    n = len(models)
                    names = ", ".join(models[:5]) + ("…" if n > 5 else "")
                    return (True, f"{n} model(s) available: {names}" if models else "Connected (no models pulled yet)")
        except aiohttp.ClientConnectorError:
            return (
                False,
                f"Cannot reach Ollama at {self.base_url}.\n"
                "  → Start it with: ollama serve\n"
                "  → Or set: export OLLAMA_BASE_URL=http://<your-host>:11434",
            )
        except Exception as exc:
            return (False, f"Unexpected error checking Ollama: {exc}")

    async def check_model_exists(self, model: str) -> tuple[bool, str]:
        """
        Verify a specific model is available locally.

        Returns:
            (True, "Model '<model>' is available")
            (False, "Model '<model>' not found. Run: ollama pull <model>")
        """
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                async with session.get(f"{self.base_url}/api/tags") as resp:
                    if resp.status != 200:
                        return (False, f"Could not list models (HTTP {resp.status})")
                    data = await resp.json()
                    # Model names may have :tag suffix, check both exact and prefix
                    available = [m["name"] for m in data.get("models", [])]
                    # Match: exact, or model is a prefix of available name (llama3 → llama3:latest)
                    matched = any(
                        m == model or m.startswith(model + ":") or model.startswith(m.split(":")[0])
                        for m in available
                    )
                    if matched:
                        return (True, f"Model '{model}' is available")
                    suggestions = ", ".join(available[:5]) if available else "none"
                    return (
                        False,
                        f"Model '{model}' not found locally.\n"
                        f"  → Pull it: ollama pull {model}\n"
                        f"  → Available models: {suggestions}",
                    )
        except Exception as exc:
            return (False, f"Could not check model '{model}': {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    #  Request
    # ─────────────────────────────────────────────────────────────────────────

    async def send(
        self,
        prompt: str,
        model: str = "llama3",
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ModelResponse:
        """Send a chat prompt to a local Ollama model."""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        t0 = time.monotonic()
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Ollama HTTP %d: %s", resp.status, body[:300])
                    # Surface a helpful error for common cases
                    if resp.status == 404:
                        raise RuntimeError(
                            f"Model '{model}' not found in Ollama. "
                            f"Run: ollama pull {model}"
                        )
                    raise RuntimeError(f"Ollama error HTTP {resp.status}: {body[:200]}")
                data = await resp.json()

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        content: str = data.get("message", {}).get("content", "") or ""

        logger.debug(
            "Ollama %s → %d chars in %dms",
            model,
            len(content),
            elapsed_ms,
        )

        return ModelResponse(
            content=content,
            model=model,
            provider=self.name,
            response_time_ms=elapsed_ms,
            raw=data,
        )
