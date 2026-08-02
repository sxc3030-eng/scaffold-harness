from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaffold_harness import Case, Response, compare  # noqa: E402
from scaffold_harness.adapters import (  # noqa: E402
    OllamaChat,
    OpenAICompatibleChat,
    PythonPath,
    Refusal,
)
from scaffold_harness.scoring import exact_rational  # noqa: E402

CASE = Case(case_id="c0", question="2+2 ?", target="4")


class PythonPathTests(unittest.TestCase):
    def test_a_plain_function_becomes_a_measurable_path(self) -> None:
        path = PythonPath(lambda question: "4", name="calculatrice")
        response = path(CASE)
        self.assertEqual(response.answer, "4")
        self.assertFalse(response.refused)
        self.assertTrue(response.contract_valid)

    def test_refusal_is_coverage_not_error(self) -> None:
        def picky(question: str) -> str:
            raise Refusal("hors domaine")

        response = PythonPath(picky)(CASE)
        self.assertTrue(response.refused)
        self.assertTrue(response.contract_valid)  # refuser proprement est valide
        self.assertIsNone(response.answer)

    def test_a_crash_is_an_error_not_a_refusal(self) -> None:
        def broken(question: str) -> str:
            raise ZeroDivisionError("boum")

        response = PythonPath(broken)(CASE)
        self.assertFalse(response.refused)
        self.assertFalse(response.contract_valid)
        self.assertIn("ZeroDivisionError", response.raw)

    def test_descriptor_identifies_what_ran(self) -> None:
        path = PythonPath(lambda q: "4", name="executeur", version="1.2.0")
        descriptor = path.descriptor()
        self.assertEqual(descriptor["name"], "executeur")
        self.assertEqual(descriptor["version"], "1.2.0")

    def test_a_path_may_return_a_full_response(self) -> None:
        def rich(case: Case) -> Response:
            return Response(case_id=case.case_id, answer="4", input_tokens=11)

        response = PythonPath(rich, pass_case=True)(CASE)
        self.assertEqual(response.input_tokens, 11)


class OllamaTests(unittest.TestCase):
    def test_real_token_counts_are_preferred_over_estimates(self) -> None:
        payload = {
            "message": {"content": " 4 "},
            "prompt_eval_count": 37,
            "eval_count": 5,
        }
        adapter = OllamaChat(model="gemma3:12b-it-qat")
        with mock.patch(
            "scaffold_harness.adapters.ollama.post_json", return_value=payload
        ) as call:
            response = adapter(CASE)
        self.assertEqual(response.answer, "4")
        self.assertEqual(response.input_tokens, 37)
        self.assertEqual(response.output_tokens, 5)
        self.assertIn("/api/chat", call.call_args[0][0])

    def test_missing_counts_fall_back_to_an_estimate(self) -> None:
        adapter = OllamaChat(model="m")
        with mock.patch(
            "scaffold_harness.adapters.ollama.post_json",
            return_value={"message": {"content": "4"}},
        ):
            response = adapter(CASE)
        self.assertGreater(response.input_tokens, 0)

    def test_an_empty_answer_counts_as_a_refusal(self) -> None:
        adapter = OllamaChat(model="m")
        with mock.patch(
            "scaffold_harness.adapters.ollama.post_json",
            return_value={"message": {"content": "   "}},
        ):
            response = adapter(CASE)
        self.assertTrue(response.refused)
        self.assertIsNone(response.answer)

    def test_the_system_prompt_is_sent_and_hashed_not_copied(self) -> None:
        adapter = OllamaChat(model="m", system="Réponds par un nombre.")
        with mock.patch(
            "scaffold_harness.adapters.ollama.post_json",
            return_value={"message": {"content": "4"}},
        ) as call:
            adapter(CASE)
        sent = call.call_args[0][1]["messages"]
        self.assertEqual(sent[0]["role"], "system")
        descriptor = adapter.descriptor()
        self.assertEqual(len(descriptor["system_sha256"]), 64)
        self.assertNotIn("Réponds", str(descriptor))


class OpenAICompatibleTests(unittest.TestCase):
    def test_usage_is_read_from_the_response(self) -> None:
        payload = {
            "choices": [{"message": {"content": "4"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        }
        adapter = OpenAICompatibleChat(model="gpt-x", api_key="secret")
        with mock.patch(
            "scaffold_harness.adapters.openai_compatible.post_json",
            return_value=payload,
        ) as call:
            response = adapter(CASE)
        self.assertEqual(response.input_tokens, 12)
        self.assertEqual(call.call_args[1]["headers"]["Authorization"], "Bearer secret")

    def test_the_api_key_never_reaches_the_descriptor(self) -> None:
        adapter = OpenAICompatibleChat(model="m", api_key="tres-secret")
        descriptor = adapter.descriptor()
        self.assertTrue(descriptor["api_key_present"])
        self.assertNotIn("tres-secret", str(descriptor))


class IntegrationTests(unittest.TestCase):
    def test_a_refusing_expert_against_a_bare_model(self) -> None:
        # L'expert ne couvre qu'un cas sur trois; le modèle nu répond toujours,
        # mal. Le rapport doit montrer la couverture, pas seulement le score.
        cases = [
            Case(case_id="c0", question="2+2 ?", target="4"),
            Case(case_id="c1", question="capitale ?", target="Paris"),
            Case(case_id="c2", question="pourquoi ?", target="42"),
        ]

        def bare(question: str) -> str:
            return "BAD"

        def expert(question: str) -> str:
            if question == "2+2 ?":
                return "4"
            raise Refusal("hors domaine")

        report = compare(
            cases,
            PythonPath(bare, name="nu"),
            {"expert": PythonPath(expert, name="expert")},
            exact_rational,
        )
        row = report.variants[0].as_dict()
        self.assertEqual(row["correct"], 1)
        self.assertEqual(row["refused"], 2)
        self.assertAlmostEqual(row["coverage"], 1 / 3)


if __name__ == "__main__":
    unittest.main()
