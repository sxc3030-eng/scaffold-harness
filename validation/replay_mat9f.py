"""Validation de l'instrument sur des données réelles.

Le harnais est rejoué sur une campagne déjà notée par un autre système, et doit
retrouver ses chiffres. Tant que ce script ne passe pas, rien ne doit être
publié : un outil de mesure qui n'a jamais été confronté à une mesure connue
n'est qu'une opinion avec des tableaux.

Ce fichier vit **hors du paquet**. Il lit les données d'un projet voisin et
importe son exécuteur déterministe pour servir de chemin de référence — c'est
une pièce de validation, pas du code de bibliothèque.

Cibles connues, campagne `nexus-intelligence-four-arm-800q-v2`, 800 questions :

    exécuteur seul       100,00 %   (800/800)
    llm_direct             6,38 %
    llm_memory             7,88 %
    llm_experts           81,00 %
    llm_nexus_adaptive    81,38 %

et, comptées contre l'exécuteur : 152 destructions pour `llm_experts`,
149 pour `llm_nexus_adaptive`, **zéro amélioration** dans les deux cas.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from scaffold_harness import Case, Response, compare  # noqa: E402
from scaffold_harness.report import build, render  # noqa: E402
from scaffold_harness.provenance import digest_text, write_atomic  # noqa: E402
from scaffold_harness.scoring import exact_rational  # noqa: E402

MAT9F = Path(r"C:\Users\sxc_2\Documents\Codex\2026-07-20\je\outputs\mat-9f")
CORPUS = Path(r"D:\MAT-LM\evaluation\nexus-intelligence-800q-v2\sealed")
RUN = Path(r"D:\MAT-LM\runs\nexus-intelligence-four-arm-800q-v2\arms")
ARMS = ("llm_direct", "llm_memory", "llm_experts", "llm_nexus_adaptive")

EXPECTED_ACCURACY = {
    "llm_direct": 0.0638,
    "llm_memory": 0.0788,
    "llm_experts": 0.8100,
    "llm_nexus_adaptive": 0.8138,
}
EXPECTED_DESTROYED = {"llm_experts": 152, "llm_nexus_adaptive": 149}


def load_executor():
    """Importe l'exécuteur déterministe du projet voisin, s'il est là."""
    script = MAT9F / "scripts" / "run_nexus_intelligence_four_arm_800q.py"
    if not script.is_file():
        return None
    sys.path.insert(0, str(MAT9F / "src"))
    sys.path.insert(0, str(MAT9F / "scripts"))
    spec = importlib.util.spec_from_file_location("mat9f_runner", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules["mat9f_runner"] = module
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def answer_of(raw: str) -> str | None:
    try:
        value = json.loads(raw).get("answer")
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None
    return None if value is None else str(value)


def main() -> int:
    if not CORPUS.is_dir() or not RUN.is_dir():
        print("données absentes — validation ignorée")
        return 0

    questions = {
        digest_text(row["example_id"]): row for row in read_jsonl(CORPUS / "questions.jsonl")
    }
    targets = {
        digest_text(row["example_id"]): row["target"]
        for row in read_jsonl(CORPUS / "targets.jsonl")
    }

    def canonical_target(target: dict) -> str:
        exact = target.get("exact")
        if isinstance(exact, dict):
            numerator, denominator = exact["numerator"], exact["denominator"]
            return str(numerator) if denominator == 1 else f"{numerator}/{denominator}"
        return str(target.get("canonical"))

    cases = [
        Case(
            case_id=key,
            question=str(row["messages"][-1]["content"]),
            target=canonical_target(targets[key]),
            metadata={"family": row["public_metadata"]["family"]},
        )
        for key, row in questions.items()
        if key in targets
    ]

    ledgers: dict[str, dict[str, Response]] = {}
    for arm in ARMS:
        rows = read_jsonl(RUN / arm / "output-ledger.jsonl")
        ledgers[arm] = {
            row["example_id_sha256"]: Response(
                case_id=row["example_id_sha256"],
                answer=answer_of(row["response"]),
                contract_valid=bool(row.get("contract_valid")),
                latency_ms=float(row.get("latency_ms", 0.0)),
                input_tokens=int(row.get("input_tokens", 0)),
                output_tokens=int(row.get("output_tokens", 0)),
                raw=str(row["response"]),
            )
            for row in rows
        }

    def replay(arm: str):
        return lambda case: ledgers[arm].get(
            case.case_id, Response(case_id=case.case_id, answer=None, refused=True)
        )

    runner = load_executor()
    if runner is None:
        print("exécuteur introuvable — référence = modèle nu")
        reference, reference_name = None, "baseline"
    else:

        def executor(case: Case) -> Response:
            row = questions[case.case_id]
            try:
                return Response(
                    case_id=case.case_id,
                    answer=str(runner.solve_public_question(row)["answer"]),
                )
            except Exception:
                return Response(case_id=case.case_id, answer=None, refused=True)

        reference, reference_name = executor, "deterministic executor"

    report = compare(
        cases,
        replay("llm_direct"),
        {arm: replay(arm) for arm in ARMS if arm != "llm_direct"},
        exact_rational,
        reference=reference,
        reference_name=reference_name,
    )

    print(f"cas rejoués : {report.case_count}\n")
    if reference is not None:
        hits = sum(1 for case in report.cases if case.reference_correct)
        print(f"  {'exécuteur seul':24} {hits}/{report.case_count} = "
              f"{100 * hits / report.case_count:6.2f}%   (attendu 100,00 %)")

    failures = 0
    rows = [("llm_direct", report.baseline)] + [(row.name, row) for row in report.variants]
    for name, row in rows:
        expected = EXPECTED_ACCURACY[name]
        gap = abs(row.accuracy - expected)
        flag = "OK " if gap < 0.0051 else "ÉCART"
        failures += gap >= 0.0051
        print(f"  {name:24} {row.accuracy:7.2%}   attendu {expected:6.2%}   {flag}")

    print()
    for row in report.variants:
        expected = EXPECTED_DESTROYED.get(row.name)
        dev = row.deviation_vs_reference
        note = "" if expected is None else f"   attendu {expected}"
        flag = "" if expected is None or dev.destroyed == expected else "   ÉCART"
        failures += bool(flag)
        print(
            f"  {row.name:24} détruites {dev.destroyed:4}  améliorées "
            f"{dev.improved:3}{note}{flag}"
        )

    total_improved = sum(row.deviation_vs_reference.improved for row in report.variants)
    print(f"\n  améliorations totales : {total_improved}   (attendu 0)")
    failures += total_improved != 0

    artefact = build(
        report,
        {"kind": "ledger", "name": "llm_direct", "run": "four-arm-800q-v2"},
        {arm: {"kind": "ledger", "run": "four-arm-800q-v2"} for arm in ARMS[1:]},
        {"name": "nexus-intelligence-800q-v2 (sealed)", "count": report.case_count},
        reproduction="python validation/replay_mat9f.py",
    )
    out = HERE.parent / "demo"
    out.mkdir(exist_ok=True)
    write_atomic(out / "validation-mat9f.json", artefact)
    (out / "validation-mat9f.html").write_text(render(artefact), encoding="utf-8")

    print("\n" + ("VALIDATION RÉUSSIE" if failures == 0 else f"{failures} ÉCART(S)"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
