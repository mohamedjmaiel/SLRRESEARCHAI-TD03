# TD03 - Des outils à l'agent : workflow, politique codée et ReAct contrôlé

## 1. Mission

Au TD02, le LLM a produit des questions de recherche (RQ), puis des requêtes
booléennes validées, une par moteur :

```text
{"RQ1": {"scholar": "...", "ieee": "...", "acm": "..."}, "RQ2": {...}, ...}
```

Une requête n'est pas un résultat. Pour trouver des articles réels, le système
doit maintenant **agir sur son environnement** : appeler des API
bibliographiques, observer leurs réponses et leurs échecs, puis consolider les
résultats.

Dans ce TD, vous construisez le `SearchAgent` en **trois niveaux**. Les outils,
les requêtes et le format de sortie restent identiques ; seule change la
réponse à la question :

> **Qui décide de l'action suivante ?**

| Niveau | Nom | Qui décide ? | Fonction |
|---|---|---|---|
| 1 | Workflow outillé | le plan fixe `ROUTES` | `run_workflow()` |
| 2 | Agent à politique codée | des règles Python | `run_agent(state, decide_next, ...)` |
| 3 | Agent ReAct contrôlé | le LLM **propose**, le logiciel **dispose** | `run_agent(state, llm_decide, ...)` |

Idée directrice : **chaque action est autorisée, tracée, et son échec est
traité explicitement.**

## 2. Objectifs pédagogiques

À la fin du TD, vous devez savoir :

1. définir un outil par un nom et un contrat d'entrée, de sortie et d'erreur ;
2. appliquer le moindre privilège : registre d'outils, refus avant tout appel ;
3. transformer un échec d'API en observation typée au lieu d'une exception ;
4. normaliser et dédupliquer des résultats hétérogènes en gardant leur provenance ;
5. distinguer un workflow outillé d'un agent qui décide selon ses observations ;
6. écrire une politique de décision codée, ordonnée et bornée ;
7. implémenter une boucle ReAct contrôlée : décider, contrôler, agir, observer ;
8. imposer un contrat Pydantic aux actions proposées par un LLM ;
9. expliquer pourquoi un agent ReAct n'est pas une autonomie illimitée.

## 3. Prérequis

- TD01 : appel d'un ChatModel LangChain (`model.invoke(...)`).
- TD02 : contrat Pydantic, `ValidationError`, repair borné, requêtes par moteur,
  `extract_json_object()` pour isoler un objet JSON dans une sortie LLM.
- Python : `try/except`, dictionnaires, listes, `pydantic.BaseModel`.

Le TD02 complet est fourni dans `slrresearch/search_plan.py`. Vous ne le
modifiez pas : vous l'utilisez.

## 4. Architecture

```text
sujet saisi par l'utilisateur
   │  TD02 (fourni) : RQ → concepts → revue humaine → requêtes par moteur
   ▼
queries = {"scholar": "...", "ieee": "...", "acm": "..."}      ← une RQ
   │
   ├── Niveau 1  run_workflow   : pour chaque base de ROUTES → appeler l'outil
   ├── Niveau 2  run_agent + decide_next : des règles choisissent l'action
   └── Niveau 3  run_agent + llm_decide  : le LLM propose une AgentAction
   │
   ▼  pour chaque action :  valider → autoriser → appeler → tracer
SearchState : papers · observations (trace) · raw_count · duplicates_removed · status
```

### Fichiers

Fichier à compléter :

```text
slrresearch/search_agent.py      TODO 1 à TODO 10
```

Fichiers fournis, à lire mais à ne pas modifier :

| Fichier | Rôle |
|---|---|
| `slrresearch/models.py` | `PaperRecord`, `TraceEvent` (= observation), `ActionError` |
| `slrresearch/tools.py` | outils simulés et réels, erreurs typées, registre |
| `slrresearch/td02_bridge.py` | pont TD02 → TD03 : du sujet aux requêtes |
| `slrresearch/demo_llm.py` | LLM de démonstration, sans clé ni réseau |
| `slrresearch/search_plan.py` | acquis complet du TD02 |
| `data/catalog_td03.json` | catalogue simulé (quatre scénarios) |
| `main.py` · `streamlit_app.py` | exécution en ligne de commande et interface |
| `tests/test_td03.py` | contrat exécutable de chaque TODO |

