"""
JailHunter Ollama Provider - Fixed for /api/generate endpoint
"""
from __future__ import annotations
import logging
import time
from typing import Optional
import aiohttp
from .base_provider import BaseProvider, ModelResponse

logger = logging.getLogger("jailhunter.providers.ollama")

class OllamaProvider(BaseProvider):
    name: str = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 120) -> None:
        self.base_url: str = (base_url or "http://localhost:11434").rstrip("/")
        self.timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(total=timeout)

    async def check_connection(self) -> tuple[bool, str]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/api/tags") as resp:
                    if resp.status != 200:
                        return (False, f"Ollama returned HTTP {resp.status}. Is `ollama serve` running?")
                    data = await resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    n = len(models)
                    names = ", ".join(models[:5])
                    return (True, f"{n} model(s) available: {names}" if models else "Connected (no models pulled yet)")
        except aiohttp.ClientConnectorError:
            return (False, f"Cannot reach Ollama at {self.base_url}.\n  → Start it with: ollama serve")
        except Exception as exc:
            return (False, f"Unexpected error: {exc}")

    async def check_model_exists(self, model: str) -> tuple[bool, str]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/api/tags") as resp:
                    if resp.status != 200:
                        return (False, f"Could not list models (HTTP {resp.status})")
                    data = await resp.json()
                    available = [m["name"] for m in data.get("models", [])]
                    matched = any(
                        m == model or m.startswith(model + ":") or model.startswith(m.split(":")[0])
                        for m in available
                    )
                    if matched:
                        return (True, f"Model '{model}' is available")
                    suggestions = ", ".join(available[:5]) if available else "none"
                    return (False, f"Model '{model}' not found.\n  → Run: ollama pull {model}\n  → Available: {suggestions}")
        except Exception as exc:
            return (False, f"Could not check model '{model}': {exc}")

    async def send(
        self,
        prompt: str,
        model: str = "llama3",
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ModelResponse:
        # Use /api/generate (more compatible) instead of /api/chat
        full_prompt = ""
        if system_prompt:
            full_prompt = f"System: {system_prompt}\n\n"
        full_prompt += prompt

        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        t0 = time.monotonic()
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(f"{self.base_url}/api/generate", json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Ollama HTTP %d: %s", resp.status, body[:300])
                    if resp.status == 404:
                        raise RuntimeError(f"Model '{model}' not found. Run: ollama pull {model}")
                    raise RuntimeError(f"Ollama error HTTP {resp.status}: {body[:200]}")
                data = await resp.json()

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        content: str = data.get("response", "") or ""

        logger.debug("Ollama %s → %d chars in %dms", model, len(content), elapsed_ms)

        return ModelResponse(
            content=content,
            model=model,
            provider=self.name,
            response_time_ms=elapsed_ms,
            raw=data,
        )
