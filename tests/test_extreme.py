"""Tests extrêmes : est-ce que l'instrument ment sous pression ?

Pour un outil de mesure, « est-ce que ça tourne » n'est pas la question. La
question est : **existe-t-il une entrée qui lui fait afficher un chiffre faux
sans planter ?** Un plantage se voit ; un chiffre faux se publie.

Trois familles :

* **invariants métamorphiques** — des propriétés qui doivent tenir quelle que
  soit l'entrée. Mélanger l'ordre des questions ne peut pas changer un résultat ;
  comparer un chemin à lui-même ne peut pas produire de destruction. Ces tests
  attrapent des bugs qu'aucun cas d'exemple ne révèle.
* **statistiques contre valeurs connues** — Wilson et McNemar ont des réponses
  publiées. Si les nôtres divergent, tout le reste est décoratif.
* **entrées dégénérées et hostiles** — tout refusé, tout en panne, un seul cas,
  du HTML dans les questions, des réponses de 100 000 caractères.
"""

from __future__ import annotations

import random
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaffold_harness import Case, Response, compare  # noqa: E402
from scaffold_harness.report import build, render  # noqa: E402
from scaffold_harness.stats import mcnemar_exact, wilson_interval  # noqa: E402


def scorer(response: Response, case: Case) -> bool:
    return response.answer == case.target


def path_from(table):
    return lambda case: Response(case_id=case.case_id, answer=table.get(case.case_id))


def build_set(count: int, wrong_before: int = 0):
    cases = [Case(f"c{i}", f"q{i}", target=str(i)) for i in range(count)]
    good = {f"c{i}": str(i) for i in range(count)}
    bad = {f"c{i}": ("X" if i < wrong_before else str(i)) for i in range(count)}
    return cases, good, bad


class MetamorphicTests(unittest.TestCase):
    """Propriétés qui doivent tenir quelle que soit l'entrée."""

    def test_shuffling_the_questions_changes_nothing(self) -> None:
        cases, good, bad = build_set(60, 20)
        straight = compare(cases, path_from(good), {"v": path_from(bad)}, scorer)
        shuffled = list(cases)
        random.Random(7).shuffle(shuffled)
        mixed = compare(shuffled, path_from(good), {"v": path_from(bad)}, scorer)
        self.assertEqual(straight.variants[0].accuracy, mixed.variants[0].accuracy)
        self.assertEqual(
            straight.variants[0].deviation_vs_reference.as_dict(),
            mixed.variants[0].deviation_vs_reference.as_dict(),
        )
        self.assertEqual(straight.variants[0].mcnemar_p, mixed.variants[0].mcnemar_p)

    def test_comparing_a_path_to_itself_can_never_destroy(self) -> None:
        # Le test le plus simple, et celui qu'un bug d'appariement fait tomber
        # immédiatement.
        cases, good, _ = build_set(40, 0)
        report = compare(cases, path_from(good), {"clone": path_from(good)}, scorer)
        deviation = report.variants[0].deviation_vs_reference
        self.assertEqual(deviation.changed, 0)
        self.assertEqual(deviation.destroyed, 0)
        self.assertEqual(deviation.improved, 0)
        self.assertEqual(report.variants[0].mcnemar_p, 1.0)
        self.assertEqual(report.outcome("clone"), "inconclusive")

    def test_duplicating_the_corpus_keeps_rates_and_doubles_counts(self) -> None:
        cases, good, bad = build_set(30, 9)
        single = compare(cases, path_from(good), {"v": path_from(bad)}, scorer)
        doubled_cases = cases + [
            Case(f"{case.case_id}-bis", case.question, target=case.target)
            for case in cases
        ]
        good2 = {**good, **{f"c{i}-bis": str(i) for i in range(30)}}
        bad2 = {**bad, **{f"c{i}-bis": ("X" if i < 9 else str(i)) for i in range(30)}}
        doubled = compare(doubled_cases, path_from(good2), {"v": path_from(bad2)}, scorer)
        self.assertAlmostEqual(single.variants[0].accuracy, doubled.variants[0].accuracy)
        self.assertEqual(
            2 * single.variants[0].deviation_vs_reference.destroyed,
            doubled.variants[0].deviation_vs_reference.destroyed,
        )
        # Plus de données, intervalle plus serré: la statistique doit réagir.
        self.assertLess(
            doubled.variants[0].accuracy_ci95[1] - doubled.variants[0].accuracy_ci95[0],
            single.variants[0].accuracy_ci95[1] - single.variants[0].accuracy_ci95[0],
        )

    def test_swapping_the_two_paths_inverts_wins_and_keeps_the_p_value(self) -> None:
        cases, good, bad = build_set(50, 14)
        forward = compare(cases, path_from(good), {"v": path_from(bad)}, scorer)
        backward = compare(cases, path_from(bad), {"v": path_from(good)}, scorer)
        self.assertEqual(forward.variants[0].paired_losses, backward.variants[0].paired_wins)
        self.assertEqual(forward.variants[0].paired_wins, backward.variants[0].paired_losses)
        self.assertAlmostEqual(forward.variants[0].mcnemar_p, backward.variants[0].mcnemar_p)

    def test_deviation_matches_paired_counts_when_reference_is_the_baseline(self) -> None:
        # Sans référence déterministe, «détruites» doit coïncider exactement
        # avec les pertes appariées. Une divergence signalerait deux comptes
        # indépendants qui dérivent l'un de l'autre.
        cases, good, bad = build_set(45, 17)
        report = compare(cases, path_from(good), {"v": path_from(bad)}, scorer)
        row = report.variants[0]
        self.assertEqual(row.deviation_vs_reference.destroyed, row.paired_losses)
        self.assertEqual(row.deviation_vs_reference.improved, row.paired_wins)


