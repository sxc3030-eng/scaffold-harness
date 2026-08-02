"""Adaptateur Ollama.

Ollama rapporte `prompt_eval_count` et `eval_count`: on utilise ses comptes
réels plutôt qu'une estimation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core import Case
from .base import ChatAdapter, estimate_tokens, post_json


@dataclass
class OllamaChat(ChatAdapter):
    host: str = "http://127.0.0.1:11434"
    timeout: float = 300.0

    def descriptor(self) -> dict[str, Any]:
        return {**super().descriptor(), "host": self.host, "provider": "ollama"}

    def generate(self, case: Case) -> tuple[str, int, int]:
        payload = {
            "model": self.model,
            "messages": self.messages(case),
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                **dict(self.extra),
            },
        }
        data = post_json(
            f"{self.host.rstrip('/')}/api/chat", payload, timeout=self.timeout
        )
        text = str(data.get("message", {}).get("content", ""))
        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")
        return (
            text,
            int(prompt_tokens)
            if isinstance(prompt_tokens, int)
            else estimate_tokens(case.question),
            int(completion_tokens)
            if isinstance(completion_tokens, int)
            else estimate_tokens(text),
        )