### Routage : base logique ≠ outil

Le TD02 parle de **bases** (`scholar`, `ieee`, `acm`). Le TD03 les associe à des
**outils** réellement appelables :

```python
ROUTES = {"scholar": "openalex", "ieee": "crossref", "acm": "semantic_scholar"}
FALLBACK_TOOL = "openalex_broad"   # source de secours
```

Une action porte toujours le **nom d'un outil du registre**
(`tool="openalex"`), jamais le nom d'une base (`tool="scholar"`). La requête,
elle, est lue dans le dictionnaire du TD02 (`queries["scholar"]`) et transmise
sans recopie. Chaque outil traduit ensuite la requête dans le langage de son
API (code fourni dans `tools.py`).

### Contrats

```python
class TraceEvent(BaseModel):          # une ligne de trace = une observation
    step: int
    tool: str
    query: str
    status: Literal["success", "rate_limited", "http_error",
                    "network_error", "refused", "invalid"]
    found: int
    error: str

class AgentAction(BaseModel):         # ce qu'un décideur peut proposer
    action: Literal["search", "finish"]
    tool: str | None                  # nom d'un outil du registre
    query: str | None
    limit: int | None                 # entre 1 et 50

class SearchState(BaseModel):         # ce que l'agent sait
    objective: str
    queries: dict[str, str]
    raw_records, papers               # résultats bruts / uniques
    actions_executed, observations    # alignées : une action ↔ une observation
    errors: list[str]
    step: int
    finished: bool
    raw_count, duplicates_removed, status
```

`state.add(action, records, event)` met l'état à jour après chaque action.

### Les quatre scénarios du catalogue simulé

| Scénario | Ce qu'il rend observable |
|---|---|
| `stable` | 4 résultats bruts, 3 articles uniques, 1 doublon (même DOI dans deux sources) |
| `perturbe` | Semantic Scholar répond 429 au premier appel, puis répond |
| `maigre` | trop peu d'articles : la source de secours devient utile |
| `panne` | Crossref en erreur HTTP 500, Semantic Scholar injoignable |

Le catalogue vérifie la **mécanique** de l'agent de façon reproductible. Il ne
prouve pas la pertinence des articles : c'est le rôle du mode réel.

## 5. Installation et lancement

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env          # utile seulement pour le mode « LLM réel »
```

| Commande | Effet |
|---|---|
| `python -m pytest -v -k "fourni"` | tests du code fourni (verts dès le départ) |
| `python -m pytest -v -k "todo_4"` | tests d'un TODO |
| `python -m pytest -v` | validation complète |
| `python main.py` | exécution guidée en ligne de commande |
| `python -m streamlit run streamlit_app.py` | interface pédagogique |

`main.py` vous demande d'abord le mode du LLM (`demo` ou `reel`), les sources
(`simule` ou `reel`), puis **le sujet de la revue** : le TD02 génère les RQ et
les requêtes, vous validez les concepts, puis les trois niveaux s'exécutent.
Exécution non interactive :

```bash
python main.py --llm demo --sources simule --scenario perturbe --react discipline --accepter --rq RQ1
```

Le mode `demo` n'exige ni clé ni réseau. Le mode `reel` utilise le fournisseur
choisi dans `.env` (Groq ou Ollama), comme au TD02 : vous y saisissez votre
propre sujet. Le mode `simule` des sources rejoue le catalogue ; le mode `reel`
interroge OpenAlex, Crossref et Semantic Scholar.

---

## Étape 0 - Observer avant de coder

1. Lancez `python -m pytest -v -k "fourni"` : tous ces tests passent.
2. Lancez `python -m pytest -q` : les tests `todo_*` échouent. C'est votre
   contrat de travail.
3. Lancez `python -m streamlit run streamlit_app.py`, gardez le mode
   démonstration, générez les RQ, validez les concepts, puis cliquez sur
   « Exécuter les niveaux ». Chaque niveau affiche « Non disponible » et
   nomme un TODO encore manquant.
4. Ouvrez `data/catalog_td03.json` et `slrresearch/tools.py`.

Répondez par écrit :

- Quel dictionnaire le TD02 transmet-il au TD03 pour une RQ ?
- Quelle API sera appelée pour la base `ieee` ? Où ce choix est-il écrit ?
- Sous quelles trois formes le même DOI apparaît-il dans le scénario `stable` ?
- Quelles exceptions un outil peut-il lever ? Quel attribut donne le statut à tracer ?

---

# Partie A - Niveau 1 : le workflow outillé

Le plan est fixé à l'avance : une base, un outil, un appel. Aucune décision ne
dépend des observations.

## TODO 1 - Normaliser un DOI

### Objectif

Les API écrivent le même DOI différemment :

```text
OpenAlex          https://doi.org/10.5555/SLR.2024.001
Crossref          10.5555/slr.2024.001
Semantic Scholar  10.5555/SLR.2024.001
```

Sans normalisation, la déduplication échoue silencieusement.

### Fonction à compléter

```python
def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    clean = doi.strip().lower()
    # TODO 1 - Retirer le préfixe éventuel (voir DOI_PREFIXES),
    #          puis supprimer les espaces internes.
