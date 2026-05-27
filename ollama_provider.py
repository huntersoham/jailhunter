"""
JailHunter Ollama Provider
Connects to locally running Ollama instance for local model testing.
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp

from base_provider import BaseProvider, ModelResponse

logger = logging.getLogger("jailhunter.providers.ollama")


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url if base_url else "http://localhost:11434"
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    def is_available(self) -> bool:
        return True  # Availability checked at runtime

    async def send(
        self,
        prompt: str,
        model: str = "llama3",
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ModelResponse:
        messages = []
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

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error("Ollama error %d: %s", resp.status, text[:300])
                    raise RuntimeError(f"Ollama error {resp.status}: {text[:200]}")
                data = await resp.json()

        content = data.get("message", {}).get("content", "")
        return ModelResponse(
            content=content,
            model=model,
            provider=self.name,
            raw=data,
        )
