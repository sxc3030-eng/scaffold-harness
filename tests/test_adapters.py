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


class AnthropicTests(unittest.TestCase):
    def test_system_is_a_top_level_field_not_a_message(self) -> None:
        from scaffold_harness.adapters import AnthropicChat

        payload = {
            "content": [{"type": "text", "text": "4"}],
            "usage": {"input_tokens": 21, "output_tokens": 2},
        }
        adapter = AnthropicChat(model="claude-x", api_key="k", system="Be exact.")
        with mock.patch(
            "scaffold_harness.adapters.anthropic.post_json", return_value=payload
        ) as call:
            response = adapter(CASE)
        sent = call.call_args[0][1]
        self.assertEqual(sent["system"], "Be exact.")
        self.assertEqual([row["role"] for row in sent["messages"]], ["user"])
        self.assertEqual(response.input_tokens, 21)
        self.assertEqual(call.call_args[1]["headers"]["x-api-key"], "k")
        self.assertIn("anthropic-version", call.call_args[1]["headers"])

    def test_text_blocks_are_joined_and_key_stays_private(self) -> None:
        from scaffold_harness.adapters import AnthropicChat

        payload = {"content": [{"type": "text", "text": "3/"}, {"type": "text", "text": "4"}]}
        adapter = AnthropicChat(model="m", api_key="tres-secret")
        with mock.patch(
            "scaffold_harness.adapters.anthropic.post_json", return_value=payload
        ):
            self.assertEqual(adapter(CASE).answer, "3/4")
        self.assertNotIn("tres-secret", str(adapter.descriptor()))


class ResilienceTests(unittest.TestCase):
    def test_a_transient_failure_is_retried_then_succeeds(self) -> None:
        # Une coupure d'une seconde ne doit pas coûter les appels déjà payés.
        import json as _json
        import urllib.error

        from scaffold_harness.adapters.base import post_json

        class FakeStream:
            def __init__(self, payload):
                self.payload = payload

            def read(self):
                return _json.dumps(self.payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        calls = []

        def opener(*_args, **_kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise urllib.error.URLError("connexion coupée")
            return FakeStream({"message": {"content": "4"}})

        with mock.patch("scaffold_harness.adapters.base.urllib.request.urlopen",
                        side_effect=opener):
            data = post_json("http://x/y", {}, attempts=3, backoff=0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(data["message"]["content"], "4")

    def test_a_client_error_is_not_retried(self) -> None:
        import urllib.error

        from scaffold_harness.adapters.base import AdapterError, post_json

        calls = []

        def opener(*_args, **_kwargs):
            calls.append(1)
            raise urllib.error.HTTPError("u", 400, "Bad", {}, None)

        with mock.patch("scaffold_harness.adapters.base.urllib.request.urlopen",
                        side_effect=opener):
            with self.assertRaises(AdapterError):
                post_json("http://x/y", {}, attempts=3, backoff=0)
        self.assertEqual(len(calls), 1)

    def test_a_provider_failure_costs_one_case_not_the_run(self) -> None:
        # Le run entier ne doit jamais tomber pour un 500 passager: ce serait
        # perdre tous les appels déjà payés.
        from scaffold_harness.adapters.base import AdapterError

        adapter = OllamaChat(model="m")
        with mock.patch(
            "scaffold_harness.adapters.ollama.post_json",
            side_effect=AdapterError("500 transitoire"),
        ):
            response = adapter(CASE)
        self.assertIsNone(response.answer)
        self.assertFalse(response.contract_valid)
        self.assertFalse(response.refused)  # échec ≠ refus
        self.assertIn("AdapterError", response.raw)


class OllamaProvenanceTests(unittest.TestCase):
    def test_the_report_pins_the_digest_not_the_mutable_tag(self) -> None:
        import io
        import json as _json

        catalogue = {"models": [{"name": "gemma3:12b", "digest": "d" * 64}]}

        class Stream(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

        adapter = OllamaChat(model="gemma3:12b")
        with mock.patch(
            "scaffold_harness.adapters.ollama.urllib.request.urlopen",
            return_value=Stream(_json.dumps(catalogue).encode()),
        ):
            descriptor = adapter.descriptor()
        self.assertEqual(descriptor["model_digest"], "d" * 64)

    def test_an_unreachable_catalogue_does_not_break_the_report(self) -> None:
        import urllib.error

        adapter = OllamaChat(model="absent")
        with mock.patch(
            "scaffold_harness.adapters.ollama.urllib.request.urlopen",
            side_effect=urllib.error.URLError("down"),
        ):
            self.assertIsNone(adapter.descriptor()["model_digest"])

    def test_keep_alive_is_sent_so_the_model_stays_loaded(self) -> None:
        adapter = OllamaChat(model="m", keep_alive="30m")
        with mock.patch(
            "scaffold_harness.adapters.ollama.post_json",
            return_value={"message": {"content": "4"}},
        ) as call:
            adapter(CASE)
        self.assertEqual(call.call_args[0][1]["keep_alive"], "30m")
