"""Adaptateur pour toute API compatible OpenAI (`/v1/chat/completions`).

Couvre les fournisseurs hébergés comme les serveurs locaux qui exposent cette
interface — vLLM, llama.cpp, LM Studio, TGI.

La clé d'API n'apparaît jamais dans le descripteur : un rapport est fait pour
être partagé.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core import Case
from .base import AdapterError, ChatAdapter, estimate_tokens, post_json


@dataclass
class OpenAICompatibleChat(ChatAdapter):
    base_url: str = "https://api.openai.com/v1"
    api_key: str | None = None
    timeout: float = 300.0

    def descriptor(self) -> dict[str, Any]:
        return {
            **super().descriptor(),
            "base_url": self.base_url,
            "provider": "openai_compatible",
            "api_key_present": self.api_key is not None,
        }

    def generate(self, case: Case) -> tuple[str, int, int]:
        payload = {
            "model": self.model,
            "messages": self.messages(case),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **dict(self.extra),
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = post_json(
            f"{self.base_url.rstrip('/')}/chat/completions",
            payload,
            headers=headers,
            timeout=self.timeout,
        )
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AdapterError("réponse sans 'choices'")
        text = str(choices[0].get("message", {}).get("content", ""))
        usage = data.get("usage") or {}
        return (
            text,
            int(usage.get("prompt_tokens", estimate_tokens(case.question))),
            int(usage.get("completion_tokens", estimate_tokens(text))),
        )
