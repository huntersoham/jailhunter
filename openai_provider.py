"""
JailHunter OpenAI Provider
Supports OpenAI API and any OpenAI-compatible endpoint.
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp

from base_provider import BaseProvider, ModelResponse

logger = logging.getLogger("jailhunter.providers.openai")


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def send(
        self,
        prompt: str,
        model: str = "gpt-4o",
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
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error("OpenAI API error %d: %s", resp.status, text[:300])
                    raise RuntimeError(f"API error {resp.status}: {text[:200]}")
                data = await resp.json()

        content = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})

        return ModelResponse(
            content=content,
            model=model,
            provider=self.name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            raw=data,
        )
