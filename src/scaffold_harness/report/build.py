"""Construction du rapport : un objet signé, relisible par un tiers.

Ce qui doit y figurer pour qu'un lecteur qui ne vous croit pas puisse trancher :

* **sur quoi** la mesure a été faite — modèles, échafaudage, jeu de questions,
  chacun identifié par une empreinte ;
* **ce que la couche a changé** — le tableau des déviations, en pièce maîtresse
  et non en annexe ;
* **ce qu'on ne peut pas conclure** — un intervalle de confiance et une
  p-valeur, affichés même (surtout) quand ils empêchent de conclure ;
* **comment le refaire**.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from ..core import MAX_FAILURE_RATE, ComparisonReport
from ..i18n import DEFAULT_LANG, t
from ..provenance import sign

SCHEMA = "scaffold-harness-report-v1"


def build(
    comparison: ComparisonReport,
    baseline_descriptor: Mapping[str, Any],
    variant_descriptors: Mapping[str, Mapping[str, Any]],
    question_set: Mapping[str, Any],
    reproduction: str | None = None,
    notes: Mapping[str, Any] | None = None,
    include_cases: bool = True,
    max_cases: int = 400,
) -> dict[str, Any]:
    # Le rapport stocke un code et des nombres, jamais une phrase: il doit
    # pouvoir être rendu dans une autre langue sans être recalculé.
    body = {
        "schema_version": SCHEMA,
        "generated_at_unix": round(time.time(), 3),
        "question_set": dict(question_set),
        "baseline": {
            "descriptor": dict(baseline_descriptor),
            **comparison.baseline.as_dict(),
        },
        "variants": [
            {
                "descriptor": dict(variant_descriptors.get(row.name, {})),
                "outcome": comparison.outcome(row.name),
                "delta_vs_baseline": comparison.delta(row.name),
                **row.as_dict(),
            }
            for row in comparison.variants
        ],
        "reference_for_deviation": comparison.reference_name,
        "case_count": comparison.case_count,
        # Deux avertissements qui priment sur le verdict: une panne massive et
        # un noteur incertain rendent tous les autres chiffres indéfendables.
        "provider_failures": sum(
            row.failed for row in (comparison.baseline, *comparison.variants)
        ),
        "max_failure_rate": MAX_FAILURE_RATE,
        "scorer_disagreements": list(comparison.scorer_disagreements),
        # Le détail par cas, trié pour que les destructions arrivent en tête:
        # c'est ce qu'un lecteur doit voir en premier, pas les cas inchangés.
        "cases": _ordered_cases(comparison, max_cases) if include_cases else [],
        "cases_truncated": bool(
            include_cases and comparison.case_count > max_cases
        ),
        "reproduction": reproduction,
        "notes": dict(notes or {}),
        # Déclarations explicites: un rapport muet sur ces points n'est pas
        # vérifiable, et l'absence de déclaration se lit comme un aveu.
        "controls": {
            "paired_case_ids": True,
            "targets_never_shown_to_paths": True,
            "automatic_promotion": False,
        },
    }
    return sign(body)


_PRIORITY = {"destroyed": 0, "improved": 1, "neutral_change": 2, "unchanged": 3}


def _ordered_cases(comparison: ComparisonReport, limit: int) -> list[dict[str, Any]]:
    """Trie les cas: destructions d'abord, cas inchangés en dernier.

    Si le rapport doit être tronqué, ce qui se perd est ce que personne ne
    regarde. L'inverse — tronquer par ordre d'identifiant — ferait disparaître
    exactement les cas qui justifient le rapport.
    """

    def rank(case: Any) -> tuple[int, str]:
        labels = [row["label"] for row in case.variants.values()] or ["unchanged"]
        return (min(_PRIORITY.get(label, 3) for label in labels), case.case_id)

    return [case.as_dict() for case in sorted(comparison.cases, key=rank)[:limit]]


def verdict_sentence(report: Mapping[str, Any], variant: Mapping[str, Any],
                     lang: str = DEFAULT_LANG) -> str:
    """Met un code de résultat en phrase, dans la langue demandée."""
    outcome = variant.get("outcome", "inconclusive")
    delta = variant.get("delta_vs_baseline", 0.0)
    shown = f"{delta:+.1%}" if outcome == "inconclusive" else f"{abs(delta):.1%}"
    return t(lang, f"verdict.{outcome}", delta=shown,
             p=f"{variant.get('mcnemar_p', 1.0):.3f}")


def headline(report: Mapping[str, Any], lang: str = DEFAULT_LANG) -> str:
    """Une phrase pour un lecteur pressé, ou pour un objet de courriel."""
    variants = report.get("variants") or []
    if not variants:
        return t(lang, "headline.none", n=0, count=report.get("case_count", 0))
    conclusive = [row for row in variants if row.get("outcome") != "inconclusive"]
    if not conclusive:
        return t(lang, "headline.none", n=len(variants),
                 count=report.get("case_count", 0))
    best = max(conclusive, key=lambda row: row["delta_vs_baseline"])
    if best["delta_vs_baseline"] > 0:
        return t(lang, "headline.gain", name=best["name"],
                 delta=f"{best['delta_vs_baseline']:+.1%}")
    worst = min(conclusive, key=lambda row: row["delta_vs_baseline"])
    return t(lang, "headline.loss", name=worst["name"],
             delta=f"{worst['delta_vs_baseline']:+.1%}")
