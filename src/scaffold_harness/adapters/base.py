"""Socle commun aux adaptateurs.

Un adaptateur transforme « un modèle » en `Callable[[Case], Response]`. Il doit
renseigner trois choses que le rapport ne peut pas inventer :

* la **latence**, mesurée autour de l'appel réel ;
* les **tokens**, rapportés par le fournisseur quand il le fait ;
* un **descripteur** qui identifie exactement ce qui a tourné.

Sans le coût, le rapport ne peut pas dire « vous avez doublé la facture pour
rien » — et c'est un de ses arguments les plus utiles. Sans le descripteur, un
tiers ne peut pas savoir sur quoi le chiffre a été obtenu.

Aucune dépendance externe : les appels HTTP passent par `urllib`, et les
bibliothèques lourdes sont importées à l'usage, pas au chargement du module.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..core import Case, Response


class AdapterError(RuntimeError):
    """L'adaptateur n'a pas pu produire une réponse exploitable."""


def estimate_tokens(text: str) -> int:
    """Estimation grossière quand le fournisseur ne compte pas.

    Environ quatre caractères par token. À n'utiliser qu'en repli : un rapport
    doit préférer les comptes réels, et signaler quand ils sont estimés.
    """
    return max(1, len(text) // 4)


@dataclass
class Timed:
    value: Any
    latency_ms: float


def timed(function, *args, **kwargs) -> Timed:
    started = time.perf_counter()
    value = function(*args, **kwargs)
    return Timed(value, (time.perf_counter() - started) * 1000.0)


def post_json(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str] | None = None,
    timeout: float = 120.0,
    attempts: int = 3,
    backoff: float = 0.5,
) -> dict[str, Any]:
    """POST JSON, avec réessai sur les défaillances passagères.

    Un serveur local qui décharge un modèle, une API qui renvoie 503, une
    coupure d'une seconde: ces incidents sont normaux sur un run long et ne
    doivent pas coûter les centaines d'appels déjà payés. On réessaie sur 5xx,
    429 et erreurs réseau; jamais sur une 4xx, qui ne changera pas d'avis.
    """
    body = json.dumps(payload).encode("utf-8")
    last = ""
    for attempt in range(1, max(1, attempts) + 1):
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as stream:
                return json.loads(stream.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            last = f"{url} a répondu {error.code}: {detail}"
            if error.code < 500 and error.code != 429:
                raise AdapterError(last) from error
        except urllib.error.URLError as error:
            last = f"{url} injoignable: {error.reason}"
        except json.JSONDecodeError as error:
            last = f"{url} a renvoyé une réponse illisible: {error}"
        if attempt < attempts:
            time.sleep(backoff * (2 ** (attempt - 1)))
    raise AdapterError(f"{last} (après {attempts} tentatives)")


@dataclass
class ChatAdapter:
    """Base des adaptateurs conversationnels.

    `system` est le point d'insertion de l'échafaudage le plus simple qui soit :
    comparer deux `ChatAdapter` qui ne diffèrent que par leur consigne système
    est déjà une expérience appariée valable.
    """

    model: str
    system: str | None = None
    temperature: float = 0.0
    max_tokens: int = 512
    extra: Mapping[str, Any] = field(default_factory=dict)

    def descriptor(self) -> dict[str, Any]:
        return {
            "kind": type(self).__name__,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_sha256": None
            if self.system is None
            else __import__("hashlib").sha256(self.system.encode("utf-8")).hexdigest(),
        }

    def messages(self, case: Case) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if self.system:
            rows.append({"role": "system", "content": self.system})
        rows.append({"role": "user", "content": case.question})
        return rows

    def generate(self, case: Case) -> tuple[str, int, int]:  # pragma: no cover
        raise NotImplementedError

    def __call__(self, case: Case) -> Response:
        try:
            result = timed(self.generate, case)
        except AdapterError as error:
            # Une défaillance du fournisseur est un échec DE CE CAS, pas du run.
            # Faire tomber la comparaison entière ferait perdre tous les appels
            # déjà payés — et ce serait l'incident le plus coûteux possible sur
            # un jeu de plusieurs centaines de questions.
            return Response(
                case_id=case.case_id,
                answer=None,
                contract_valid=False,
                refused=False,
                raw=f"AdapterError: {error}",
            )
        text, input_tokens, output_tokens = result.value
        answer = text.strip()
        return Response(
            case_id=case.case_id,
            answer=answer or None,
            contract_valid=bool(answer),
            refused=not answer,
            latency_ms=result.latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=text,
        )
