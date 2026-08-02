# scaffold-harness — plan

## Ce qu'on construit, en une phrase

> **Un harnais qui mesure si l'échafaudage construit par-dessus un LLM aide ou nuit.**

Pas « quel score fait mon modèle » — les benchmarks existants le font, et bien.
La question à laquelle personne ne répond : *quand ma couche a modifié la
réponse, l'a-t-elle améliorée ou détruite ?*

**Ne jamais dériver vers un énième lanceur de benchmarks.** Si on se met à
mesurer des modèles au lieu de mesurer des couches, le projet a perdu sa raison
d'être.

## Répartition

```
scaffold-harness   →  Simon + Claude
mat-9f / Nexus     →  Simon + GPT     (indépendant, sert de premier sujet de test)
```

Aucun import de `mat-9f`. Ce qui est utile est **porté**, pas référencé — sinon
les deux projets se bloquent mutuellement.

---

## Phase 0 — Noyau *(fait)*

- [x] `stats.py` — Wilson, McNemar exact, sans dépendance
- [x] `core.py` — `Case`, `Response`, `compare()`, `Deviation`, `verdict()`
- [x] Le paramètre `reference` : compter les déviations contre un chemin
      déterministe et non contre le modèle nu
- [x] `refused` distinct d'une mauvaise réponse → mesure de couverture
- [x] 12 tests, dont un qui verrouille le refus de conclure à petit effectif

## Phase 1 — Fondations *(fait, sauf emballage)*

- [x] `provenance.py` — JSON canonique, sha256, écriture atomique, rapport signé
- [x] `scoring.py` — noteurs réutilisables, dont **égalité rationnelle exacte**
- [x] Tests pour chacun
- [ ] `pyproject.toml`, `README.md`, licence

> **Pourquoi le noteur rationnel exact.** Un correcteur qui comparait des
> chaînes canoniques a sous-compté **43 réponses justes** sur un run réel
> (77,25 % rapportés comme 73,25 %). Un harnais dont le noteur ment est pire
> qu'aucun harnais.

## Phase 2 — Adaptateurs *(fait, sauf HF local)*

- [x] `adapters/base.py` — latence, tokens, descripteur, HTTP sans dépendance
- [x] `adapters/ollama.py` — comptes de tokens réels
- [x] `adapters/openai_compatible.py` — clé d'API jamais dans le descripteur
- [x] `adapters/python_callable.py` — `Refusal` distingué d'un plantage
- [x] Tests avec doublures, sans réseau ni GPU
- [ ] `adapters/hf_local.py` — transformers, import paresseux

Chaque adaptateur doit renseigner `latency_ms`, `input_tokens`, `output_tokens`.
**Sans le coût, le rapport ne peut pas dire « vous avez doublé la facture pour
rien »** — et c'est un de ses arguments les plus forts.

## Phase 3 — Le rapport

- [ ] Rendu JSON signé (sha256 du contenu, révisions de modèles, hash du jeu)
- [ ] Rendu HTML lisible par un client
- [ ] **Le tableau des déviations en pièce maîtresse**, pas en annexe
- [ ] « Aucune différence significative » affichable en grand
- [ ] Section reproduction : la commande exacte

## Phase 4 — CLI

- [ ] `scaffold-harness run --baseline … --scaffold … --questions … --out …`
- [ ] Chargeurs de jeux de questions : JSONL maison, pont lm-eval
- [ ] Reprise sur incident : ledgers incrémentaux

> **Reprise obligatoire dès le départ.** Sur `mat-9f`, l'empreinte du manifeste
> incluait le `pid`, donc aucune campagne interrompue ne pouvait reprendre —
> 1574 générations perdues sur une panne GPU. Ne jamais faire entrer d'identité
> de processus dans une empreinte de campagne.

## Phase 5 — Se manger soi-même *(le jalon qui compte)*

- [ ] Rejouer les ledgers `mat-9f` v2/v3 dans le harnais
- [ ] **Reproduire les chiffres connus** : 4316 déviations / 4316 destructions /
      0 amélioration, et Granite 11/25 nu contre 9/25 avec l'échafaudage
- [ ] Si les chiffres ne tombent pas, c'est le harnais qui a tort

C'est la validation de l'instrument. Aucune diffusion avant ça.

## Phase 6 — Publication

- [ ] Dépôt public, licence permissive
- [ ] **Publier le résultat défavorable sur Nexus** : « notre échafaudage fait
      perdre 8 points à Granite 2B sur des benchmarks externes, voici l'outil
      qui l'a trouvé »
- [ ] Formulation à tenir : le harnais n'a pas causé la dégradation, il l'a
      révélée
- [ ] Viser ceux qui livrent des agents et doivent le justifier

## Phase 7 — Interface

- [ ] Écran 1 : choisir modèle(s), échafaudage, jeu de questions
- [ ] Écran 2 : lancer, suivre
- [ ] Écran 3 : **détail par question, filtré sur « détruites »** ← l'écran qui
      vend l'outil ; c'est là qu'un utilisateur a son moment « oh non »

Pas d'interface de conversation. Un lanceur de tâches avec une vue de résultats.

---

## À ne pas oublier — les leçons payées cher

1. **Toujours publier la ligne du chemin de référence.** Pendant 33 runs,
   personne n'a vu que le LLM détruisait 19 points parce qu'aucun rapport
   n'affichait ce que l'exécuteur seul obtenait.
2. **Un vérificateur-LLM est une fonction de perte.** La formulation la plus
   prudente possible (« rapporte ce résultat sauf si tu peux démontrer une
   erreur ») a quand même détruit 26,5 % des bonnes réponses.
3. **La couverture est une métrique, pas un détail.** 100 % sur un corpus
   fabriqué et 8 % sur du réel décrivent deux systèmes différents.
4. **Refuser de conclure est une fonctionnalité.** Un outil qui trouve toujours
   quelque chose ne vaut rien.
5. **Ne jamais faire d'un jeu de test un jeu d'entraînement par accident.** Dès
   qu'on a inspecté ou résolu à la main des questions d'évaluation, elles sont
   consommées.
6. **Se méfier de ses propres mesures.** Trois affirmations ont été renversées
   en une journée par une mesure : le baseline « cassé » qui était réel, les
   « faux silencieux » absents qui étaient à 100 % hors gabarit, et
   l'hypothèse de complexité, inversée.
