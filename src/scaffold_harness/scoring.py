"""Noteurs réutilisables.

Un harnais dont le noteur ment est pire qu'aucun harnais. Sur un run réel, un
correcteur qui comparait des chaînes canoniques a compté faux **43 réponses
mathématiquement justes** — le système notait 73,25 % au lieu de 77,25 %, et
l'erreur pénalisait systématiquement le bras qui rendait des fractions non
réduites.

D'où deux principes ici :

* comparer des **valeurs**, pas des représentations, dès que le domaine le
  permet ;
* laisser le noteur déclarer ce qu'il ne sait pas juger, plutôt que de compter
  faux en silence.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from fractions import Fraction
from typing import Any

from .core import Case, Response

Scorer = Callable[[Response, Case], bool]

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def as_fraction(value: Any) -> Fraction | None:
    """Convertit en rationnel exact, ou None si ce n'en est pas un."""
    if value is None:
        return None
    text = str(value).strip().replace(" ", "").replace(",", ".")
    if not text:
        return None
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def exact_rational(response: Response, case: Case) -> bool:
    """Égalité rationnelle exacte : `6/8`, `0.75` et `3/4` sont la même réponse.

    C'est le noteur correct pour tout ce qui est numérique et exact. Comparer
    les chaînes ferait dépendre le score de la forme choisie par le modèle.
    """
    got = as_fraction(response.answer)
    want = as_fraction(case.target)
    if got is None or want is None:
        return normalized_text(response, case)
    return got == want


def normalized_text(response: Response, case: Case) -> bool:
    """Comparaison textuelle insensible à la casse et aux espaces de bord."""
    if response.answer is None or case.target is None:
        return False
    return str(response.answer).strip().casefold() == str(case.target).strip().casefold()


def json_field(field: str = "answer", inner: Scorer | None = None) -> Scorer:
    """Extrait un champ d'une réponse JSON avant de la noter.

    Tolère les clés supplémentaires. Exiger exactement `{"answer"}` a déjà
    coûté des réponses justes à un bras qui recopiait les métadonnées de son
    outil à côté du résultat.
    """
    judge = inner or exact_rational

    def scorer(response: Response, case: Case) -> bool:
        payload = response.raw or (response.answer or "")
        match = _JSON_OBJECT.search(payload)
        if match is None:
            return judge(response, case)
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return False
        if not isinstance(parsed, dict) or field not in parsed:
            return False
        extracted = Response(
            case_id=response.case_id,
            answer=None if parsed[field] is None else str(parsed[field]),
            contract_valid=response.contract_valid,
            refused=response.refused,
            latency_ms=response.latency_ms,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            raw=payload,
        )
        return judge(extracted, case)

    return scorer


def multiple_choice(choices_key: str = "choices") -> Scorer:
    """Note un choix multiple en acceptant la lettre ou le texte de l'option."""

    def scorer(response: Response, case: Case) -> bool:
        if response.answer is None or case.target is None:
            return False
        given = str(response.answer).strip().casefold()
        target = str(case.target).strip().casefold()
        if given == target:
            return True
        options = case.metadata.get(choices_key)
        if not isinstance(options, (list, tuple)):
            return False
        for index, option in enumerate(options):
            letter = chr(ord("a") + index)
            if target in {letter, str(option).strip().casefold()}:
                return given in {letter, str(option).strip().casefold()}
        return False

    return scorer
