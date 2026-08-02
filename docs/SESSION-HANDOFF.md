# Reprise de session — état au 2026-08-02

Coller ce document comme premier message d'une nouvelle conversation.

---

Je reprends deux projets liés. Parle-moi en français.

## Les deux dépôts

```
D:\scaffold-harness
    L'outil. Public sur github.com/sxc3030-eng/scaffold-harness, FSL-1.1-ALv2.
    102 tests, 18 commits, CI verte sur 3 OS × 3 versions de Python.
    Aucune dépendance d'exécution. Je travaille dessus avec toi.

C:\Users\sxc_2\Documents\Codex\2026-07-20\je\outputs\mat-9f
    MAT-Nexus, ma recherche. Privé, reste privé. GPT travaille dessus,
    pas toi — sauf si je le demande. Sert de premier sujet de mesure.
    Lire HANDOFF-2026-08-01.md et TODO-BYPASS-2026-08-02.md avant d'y toucher.
```

## Ce que fait le harnais

Il mesure **si la couche construite par-dessus un LLM aide ou nuit**, pas le
score du modèle. Sa question propre : *quand la couche a modifié une réponse,
l'a-t-elle améliorée ou détruite ?* Aucun benchmark classique ne la pose.

Ne jamais le laisser dériver vers un énième lanceur de benchmarks.

Fait et testé : noyau de comparaison appariée, Wilson + McNemar exact,
provenance signée, noteurs (dont audit à deux correcteurs), adaptateurs
ollama/openai/anthropic/python, rapport HTML bilingue autonome + JSON signé,
journal de reprise, CLI, icône, `docs/FINDINGS.md`, CI.

## Mesures établies — ne pas contredire sans remesurer

Run scellé v3, 800 questions, corpus MAT-Nexus :

```
exécuteur déterministe seul   100,00 %
llm_nexus_adaptive             87,25 %
llm_experts                    81,00 %
llm_memory                      7,88 %
llm_direct                      6,38 %
```

- **4316 écarts par rapport à la proposition déterministe, 4316 destructions,
  0 amélioration**, sur 11 combinaisons bras × run. Réserve à conserver :
  l'exécuteur est juste sur 2400/2400, donc aucune occasion de réparer
  n'existait — le résultat démontré est celui des écarts.
- **73,2 % des destructions sont une recopie littérale d'un fragment du
  prompt.** L'arrondi n'explique que 3 cas sur 680. 86 % des dégâts en algèbre.
- Les réponses **courtes et entières** sont détruites deux fois plus que les
  fractions longues (32,1 % contre 16,0 %).
- **Couverture réelle : 2/25 questions de benchmark formalisées, 0/25 justes.**
  Le 100 % ci-dessus mesure la couverture de gabarits, pas une capacité.
- **43 réponses justes rejetées** par le correcteur d'origine — 32 sur
  `llm_experts`, 11 sur `llm_nexus_adaptive`, 0 ailleurs. Le biais ne frappait
  que les bras sous mesure.
- Run réel llama3.2 : exécuteur 24/24, modèle nu 0/24, échafaudage 0/24,
  24 déviations toutes destructrices.

**À ne pas revendiquer** : le « −8 points de Nexus sur benchmark externe » n'est
**pas significatif** (11/25 contre 9/25, p = 0,688). Le harnais lui-même le
refuse. Le résultat publiable est celui des 43 réponses.

## Cinq défauts que le harnais a trouvés chez lui

Utile parce que c'est le motif à reproduire, et le meilleur argument du projet :

1. `mcnemar_exact` dépassait la plage des flottants au-delà de ~1000 paires
   discordantes — il plantait sur son propre cas d'usage.
2. Wilson renvoyait `0,9999999999999999` pour un score parfait : un intervalle
   qui n'encadrait pas sa propre proportion.
3. Un HTTP 500 passager tuait tout le run.
4. Les pannes de fournisseur n'étaient comptées nulle part.
5. Le démarrage à froid faussait le coût : le rapport annonçait un échafaudage
   « 4× plus rapide » alors qu'il est 2,4× plus lent. **Aucun test ne pouvait
   l'attraper** — il a fallu regarder une capture d'écran.

## En cours au moment de la coupure

- Un run réel préchauffé dans `examples/real_run/out3/` — journal à 24/24,
  24/24, 11/24. Relancer la même commande le reprend sans repayer d'appel :
  `cd examples/real_run && PYTHONPATH=. scaffold-harness run config.json --out out3/`
- **La capture du rapport HTML pour le README** n'est pas faite. C'est la seule
  chose qui manque pour qu'un visiteur voie le produit et pas seulement des
  figures. Servir le rapport en local (`.claude/launch.json` a une entrée
  `scaffold-report`) puis capturer.

## Suite prévue

1. Capture du rapport dans le README.
2. Billet public sur les 43 réponses — le récit qui amène les gens au dépôt.
   Un post LinkedIn en français est déjà rédigé, à retrouver dans l'historique
   ou à refaire.
3. Côté MAT-Nexus, si je le demande : architecture à essai d'experts avec
   bypass, puis élargir la couverture (8 % aujourd'hui). Spéc dans
   `TODO-BYPASS-2026-08-02.md`.

## Comment je travaille

- **Je valide chaque étape avant la suivante.** Ne pas enchaîner cinq chantiers.
- Je veux des mesures, pas des suppositions. Si une mesure me contredit, dis-le.
- Corrige-moi quand je me trompe — trois de mes conclusions ont été renversées
  par une mesure en une journée, et c'est ce qui a fait avancer le projet.
- Ne sur-vends jamais un chiffre. C'est le sujet même de l'outil.

## Pièges opérationnels

```
git sur D:            `git config --global --add safe.directory D:/scaffold-harness`
                      déjà fait ; gh appelle git sans surcharge possible
python                D:\scaffold-harness s'installe avec pip install -e .
                      côté mat-9f : .matlm-venv312\Scripts\python.exe
pytest                vendorisé dans mat-9f\.test-deps\pytest-9.1.1
                      le harnais utilise unittest, rien à installer
tests du harnais      PYTHONPATH=tests python -m unittest discover -s tests
Ollama                le préflight matériel de mat-9f refuse de démarrer si une
                      vidéo tourne dans un navigateur (moteur VideoDecode)
corpus scellé         ne jamais publier son contenu, même en capture d'écran
contributions         aucune PR externe sans cession de droits, sinon la
                      revente et le changement de licence deviennent impossibles
```
