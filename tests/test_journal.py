from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaffold_harness import Case, Response, compare  # noqa: E402
from scaffold_harness.journal import Journal, ResumeError  # noqa: E402


def cases(count: int) -> list[Case]:
    return [Case(f"c{i}", f"q{i}", target=str(i)) for i in range(count)]


def scorer(response: Response, case: Case) -> bool:
    return response.answer == case.target


class CountingPath:
    """Compte les appels réels, pour prouver qu'aucun n'est repayé."""

    def __init__(self, fail_after: int | None = None) -> None:
        self.calls = 0
        self.fail_after = fail_after

    def __call__(self, case: Case) -> Response:
        if self.fail_after is not None and self.calls >= self.fail_after:
            raise KeyboardInterrupt("incident")
        self.calls += 1
        return Response(case.case_id, case.target)


class JournalTests(unittest.TestCase):
    def test_an_interrupted_run_resumes_without_repaying(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rows = cases(20)
            manifest = {"questions_sha256": "a" * 64, "count": 20}

            first = Journal(root)
            self.assertFalse(first.guard(manifest))  # première fois: pas de reprise
            crashing = CountingPath(fail_after=12)
            wrapped = first.wrap("baseline", crashing)
            with self.assertRaises(KeyboardInterrupt):
                for case in rows:
                    wrapped(case)
            self.assertEqual(crashing.calls, 12)

            second = Journal(root)
            self.assertTrue(second.guard(manifest))  # même campagne: on reprend
            resumed = CountingPath()
            wrapped = second.wrap("baseline", resumed)
            answers = [wrapped(case).answer for case in rows]
            self.assertEqual(resumed.calls, 8)  # seuls les 8 manquants
            self.assertEqual(answers, [case.target for case in rows])

    def test_a_different_question_set_refuses_to_resume(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Journal(root).guard({"questions_sha256": "a" * 64})
            with self.assertRaisesRegex(ResumeError, "différente"):
                Journal(root).guard({"questions_sha256": "b" * 64})

    def test_a_changed_path_refuses_to_resume(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Journal(root).guard({"q": "x", "baseline": {"model": "llama3.2"}})
            with self.assertRaises(ResumeError):
                Journal(root).guard({"q": "x", "baseline": {"model": "gemma3"}})

    def test_process_identity_never_blocks_a_resume(self) -> None:
        # LE bug qui a coûté 1574 générations sur un système réel: le `pid`
        # entrait dans l'empreinte du manifeste, donc l'empreinte ne
        # correspondait jamais après une relance et aucune reprise n'était
        # possible. Les journaux incrémentaux prévus pour ça étaient du code
        # mort sans que personne le sache.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Journal(root).guard({"q": "x", "pid": 22900, "started_at": 1.0})
            self.assertTrue(
                Journal(root).guard({"q": "x", "pid": 31337, "started_at": 2.0})
            )

    def test_a_truncated_line_costs_one_case_not_the_journal(self) -> None:
        # Un incident coupe une écriture en cours. La ligne tronquée est
        # perdue et sera rejouée; les précédentes doivent survivre.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal = Journal(root)
            journal.guard({"q": "x"})
            for case in cases(5):
                journal.record("baseline", Response(case.case_id, case.target))
            path = root / "journal" / "baseline.jsonl"
            broken = path.read_text(encoding="utf-8") + '{"case_id": "c9", "ans'
            path.write_text(broken, encoding="utf-8")
            self.assertEqual(len(Journal(root).recorded("baseline")), 5)

    def test_a_resumed_run_gives_the_same_report_as_an_unbroken_one(self) -> None:
        rows = cases(30)

        def good(case: Case) -> Response:
            return Response(case.case_id, case.target)

        def bad(case: Case) -> Response:
            broken = int(case.case_id[1:]) < 9
            return Response(case.case_id, "X" if broken else case.target)

        straight = compare(rows, good, {"v": bad}, scorer)

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = {"questions_sha256": "c" * 64}
            first = Journal(root)
            first.guard(manifest)
            wrapped = first.wrap("v", bad)
            for case in rows[:11]:  # interruption au milieu
                wrapped(case)

            second = Journal(root)
            second.guard(manifest)
            resumed = compare(
                rows,
                second.wrap("baseline", good),
                {"v": second.wrap("v", bad)},
                scorer,
            )
        self.assertEqual(straight.variants[0].accuracy, resumed.variants[0].accuracy)
        self.assertEqual(
            straight.variants[0].deviation_vs_reference.as_dict(),
            resumed.variants[0].deviation_vs_reference.as_dict(),
        )

    def test_progress_reports_what_is_already_paid_for(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal = Journal(root)
            journal.guard({"q": "x"})
            for case in cases(7):
                journal.record("baseline", Response(case.case_id, "1"))
            for case in cases(3):
                journal.record("my layer", Response(case.case_id, "1"))
            self.assertEqual(journal.progress(), {"baseline": 7, "my_layer": 3})


if __name__ == "__main__":
    unittest.main()
