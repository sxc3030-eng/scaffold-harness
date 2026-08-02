"""Reprise après incident : ne jamais repayer un appel déjà payé.

Un run de plusieurs milliers de questions contre une API dure des heures et
coûte de l'argent. Il sera interrompu — coupure réseau, machine qui redémarre,
GPU qui lâche. Sans journal, l'incident renvoie à zéro.

Le mécanisme tient en deux pièces :

* un **journal append-only** par chemin, écrit au fur et à mesure ;
* un **manifeste** qui décide si reprendre est légitime.

La conception du manifeste est le point délicat, et c'est là qu'un système réel
s'est piégé : son empreinte incluait le `pid`. Comme le `pid` change à chaque
relance, l'empreinte ne correspondait jamais, aucune reprise n'était possible,
et les journaux incrémentaux prévus pour ça étaient du code mort — 1574
générations perdues sur une seule panne. **Aucune identité de processus, aucun
horodatage, ne doit entrer dans une empreinte de campagne.**
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .core import Case, Response
from .provenance import campaign_digest, write_atomic


class ResumeError(RuntimeError):
    """Le journal existant ne décrit pas la même campagne."""


def _safe(name: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in name)


class Journal:
    """Journal de campagne : enregistre chaque réponse dès qu'elle arrive."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.directory = self.root / "journal"

    # -- manifeste ---------------------------------------------------------

    def guard(self, manifest: Mapping[str, Any]) -> bool:
        """Autorise ou refuse la reprise. Renvoie True si on reprend.

        Le manifeste est comparé par empreinte, `pid` et horodatages exclus.
        Une campagne relancée depuis un autre processus reste la même campagne;
        une campagne dont le jeu de questions ou un chemin a changé, non.
        """
        path = self.root / "run-manifest.json"
        digest = campaign_digest(manifest)
        if not path.is_file():
            self.root.mkdir(parents=True, exist_ok=True)
            write_atomic(path, {**dict(manifest), "campaign_sha256": digest})
            return False
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored.get("campaign_sha256") != digest:
            raise ResumeError(
                f"{path}: campagne différente — le jeu de questions ou un chemin "
                "a changé. Choisissez un autre dossier de sortie, ou supprimez "
                "celui-ci pour repartir de zéro."
            )
        return True

    # -- journal -----------------------------------------------------------

    def _path(self, name: str) -> Path:
        return self.directory / f"{_safe(name)}.jsonl"

    def recorded(self, name: str) -> dict[str, Response]:
        path = self._path(name)
        if not path.is_file():
            return {}
        rows: dict[str, Response] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # Une ligne tronquée = l'incident a coupé une écriture. On perd
                # ce cas et on le rejouera; on ne perd pas le reste du journal.
                continue
            rows[str(row["case_id"])] = Response(**row)
        return rows

    def record(self, name: str, response: Response) -> None:
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(asdict(response), ensure_ascii=False) + "\n")
            stream.flush()

    def wrap(self, name: str, path: Callable[[Case], Response]) -> Callable[[Case], Response]:
        """Enveloppe un chemin pour qu'il n'appelle jamais deux fois le même cas."""
        already = self.recorded(name)

        def resumable(case: Case) -> Response:
            found = already.get(case.case_id)
            if found is not None:
                return found
            response = path(case)
            self.record(name, response)
            already[case.case_id] = response
            return response

        return resumable

    def progress(self) -> dict[str, int]:
        """Combien de cas sont déjà enregistrés, par chemin."""
        if not self.directory.is_dir():
            return {}
        return {
            entry.stem: len(self.recorded(entry.stem))
            for entry in sorted(self.directory.glob("*.jsonl"))
        }
