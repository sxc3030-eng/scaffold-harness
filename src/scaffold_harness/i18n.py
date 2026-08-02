"""Bilingual strings. English is the default; French is a first-class peer.

The core never contains prose. It produces an *outcome code* — ``gain``,
``loss`` or ``inconclusive`` — and the renderer turns it into a sentence. That
separation is what makes the report translatable without touching the
measurement, and it also stops a verdict from being buried in a formatting
change.

Three words were chosen because they read the same way in both languages and
need no glossary: **gain / loss / inconclusive**.
"""

from __future__ import annotations

from typing import Any

DEFAULT_LANG = "en"
LANGS = ("en", "fr")

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "title": "What did your layer actually change?",
        "subtitle": "{count} paired cases · set: {name}",
        "outcome.gain": "GAIN",
        "outcome.loss": "LOSS",
        "outcome.inconclusive": "INCONCLUSIVE",
        "verdict.gain": "Your layer improves the model by {delta} (p={p}).",
        "verdict.loss": "Your layer degrades the model by {delta} (p={p}).",
        "verdict.inconclusive": (
            "No measurable difference ({delta}, p={p}). "
            "This sample is too small to conclude."
        ),
        "headline.none": (
            "None of the {n} variants differs measurably from the bare model "
            "over {count} cases."
        ),
        "headline.gain": "“{name}” improves the model by {delta}.",
        "headline.loss": "“{name}” degrades the model by {delta}.",
        "section.changed": "What your layer changed",
        "section.changed.note": (
            "Compared against: {reference}. A change that does not improve the "
            "answer is a change that costs."
        ),
        "section.accuracy": "Accuracy and coverage",
        "section.accuracy.note": (
            "Intervals are Wilson 95%. A wide interval means the sample cannot "
            "settle the question — that is missing data, not a flaw in the "
            "system being measured."
        ),
        "section.cost": "Cost",
        "section.what": "What this report measures",
        "section.faq": "Questions",
        "section.repro": "Reproduce this",
        "section.cases": "Question by question",
        "warn.failures": (
            "{count} of {total} calls failed at the provider. Above {limit}, a "
            "result can no longer be attributed to the layer rather than to the "
            "outage, and the verdict abstains."
        ),
        "warn.scorer": (
            "{count} cases where two graders disagree. The score there depends "
            "on how answers are compared, not on the answers themselves — read "
            "them before trusting any number in this report."
        ),
        "col.failed": "failed",
        "section.cases.note": (
            "Destroyed answers first. This is where a number becomes a "
            "decision: read three of them and you will know whether the layer "
            "is worth keeping."
        ),
        "filter.all": "all",
        "filter.destroyed": "destroyed",
        "filter.improved": "improved",
        "filter.changed": "changed",
        "col.question": "question",
        "col.reference": "reference",
        "col.answer": "your layer",
        "col.expected": "expected",
        "label.destroyed": "destroyed",
        "label.improved": "improved",
        "label.neutral_change": "changed, still wrong",
        "label.unchanged": "unchanged",
        "cases.truncated": "Showing the {shown} most relevant of {total} cases.",
        "cases.empty": "No case detail was recorded for this run.",
        "col.variant": "variant",
        "col.changed": "changed",
        "col.improved": "improved",
        "col.destroyed": "destroyed",
        "col.neutral": "neutral",
        "col.net": "net",
        "col.path": "path",
        "col.correct": "correct",
        "col.accuracy": "accuracy",
        "col.ci": "95% CI",
        "col.coverage": "coverage",
        "col.refused": "refused",
        "col.tokens": "tokens",
        "col.latency": "p95 latency",
        "col.latency_abs": "p95 absolute",
        "col.mcnemar": "McNemar",
        "row.baseline": "bare model (reference)",
        "signature": "signature",
        "lang.switch": "Français",
    },
    "fr": {
        "title": "Qu'est-ce que votre couche a réellement changé ?",
        "subtitle": "{count} cas appariés · jeu : {name}",
        "outcome.gain": "GAIN",
        "outcome.loss": "PERTE",
        "outcome.inconclusive": "NON CONCLUANT",
        "verdict.gain": "Votre couche améliore le modèle de {delta} (p={p}).",
        "verdict.loss": "Votre couche dégrade le modèle de {delta} (p={p}).",
        "verdict.inconclusive": (
            "Aucune différence mesurable ({delta}, p={p}). "
            "L'échantillon est trop petit pour conclure."
        ),
        "headline.none": (
            "Aucune des {n} variantes ne se distingue du modèle nu "
            "sur {count} cas."
        ),
        "headline.gain": "« {name} » améliore le modèle de {delta}.",
        "headline.loss": "« {name} » dégrade le modèle de {delta}.",
        "section.changed": "Ce que votre couche a changé",
        "section.changed.note": (
            "Comparé à : {reference}. Une modification qui n'améliore pas la "
            "réponse est une modification qui coûte."
        ),
        "section.accuracy": "Exactitude et couverture",
        "section.accuracy.note": (
            "Les intervalles sont ceux de Wilson à 95 %. Un intervalle large "
            "signifie que l'échantillon ne peut pas trancher — c'est un manque "
            "de données, pas un défaut du système mesuré."
        ),
        "section.cost": "Coût",
        "section.what": "Ce que ce rapport mesure",
        "section.faq": "Questions",
        "section.repro": "Reproduire",
        "section.cases": "Question par question",
        "warn.failures": (
            "{count} appels sur {total} ont échoué chez le fournisseur. Au-delà "
            "de {limit}, un résultat n'est plus attribuable à la couche plutôt "
            "qu'à la panne, et le verdict s'abstient."
        ),
        "warn.scorer": (
            "{count} cas où deux correcteurs sont en désaccord. Le score y "
            "dépend de la façon de comparer, pas des réponses — à lire avant de "
            "faire confiance à un chiffre de ce rapport."
        ),
        "col.failed": "pannes",
        "section.cases.note": (
            "Les réponses détruites d'abord. C'est ici qu'un chiffre devient "
            "une décision : lisez-en trois et vous saurez si la couche mérite "
            "d'être gardée."
        ),
        "filter.all": "tout",
        "filter.destroyed": "détruites",
        "filter.improved": "améliorées",
        "filter.changed": "modifiées",
        "col.question": "question",
        "col.reference": "référence",
        "col.answer": "votre couche",
        "col.expected": "attendu",
        "label.destroyed": "détruite",
        "label.improved": "améliorée",
        "label.neutral_change": "modifiée, toujours fausse",
        "label.unchanged": "inchangée",
        "cases.truncated": "Affichage des {shown} cas les plus pertinents sur {total}.",
        "cases.empty": "Aucun détail par cas n'a été enregistré pour ce run.",
        "col.variant": "variante",
        "col.changed": "modifiées",
        "col.improved": "améliorées",
        "col.destroyed": "détruites",
        "col.neutral": "neutres",
        "col.net": "net",
        "col.path": "chemin",
        "col.correct": "justes",
        "col.accuracy": "exactitude",
        "col.ci": "IC 95 %",
        "col.coverage": "couverture",
        "col.refused": "refus",
        "col.tokens": "tokens",
        "col.latency": "latence p95",
        "col.latency_abs": "p95 absolu",
        "col.mcnemar": "McNemar",
        "row.baseline": "modèle nu (référence)",
        "signature": "signature",
        "lang.switch": "English",
    },
}

