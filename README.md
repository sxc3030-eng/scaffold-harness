# scaffold-harness

**Measure whether the layer you built on top of an LLM helps or hurts.**

*Version française plus bas · [French version below](#scaffold-harness-français)*

Benchmarks tell you how a **model** scores. Almost nobody measures what the
agent, RAG pipeline, router or verification step built **on top of it** actually
adds — or removes.

This harness answers one question that aggregate scores structurally cannot:

> When your layer **changed** an answer, did it improve it or break it?

## Why that question

A layer that fixes 8 answers and breaks 5 shows up as “+3” and hides the 13
questions it touched. On a real system measured over 800 questions, a scaffold
changed **4316** answers from its deterministic reference path: 4316
degradations, zero improvements. The aggregate score looked acceptable. No
classic benchmark could see it, because none compares answers pairwise.

## Quick start

```bash
pip install -e .
scaffold-harness smoke          # three built-in questions, no model, no network
```

That writes `report.html` and `report.json`, and proves the install works before
you build anything.

## Running your own comparison

One JSON file describes what to compare. No code for the common case.

```json
{
  "questions": { "path": "questions.jsonl", "name": "my eval set" },
  "scorer": "exact_rational",

  "baseline": { "adapter": "ollama", "model": "llama3.2:latest" },

  "variants": {
    "my-agent": { "adapter": "python", "import": "my_project.agent:run" }
  },

  "reference": { "adapter": "python", "import": "my_project.calculator:solve" },
  "reference_name": "deterministic calculator"
}
```

```bash
scaffold-harness run config.json --out reports/ --limit 20   # cheap dry run
scaffold-harness run config.json --out reports/              # the full set
```

Questions are JSONL, one object per line:

```json
{"case_id": "q1", "question": "1/2 + 1/3 ?", "target": "5/6"}
```

### Adapters

| `adapter` | keys | notes |
|---|---|---|
| `ollama` | `model`, `host`, `system`, `max_tokens`, `keep_alive` | pins the model **digest**, not the mutable tag |
| `openai` | `model`, `base_url`, `api_key`, `system` | any OpenAI-compatible server: vLLM, llama.cpp, LM Studio, TGI |
| `anthropic` | `model`, `api_key`, `system` | Messages API |
| `python` | `import: "module:function"`, `pass_case` | **your scaffold** — see the security note |

### Scorers

`exact_rational` · `normalized_text` · `json_answer` · `multiple_choice`

### The reference path

`reference` is what deviations are counted against. By default it is the bare
model — everyone has one. If you also have a **deterministic** path (a
calculator, a solver, a database lookup), point the harness at it: changes are
then counted against something known to be right, which is far sharper.

On real data, the same scaffold measured against the bare model showed 7
improvements and 0 degradations; measured against a deterministic executor, 0
improvements and 3 degradations. Same answers, opposite reading.

## ⚠️ Security

**The `python` adapter imports and executes the module named in the config.**
That is unavoidable — the thing being measured *is* your code — but it means a
config file is executable content.

**Never run a config you did not write**, exactly as you would never run a
`Makefile` or a `setup.py` from an untrusted source. The harness makes no
attempt to sandbox it.

API keys go in the config and are used to call your provider; they are never
written into the report — only a boolean saying a key was present.

## Resuming

Every run keeps an append-only journal. Relaunching the same config into the
same output folder resumes instead of recalling: on a real 24-question run
against a local model, 48.9 s the first time, **0.21 s** the second, identical
result.

A different question set, model or scorer refuses to resume rather than mixing
two campaigns.

## What you get

```
GAIN / LOSS / INCONCLUSIVE          a verdict, including “we cannot tell”

changed · improved · destroyed      what your layer did to each answer
accuracy + Wilson 95% CI            with the interval, not just the number
coverage · refusals · failures      “I don’t know” ≠ wrong ≠ the API was down
tokens × · p95 latency ×            what the layer costs
McNemar exact p                     paired significance
per-question detail                 destroyed cases first
```

Reports are self-contained HTML — bilingual, printable, no external resource —
plus a signed JSON twin. `scaffold-harness run` exits with code `2` when a layer
destroys more than it improves, so it can act as a CI gate.

## Design rules

- **No runtime dependencies.** HTTP through `urllib`, statistics through `math`.
  A measurement tool must not impose a dependency tree on someone who just wants
  to check a number.
- **The core produces no prose.** It emits an outcome code; rendering turns it
  into a sentence. That is what makes the report translatable without touching
  the measurement.
- **Refusing to conclude is a feature.** Four losses and zero gains looks
  decisive and still gives p = 0.125. A tool that always finds something is
  worth nothing.
- **No process identity in a campaign hash.** A harness where the `pid` entered
  the manifest digest could never resume an interrupted run.
- **Audit your grader.** `audit_scorer` runs a second grader whose only job is to
  disagree. On real data it found 43 correct answers that the original grader
  silently rejected — and the bias fell on exactly the arms under measurement.

## Status

**0.1.0 — early, API unstable.** Core, statistics, provenance, scoring, adapters,
reporting, resume and CLI are implemented and tested (98 tests, no network or GPU
required). Validated by replaying two known real campaigns and reproducing their
published numbers.

## Licence

**FSL-1.1-ALv2** — Functional Source License. Read it, run it, modify it, use it
inside your company, in research or in teaching. The one thing you may not do is
offer it as a commercial product or service that competes with it.

It converts automatically to **Apache 2.0 two years after each release**, so
nothing you build on it is locked away for good.

---

<a name="scaffold-harness-français"></a>

# scaffold-harness *(français)*

**Mesurer si la couche que vous avez construite par-dessus un LLM aide ou nuit.**

Les benchmarks vous disent le score d'un **modèle**. Presque personne ne mesure
ce que l'agent, la chaîne RAG, le routeur ou l'étape de vérification construits
**par-dessus** ajoutent — ou retirent réellement.

Ce harnais répond à une question qu'un score agrégé ne peut structurellement pas
poser :

> Quand votre couche a **modifié** une réponse, l'a-t-elle améliorée ou cassée ?

## Pourquoi cette question

Une couche qui corrige 8 réponses et en casse 5 affiche « +3 » et masque les 13
questions qu'elle a touchées. Sur un système réel mesuré sur 800 questions, un
échafaudage a modifié **4316** réponses de son chemin de référence
déterministe : 4316 dégradations, aucune amélioration. Le score agrégé avait
l'air correct.

## Démarrage

```bash
pip install -e .
scaffold-harness smoke          # trois questions intégrées, sans modèle ni réseau
```

Puis une comparaison décrite par un seul fichier JSON — voir le format anglais
ci-dessus, il est identique.

## ⚠️ Sécurité

**L'adaptateur `python` importe et exécute le module nommé dans la config.**
C'est inévitable — l'objet mesuré *est* votre code — mais cela fait d'un fichier
de configuration un contenu exécutable.

**N'exécutez jamais une config que vous n'avez pas écrite**, exactement comme
vous n'exécuteriez pas un `Makefile` reçu d'une source inconnue. Le harnais ne
tente aucun bac à sable.

Les clés d'API servent à appeler votre fournisseur ; elles ne sont jamais
écrites dans le rapport — seulement un booléen indiquant qu'une clé était
présente.

## Ce que vous obtenez

```
GAIN / PERTE / NON CONCLUANT        un verdict, y compris « on ne peut pas dire »

modifiées · améliorées · détruites  ce que votre couche a fait à chaque réponse
exactitude + IC 95 % de Wilson      avec l'intervalle, pas seulement le chiffre
couverture · refus · pannes         « je ne sais pas » ≠ faux ≠ l'API est tombée
tokens × · latence p95 ×            ce que la couche coûte
p exact de McNemar                  significativité appariée
détail par question                 destructions en tête
```

Rapports en HTML autonome — bilingue, imprimable, aucune ressource externe — et
un jumeau JSON signé. Code de sortie `2` quand une couche détruit plus qu'elle
n'améliore : la mesure peut servir de barrière d'intégration continue.

## Licence

**FSL-1.1-ALv2**. Lisez-le, exécutez-le, modifiez-le, utilisez-le dans votre
entreprise, en recherche ou en enseignement. La seule chose interdite est d'en
faire un produit ou un service commercial qui lui fait concurrence.

Elle bascule automatiquement en **Apache 2.0 deux ans après chaque version** :
rien de ce que vous construisez dessus n'est verrouillé pour toujours.
