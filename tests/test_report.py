from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaffold_harness import Case, Response, compare  # noqa: E402
from scaffold_harness.provenance import verify  # noqa: E402
from scaffold_harness.report import build, headline, render  # noqa: E402
from scaffold_harness.scoring import exact_rational  # noqa: E402


def cases(count: int) -> list[Case]:
    return [Case(case_id=f"c{i}", question=f"q{i}", target=str(i)) for i in range(count)]


def fixed(answers):
    return lambda case: Response(case_id=case.case_id, answer=answers(case.case_id))


def wreck(count: int, broken: int):
    rows = cases(count)
    reference = fixed(lambda cid: cid[1:])
    scaffold = fixed(lambda cid: "BAD" if int(cid[1:]) < broken else cid[1:])
    return compare(rows, reference, {"ma-couche": scaffold}, exact_rational)


class ReportTests(unittest.TestCase):
    def test_the_report_is_signed_and_verifiable(self) -> None:
        report = build(
            wreck(30, 12),
            {"kind": "OllamaChat", "model": "granite"},
            {"ma-couche": {"kind": "PythonPath", "name": "agent"}},
            {"name": "demo", "sha256": "a" * 64, "count": 30},
        )
        self.assertTrue(verify(report))
        tampered = {**report, "case_count": 999}
        self.assertFalse(verify(tampered))

    def test_a_degradation_is_named_in_the_headline(self) -> None:
        report = build(wreck(30, 12), {}, {}, {"name": "demo"})
        self.assertIn("degrades", headline(report))
        self.assertIn("dégrade", headline(report, "fr"))

    def test_a_non_conclusive_sample_is_declared_as_such(self) -> None:
        report = build(wreck(10, 4), {}, {}, {"name": "demo"})
        self.assertIn("None of the", headline(report))
        self.assertIn("Aucune des", headline(report, "fr"))
        self.assertEqual(report["variants"][0]["outcome"], "inconclusive")

    def test_controls_are_declared_explicitly(self) -> None:
        report = build(wreck(30, 12), {}, {}, {"name": "demo"})
        self.assertIn("controls", report)
        self.assertIs(report["controls"]["automatic_promotion"], False)

    def test_the_deviation_table_reaches_the_report(self) -> None:
        report = build(wreck(30, 12), {}, {}, {"name": "demo"})
        deviation = report["variants"][0]["deviation_vs_reference"]
        self.assertEqual(deviation["destroyed"], 12)
        self.assertEqual(deviation["improved"], 0)
        self.assertEqual(deviation["net"], -12)


class HtmlTests(unittest.TestCase):
    def test_html_is_standalone_and_shows_the_deviation_table(self) -> None:
        report = build(
            wreck(30, 12),
            {"model": "granite"},
            {"ma-couche": {"name": "agent"}},
            {"name": "demo", "sha256": "b" * 64},
            reproduction="scaffold-harness run demo.json",
        )
        page = render(report)
        self.assertTrue(page.startswith("<!doctype html>"))
        # Autonome: rien à télécharger. Le seul script est en ligne.
        self.assertNotIn("<link", page)
        self.assertNotIn("src=", page)
        self.assertNotIn("http://", page)
        # Les deux langues sont dans le fichier: le destinataire n'a pas à
        # redemander une autre version.
        self.assertIn("What your layer changed", page)
        self.assertIn("Ce que votre couche a changé", page)
        self.assertIn("destroyed", page)
        self.assertIn("détruites", page)
        self.assertIn("scaffold-harness run demo.json", page)
        self.assertIn(report["report_sha256"], page)

    def test_the_page_still_reads_without_javascript(self) -> None:
        # Un rapport peut être imprimé, converti en PDF, ou ouvert avec le
        # script bloqué. L'anglais doit rester visible par la seule CSS.
        page = render(build(wreck(30, 12), {}, {}, {"name": "demo"}))
        self.assertIn('<html lang="en">', page)
        self.assertIn(':root[lang="en"] [data-lang="en"]', page)

    def test_a_single_language_render_carries_no_switch(self) -> None:
        page = render(build(wreck(30, 12), {}, {}, {"name": "demo"}), lang="fr")
        self.assertIn("Ce que votre couche a changé", page)
        self.assertNotIn("What your layer changed", page)

    def test_html_marks_an_inconclusive_run_as_uncertain(self) -> None:
        page = render(build(wreck(10, 4), {}, {}, {"name": "demo"}))
        self.assertIn("verdict inconclusive", page)
        self.assertNotIn("verdict loss", page)

    def test_html_escapes_hostile_names(self) -> None:
        comparison = wreck(30, 12)
        report = build(
            comparison,
            {},
            {"ma-couche": {"name": "<script>alert(1)</script>"}},
            {"name": "<img src=x onerror=alert(1)>"},
        )
        page = render(report)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn("<img src=x", page)


if __name__ == "__main__":
    unittest.main()
