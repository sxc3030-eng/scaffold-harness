"""Provenance : rendre un rapport vérifiable par quelqu'un qui ne vous croit pas.

Un rapport d'évaluation ne vaut que si un tiers peut établir *sur quoi* il a été
produit. Trois primitives suffisent : une sérialisation canonique, une empreinte
stable, et une écriture qui ne laisse jamais de fichier à moitié écrit.

Une règle non négociable, apprise à ses dépens : **aucune identité de processus
dans une empreinte de campagne.** Un harnais où le `pid` entrait dans le sha du
manifeste rendait toute reprise après incident impossible — la campagne
repartait de zéro à chaque panne.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

# Clés volatiles : elles décrivent l'exécution courante, pas la campagne.
# Les exclure de l'empreinte permet à une campagne interrompue de reprendre.
VOLATILE_KEYS = frozenset({"pid", "hostname", "started_at", "elapsed_ms"})


def canonical(value: Any) -> str:
    """Sérialisation stable : clés triées, pas d'espaces, pas de NaN."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_file(path: Path) -> str:
    accumulator = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            accumulator.update(block)
    return accumulator.hexdigest()


def campaign_digest(manifest: Mapping[str, Any]) -> str:
    """Empreinte d'une campagne, indépendante du processus qui l'exécute."""
    return digest(
        {key: item for key, item in manifest.items() if key not in VOLATILE_KEYS}
    )


def question_set_digest(questions: Iterable[str]) -> str:
    """Empreinte d'un jeu de questions, indépendante de l'ordre de lecture."""
    return digest(sorted(digest_text(text) for text in questions))


def sign(report: Mapping[str, Any]) -> dict[str, Any]:
    """Ajoute au rapport sa propre empreinte, calculée sans elle."""
    body = {key: value for key, value in report.items() if key != "report_sha256"}
    return {**body, "report_sha256": digest(body)}


def verify(report: Mapping[str, Any]) -> bool:
    """Un tiers peut recalculer l'empreinte et détecter toute retouche."""
    claimed = report.get("report_sha256")
    if not isinstance(claimed, str):
        return False
    body = {key: value for key, value in report.items() if key != "report_sha256"}
    return digest(body) == claimed


def write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    """Écrit un JSON indenté sans jamais laisser de fichier partiel."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
