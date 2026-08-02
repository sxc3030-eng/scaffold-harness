# scaffold-harness

**Measure whether the layer you built on top of an LLM helps or hurts.**

*(Version française plus bas.)*

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

## What you get

```
GAIN / LOSS / INCONCLUSIVE          a verdict, including "we cannot tell"

changed · improved · destroyed      what your layer did to each answer
accuracy + Wilson 95% CI            with the interval, not just the number
coverage · refusals                 "I don't know" is not a wrong answer
tokens × · p95 latency ×            what the layer costs
McNemar exact p                     paired significance
```

Reports are self-contained HTML — bilingual, printable, no external resource —
and a signed JSON twin for machines.

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

## Status

Early. Core, statistics, provenance, scoring, adapters and reporting are
implemented and tested (46 tests). CLI and question-set loaders are next. See
`PLAN.md`.

Licence: to be decided before publication — intended permissive.

---

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
l'air correct. Aucun benchmark classique ne pouvait le voir, parce qu'aucun ne
compare les réponses deux à deux.

## Ce que vous obtenez

```
GAIN / PERTE / NON CONCLUANT        un verdict, y compris « on ne peut pas dire »

modifiées · améliorées · détruites  ce que votre couche a fait à chaque réponse
exactitude + IC 95 % de Wilson      avec l'intervalle, pas seulement le chiffre
couverture · refus                  « je ne sais pas » ≠ mauvaise réponse
tokens × · latence p95 ×            ce que la couche coûte
p exact de McNemar                  significativité appariée
```

Rapports en HTML autonome — bilingue, imprimable, aucune ressource externe — et
un jumeau JSON signé pour les machines.
