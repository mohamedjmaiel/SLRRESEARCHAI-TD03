# TD03 - Guide enseignant

Document réservé à l'enseignant : il n'est pas distribué avec la version étudiant.

## 1. Objectifs d'apprentissage

À l'issue du TD, l'étudiant sait :

1. définir un outil par un nom et un contrat d'entrée, de sortie et d'erreur ;
2. appliquer le moindre privilège (registre, refus avant appel) ;
3. transformer un échec d'API en observation typée ;
4. normaliser et dédupliquer des résultats hétérogènes en gardant leur provenance ;
5. distinguer workflow outillé, agent à politique codée et agent ReAct contrôlé ;
6. écrire une politique de décision ordonnée et bornée ;
7. écrire la boucle décider → contrôler → agir → observer, commune aux niveaux 2 et 3 ;
8. imposer un contrat Pydantic aux actions proposées par un LLM ;
9. expliquer les garde-fous qui empêchent l'autonomie illimitée.

Un seul concept nouveau est introduit par TODO ; chaque partie se termine par
un point de contrôle observable (CLI ou Streamlit).

## 2. Répartition du travail

| Bloc | Contenu | Durée estimée | Lieu |
|---|---|---|---|
| Étape 0 | observation guidée (tests fournis, Streamlit, catalogue) | 10 min | séance |
| Partie A | TODO 1 à 4 - niveau 1 | 34 min | séance |
| Partie B | TODO 5 et 6 - niveau 2 | 22 min | séance |
| Partie C | TODO 7 et 8 - niveau 3 | 16 min | séance |
| Synthèse | comparaison des trois niveaux | 8 min | séance |
| Partie D | TODO 9 (relance unique) et TODO 10 (anti-répétition) | ≈ 18 min | après la séance |
| Questions | rédaction de 4 réponses de synthèse au choix | ≈ 8 min | après la séance |

Charge totale ≈ 116 min : ≈ 90 min en séance (≈ 78 %), ≈ 26 min ensuite
(≈ 22 %). Tests : 41 tests portent sur le code fourni et les TODO 1 à 8,
5 tests sur les TODO 9 et 10 (46 au total).

Conformément à la consigne, l'énoncé étudiant ne mentionne pas cette
répartition : la partie D y apparaît comme la suite naturelle du TD. Les
TODO 9 et 10 sont indépendants de la séance : leurs fonctions existent déjà
sous forme permissive (`return None`), si bien que les niveaux 1 à 3
fonctionnent à la fin de la séance.

## 3. Scénario détaillé des 90 minutes

| Horaire | Activité | Rôle de l'enseignant | Livrable observable |
|---|---|---|---|
| 0-5 | Rappel : « qui décide de l'action suivante ? » ; tableau des trois niveaux (diapo 10 de la séance 4) | poser la question, ne pas répondre | - |
| 5-10 | Étape 0 : `pytest -k fourni`, Streamlit en mode démo, lecture du catalogue | circuler, vérifier les installations | 11 tests verts |
| 10-14 | TODO 1 `normalize_doi` (échauffement) | - | `-k todo_1` vert |
| 14-26 | TODO 2 `call_tool` : succès puis erreurs typées | insister : `try` autour de l'appel externe seulement | `-k todo_2` vert |
| 26-36 | TODO 3 `dedup_key` / `deduplicate` | pourquoi une copie ? pourquoi le DOI d'abord ? | `-k todo_3` vert |
| 36-46 | TODO 4 `run_workflow` + point de contrôle A | faire comparer `stable`, `perturbe`, `panne` | trace du niveau 1 |
| 46-56 | TODO 5 `decide_next` | faire justifier l'ordre des règles ; `called` vs `attempted` | `-k todo_5` vert |
| 56-68 | TODO 6 `run_agent` + point de contrôle B | montrer que la boucle servira au niveau 3 | `maigre` : secours au niveau 2 |
| 68-78 | TODO 7 `parse_agent_action` + observation guidée `indiscipline` | faire constater l'arrêt prématuré au pas 3 | trace `refused`, `invalid`, arrêt |
| 78-84 | TODO 8 règles d'`AgentAction` + point de contrôle C | « JSON valide ≠ action cohérente » | trace `refused`, `invalid`, `invalid`, recherches |
| 84-90 | Synthèse : comparaison des trois niveaux sur `perturbe` ; annonce de la partie D | relier aux garde-fous (budget, registre, contrat, bornes) | tableau de comparaison |

