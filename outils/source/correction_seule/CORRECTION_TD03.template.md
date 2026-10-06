# TD03 - Correction

Le code ci-dessous est extrait automatiquement de
`slrresearch/search_agent.py` (version correction) : il est identique au code
testé.

## Partie A - Niveau 1 : workflow outillé

### TODO 1 - `normalize_doi`

```python
{{code:normalize_doi}}
```

Points clés : la mise en minuscules précède le retrait du préfixe ; une chaîne
vide redevient `None` pour ne pas créer de clé `doi:` vide.

### TODO 2 - `call_tool`

```python
{{code:call_tool}}
```

Points clés : le `try` n'entoure que l'appel externe ; `ToolError` (et non
`Exception`) pour ne pas masquer un bug ; le statut vient de `error.status`,
ce qui évite trois branches `except` identiques (trois branches restent
acceptables).

### TODO 3 - `dedup_key` et `deduplicate`

```python
{{code:dedup_key}}
```

```python
{{code:deduplicate}}
```

Points clés : la copie protège `state.raw_records` ; l'ordre des sources est
celui de la découverte, sans doublon.

### TODO 4 - `run_workflow`

```python
{{code:run_workflow}}
```

Points clés : le refus est tracé et n'interrompt pas le plan ; aucune requête
n'est recopiée (`queries[base]`).

## Partie B - Niveau 2 : politique codée

### TODO 5 - `decide_next`

```python
{{code:decide_next}}
```

Points clés : `called` mesure le coût (budget) ; `attempted` mesure
l'avancement du plan (un outil refusé n'est pas reproposé) ; le secours n'est
tenté qu'une fois.

### TODO 6 - `run_agent`

```python
{{code:run_agent}}
```

Points clés : un seul `try` pour décider et contrôler ; l'appel externe est
hors du `try`, car `call_tool` ne lève jamais d'erreur d'API ; `finish` n'est
pas tracé comme observation ; sans `finish`, la borne `max_steps` arrête la
boucle et `finished` reste `False`.

## Partie C - Niveau 3 : ReAct contrôlé

### TODO 7 - `parse_agent_action`

```python
{{code:parse_agent_action}}
```

### TODO 8 - `AgentAction.check_rules`

```python
{{code:AgentAction.check_rules}}
```

Observation guidée attendue (TODO 7 fait, TODO 8 non fait) avec
`indiscipline` : pas 1 `refused` (`scholar`), pas 2 `invalid` (texte libre),
puis l'action `{"action": "finish", "tool": "openalex"}` est acceptée et
**arrête l'agent sans aucun article**. Après le TODO 8, elle devient `invalid`
et l'agent poursuit.

## Partie D - Robustesse

### TODO 9 - `retry_after_rate_limit`

```python
{{code:retry_after_rate_limit}}
```

### TODO 10 - `check_not_repeated`

```python
{{code:check_not_repeated}}
```

Points clés : les TODO 9 et 10 sont cohérents (la relance autorisée par l'un
est exactement l'exception acceptée par l'autre) ; un refus pour répétition est
une observation `refused`, pas une exception.

## Résultats attendus (catalogue simulé, RQ1)

| Scénario | Niveau 1 | Niveau 2 | Niveau 3 `discipline` | Niveau 3 `indiscipline` |
|---|---|---|---|---|
| `stable` | complete · 3 appels · 4 bruts · 3 uniques | complete · 3 appels · 3 uniques | complete · 3 appels · 3 uniques | partial · 2 appels · 4 refus/invalides · 3 uniques |
| `perturbe` | partial · 3 appels · 3 uniques | complete · 4 appels · 5 bruts · 4 uniques | complete · 4 appels · 4 uniques | partial · 2 appels · 3 uniques |
| `maigre` | complete · 1 unique | complete · 4 appels (secours) · 4 uniques | complete · 4 appels · 4 uniques | partial · 1 unique |
| `panne` | partial · 2 uniques | partial · 4 appels (secours) · 3 uniques | partial · 4 appels · 3 uniques | partial · 2 uniques |

## Réponses aux questions de synthèse

1. **LLM seul.** Son savoir est figé et non vérifiable : un DOI généré n'est pas
   un DOI trouvé. Une SLR exige des références réelles et une recherche
   rejouable (bases, requêtes, nombres de résultats).
2. **Outil.** Une capacité externe nommée, enregistrée, dont l'entrée, la sortie
   et les échecs (429, HTTP, réseau) sont connus et typés.
3. **Refus avant appel.** Moindre privilège : un nom inconnu est une erreur,
   jamais une improvisation ; aucun effet externe, aucun coût, aucune donnée
   envoyée à un service non prévu.
4. **429 en observation.** L'échec d'une source ne doit pas faire perdre les
   autres résultats ; il devient une information utile à la décision suivante
   (relancer, passer à la source suivante).
5. **DOI d'abord, fusion des sources.** Le DOI est stable, le titre varie. La
   fusion conserve la provenance (PRISMA : identifiés, doublons retirés, bases).
6. **Agent vs workflow.** Au niveau 2, l'action suivante dépend de l'état
   observé (échecs, nombre d'articles) ; au niveau 1, le chemin est fixé
   d'avance.
7. **Ordre des règles.** C'est une priorité : le budget d'abord garantit la
   terminaison ; la relance passe avant la source suivante ; le secours n'a de
   sens qu'une fois le plan terminé.
8. **Même boucle.** Le cadre de contrôle (validation, registre, trace, bornes)
   ne dépend pas du décideur : remplacer des règles par un LLM ne doit pas
   affaiblir ce cadre.
9. **JSON valide ≠ action cohérente.** Un JSON peut respecter les types et
   violer une règle entre champs (`search` sans `query`, `finish` avec un outil).
10. **État réduit.** Le système conserve l'état complet ; le prompt n'en expose
    que l'utile (coût, confidentialité, attention du modèle, reproductibilité).
11. **Garde-fous du niveau 3.** Contrat `AgentAction`, registre, refus des
    répétitions, `MAX_STEPS`, action `finish`, trace complète.
12. **Vers le TD04.** `papers` (avec `doi`, `url`, `open_access`, `sources`),
    `observations`, `raw_count`, `duplicates_removed`, `status`.
