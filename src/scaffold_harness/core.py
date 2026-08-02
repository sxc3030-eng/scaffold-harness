"""Comparaison appariée d'un échafaudage contre le modèle nu.

Les harnais d'évaluation existants répondent à « quel score fait mon système ».
Celui-ci répond à une autre question, que presque personne ne pose:

    quand ma couche a MODIFIÉ la réponse, l'a-t-elle améliorée ou détruite ?

La distinction n'est pas cosmétique. Un système mesuré sur 800 questions a
modifié 4316 réponses de sa référence déterministe: 4316 destructions, aucune
amélioration. Son score agrégé, lui, avait l'air correct. Aucun benchmark
classique ne pouvait le voir, parce qu'aucun ne compare les réponses deux à
deux.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .stats import mcnemar_exact, wilson_interval


@dataclass(frozen=True)
class Case:
    """Une question, sa cible éventuelle, ses métadonnées publiques."""

    case_id: str
    question: str
    target: Any | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    """Ce qu'un chemin (modèle nu ou échafaudage) a produit pour un cas.

    `refused` distingue « je ne sais pas » d'une mauvaise réponse. C'est la
    seule métrique qui permette de mesurer la couverture réelle d'un système:
    un exécuteur qui refuse 92 % du monde réel et se trompe sur les 8 % restants
    a un profil radicalement différent d'un système qui répond toujours mal, et
    aucun score agrégé ne les distingue.
    """

    case_id: str
    answer: str | None
    contract_valid: bool = True
    refused: bool = False
    # Panne du fournisseur: ni une mauvaise réponse, ni un refus. Sans ce
    # troisième état, un run où l'API est tombée affiche une exactitude basse
    # sans jamais dire pourquoi — un mensonge par omission.
    failed: bool = False
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    raw: str = ""


Scorer = Callable[[Response, Case], bool]
Path = Callable[[Case], Response]

# Au-delà de ce taux de pannes, un résultat n'est plus attribuable à la couche
# mesurée. Cinq pour cent est déjà beaucoup pour un run qu'on veut publier.
MAX_FAILURE_RATE = 0.05


@dataclass(frozen=True)
class Deviation:
    """Ce que la variante a fait des réponses de la référence."""

    changed: int
    improved: int
    destroyed: int
    neutral_changed: int
    unchanged: int

    @property
    def net(self) -> int:
        return self.improved - self.destroyed

    def as_dict(self) -> dict[str, int]:
        return {
            "changed": self.changed,
            "improved": self.improved,
            "destroyed": self.destroyed,
            "neutral_changed": self.neutral_changed,
            "unchanged": self.unchanged,
            "net": self.net,
        }


@dataclass(frozen=True)
class VariantResult:
    name: str
    cases: int
    correct: int
    contract_valid: int
    refused: int
    failed: int
    accuracy: float
    accuracy_ci95: tuple[float, float]
    deviation_vs_reference: Deviation
    paired_wins: int
    paired_losses: int
    mcnemar_p: float
    significant_at_05: bool
    mean_input_tokens: float
    mean_output_tokens: float
    p95_latency_ms: float
    token_ratio_vs_baseline: float
    latency_ratio_vs_baseline: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cases": self.cases,
            "correct": self.correct,
            "accuracy": self.accuracy,
            "accuracy_ci95": list(self.accuracy_ci95),
            "contract_valid": self.contract_valid,
            "refused": self.refused,
            "failed": self.failed,
            "failure_rate": self.failed / self.cases if self.cases else 0.0,
            "coverage": (self.cases - self.refused) / self.cases if self.cases else 0.0,
            "deviation_vs_reference": self.deviation_vs_reference.as_dict(),
            "paired_wins_vs_baseline": self.paired_wins,
            "paired_losses_vs_baseline": self.paired_losses,
            "mcnemar_p": self.mcnemar_p,
            "significant_at_05": self.significant_at_05,
            "mean_input_tokens": self.mean_input_tokens,
            "mean_output_tokens": self.mean_output_tokens,
            "p95_latency_ms": self.p95_latency_ms,
            "token_ratio_vs_baseline": self.token_ratio_vs_baseline,
            "latency_ratio_vs_baseline": self.latency_ratio_vs_baseline,
        }


@dataclass(frozen=True)
class CaseOutcome:
    """Le détail d'une question, pour l'écran qui compte le plus.

    Un tableau agrégé dit « votre couche a détruit 12 réponses ». Celui-ci dit
    *lesquelles*, avec ce que la référence répondait et ce que la couche a mis à
    la place. C'est le moment où un utilisateur comprend ce qui se passe chez
    lui — aucun chiffre ne remplace la lecture de trois cas détruits.
    """

    case_id: str
    question: str
    target: str | None
    reference_answer: str | None
    reference_correct: bool
    variants: Mapping[str, Mapping[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "question": self.question,
            "target": self.target,
            "reference_answer": self.reference_answer,
            "reference_correct": self.reference_correct,
            "variants": {name: dict(row) for name, row in self.variants.items()},
        }


def _label(changed: bool, was: bool, now: bool) -> str:
    if not changed:
        return "unchanged"
    if now and not was:
        return "improved"
    if was and not now:
        return "destroyed"
    return "neutral_change"


@dataclass(frozen=True)
class ComparisonReport:
    baseline: VariantResult
    variants: tuple[VariantResult, ...]
    case_count: int
    reference_name: str
    cases: tuple[CaseOutcome, ...] = ()
    scorer_disagreements: tuple[str, ...] = ()

    def _find(self, variant: str) -> VariantResult:
        found = next((row for row in self.variants if row.name == variant), None)
        if found is None:
            raise KeyError(variant)
        return found

    def delta(self, variant: str) -> float:
        """Écart d'exactitude par rapport au modèle nu."""
        return self._find(variant).accuracy - self.baseline.accuracy

    def outcome(self, variant: str) -> str:
        """Code de résultat: `gain`, `loss` ou `inconclusive`.

        Le cœur ne produit aucune prose. Il renvoie un code, et c'est la couche
        de rendu qui le met en phrase, dans la langue du lecteur. Sans cette
        séparation, un verdict finit par être modifié à l'occasion d'un
        changement de mise en forme.
        """
        found = self._find(variant)
        # Au-delà du seuil, on ne peut plus distinguer «la couche est mauvaise»
        # de «le fournisseur était en panne». Le verdict doit s'abstenir plutôt
        # que d'attribuer à l'échafaudage ce qui revient au réseau.
        if found.cases and found.failed / found.cases > MAX_FAILURE_RATE:
            return "inconclusive"
        if not found.significant_at_05:
            return "inconclusive"
        return "gain" if self.delta(variant) > 0 else "loss"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "scaffold-harness-comparison-v1",
            "case_count": self.case_count,
            "reference_for_deviation": self.reference_name,
            "baseline": self.baseline.as_dict(),
            "variants": [row.as_dict() for row in self.variants],
        }