```

Règles : minuscules, aucun préfixe parmi
`DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:")`,
aucun espace. Une chaîne vide après nettoyage donne `None`.

### Vérification

```bash
python -m pytest -v -k "todo_1"
```

### Erreurs fréquentes

- Mettre en minuscules après avoir testé le préfixe : `HTTPS://DOI.ORG/` n'est pas retiré.
- Retourner `""` au lieu de `None` pour un DOI vide.

## TODO 2 - Appeler un outil et tracer l'appel

### Objectif

Un appel d'outil produit toujours deux choses : des résultats (éventuellement
aucun) et **une trace**. Un échec n'est jamais propagé : il devient une
observation.

```text
succès          → records normalisés + TraceEvent(status="success", found=n)
RateLimitError  → []                 + TraceEvent(status="rate_limited", error=...)
HttpError       → []                 + TraceEvent(status="http_error", error=...)
NetworkError    → []                 + TraceEvent(status="network_error", error=...)
```

Les trois erreurs héritent de `ToolError` et portent leur statut dans
`error.status`.

### Fonction à compléter

```python
def call_tool(tool, query, limit=DEFAULT_LIMIT) -> tuple[list[PaperRecord], TraceEvent]:
    # TODO 2.1 - Appeler l'outil : raw_items = tool.search(query, limit)
    # TODO 2.2 - Si une ToolError est levée : retourner ([], TraceEvent(...))
    #            avec status=error.status et error=str(error).
    # TODO 2.3 - Sinon, normaliser chaque élément avec to_paper_record(tool.name, raw)
    # TODO 2.4 - Retourner (records, TraceEvent(...)) avec status="success"
    #            et found=len(records).
```

`to_paper_record()` est fourni : il appelle `normalize_doi()` et ajoute la
provenance `sources=[tool.name]`. Renseignez `tool=tool.name` et `query=query`
dans chaque `TraceEvent`.

### Vérification

```bash
python -m pytest -v -k "todo_2"
```

### Erreurs fréquentes

- Placer tout le corps de la fonction dans le `try` : une erreur de
  normalisation serait confondue avec une erreur d'API. Le `try` entoure
  **uniquement** l'appel externe.
- Écrire `except Exception` : un bug du code deviendrait une « erreur HTTP ».
- Écrire `return` sans trace dans le `except`.

## TODO 3 - Dédupliquer en fusionnant la provenance

### Objectif

Deux bases peuvent retourner le même article. On ne le compte qu'une fois, mais
on garde **toutes ses sources** (utile pour le diagramme PRISMA).

### TODO 3.1 - Clé de déduplication

```python
def dedup_key(record: PaperRecord) -> str:
    # "doi:<doi>" si le DOI existe ;
    # sinon "title:<titre en minuscules, espaces compactés>".
```

Le DOI passe d'abord : il est stable ; un titre varie (casse, ponctuation,
sous-titre).

### TODO 3.2 - Regrouper et fusionner

```python
def deduplicate(records) -> tuple[list[PaperRecord], int]:
    unique: dict[str, PaperRecord] = {}
    for record in records:
        key = dedup_key(record)
        # Première occurrence : conserver une COPIE (record.model_copy(deep=True)).
        # Doublon : ajouter ses sources absentes à l'entrée conservée.
    return list(unique.values()), len(records) - len(unique)
```

