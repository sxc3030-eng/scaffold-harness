"""Adaptateur Ollama.

Ollama rapporte `prompt_eval_count` et `eval_count`: on utilise ses comptes
réels plutôt qu'une estimation.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ..core import Case
from .base import ChatAdapter, estimate_tokens, post_json


@dataclass
class OllamaChat(ChatAdapter):
    host: str = "http://127.0.0.1:11434"
    timeout: float = 300.0
    # Ollama décharge un modèle inactif; sur un run long, le rechargement peut
    # échouer en plein milieu. Le garder en mémoire évite l'incident.
    keep_alive: str = "10m"
    _digest: str | None = field(default=None, init=False, repr=False)

    def model_digest(self) -> str | None:
        """Empreinte du build réellement servi.

        Un tag Ollama est **mutable**: `gemma3:12b` aujourd'hui n'est pas
        forcément le même poids dans trois mois. Un rapport qui prétend être
        reproductible doit épingler le digest, pas le nom.
        """
        if self._digest is not None:
            return self._digest or None
        try:
            with urllib.request.urlopen(
                f"{self.host.rstrip('/')}/api/tags", timeout=10
            ) as stream:
                catalogue = json.loads(stream.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            object.__setattr__(self, "_digest", "")
            return None
        for row in catalogue.get("models") or []:
            if str(row.get("name")) == self.model:
                found = str(row.get("digest") or "")
                object.__setattr__(self, "_digest", found)
                return found or None
        object.__setattr__(self, "_digest", "")
        return None

    def descriptor(self) -> dict[str, Any]:
        return {
            **super().descriptor(),
            "host": self.host,
            "provider": "ollama",
            "keep_alive": self.keep_alive,
            # Sans le digest, «reproduire ce rapport» n'est pas vérifiable.
            "model_digest": self.model_digest(),
        }

    def generate(self, case: Case) -> tuple[str, int, int]:
        payload = {
            "model": self.model,
            "messages": self.messages(case),
            "stream": False,
            "keep_alive": self.keep_alive,
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
