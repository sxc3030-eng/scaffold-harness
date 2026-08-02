"""Adaptateur pour un échafaudage écrit en Python.

C'est l'adaptateur le plus important du lot : c'est par lui qu'on branche
l'objet réellement mesuré — un agent, une chaîne RAG, un routeur, un exécuteur
déterministe.

Deux comportements que le harnais traite différemment, et qu'il faut savoir
exprimer :

* lever `Refusal` → le chemin **refuse** ; ça compte dans la couverture, pas
  dans les erreurs ;
* lever autre chose → l'échafaudage a planté ; ça compte comme une erreur, et
  le rapport le distingue d'un refus.

Un système qui refuse 92 % du temps et un système qui répond mal 92 % du temps
n'ont rien à voir, et aucun score agrégé ne les sépare.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ..core import Case, Response
from .base import estimate_tokens, timed


class Refusal(Exception):
    """Le chemin déclare qu'il ne sait pas répondre."""


@dataclass
class PythonPath:
    """Enveloppe `f(question) -> str` en chemin mesurable."""

    function: Callable[..., Any]
    name: str = "python"
    pass_case: bool = False
    version: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def descriptor(self) -> dict[str, Any]:
        return {
            "kind": "PythonPath",
            "name": self.name,
            "version": self.version,
            "callable": getattr(self.function, "__qualname__", repr(self.function)),
            "metadata": dict(self.metadata),
        }

    def __call__(self, case: Case) -> Response:
        argument = case if self.pass_case else case.question
        try:
            result = timed(self.function, argument)
        except Refusal:
            return Response(
                case_id=case.case_id,
                answer=None,
                contract_valid=True,
                refused=True,
                input_tokens=estimate_tokens(case.question),
            )
        except Exception as error:  # noqa: BLE001
            # Volontairement large: on mesure le code de quelqu'un d'autre, et
            # il peut lever n'importe quoi. Un plantage de l'échafaudage est un
            # échec DE CE CAS — le laisser remonter ferait tomber la campagne
            # entière et perdrait tous les appels déjà payés.
            return Response(
                case_id=case.case_id,
                answer=None,
                contract_valid=False,
                refused=False,
                failed=True,
                input_tokens=estimate_tokens(case.question),
                raw=f"{type(error).__name__}: {error}",
            )
        value = result.value
        if isinstance(value, Response):
            return value
        text = "" if value is None else str(value)
        return Response(
            case_id=case.case_id,
            answer=text.strip() or None,
            contract_valid=bool(text.strip()),
            refused=not text.strip(),
            latency_ms=result.latency_ms,
            input_tokens=estimate_tokens(case.question),
            output_tokens=estimate_tokens(text),
            raw=text,
        )