Pourquoi une copie ? Sans copie, ajouter une source à l'entrée conservée
modifierait aussi les résultats bruts de l'état.

### Vérification

```bash
python -m pytest -v -k "todo_3"
```

Résultat attendu sur le scénario `stable` : `4` bruts, `3` uniques, `1` doublon ;
l'article doublon a `sources == ["openalex", "crossref"]`.

## TODO 4 - Assembler le workflow outillé

### Objectif

Le niveau 1 exécute le plan `ROUTES` dans l'ordre. Avant chaque appel, il
vérifie que l'outil est **enregistré** (moindre privilège) : un outil absent
est refusé **avant tout appel externe**, et ce refus est tracé.

### Code fourni

```python
def authorize(tool_name, registry) -> SearchTool       # lève ActionError("refused", ...)
def refused_event(action, error) -> TraceEvent          # refus → observation
def finalize(state) -> SearchState                       # dédoublonne, compte, statut
```

### Fonction à compléter

```python
def run_workflow(queries, registry, limit=DEFAULT_LIMIT, objective=""):
    state = SearchState(objective=objective, queries=queries)
    for base, tool_name in ROUTES.items():
        if base not in queries:
            continue
        action = AgentAction(action="search", tool=tool_name,
                             query=queries[base], limit=limit)
        # TODO 4.1 - Autoriser l'outil avec authorize(tool_name, registry).
        #            En cas d'ActionError : state.add(action, [], refused_event(...))
        #            puis passer à la base suivante.
        # TODO 4.2 - Appeler call_tool(tool, action.query, limit)
        #            puis mettre à jour l'état avec state.add(...).
    state.finished = True
    return finalize(state)
```

### Statut global (fourni)

`overall_status()` raisonne outil par outil : un outil a réussi s'il a répondu
au moins une fois.

| Statut | Signification |
|---|---|
| `complete` | chaque outil tenté a répondu |
| `partial` | au moins un échec ou un refus, mais des résultats conservés |
| `failed` | aucun outil n'a répondu |

### Vérification

```bash
python -m pytest -v -k "todo_4"
python main.py --llm demo --sources simule --scenario perturbe --accepter --rq RQ1 --niveaux 1
```

Attendu avec `perturbe` : Semantic Scholar est `rate_limited`, les 4 articles
d'OpenAlex et Crossref sont conservés, le statut est `partial`.

### Erreurs fréquentes

- Écrire `return` dans le `except` : les sources suivantes ne seraient jamais interrogées.
- Recopier la requête à la main au lieu d'utiliser `queries[base]`.

### Point de contrôle A

Dans Streamlit, l'onglet « Niveau 1 » affiche maintenant une trace d'une ligne
par appel. Comparez les scénarios `stable`, `perturbe` et `panne`.

---

# Partie B - Niveau 2 : l'agent à politique codée

Les outils restent les mêmes. Ce qui change : **à chaque pas, une fonction
observe l'état et choisit l'action suivante.**

```text
OBSERVER (état) → DÉCIDER (decide_next) → AGIR (call_tool) → OBSERVER ...
```

## TODO 5 - Écrire la politique de décision

### Règles évaluées dans l'ordre

| # | Condition | Action |
|---|---|---|
| 1 | budget d'appels épuisé (`MAX_CALLS`) | `finish` *(fourni)* |
| 2 | dernier appel en 429, pas encore relancé | relancer *(fourni, voir TODO 9)* |
| 3 | une base du plan n'a pas encore été tentée | `search` vers l'outil suivant de `ROUTES` |
| 4 | plan terminé, moins de `MIN_UNIQUE` articles uniques, secours non tenté | `search` vers `FALLBACK_TOOL` avec `queries["scholar"]` |
| 5 | sinon | `finish` |

L'ordre est une priorité : le budget passe en premier, car il garantit la
terminaison même si une API répond indéfiniment 429.

### Fonction à compléter