def _percentile95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[index]


def _deviation(
    reference: Mapping[str, Response],
    variant: Mapping[str, Response],
    correct_reference: Mapping[str, bool],
    correct_variant: Mapping[str, bool],
) -> Deviation:
    changed = improved = destroyed = neutral = unchanged = 0
    for case_id, response in variant.items():
        other = reference.get(case_id)
        if other is None:
            continue
        if _same_answer(response, other):
            unchanged += 1
            continue
        changed += 1
        was = correct_reference.get(case_id, False)
        now = correct_variant.get(case_id, False)
        if now and not was:
            improved += 1
        elif was and not now:
            destroyed += 1
        else:
            neutral += 1
    return Deviation(changed, improved, destroyed, neutral, unchanged)


def _same_answer(left: Response, right: Response) -> bool:
    if left.answer is None and right.answer is None:
        return True
    if left.answer is None or right.answer is None:
        return False
    return left.answer.strip() == right.answer.strip()


def _collect(path: Path, cases: Sequence[Case]) -> dict[str, Response]:
    return {case.case_id: path(case) for case in cases}


def compare(
    cases: Iterable[Case],
    baseline: Path,
    variants: Mapping[str, Path],
    scorer: Scorer,
    reference: Path | None = None,
    reference_name: str = "baseline",
    audit_scorer: Scorer | None = None,
) -> ComparisonReport:
    """Compare des variantes au modèle nu, sur les mêmes cas, appariées.

    `audit_scorer` est un second noteur, facultatif, qui ne sert qu'à se
    contredire. Chaque désaccord est un cas où la note dépend de la manière de
    comparer et non de la réponse. Sur un système réel, un correcteur qui
    comparait des chaînes canoniques a compté faux **43 réponses justes** — un
    harnais dont le noteur ment produit des chiffres faux avec une confiance
    parfaite, et aucun autre test ne l'attrape.

    `reference` est le chemin par rapport auquel on compte les modifications.
    Par défaut c'est le modèle nu — tout le monde en a un. Si un chemin
    déterministe existe (calculateur, solveur, oracle), le passer ici rend la
    mesure bien plus tranchante: c'est ainsi qu'on découvre qu'une couche
    réécrit des réponses déjà exactes.
    """
    ordered = list(cases)
    if not ordered:
        raise ValueError("aucun cas à comparer")
    if len({case.case_id for case in ordered}) != len(ordered):
        raise ValueError("les identifiants de cas doivent être uniques")

    baseline_responses = _collect(baseline, ordered)
    reference_responses = (
        baseline_responses if reference is None else _collect(reference, ordered)
    )
    by_id = {case.case_id: case for case in ordered}

    def score_all(responses: Mapping[str, Response]) -> dict[str, bool]:
        return {
            case_id: bool(scorer(response, by_id[case_id]))
            for case_id, response in responses.items()
        }

    correct_baseline = score_all(baseline_responses)
    correct_reference = score_all(reference_responses)

    def summarise(
        name: str,
        responses: Mapping[str, Response],
        correct: Mapping[str, bool],
    ) -> VariantResult:
        total = len(ordered)
        hits = sum(correct.values())
        wins = sum(
            1
            for case_id in correct
            if correct[case_id] and not correct_baseline.get(case_id, False)
        )
        losses = sum(
            1
            for case_id in correct
            if correct_baseline.get(case_id, False) and not correct[case_id]
        )
        latencies = [row.latency_ms for row in responses.values()]
        p95 = _percentile95(latencies)
        mean_in = sum(row.input_tokens for row in responses.values()) / total
        mean_out = sum(row.output_tokens for row in responses.values()) / total
        base_tokens = sum(
            row.input_tokens + row.output_tokens for row in baseline_responses.values()
        ) / total
        base_p95 = _percentile95(
            [row.latency_ms for row in baseline_responses.values()]
        )
        p_value = mcnemar_exact(losses, wins)
        return VariantResult(
            name=name,
            cases=total,
            correct=hits,
            contract_valid=sum(row.contract_valid for row in responses.values()),
            refused=sum(row.refused for row in responses.values()),
            failed=sum(row.failed for row in responses.values()),
            accuracy=hits / total,
            accuracy_ci95=wilson_interval(hits, total),
            deviation_vs_reference=_deviation(
                reference_responses, responses, correct_reference, correct
            ),
            paired_wins=wins,
            paired_losses=losses,
            mcnemar_p=p_value,
            significant_at_05=p_value <= 0.05,
            mean_input_tokens=mean_in,
            mean_output_tokens=mean_out,
            p95_latency_ms=p95,
            token_ratio_vs_baseline=(mean_in + mean_out) / base_tokens
            if base_tokens
            else 1.0,
            latency_ratio_vs_baseline=p95 / base_p95 if base_p95 else 1.0,
        )

    # Les réponses sont collectées avant d'être résumées: le détail par cas est
    # ce qui permet la vue « quelles réponses ma couche a-t-elle cassées ».
    variant_responses = {name: _collect(path, ordered) for name, path in variants.items()}
    variant_correct = {name: score_all(rows) for name, rows in variant_responses.items()}

    disagreements: list[str] = []
    if audit_scorer is not None:
        for name, responses in {"baseline": baseline_responses, **variant_responses}.items():
            for case in ordered:
                response = responses[case.case_id]
                first = bool(scorer(response, case))
                second = bool(audit_scorer(response, case))
                if first != second:
                    disagreements.append(f"{name}:{case.case_id}")

    outcomes: list[CaseOutcome] = []
    for case in ordered:
        reference_response = reference_responses[case.case_id]
        rows: dict[str, dict[str, Any]] = {}
        for name, responses in variant_responses.items():
            response = responses[case.case_id]
            changed = not _same_answer(response, reference_response)
            was = correct_reference[case.case_id]
            now = variant_correct[name][case.case_id]
            rows[name] = {
                "answer": response.answer,
                "correct": now,
                "refused": response.refused,
                "changed": changed,
                "label": _label(changed, was, now),
            }
        outcomes.append(
            CaseOutcome(
                case_id=case.case_id,
                question=case.question,
                target=None if case.target is None else str(case.target),
                reference_answer=reference_response.answer,
                reference_correct=correct_reference[case.case_id],
                variants=rows,
            )
        )

    return ComparisonReport(
        baseline=summarise("baseline", baseline_responses, correct_baseline),
        variants=tuple(
            summarise(name, variant_responses[name], variant_correct[name])
            for name in variants
        ),
        case_count=len(ordered),
        reference_name=reference_name,
        cases=tuple(outcomes),
        scorer_disagreements=tuple(sorted(set(disagreements))),
    )
