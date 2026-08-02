"""Exemple réel : un exécuteur déterministe et l'échafaudage qui le vérifie.

C'est la reproduction, en 60 lignes, du motif qui a produit la découverte
d'origine : on donne au modèle une proposition exacte et on lui demande de la
vérifier. La question est de savoir ce qu'il en fait.

Sert aussi de test de bout en bout : ce fichier est chargé par le CLI via
`{"adapter": "python", "import": "paths:executor"}`.
"""

from __future__ import annotations

import json
import os
import re
from fractions import Fraction

from scaffold_harness.adapters import OllamaChat, Refusal
from scaffold_harness.core import Case

# Modèle volontairement petit: l'exemple doit tourner sur une machine modeste.
# Surchargeable, parce que personne n'a exactement le même catalogue local.
MODEL = os.environ.get("SCAFFOLD_DEMO_MODEL", "llama3.2:latest")
EXPRESSION = re.compile(r"[-+]?\d+/\d+(?:\s*[-+]\s*\d+/\d+)*")

CONTRACT = (
    'Answer with one JSON object only: {"answer":"p/q"}. '
    "The value must be a single exact reduced fraction. No explanation."
)


def _expression_of(question: str) -> str:
    found = EXPRESSION.search(question)
    if found is None:
        raise Refusal("aucune expression rationnelle reconnue")
    return found.group(0).replace(" ", "")


def executor(question: str) -> str:
    """Chemin déterministe : exact, ou refus explicite.

    Il ne devine jamais. Hors de son domaine il lève `Refusal`, ce que le
    harnais compte dans la couverture et non dans les erreurs — un expert qui
    ment coûte plus cher qu'un expert qui se tait.
    """
    expression = _expression_of(question)
    total = Fraction(0)
    for sign, term in re.findall(r"([-+]?)(\d+/\d+)", expression):
        value = Fraction(term)
        total += -value if sign == "-" else value
    return str(total)


_CHAT = OllamaChat(model=MODEL, system=CONTRACT, max_tokens=64)


def require_model() -> None:
    """Échoue tôt et clairement si le modèle de l'exemple n'est pas installé.

    Un exemple qui plante avec une trace d'erreur HTTP au bout de trois minutes
    fait fuir; un message d'une ligne au démarrage, non.
    """
    if _CHAT.model_digest() is None:
        raise SystemExit(
            "\n".join(
                (
                    f"Le modèle « {MODEL} » n'est pas disponible sur Ollama.",
                    f"    ollama pull {MODEL}",
                    "ou choisissez-en un autre :",
                    "    SCAFFOLD_DEMO_MODEL=mistral:7b-instruct-q4_0"
                    " scaffold-harness run config.json",
                )
            )
        )


def verify_scaffold(case: Case):
    """L'échafaudage : proposition exacte + demande de vérification.

    Formulation volontairement prudente — « rapporte ce résultat sauf si tu peux
    démontrer une erreur ». C'est la version la plus protectrice possible, et
    c'est celle qui avait quand même détruit 26,5 % des bonnes réponses.
    """
    try:
        proposal = executor(case.question)
    except Refusal:
        return _CHAT(case)
    scaffolded = OllamaChat(
        model=MODEL,
        max_tokens=64,
        system=(
            "A deterministic specialist already computed and verified this "
            "result. Report that result unless you can demonstrate a specific "
            f"error in it.\nEXPERT_PROPOSAL={json.dumps({'answer': proposal})}\n"
            + CONTRACT
        ),
    )
    return scaffolded(case)