```python
def decide_next(state, max_calls=MAX_CALLS, min_unique=MIN_UNIQUE) -> AgentAction:
    called = state.tools_called()                              # appels réels
    attempted = {event.tool for event in state.observations}   # appels + refus
    # Règle 1 (fournie)  ...
    # Règle 2 (fournie)  ...
    # TODO 5 - Règle 3, Règle 4, Règle 5
```

Pourquoi deux listes ? `called` sert au budget (seuls les vrais appels
coûtent). `attempted` sert au plan : un outil refusé par le registre ne doit pas
être reproposé indéfiniment.

`state.unique_count()` utilise votre `deduplicate()` du TODO 3.

### Vérification

```bash
python -m pytest -v -k "todo_5"
```

### Erreurs fréquentes

- Utiliser `called` pour la règle 3 : un outil refusé serait reproposé à chaque pas.
- Oublier `limit=DEFAULT_LIMIT` dans l'action.
- Écrire la requête de secours à la main au lieu de `state.queries["scholar"]`.

## TODO 6 - Écrire la boucle bornée

### Objectif

La même boucle servira aux niveaux 2 et 3 : **seule la fonction `decide`
change**. Le code fourni `validate_action()` applique le contrat
`AgentAction` et transforme une violation en `ActionError("invalid", ...)`.
`check_not_repeated()` est appelée dans la boucle ; elle sera complétée au
TODO 10 et accepte tout pour l'instant.

### Fonction à compléter

```python
def run_agent(state, decide, registry, max_steps=MAX_STEPS) -> SearchState:
    for _ in range(max_steps):
        action = None
        # TODO 6.1 - DÉCIDER puis CONTRÔLER, dans un bloc try :
        #     action = validate_action(decide(state))
        #     si action.action == "finish" : state.finished = True puis break
        #     check_not_repeated(action, state)
        #     tool = authorize(action.tool, registry)
        # TODO 6.2 - except ActionError as error :
        #     state.add(action, [], refused_event(action, error)) puis continue
        # TODO 6.3 - AGIR et OBSERVER :
        #     call_tool(tool, action.query, action.limit or DEFAULT_LIMIT)
        #     puis state.add(action, records, event)
    return finalize(state)
```

La boucle s'arrête de deux façons : une action `finish`, ou la borne
`max_steps`. Dans le second cas, `state.finished` reste `False`.

### Vérification

```bash
python -m pytest -v -k "todo_6"
python main.py --llm demo --sources simule --scenario maigre --accepter --rq RQ1 --niveaux 1,2
```

Attendu avec `maigre` : le niveau 1 s'arrête avec 1 article ; le niveau 2
interroge `openalex_broad` et termine avec 4 articles uniques.

### Point de contrôle B

Comparez les niveaux 1 et 2 sur les quatre scénarios. Sur quel scénario le
niveau 2 apporte-t-il quelque chose ? Pourquoi `maigre` est-il « complete » au
niveau 1 malgré un seul article ?

---

# Partie C - Niveau 3 : l'agent ReAct contrôlé

Le niveau 3 garde **tout** le cadre des niveaux 1 et 2 : registre, trace,
budget, boucle. Seule l'origine de la décision change : le LLM **propose** une
`AgentAction` ; le logiciel la **valide**, l'**autorise**, l'**exécute** et
**borne** la boucle.

```text
LLM ──propose──► texte ──parse──► AgentAction ──valide──► registre ──autorise──► outil
 ▲                                                                                │
 └────────── état réduit (describe_state) ◄────── observation ◄──────────────────┘
```

Frontière de contrôle : **le LLM ne lance jamais directement un outil.**

### Code fourni à lire

- `describe_state(state, registry)` : la partie de l'état utile à la décision.
  L'état complet reste dans Python ; le prompt n'en expose qu'un résumé.
- `build_decision_prompt(state, registry)` : objectif, outils autorisés, état,
  règles de réponse.