# Explication du produit, en deux paragraphes courts. C'est la section que lit
# quelqu'un qui reçoit le rapport sans connaître l'outil.
WHAT: dict[str, list[str]] = {
    "en": [
        "Benchmarks tell you how a <em>model</em> scores. This report tells you "
        "what the layer you built <em>on top of it</em> — an agent, a RAG "
        "pipeline, a router, a verification step — actually adds or removes.",
        "Every question is answered twice: once by the bare model, once through "
        "your layer. Because the two runs are paired on the same questions, the "
        "report can count the answers your layer <strong>changed</strong>, and "
        "say whether each change made things better or worse. An aggregate "
        "score cannot do that: a layer that fixes 8 answers and breaks 5 looks "
        "like “+3” and hides the 13 questions it touched.",
    ],
    "fr": [
        "Les benchmarks vous disent le score d'un <em>modèle</em>. Ce rapport "
        "vous dit ce que la couche que vous avez construite <em>par-dessus</em> "
        "— un agent, une chaîne RAG, un routeur, une étape de vérification — "
        "ajoute ou retire réellement.",
        "Chaque question reçoit deux réponses : celle du modèle nu, et celle qui "
        "passe par votre couche. Comme les deux passages sont appariés sur les "
        "mêmes questions, le rapport peut compter les réponses que votre couche "
        "a <strong>modifiées</strong>, et dire si chaque modification a amélioré "
        "ou dégradé le résultat. Un score agrégé ne le peut pas : une couche qui "
        "corrige 8 réponses et en casse 5 affiche « +3 » et masque les 13 "
        "questions qu'elle a touchées.",
    ],
}

