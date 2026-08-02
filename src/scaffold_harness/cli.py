"""Le programme : une config, une commande, un rapport.

    scaffold-harness run config.json --out reports/

L'objectif est qu'un utilisateur n'écrive **aucun code** pour le cas courant :
comparer un modèle nu à la couche qu'il a construite. L'échappatoire Python
reste disponible pour brancher n'importe quel échafaudage, parce que c'est
justement ce qu'on veut mesurer et qu'aucune configuration ne peut le décrire.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .adapters import AnthropicChat, OllamaChat, OpenAICompatibleChat, PythonPath
from .core import Case, compare
from .journal import Journal, ResumeError
from .provenance import question_set_digest, write_atomic
from .report import build, headline, render
from .scoring import exact_rational, json_field, multiple_choice, normalized_text

SCORERS = {
    "exact_rational": exact_rational,
    "normalized_text": normalized_text,
    "json_answer": json_field(),
    "multiple_choice": multiple_choice(),
}


class ConfigError(RuntimeError):
    """La configuration ne décrit pas une comparaison exécutable."""


def load_questions(spec: Mapping[str, Any] | str) -> tuple[list[Case], dict[str, Any]]:
    """Lit un JSONL de questions.

    Une ligne = un objet avec au minimum `question`. `case_id` et `target` sont
    recommandés ; sans `case_id`, l'index sert d'identifiant, ce qui suffit tant
    que le fichier ne change pas d'ordre entre deux runs.
    """
    if isinstance(spec, str):
        spec = {"path": spec}
    path = Path(spec["path"]).expanduser()
    if not path.is_file():
        raise ConfigError(f"jeu de questions introuvable: {path}")
    cases: list[Case] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        if "question" not in row:
            raise ConfigError(f"{path}:{index + 1}: champ 'question' absent")
        cases.append(
            Case(
                case_id=str(row.get("case_id", index)),
                question=str(row["question"]),
                target=row.get("target"),
                metadata=row.get("metadata") or {},
            )
        )
    if not cases:
        raise ConfigError(f"{path}: aucune question")
    descriptor = {
        "name": spec.get("name", path.name),
        "path": str(path),
        "count": len(cases),
        "sha256": question_set_digest(case.question for case in cases),
    }
    return cases, descriptor


def build_path(spec: Mapping[str, Any]) -> Any:
    """Fabrique un chemin mesurable à partir de sa description."""
    kind = str(spec.get("adapter", "")).lower()
    options = {
        key: value
        for key, value in spec.items()
        if key not in {"adapter", "import", "name"}
    }
    if kind == "ollama":
        return OllamaChat(**options)
    if kind in {"openai", "openai_compatible"}:
        return OpenAICompatibleChat(**options)
    if kind in {"anthropic", "claude"}:
        return AnthropicChat(**options)
    if kind == "python":
        target = str(spec.get("import", ""))
        if ":" not in target:
            raise ConfigError(
                f"'import' doit valoir 'module:fonction', reçu {target!r}"
            )
        module_name, function_name = target.split(":", 1)
        try:
            module = importlib.import_module(module_name)
        except ImportError as error:
            raise ConfigError(f"module introuvable: {module_name} ({error})") from error
        function = getattr(module, function_name, None)
        if function is None:
            raise ConfigError(f"{module_name} n'expose pas {function_name}")
        return PythonPath(
            function,
            name=str(spec.get("name", function_name)),
            pass_case=bool(options.get("pass_case", False)),
        )
    raise ConfigError(f"adaptateur inconnu: {kind!r}")


def run_config(config: Mapping[str, Any], out: Path, lang: str | None) -> int:
    if "baseline" not in config or "variants" not in config:
        raise ConfigError("la configuration exige 'baseline' et 'variants'")
    cases, question_set = load_questions(config["questions"])

    scorer_name = str(config.get("scorer", "exact_rational"))
    scorer = SCORERS.get(scorer_name)
    if scorer is None:
        raise ConfigError(
            f"noteur inconnu: {scorer_name!r} — disponibles: {', '.join(sorted(SCORERS))}"
        )

    baseline = build_path(config["baseline"])
    variants = {name: build_path(spec) for name, spec in config["variants"].items()}
    reference = build_path(config["reference"]) if config.get("reference") else None

    def descriptor(path: Any) -> dict[str, Any]:
        getter = getattr(path, "descriptor", None)
        return getter() if callable(getter) else {"kind": type(path).__name__}

    # Journal de reprise, activé par défaut. Un run interrompu ne doit jamais
    # repayer un appel déjà payé: sur une campagne de plusieurs heures contre
    # une API, c'est l'incident le plus coûteux qui puisse arriver.
    journal = Journal(out)
    manifest = {
        "questions_sha256": question_set["sha256"],
        "question_count": len(cases),
        "scorer": scorer_name,
        "baseline": descriptor(baseline),
        "reference": descriptor(reference) if reference is not None else None,
        "variants": {name: descriptor(path) for name, path in variants.items()},
    }
    resuming = journal.guard(manifest)
    already = journal.progress()
    if resuming and already:
        summary = " · ".join(f"{k} {v}/{len(cases)}" for k, v in already.items())
        print(f"reprise : {summary}", file=sys.stderr)

    print(f"{len(cases)} questions · {len(variants) + 1} chemins…", file=sys.stderr)
    comparison = compare(
        cases,
        journal.wrap("baseline", baseline),
        {name: journal.wrap(name, path) for name, path in variants.items()},
        scorer,
        reference=(
            journal.wrap("reference", reference) if reference is not None else None
        ),
        reference_name=str(config.get("reference_name", "baseline")),
    )

    report = build(
        comparison,
        descriptor(baseline),
        {name: descriptor(path) for name, path in variants.items()},
        question_set,
        reproduction=str(config.get("reproduction") or "scaffold-harness run <config>"),
    )
    out.mkdir(parents=True, exist_ok=True)
    write_atomic(out / "report.json", report)
    (out / "report.html").write_text(render(report, lang), encoding="utf-8")

    print(headline(report, lang or "en"))
    for row in report["variants"]:
        deviation = row["deviation_vs_reference"]
        print(
            f"  {row['name']:24} {row['accuracy']:7.2%}  "
            f"changed {deviation['changed']:4}  "
            f"improved {deviation['improved']:4}  "
            f"destroyed {deviation['destroyed']:4}"
        )
    print(f"\n{out / 'report.html'}")
    # Un échafaudage qui détruit plus qu'il n'améliore rend un code non nul:
    # une barrière d'intégration continue doit pouvoir s'en servir.
    worst = min(
        (row["deviation_vs_reference"]["net"] for row in report["variants"]),
        default=0,
    )
    return 0 if worst >= 0 else 2


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        prog="scaffold-harness",
        description="Measure whether the layer you built on top of an LLM helps or hurts.",
    )
    subcommands = value.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("run", help="run a comparison from a config file")
    run.add_argument("config", type=Path)
    run.add_argument("--out", type=Path, default=Path("scaffold-report"))
    run.add_argument("--lang", choices=("en", "fr"), default=None,
                     help="single-language report; both are embedded by default")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        return run_config(config, args.out, args.lang)
    except ConfigError as error:
        print(f"configuration: {error}", file=sys.stderr)
        return 3
    except ResumeError as error:
        print(f"reprise impossible: {error}", file=sys.stderr)
        return 4
    except FileNotFoundError as error:
        print(f"fichier introuvable: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