class KnownStatisticsTests(unittest.TestCase):
    """Valeurs publiées. Si elles divergent, tout le reste est décoratif."""

    def test_mcnemar_matches_hand_computable_values(self) -> None:
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertEqual(mcnemar_exact(1, 0), 1.0)          # 2 × 1/2
        self.assertAlmostEqual(mcnemar_exact(4, 0), 0.125)   # 2 × 1/16
        self.assertAlmostEqual(mcnemar_exact(10, 0), 2 / 1024)
        self.assertEqual(mcnemar_exact(5, 5), 1.0)           # parfaitement symétrique

    def test_mcnemar_never_leaves_the_unit_interval(self) -> None:
        for left in range(0, 25):
            for right in range(0, 25):
                value = mcnemar_exact(left, right)
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_wilson_brackets_the_proportion_and_stays_bounded(self) -> None:
        for successes, total in ((0, 10), (1, 10), (5, 10), (9, 10), (10, 10), (1, 1)):
            low, high = wilson_interval(successes, total)
            self.assertGreaterEqual(low, 0.0)
            self.assertLessEqual(high, 1.0)
            self.assertLessEqual(low, successes / total)
            self.assertGreaterEqual(high, successes / total)

    def test_wilson_refuses_impossible_counts(self) -> None:
        with self.assertRaises(ValueError):
            wilson_interval(11, 10)


class DegenerateInputTests(unittest.TestCase):
    def test_a_single_case_produces_a_maximally_wide_interval(self) -> None:
        report = compare(
            [Case("only", "q", target="1")],
            path_from({"only": "1"}),
            {"v": path_from({"only": "1"})},
            scorer,
        )
        low, high = report.variants[0].accuracy_ci95
        self.assertLess(low, 0.35)  # 1/1 ne prouve rien
        self.assertEqual(high, 1.0)

    def test_a_path_that_refuses_everything_reports_zero_coverage(self) -> None:
        cases, good, _ = build_set(20)
        silent = lambda case: Response(case.case_id, None, refused=True)  # noqa: E731
        report = compare(cases, path_from(good), {"mute": silent}, scorer)
        row = report.variants[0].as_dict()
        self.assertEqual(row["coverage"], 0.0)
        self.assertEqual(row["refused"], 20)
        self.assertEqual(row["correct"], 0)

    def test_a_path_that_crashes_everywhere_is_not_confused_with_refusal(self) -> None:
        cases, good, _ = build_set(15)
        broken = lambda case: Response(  # noqa: E731
            case.case_id, None, contract_valid=False, refused=False, raw="boom"
        )
        report = compare(cases, path_from(good), {"broken": broken}, scorer)
        row = report.variants[0].as_dict()
        self.assertEqual(row["refused"], 0)
        self.assertEqual(row["coverage"], 1.0)
        self.assertEqual(row["contract_valid"], 0)

    def test_an_empty_question_set_is_refused_loudly(self) -> None:
        with self.assertRaises(ValueError):
            compare([], path_from({}), {"v": path_from({})}, scorer)

    def test_missing_answers_on_both_sides_count_as_unchanged(self) -> None:
        cases = [Case("a", "q", target="1")]
        empty = lambda case: Response(case.case_id, None)  # noqa: E731
        report = compare(cases, empty, {"v": empty}, scorer)
        self.assertEqual(report.variants[0].deviation_vs_reference.unchanged, 1)