FAQ: dict[str, list[tuple[str, str]]] = {
    "en": [
        (
            "Why does it sometimes refuse to conclude?",
            "Because a difference can be real and still be unprovable at this "
            "sample size. Four losses and zero gains looks decisive, but the "
            "exact test gives p = 0.125 — one run in eight would show that by "
            "chance alone. A tool that always finds something is worth nothing.",
        ),
        (
            "What does “destroyed” mean exactly?",
            "Your layer changed an answer that the reference path had right, "
            "and the new answer is wrong. It is counted separately from "
            "“improved” — the reverse case — because the two cancel out in any "
            "aggregate score and tell you completely different things.",
        ),
        (
            "What is the reference path?",
            "By default, the bare model — everyone has one. If you also have a "
            "deterministic path (a calculator, a solver, a database lookup), "
            "point the harness at it: changes are then counted against "
            "something known to be right, which is far sharper.",
        ),
        (
            "Is a refusal the same as a wrong answer?",
            "No, and the distinction matters. A system that refuses 90% of "
            "questions and a system that answers 90% of them wrongly score the "
            "same on accuracy alone. Coverage separates them.",
        ),
        (
            "Can I trust these numbers?",
            "You can check them. The report carries a hash of its own contents, "
            "of the question set, and of every path that ran. Nothing is "
            "promoted automatically, and the reproduction command is included.",
        ),
    ],
    "fr": [
        (
            "Pourquoi refuse-t-il parfois de conclure ?",
            "Parce qu'une différence peut être réelle et rester indémontrable à "
            "cette taille d'échantillon. Quatre pertes et zéro gain semble net, "
            "mais le test exact donne p = 0,125 — une fois sur huit, le hasard "
            "seul produirait ça. Un outil qui trouve toujours quelque chose ne "
            "vaut rien.",
        ),
        (
            "Que veut dire « détruite » exactement ?",
            "Votre couche a modifié une réponse que le chemin de référence "
            "avait juste, et la nouvelle est fausse. C'est compté séparément "
            "des « améliorées » — le cas inverse — parce que les deux "
            "s'annulent dans un score agrégé et ne disent pas du tout la même "
            "chose.",
        ),
        (
            "Qu'est-ce que le chemin de référence ?",
            "Par défaut, le modèle nu — tout le monde en a un. Si vous disposez "
            "aussi d'un chemin déterministe (calculateur, solveur, requête en "
            "base), branchez-le : les modifications sont alors comptées contre "
            "quelque chose dont on sait que c'est juste, ce qui est bien plus "
            "tranchant.",
        ),
        (
            "Un refus est-il équivalent à une mauvaise réponse ?",
            "Non, et la distinction compte. Un système qui refuse 90 % des "
            "questions et un système qui y répond mal à 90 % obtiennent la même "
            "exactitude. C'est la couverture qui les sépare.",
        ),
        (
            "Puis-je faire confiance à ces chiffres ?",
            "Vous pouvez les vérifier. Le rapport porte l'empreinte de son "
            "propre contenu, du jeu de questions, et de chaque chemin exécuté. "
            "Rien n'est promu automatiquement, et la commande de reproduction "
            "est incluse.",
        ),
    ],
}


def normalise(lang: str | None) -> str:
    if not lang:
        return DEFAULT_LANG
    short = str(lang).split("-")[0].lower()
    return short if short in LANGS else DEFAULT_LANG


def t(lang: str, key: str, **kwargs: Any) -> str:
    table = STRINGS[normalise(lang)]
    template = table.get(key) or STRINGS[DEFAULT_LANG].get(key, key)
    return template.format(**kwargs) if kwargs else template