Points de vigilance : si un groupe prend du retard sur la partie A, fournir la
solution du TODO 3 au tableau à la minute 36 ; la partie C ne doit pas
commencer après la minute 72.

## 4. Travail après la séance

- **TODO 9** - `retry_after_rate_limit` : la règle 2 de `decide_next` devient
  effective. Avec `perturbe`, le niveau 2 passe de `partial` à `complete`
  (5 bruts, 4 uniques).
- **TODO 10** - `check_not_repeated` : la boucle refuse les répétitions, sauf la
  relance unique après 429. Avec `indiscipline`, la seconde recherche OpenAlex
  devient `refused` et les résultats bruts restent à 4.
- Rédaction de quatre réponses aux questions de synthèse.

Ces deux TODO réinvestissent la séance (lecture de l'état, alignement
`actions_executed` / `observations`, `ActionError`) sans nouveau concept.

## 5. Choix de conception

- **Une sortie commune** (`SearchState`) pour les trois niveaux : la comparaison
  devient factuelle (mêmes indicateurs, même trace).
- **Une seule boucle** pour les niveaux 2 et 3 : seul `decide` change, ce qui
  matérialise « le LLM propose, le logiciel dispose ».
- **`AgentAction` pour tous les décideurs** : le plan, les règles et le LLM
  produisent le même type d'objet. `TraceEvent` sert d'observation au niveau 3
  (alias `Observation`), pour ne pas introduire deux modèles quasi identiques.
- **Base logique ≠ outil** : `ROUTES` associe `scholar → openalex`, etc. Le
  scénario `indiscipline` fait proposer `tool="scholar"`, refusé par le registre.
- **LLM de démonstration** (`demo_llm.py`) : reproductible, sans clé ni réseau ;
  il rend observables les erreurs typiques d'un LLM (outil inexistant, texte
  libre, action incohérente, répétition).
- **Outils réels** fournis (OpenAlex, Crossref, Semantic Scholar) avec
  adaptation de la requête TD02 au langage de chaque API (`tools.py`).

## 6. Outils de l'enseignant

```bash
python outils/generer_versions.py     # régénère etudiant/ et correction/
python outils/verifier_coherence.py   # tests, progression TODO par TODO, énoncé
```

Toute modification se fait dans `outils/source/` (code commun, puis
`search_agent.src.py` avec les marqueurs `#@ TODO n`, `#@ ETUDIANT`, `#@ FIN`).

## 7. Points d'attention

- Le mode réel (LLM et API) dépend du réseau de la salle ; le mode
  démonstration et le catalogue simulé suffisent pour toute la séance.
- Avec `openai/gpt-oss-20b` sur Groq, le modèle tente parfois un appel de
  fonction natif ; Groq répond HTTP 400 `tool_use_failed`. `llm_decide`
  récupère alors `failed_generation` et le soumet au contrat `AgentAction`
  (`recover_rejected_generation`). Bon exemple à commenter : le LLM sort du
  format attendu, le logiciel garde le contrôle.
- Semantic Scholar renvoie souvent 429 sans clé : c'est un exemple réel du
  scénario `perturbe`.
- Support de séance aligné sur ce TD : `SupportsCours/Seance4_TD03_DesOutilsALAgent_v2.pptx`
  (dix TODO, 46 tests, observation = `TraceEvent`, diapo 16 de démonstration
  du LLM « indiscipliné » à lancer en direct).
