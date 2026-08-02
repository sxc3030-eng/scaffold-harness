from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scaffold_harness import Case, Response
from scaffold_harness.provenance import (
    campaign_digest,
    question_set_digest,
    sign,
    verify,
    write_atomic,
)
from scaffold_harness.scoring import (
    exact_rational,
    json_field,
    multiple_choice,
    normalized_text,
)


class ProvenanceTests(unittest.TestCase):
    def test_campaign_digest_ignores_the_process_identity(self) -> None:
        # Le bug qui a coûté 1574 générations: le pid dans l'empreinte rendait
        # toute reprise après panne impossible.
        base = {"schema": "v1", "questions": 800}
        self.assertEqual(
            campaign_digest({**base, "pid": 111}),
            campaign_digest({**base, "pid": 222}),
        )

    def test_campaign_digest_still_detects_a_real_change(self) -> None:
        self.assertNotEqual(
            campaign_digest({"schema": "v1", "questions": 800, "pid": 1}),
            campaign_digest({"schema": "v1", "questions": 400, "pid": 1}),
        )

    def test_question_set_digest_is_order_independent(self) -> None:
        self.assertEqual(
            question_set_digest(["a", "b", "c"]),
            question_set_digest(["c", "a", "b"]),
        )

    def test_signature_detects_a_retouched_report(self) -> None:
        report = sign({"accuracy": 0.87, "cases": 800})
        self.assertTrue(verify(report))
        tampered = {**report, "accuracy": 0.99}
        self.assertFalse(verify(tampered))

    def test_atomic_write_leaves_no_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "nested" / "report.json"
            write_atomic(target, {"b": 2, "a": 1})
            self.assertTrue(target.is_file())
            self.assertFalse(target.with_suffix(".json.tmp").exists())
            self.assertIn('"a": 1', target.read_text(encoding="utf-8"))


def response(answer: str | None, raw: str = "") -> Response:
    return Response(case_id="c", answer=answer, raw=raw)


class ScoringTests(unittest.TestCase):
    def test_equivalent_forms_are_the_same_answer(self) -> None:
        # 43 réponses justes avaient été comptées fausses par un correcteur
        # qui comparait des chaînes.
        case = Case(case_id="c", question="q", target="3/4")
        for form in ("3/4", "6/8", "0.75", " 0,75 "):
            self.assertTrue(exact_rational(response(form), case), form)

    def test_a_wrong_value_stays_wrong(self) -> None:
        case = Case(case_id="c", question="q", target="3/4")
        self.assertFalse(exact_rational(response("2/3"), case))

    def test_non_numeric_targets_fall_back_to_text(self) -> None:
        case = Case(case_id="c", question="q", target="none")
        self.assertTrue(exact_rational(response(" None "), case))
        self.assertFalse(exact_rational(response("infinite"), case))

    def test_json_field_tolerates_extra_keys(self) -> None:
        # Exiger exactement {"answer"} pénalisait le bras qui recopiait les
        # métadonnées de son outil à côté du résultat.
        case = Case(case_id="c", question="q", target="4")
        scorer = json_field()
        raw = '{"answer":"4","source":"executor","verification":"ok"}'
        self.assertTrue(scorer(response(None, raw=raw), case))

    def test_json_field_rejects_a_missing_field(self) -> None:
        case = Case(case_id="c", question="q", target="4")
        self.assertFalse(json_field()(response(None, raw='{"total":4}'), case))

    def test_multiple_choice_accepts_letter_or_text(self) -> None:
        case = Case(
            case_id="c",
            question="q",
            target="b",
            metadata={"choices": ["Paris", "Lyon", "Nice"]},
        )
        scorer = multiple_choice()
        self.assertTrue(scorer(response("b"), case))
        self.assertTrue(scorer(response("Lyon"), case))
        self.assertFalse(scorer(response("Paris"), case))

    def test_normalized_text_ignores_case_and_padding(self) -> None:
        case = Case(case_id="c", question="q", target="Infinite")
        self.assertTrue(normalized_text(response("  infinite "), case))


if __name__ == "__main__":
    unittest.main()
