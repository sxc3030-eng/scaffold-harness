"""Adaptateur Anthropic (API Messages).

Ce n'est pas une API compatible OpenAI : point d'entrée différent, en-tête
d'authentification différent, consigne système au premier niveau plutôt que dans
`messages`, et réponse rendue sous forme de liste de blocs. D'où un adaptateur
dédié plutôt qu'un habillage fragile.

La clé n'apparaît jamais dans le descripteur du rapport.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core import Case
from .base import AdapterError, ChatAdapter, estimate_tokens, post_json

API_VERSION = "2023-06-01"


@dataclass
class AnthropicChat(ChatAdapter):
    base_url: str = "https://api.anthropic.com/v1"
    api_key: str | None = None
    api_version: str = API_VERSION
    timeout: float = 300.0

    def descriptor(self) -> dict[str, Any]:
        return {
            **super().descriptor(),
            "provider": "anthropic",
            "base_url": self.base_url,
            "api_version": self.api_version,
            "api_key_present": self.api_key is not None,
        }

    def generate(self, case: Case) -> tuple[str, int, int]:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            # La consigne système est un champ propre, pas un message.
            "messages": [{"role": "user", "content": case.question}],
            **dict(self.extra),
        }
        if self.system:
            payload["system"] = self.system
        headers = {"anthropic-version": self.api_version}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        data = post_json(
            f"{self.base_url.rstrip('/')}/messages",
            payload,
            headers=headers,
            timeout=self.timeout,
        )
        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise AdapterError("réponse sans 'content'")
        text = "".join(
            str(block.get("text", ""))
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        )
        usage = data.get("usage") or {}
        return (
            text,
            int(usage.get("input_tokens", estimate_tokens(case.question))),
            int(usage.get("output_tokens", estimate_tokens(text))),
        )
