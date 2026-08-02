from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaffold_harness import Case, Response, compare
from scaffold_harness.stats import mcnemar_exact, wilson_interval


def cases(count: int) -> list[Case]:
    return [Case(case_id=f"c{index}", question=f"q{index}", target=str(index))
            for index in range(count)]


def fixed(answers: dict[str, str | None], **kwargs):
    def path(case: Case) -> Response:
        return Response(case_id=case.case_id, answer=answers.get(case.case_id), **kwargs)

    return path


def scorer(response: Response, case: Case) -> bool:
    return response.answer == case.target


class StatsTests(unittest.TestCase):
    def test_wilson_is_wide_at_small_samples(self) -> None:
        # 5/5 ne prouve presque rien: la borne basse reste sous 60 %.
        low, high = wilson_interval(5, 5)
        self.assertLess(low, 0.60)
        self.assertEqual(high, 1.0)

    def test_wilson_tightens_with_more_data(self) -> None:
        low_small, _ = wilson_interval(50, 100)
        low_large, _ = wilson_interval(500, 1000)
        self.assertLess(low_small, low_large)

    def test_mcnemar_without_discordance_proves_nothing(self) -> None:
        self.assertEqual(mcnemar_exact(0, 0), 1.0)

    def test_mcnemar_detects_a_one_sided_pattern(self) -> None:
        # 0 gain contre 12 pertes: le motif observé aujourd'hui, en miniature.
        self.assertLess(mcnemar_exact(12, 0), 0.001)

    def test_mcnemar_is_symmetric(self) -> None:
        self.assertAlmostEqual(mcnemar_exact(3, 8), mcnemar_exact(8, 3))


class ComparisonTests(unittest.TestCase):
    def test_scaffold_that_only_destroys_is_reported_as_such(self) -> None:
        # Le cas mesuré en vrai: la couche modifie des réponses justes et
        # n'en répare aucune. Le score agrégé baisse, mais c'est le tableau
        # des déviations qui nomme la cause.
        rows = cases(30)
        reference = fixed({f"c{i}": str(i) for i in range(30)})
        wrecker = fixed({f"c{i}": ("BAD" if i < 12 else str(i)) for i in range(30)})
        report = compare(rows, reference, {"scaffold": wrecker}, scorer)
        variant = report.variants[0]
        self.assertEqual(variant.correct, 18)
        self.assertEqual(variant.deviation_vs_reference.changed, 12)
        self.assertEqual(variant.deviation_vs_reference.destroyed, 12)
        self.assertEqual(variant.deviation_vs_reference.improved, 0)
        self.assertEqual(variant.deviation_vs_reference.net, -12)
        self.assertEqual(report.outcome("scaffold"), "loss")

    def test_a_one_sided_pattern_too_small_to_conclude_is_refused(self) -> None:
        # Quatre destructions, zéro réparation: la direction est nette, mais
        # p = 0,125. L'instrument doit refuser de conclure plutôt que
        # d'annoncer une dégradation qu'il ne peut pas établir.
        rows = cases(10)
        reference = fixed({f"c{i}": str(i) for i in range(10)})
        wrecker = fixed({f"c{i}": ("BAD" if i < 4 else str(i)) for i in range(10)})
        report = compare(rows, reference, {"scaffold": wrecker}, scorer)
        self.assertEqual(report.variants[0].deviation_vs_reference.destroyed, 4)
        self.assertFalse(report.variants[0].significant_at_05)
        self.assertEqual(report.outcome("scaffold"), "inconclusive")

    def test_a_scaffold_that_helps_is_reported_as_such(self) -> None:
        rows = cases(20)
        weak = fixed({f"c{i}": ("BAD" if i < 12 else str(i)) for i in range(20)})
        strong = fixed({f"c{i}": str(i) for i in range(20)})
        report = compare(rows, weak, {"scaffold": strong}, scorer)
        variant = report.variants[0]
        self.assertEqual(variant.deviation_vs_reference.improved, 12)
        self.assertEqual(variant.deviation_vs_reference.destroyed, 0)
        self.assertEqual(report.outcome("scaffold"), "gain")

    def test_small_sample_difference_is_declared_non_significant(self) -> None:
        # Deux réponses d'écart sur dix cas: le verdict doit refuser de conclure
        # au lieu d'annoncer une amélioration.
        rows = cases(10)
        weak = fixed({f"c{i}": ("BAD" if i < 2 else str(i)) for i in range(10)})
        slightly = fixed({f"c{i}": str(i) for i in range(10)})
        report = compare(rows, weak, {"scaffold": slightly}, scorer)
        self.assertFalse(report.variants[0].significant_at_05)
        self.assertEqual(report.outcome("scaffold"), "inconclusive")

    def test_deviation_is_counted_against_a_deterministic_reference(self) -> None:
        # Le modèle nu est mauvais, l'exécuteur est parfait, l'échafaudage
        # réécrit l'exécuteur. Compté contre le modèle nu, l'échafaudage a
        # l'air bon; compté contre l'exécuteur, il détruit. C'est cette
        # distinction qui a révélé les 4316 destructions.
        rows = cases(10)
        bare = fixed({f"c{i}": "BAD" for i in range(10)})
        executor = fixed({f"c{i}": str(i) for i in range(10)})
        scaffold = fixed({f"c{i}": ("BAD" if i < 3 else str(i)) for i in range(10)})

        against_bare = compare(rows, bare, {"s": scaffold}, scorer)
        self.assertEqual(against_bare.variants[0].deviation_vs_reference.improved, 7)
        self.assertEqual(against_bare.variants[0].deviation_vs_reference.destroyed, 0)

        against_executor = compare(
            rows, bare, {"s": scaffold}, scorer,
            reference=executor, reference_name="executor",
        )
        self.assertEqual(against_executor.variants[0].deviation_vs_reference.destroyed, 3)
        self.assertEqual(against_executor.variants[0].deviation_vs_reference.improved, 0)

    def test_refusals_are_reported_as_coverage_not_as_errors(self) -> None:
        rows = cases(10)
        bare = fixed({f"c{i}": str(i) for i in range(10)})
        partial = lambda case: Response(
            case_id=case.case_id,
            answer=None if int(case.case_id[1:]) >= 3 else case.target,
            refused=int(case.case_id[1:]) >= 3,
        )
        report = compare(rows, bare, {"expert": partial}, scorer)
        row = report.variants[0].as_dict()
        self.assertEqual(row["refused"], 7)
        self.assertAlmostEqual(row["coverage"], 0.3)

    def test_duplicate_case_ids_are_refused(self) -> None:
        duplicated = [Case("same", "q"), Case("same", "q")]
        bare = fixed({"same": "x"})
        with self.assertRaisesRegex(ValueError, "uniques"):
            compare(duplicated, bare, {"v": bare}, scorer)


if __name__ == "__main__":
    unittest.main()