class HostileContentTests(unittest.TestCase):
    def test_markup_in_questions_and_answers_never_reaches_the_page(self) -> None:
        cases = [Case("x", "<script>alert('q')</script>", target="<b>t</b>")]
        attack = lambda case: Response(  # noqa: E731
            case.case_id, "<img src=x onerror=alert('a')>"
        )
        report = compare(cases, path_from({"x": "<b>t</b>"}), {"v": attack}, scorer)
        page = render(build(report, {}, {}, {"name": "<svg onload=alert(1)>"}))
        for payload in ("<script>alert", "<img src=x", "<svg onload"):
            self.assertNotIn(payload, page)
        self.assertIn("&lt;script&gt;", page)

    def test_a_hundred_thousand_character_answer_does_not_blow_up_the_page(self) -> None:
        cases = [Case("x", "q", target="1")]
        flood = lambda case: Response(case.case_id, "9" * 100_000)  # noqa: E731
        report = compare(cases, path_from({"x": "1"}), {"v": flood}, scorer)
        page = render(build(report, {}, {}, {"name": "flood"}))
        self.assertLess(len(page), 200_000)  # la réponse est écourtée

    def test_unicode_and_bidirectional_text_survive_the_round_trip(self) -> None:
        cases = [Case("x", "Combien font ٢+٢ ? — عربى · 中文 · 🧮", target="4")]
        report = compare(
            cases, path_from({"x": "4"}), {"v": path_from({"x": "٤"})}, scorer
        )
        page = render(build(report, {}, {}, {"name": "unicode"}))
        self.assertIn("🧮", page)
        self.assertIn("中文", page)


class ScaleTests(unittest.TestCase):
    def test_ten_thousand_cases_stay_fast_and_exact(self) -> None:
        cases, good, bad = build_set(10_000, 3_000)
        started = time.perf_counter()
        report = compare(cases, path_from(good), {"v": path_from(bad)}, scorer)
        elapsed = time.perf_counter() - started
        self.assertEqual(report.case_count, 10_000)
        self.assertEqual(report.variants[0].correct, 7_000)
        self.assertEqual(report.variants[0].deviation_vs_reference.destroyed, 3_000)
        self.assertLess(elapsed, 20.0)

    def test_a_large_report_is_truncated_on_the_useful_cases(self) -> None:
        # Tronquer par identifiant ferait disparaître exactement les cas qui
        # justifient le rapport. Les destructions doivent survivre.
        cases, good, bad = build_set(5_000, 120)
        report = build(
            compare(cases, path_from(good), {"v": path_from(bad)}, scorer),
            {}, {}, {"name": "large"}, max_cases=200,
        )
        self.assertTrue(report["cases_truncated"])
        self.assertEqual(len(report["cases"]), 200)
        destroyed = sum(
            1
            for case in report["cases"]
            if case["variants"]["v"]["label"] == "destroyed"
        )
        self.assertEqual(destroyed, 120)  # toutes conservées


if __name__ == "__main__":
    unittest.main()


class LargeSampleStatisticsTests(unittest.TestCase):
    """Les deux bugs trouvés par les tests extrêmes, verrouillés."""

    def test_thousands_of_discordant_pairs_do_not_overflow(self) -> None:
        # `2**3000` dépasse la plage des flottants: la version naïve levait
        # OverflowError et faisait tomber toute la notation.
        self.assertEqual(mcnemar_exact(3_000, 0), 0.0)
        self.assertEqual(mcnemar_exact(0, 5_000), 0.0)
        self.assertAlmostEqual(mcnemar_exact(2_500, 2_500), 1.0, places=6)

    def test_the_log_path_agrees_with_the_exact_one_at_the_boundary(self) -> None:
        # Les deux chemins doivent se rejoindre autour du seuil de bascule.
        for left, right in ((450, 460), (500, 480), (899, 890)):
            exact = mcnemar_exact(left, right)
            self.assertGreaterEqual(exact, 0.0)
            self.assertLessEqual(exact, 1.0)
        self.assertAlmostEqual(mcnemar_exact(901, 899), mcnemar_exact(899, 901))

    def test_a_perfect_score_has_an_upper_bound_of_exactly_one(self) -> None:
        for total in (1, 10, 800, 10_000):
            self.assertEqual(wilson_interval(total, total)[1], 1.0)
            self.assertEqual(wilson_interval(0, total)[0], 0.0)


