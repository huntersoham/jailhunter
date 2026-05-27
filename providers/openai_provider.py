"""
JailHunter OpenAI Provider
Supports the OpenAI API and any OpenAI-compatible endpoint
(Azure OpenAI, LM Studio, vLLM, Ollama /v1, etc.).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import aiohttp

from .base_provider import BaseProvider, ModelResponse

logger = logging.getLogger("jailhunter.providers.openai")


class OpenAIProvider(BaseProvider):
    """
    Provider for OpenAI and OpenAI-compatible APIs.

    Usage:
        # OpenAI
        provider = OpenAIProvider(api_key="sk-...")

        # LM Studio / vLLM / local server
        provider = OpenAIProvider(api_key="none", base_url="http://localhost:1234/v1")
    """

    name: str = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 60,
    ) -> None:
        """
        Args:
            api_key:  OpenAI API key (required; use any non-empty string for local servers).
            base_url: API base URL. Override for OpenAI-compatible endpoints.
            timeout:  Request timeout in seconds.
        """
        if not api_key:
            raise ValueError(
                "OpenAI API key is required.\n"
                "  → Set environment variable: export OPENAI_API_KEY=sk-...\n"
                "  → Or pass: --api-key sk-..."
            )
        self.api_key: str = api_key
        self.base_url: str = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(total=timeout)

    # ─────────────────────────────────────────────────────────────────────────
    #  Connection diagnostics
    # ─────────────────────────────────────────────────────────────────────────

    async def check_connection(self) -> tuple[bool, str]:
        """
        Verify the API key is valid and the endpoint is reachable.
        Uses /models as a lightweight probe.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=8)
            ) as session:
                async with session.get(
                    f"{self.base_url}/models", headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        n = len(data.get("data", []))
                        return (True, f"Connected — {n} model(s) accessible")
                    if resp.status == 401:
                        return (
                            False,
                            "Authentication failed (HTTP 401). Check your API key.\n"
                            "  → export OPENAI_API_KEY=sk-...",
                        )
                    if resp.status == 403:
                        return (
                            False,
                            "Permission denied (HTTP 403). "
                            "Your key may lack access to this endpoint.",
                        )
                    body = await resp.text()
                    return (False, f"Unexpected HTTP {resp.status}: {body[:200]}")
        except aiohttp.ClientConnectorError:
            return (
                False,
                f"Cannot reach {self.base_url}.\n"
                "  → Check your internet connection\n"
                "  → Or verify --base-url is correct",
            )
        except Exception as exc:
            return (False, f"Connection check failed: {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    #  Request
    # ─────────────────────────────────────────────────────────────────────────

    async def send(
        self,
        prompt: str,
        model: str = "gpt-4o",
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ModelResponse:
        """Send a chat completion request."""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers: dict = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        t0 = time.monotonic()
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("OpenAI API error %d: %s", resp.status, body[:300])
                    if resp.status == 429:
                        raise RuntimeError(
                            "Rate limited (HTTP 429). "
                            "Reduce --concurrent or increase --delay."
                        )
                    if resp.status == 401:
                        raise RuntimeError(
                            "Invalid API key (HTTP 401). "
                            "Check OPENAI_API_KEY."
                        )
                    raise RuntimeError(f"API error HTTP {resp.status}: {body[:200]}")
                data = await resp.json()

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Guard against malformed response
        try:
            content: str = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected OpenAI response shape: %s", data)
            raise RuntimeError(f"Malformed API response: {exc}") from exc

        usage = data.get("usage", {})
        logger.debug(
            "OpenAI %s → %d chars in %dms (%d tokens)",
            model,
            len(content),
            elapsed_ms,
            usage.get("total_tokens", 0),
        )

        return ModelResponse(
            content=content,
            model=model,
            provider=self.name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            response_time_ms=elapsed_ms,
            raw=data,
        )
