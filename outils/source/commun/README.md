# SLRResearchAI - TD03 : des outils à l'agent

Le TD03 prolonge le TD02 : les requêtes produites à partir de votre sujet sont
maintenant exécutées par un `SearchAgent`, en trois niveaux.

```text
sujet → TD02 (RQ → concepts → revue humaine → requêtes)
      → niveau 1 : workflow outillé      (le plan décide)
      → niveau 2 : politique codée       (des règles décident)
      → niveau 3 : ReAct contrôlé        (le LLM propose, le logiciel dispose)
```

Fichier à compléter : `slrresearch/search_agent.py` (TODO 1 à 10).
Lisez d'abord `ENONCE_TD03.md`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env      # seulement pour le mode « LLM réel »
```

## Tests

```bash
python -m pytest -v -k "fourni"     # code fourni : vert dès le départ
python -m pytest -v -k "todo_1"     # un TODO
python -m pytest -v                 # validation complète
```

Résultat final attendu : `46 passed`.

## Exécution

```bash
python main.py                                    # mode guidé : sujet, revue, trois niveaux
python main.py --llm demo --sources simule --scenario perturbe --accepter --rq RQ1
python -m streamlit run streamlit_app.py
```

Le mode `demo` fonctionne sans clé ni réseau. Le mode `reel` utilise le
fournisseur LLM choisi dans `.env` et, avec `--sources reel`, les API ouvertes
OpenAlex, Crossref et Semantic Scholar.