class ProviderFailureTests(unittest.TestCase):
    """Une panne massive ne doit pas être imputée à la couche mesurée."""

    def test_failures_are_counted_apart_from_wrong_and_refused(self) -> None:
        cases, good, _ = build_set(20)
        broken = lambda case: Response(  # noqa: E731
            case.case_id, None, contract_valid=False, failed=True
        )
        report = compare(cases, path_from(good), {"down": broken}, scorer)
        row = report.variants[0].as_dict()
        self.assertEqual(row["failed"], 20)
        self.assertEqual(row["failure_rate"], 1.0)
        self.assertEqual(row["refused"], 0)

    def test_a_massive_outage_forces_the_verdict_to_abstain(self) -> None:
        # Sans ce garde-fou, une API tombée produirait un «LOSS» retentissant
        # qui n'apprend rien sur l'échafaudage.
        cases, good, _ = build_set(100)
        half = lambda case: Response(  # noqa: E731
            case.case_id,
            None if int(case.case_id[1:]) < 40 else good[case.case_id],
            failed=int(case.case_id[1:]) < 40,
        )
        report = compare(cases, path_from(good), {"flaky": half}, scorer)
        self.assertGreater(report.variants[0].failed, 5)
        self.assertEqual(report.outcome("flaky"), "inconclusive")

    def test_a_few_failures_do_not_silence_a_real_verdict(self) -> None:
        cases, good, bad = build_set(200, 60)
        one_bad = lambda case: Response(  # noqa: E731
            case.case_id,
            None if case.case_id == "c0" else bad[case.case_id],
            failed=case.case_id == "c0",
        )
        report = compare(cases, path_from(good), {"v": one_bad}, scorer)
        self.assertEqual(report.variants[0].failed, 1)
        self.assertEqual(report.outcome("v"), "loss")


class ScorerAuditTests(unittest.TestCase):
    """Un harnais dont le noteur ment produit des chiffres faux avec aplomb."""

    def test_two_agreeing_scorers_report_no_disagreement(self) -> None:
        cases, good, bad = build_set(30, 10)
        report = compare(
            cases, path_from(good), {"v": path_from(bad)}, scorer, audit_scorer=scorer
        )
        self.assertEqual(report.scorer_disagreements, ())

    def test_a_stricter_scorer_exposes_every_case_where_grading_decides(self) -> None:
        # Reproduction du cas réel: un noteur qui exigeait une enveloppe stricte
        # rejetait des réponses justes parce que le modèle recopiait les clés de
        # son outil à côté. 43 réponses, toutes dans les bras qui recevaient une
        # proposition d'expert.
        cases = [Case(f"c{i}", f"q{i}", target="7") for i in range(10)]
        chatty = lambda case: Response(  # noqa: E731
            case.case_id, "7", raw='{"answer":"7","source":"tool"}'
        )
        picky = lambda response, case: response.raw == '{"answer":"7"}'  # noqa: E731
        report = compare(
            cases, chatty, {"v": chatty}, scorer, audit_scorer=picky
        )
        # Les deux chemins sont audités: 10 cas × 2 = 20 désaccords.
        self.assertEqual(len(report.scorer_disagreements), 20)
        self.assertTrue(
            all(":" in entry for entry in report.scorer_disagreements)
        )

    def test_the_report_carries_the_warning(self) -> None:
        cases = [Case("a", "q", target="1")]
        path = lambda case: Response(case.case_id, "1")  # noqa: E731
        never = lambda response, case: False  # noqa: E731
        artefact = build(
            compare(cases, path, {"v": path}, scorer, audit_scorer=never),
            {}, {}, {"name": "audit"},
        )
        self.assertEqual(len(artefact["scorer_disagreements"]), 2)
        page = render(artefact)
        self.assertIn("two graders disagree", page)
        self.assertIn("deux correcteurs sont en désaccord", page)