- `llm_decide(model, state, registry)` : appelle le LLM puis `parse_agent_action()`.
- `demo_llm.DemoChatModel` : un LLM simulé avec deux comportements,
  `discipline` (actions valides) et `indiscipline` (erreurs typiques d'un LLM).

## TODO 7 - Transformer la sortie du LLM en action

### Objectif

Le LLM répond par du texte. Il peut entourer son JSON d'explications ou de
balises Markdown, ou ne pas respecter le contrat. Toute sortie hors contrat
devient une **observation `invalid`**, et la boucle continue.

### Fonction à compléter

```python
def parse_agent_action(text: str) -> AgentAction:
    # TODO 7 - Isoler l'objet JSON avec extract_json_object(text) (acquis du TD02),
    #          puis le valider avec AgentAction.model_validate_json(...).
    #          Toute ValueError devient ActionError("invalid", "Sortie LLM hors contrat : ...").
```

`extract_json_object()` lève une `ValueError` si la sortie est vide ou ne
contient pas d'objet JSON ; une `ValidationError` est aussi une `ValueError`.

### Vérification

```bash
python -m pytest -v -k "todo_7"
python main.py --llm demo --sources simule --scenario stable --react discipline --accepter --rq RQ1
```

Attendu : au niveau 3, le LLM discipliné interroge OpenAlex, Crossref et
Semantic Scholar, puis propose `finish`.

### Observation guidée

Lancez maintenant le LLM « indiscipliné » :

```bash
python main.py --llm demo --sources simule --scenario stable --react indiscipline --accepter --rq RQ1 --niveaux 3
```

Il propose successivement un outil inexistant (`scholar`), un texte libre, puis
`{"action": "finish", "tool": "openalex"}`. Lisez la trace : que se passe-t-il
au troisième pas ? Combien d'articles l'agent a-t-il trouvés ? Pourquoi est-ce
un problème ?

## TODO 8 - Imposer les règles du contrat d'action

### Objectif

Les types (`Literal`, bornes de `limit`) ne suffisent pas : certaines règles
dépendent de **plusieurs champs**.

| Action | Règle |
|---|---|
| `search` | `tool` **et** `query` sont obligatoires |
| `finish` | aucun `tool` |

« JSON valide » ≠ « action cohérente ».

### Méthode à compléter (classe `AgentAction`)

```python
@model_validator(mode="after")
def check_rules(self):
    # TODO 8 - Règle 1 : action "search" sans tool ou sans query -> ValueError
    # TODO 8 - Règle 2 : action "finish" avec un tool -> ValueError
    return self
```

Une `ValueError` levée dans un `model_validator` devient une `ValidationError`
Pydantic. `parse_agent_action()` (TODO 7) et `validate_action()` (fourni) la
transforment en `ActionError("invalid", ...)`.

### Vérification

```bash
python -m pytest -v -k "todo_8"
python main.py --llm demo --sources simule --scenario stable --react indiscipline --accepter --rq RQ1 --niveaux 3
```

### Point de contrôle C

Avec `--react indiscipline`, la trace du niveau 3 commence maintenant par
`refused`, `invalid`, `invalid` ; l'agent poursuit, interroge OpenAlex et
Crossref, puis termine par `finish`. Comparez enfin les trois niveaux sur la
même RQ : mêmes outils, même trace, même sortie, trois manières de décider.

---

# Partie D - Robustesse

## TODO 9 - Relancer une fois après un 429

### Objectif

Un 429 signifie « quota atteint » : réessayer **une fois** est raisonnable,
réessayer sans limite ne l'est pas. Cette règle est la règle 2 de
`decide_next` : la fonction est déjà appelée, mais elle retourne toujours
`None`.

### Fonction à compléter

```python
def retry_after_rate_limit(state) -> AgentAction | None:
    # Retourner une copie de la dernière action si :
    #   - la dernière observation a le statut "rate_limited" ;
    #   - cette action (même tool, même query) n'a été exécutée qu'une fois.
    # Sinon, retourner None.
```

`state.actions_executed[i]` correspond à `state.observations[i]`. Pour une
sortie LLM invalide, l'action enregistrée vaut `None`.

### Vérification

```bash
python -m pytest -v -k "todo_9"
python main.py --llm demo --sources simule --scenario perturbe --accepter --rq RQ1 --niveaux 1,2
```

Attendu avec `perturbe` : le niveau 2 relance Semantic Scholar une fois et passe
de `partial` à `complete` (5 bruts, 4 uniques).

## TODO 10 - Refuser les actions répétées

### Objectif

Un LLM peut proposer deux fois la même recherche. La répéter coûte un appel,
gonfle les résultats bruts et peut faire tourner la boucle jusqu'à sa borne.
Le logiciel doit refuser la répétition, **sauf** la relance unique après un 429.

### Fonction à compléter

```python
def check_not_repeated(action: AgentAction, state: SearchState) -> None:
    # Chercher les actions déjà exécutées avec le même tool et la même query.
    #   - aucune -> accepter (return) ;
    #   - une seule, dont l'observation est "rate_limited" -> accepter (relance) ;
    #   - sinon -> lever ActionError("refused", "Action déjà exécutée : ...").
```

### Vérification

```bash
python -m pytest -v -k "todo_10"
python main.py --llm demo --sources simule --scenario stable --react indiscipline --accepter --rq RQ1 --niveaux 3
```

Attendu : au pas 5, la seconde recherche OpenAlex est `refused` (« Action déjà
exécutée ») ; OpenAlex n'est appelé qu'une fois et l'agent conserve 4 résultats
bruts.

---

## 6. Validation finale

```bash
python -m pytest -v
python main.py
python -m streamlit run streamlit_app.py
```

Résultat attendu :

```text
46 passed
```

## 7. Résultats attendus (catalogue simulé, RQ1)

| Scénario | Niveau 1 | Niveau 2 | Niveau 3 `discipline` | Niveau 3 `indiscipline` |
|---|---|---|---|---|
| `stable` | complete · 4 bruts · 3 uniques | complete · 3 appels · 3 uniques | complete · 3 appels · 3 uniques | partial · 2 appels · 4 refus/invalides |
| `perturbe` | partial · 4 bruts · 3 uniques | complete · 4 appels · 4 uniques | complete · 4 appels · 4 uniques | partial · 2 appels |
| `maigre` | complete · 1 brut · 1 unique | complete · secours · 4 uniques | complete · secours · 4 uniques | partial · 1 unique |
| `panne` | partial · 2 uniques | partial · secours · 3 uniques | partial · secours · 3 uniques | partial · 2 uniques |

Au niveau 3 `indiscipline`, le statut `partial` signale qu'une action a visé un
outil refusé (`scholar`).

## 8. Erreurs fréquentes

| Symptôme | Cause probable |
|---|---|
| `NotImplementedError: TODO n` | le TODO n n'est pas terminé |
| les 4 articles disparaissent après un 429 | `return` ou exception non capturée dans `call_tool` / la boucle |
| deux entrées pour le même article | `normalize_doi` incomplet ou clé construite sur le DOI brut |
| les sources d'un résultat brut changent | `deduplicate` modifie l'objet au lieu d'une copie |
| la boucle tourne jusqu'à `MAX_STEPS` | règle 3 fondée sur `called` au lieu de `attempted` |
| `finish` avec un outil arrête l'agent | TODO 8 non terminé |
| le niveau 3 plante sur une réponse en texte libre | `parse_agent_action` (TODO 7) ne transforme pas l'erreur en `ActionError` |
| `tool="scholar"` refusé | normal : `scholar` est une base, l'outil est `openalex` |
| mode réel : `network_error` partout | réseau ou proxy indisponible ; vérifiez d'abord le mode simulé |

## 9. Questions de synthèse

1. Pourquoi un LLM seul ne peut-il pas fournir les références d'une SLR ?
2. Qu'est-ce qui distingue un outil d'une fonction quelconque ?
3. Pourquoi refuser un outil absent du registre **avant** tout appel externe ?
4. Pourquoi un 429 doit-il devenir une observation plutôt qu'une exception ?
5. Pourquoi dédupliquer par DOI avant le titre, et pourquoi fusionner les sources ?
6. Qu'est-ce qui fait du niveau 2 un agent, alors que le niveau 1 n'en est pas un ?
7. Pourquoi l'ordre des règles de `decide_next` est-il important ?
8. Pourquoi le niveau 3 réutilise-t-il exactement la boucle du niveau 2 ?
9. Pourquoi « JSON valide » ne signifie-t-il pas « action cohérente » ?
10. Pourquoi le prompt n'expose-t-il qu'une partie du `SearchState` ?
11. Quels mécanismes empêchent le niveau 3 d'être une autonomie illimitée ?
12. Quels champs de la sortie du TD03 seront nécessaires au TD04 ?
