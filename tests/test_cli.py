from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaffold_harness.cli import ConfigError, load_questions, main  # noqa: E402


def write_questions(folder: Path, count: int = 12) -> Path:
    path = folder / "questions.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"case_id": f"c{i}", "question": f"{i}+0 ?", "target": str(i)})
            for i in range(count)
        ),
        encoding="utf-8",
    )
    return path


# Chemins de test, importables par le CLI comme le ferait un vrai échafaudage.
def perfect(question: str) -> str:
    return question.split("+")[0]


_CALLS = {"n": 0}


def reset_counter() -> None:
    _CALLS["n"] = 0


def calls_made() -> int:
    return _CALLS["n"]


def counted(question: str) -> str:
    """Compte les appels réels: la preuve qu'une reprise ne repaie rien."""
    _CALLS["n"] += 1
    return question.split("+")[0]


def wrecker(question: str) -> str:
    value = int(question.split("+")[0])
    return "BAD" if value < 6 else str(value)


class QuestionLoadingTests(unittest.TestCase):
    def test_a_missing_question_field_is_reported_with_its_line(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.jsonl"
            path.write_text('{"target": "1"}', encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "ligne|:1:"):
                load_questions(str(path))

    def test_the_question_set_is_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = write_questions(Path(folder))
            cases, descriptor = load_questions(str(path))
            self.assertEqual(len(cases), 12)
            self.assertEqual(len(descriptor["sha256"]), 64)


class RunTests(unittest.TestCase):
    def config(self, folder: Path, variant: str) -> Path:
        write_questions(folder)
        path = folder / "config.json"
        path.write_text(
            json.dumps(
                {
                    "questions": str(folder / "questions.jsonl"),
                    "scorer": "exact_rational",
                    "baseline": {"adapter": "python", "import": "test_cli:perfect"},
                    "variants": {
                        "layer": {"adapter": "python", "import": f"test_cli:{variant}"}
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_a_harmless_layer_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = main(["run", str(self.config(root, "perfect")), "--out", str(root / "o")])
            self.assertEqual(code, 0)
            report = json.loads((root / "o" / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["variants"][0]["deviation_vs_reference"]["destroyed"], 0)
            self.assertTrue((root / "o" / "report.html").is_file())

    def test_a_destructive_layer_exits_non_zero(self) -> None:
        # Un code non nul permet d'en faire une barrière d'intégration continue.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = main(["run", str(self.config(root, "wrecker")), "--out", str(root / "o")])
            self.assertEqual(code, 2)
            report = json.loads((root / "o" / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["variants"][0]["deviation_vs_reference"]["destroyed"], 6)

    def test_an_unknown_scorer_is_refused_with_the_available_list(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.config(root, "perfect")
            config = json.loads(path.read_text(encoding="utf-8"))
            config["scorer"] = "vibes"
            path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(main(["run", str(path), "--out", str(root / "o")]), 3)

    def test_a_bad_import_target_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = self.config(root, "perfect")
            config = json.loads(path.read_text(encoding="utf-8"))
            config["variants"]["layer"]["import"] = "no_colon_here"
            path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(main(["run", str(path), "--out", str(root / "o")]), 3)

    def test_single_language_output_is_honoured(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            main(["run", str(self.config(root, "perfect")), "--out", str(root / "o"),
                  "--lang", "fr"])
            page = (root / "o" / "report.html").read_text(encoding="utf-8")
            self.assertIn("Ce que votre couche a changé", page)
            self.assertNotIn("What your layer changed", page)



class ResumeTests(unittest.TestCase):
    def test_a_second_run_reuses_the_journal_instead_of_recalling(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_questions(root)
            path = root / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "questions": str(root / "questions.jsonl"),
                        "baseline": {"adapter": "python", "import": "test_cli:counted"},
                        "variants": {
                            "layer": {"adapter": "python", "import": "test_cli:counted"}
                        },
                    }
                ),
                encoding="utf-8",
            )
            reset_counter()
            main(["run", str(path), "--out", str(root / "o")])
            first = calls_made()
            self.assertEqual(first, 24)  # 12 questions x 2 chemins
            main(["run", str(path), "--out", str(root / "o")])
            self.assertEqual(calls_made(), first)  # aucun appel supplémentaire

    def test_changing_the_questions_refuses_to_resume(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_questions(root, 12)
            path = root / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "questions": str(root / "questions.jsonl"),
                        "baseline": {"adapter": "python", "import": "test_cli:perfect"},
                        "variants": {
                            "layer": {"adapter": "python", "import": "test_cli:perfect"}
                        },
                    }
                ),
                encoding="utf-8",
            )
            main(["run", str(path), "--out", str(root / "o")])
            write_questions(root, 20)  # le jeu a changé
            self.assertEqual(main(["run", str(path), "--out", str(root / "o")]), 4)

if __name__ == "__main__":
    unittest.main()
