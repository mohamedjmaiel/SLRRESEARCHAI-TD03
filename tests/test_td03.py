"""Contrat exécutable du TD03 (ne pas modifier).

Lancer un groupe : python -m pytest -v -k "todo_4"
Code fourni     : python -m pytest -v -k "fourni"
"""
import httpx
import pytest
from pydantic import ValidationError

from slrresearch import tools
from slrresearch.demo_llm import DemoChatModel
from slrresearch.models import ActionError, PaperRecord, TraceEvent
from slrresearch.search_agent import (
    FALLBACK_TOOL,
    AgentAction,
    SearchState,
    authorize,
    build_decision_prompt,
    call_tool,
    check_not_repeated,
    decide_next,
    dedup_key,
    deduplicate,
    normalize_doi,
    overall_status,
    parse_agent_action,
    retry_after_rate_limit,
    run_agent,
    run_level,
    run_workflow,
    validate_action,
)
from slrresearch.search_plan import accept_proposal
from slrresearch.td02_bridge import REFERENCE_TOPIC, prepare_queries


def paper(key, doi=None, source="openalex", title=None):
    return PaperRecord(id=key, title=title or f"Titre {key}", doi=doi, sources=[source])


def search(tool, query="q"):
    return AgentAction(action="search", tool=tool, query=query, limit=10)


# ===========================================================================
# Code fourni : verts dès le départ
# ===========================================================================

def test_fourni_catalogue_contient_les_quatre_scenarios():
    assert set(tools.scenario_names()) >= {"stable", "perturbe", "maigre", "panne"}


def test_fourni_outil_simule_rejoue_un_429_puis_repond(registry):
    tool = registry("perturbe")["semantic_scholar"]
    with pytest.raises(tools.RateLimitError):
        tool.search("q", 10)
    assert len(tool.search("q", 10)) == 1


def test_fourni_champs_propres_a_chaque_api():
    assert tools.extract_fields("openalex", {"id": "W1", "display_name": "T",
                                             "doi": "https://doi.org/10.1/A"})["doi"] == "https://doi.org/10.1/A"
    assert tools.extract_fields("crossref", {"DOI": "10.1/a", "title": ["T"]})["title"] == "T"
    assert tools.extract_fields("semantic_scholar", {"paperId": "p", "title": "T",
                                                     "externalIds": {"DOI": "10.1/A"}})["doi"] == "10.1/A"


def test_fourni_adaptateurs_de_requetes(queries):
    assert tools.scholar_to_boolean(queries["scholar"]) == (
        '("large language models" OR LLM) AND (screening OR "study selection")'
    )
    assert tools.to_keywords(queries["ieee"]) == "large language models LLM screening"
    assert tools.to_keywords(queries["acm"]) == "large language models LLM screening"


def test_fourni_outils_reels_et_erreurs_typees(monkeypatch, queries):
    def handler(request):
        if "openalex" in request.url.host:
            assert request.url.params["search"].startswith('("large language models"')
            return httpx.Response(200, json={"results": [{"id": "W1", "display_name": "T"}]})
        if "crossref" in request.url.host:
            return httpx.Response(429)
        raise httpx.ConnectError("hors ligne", request=request)

    monkeypatch.setattr(tools, "_CLIENT", httpx.Client(transport=httpx.MockTransport(handler)))
    assert tools.openalex_search(queries["scholar"], 5)[0]["id"] == "W1"
    with pytest.raises(tools.RateLimitError):
        tools.crossref_search(queries["ieee"], 5)
    with pytest.raises(tools.NetworkError):
        tools.semantic_scholar_search(queries["acm"], 5)


def test_fourni_registre_refuse_un_outil_inconnu(registry):
    with pytest.raises(ActionError) as caught:
        authorize("scholar", registry())
    assert caught.value.status == "refused"
    assert "openalex" not in registry(allowed=["crossref"])


def test_fourni_statut_global_outil_par_outil():
    ok = TraceEvent(tool="openalex", status="success")
    ko = TraceEvent(tool="crossref", status="rate_limited")
    retried = TraceEvent(tool="crossref", status="success")
    assert overall_status([ok]) == "complete"
    assert overall_status([ok, ko]) == "partial"
    assert overall_status([ok, ko, retried]) == "complete"
    assert overall_status([ko]) == "failed"
    assert overall_status([]) == "failed"


def test_fourni_pont_td02_produit_les_requetes_par_rq():
    outcome, validated, plans = prepare_queries(DemoChatModel(), REFERENCE_TOPIC, accept_proposal)
    assert outcome.status == "accepted"
    assert set(plans) == {"RQ1", "RQ2", "RQ3"}
    assert all(set(item) == {"scholar", "ieee", "acm"} for item in plans.values())


def test_fourni_prompt_de_decision_expose_un_etat_reduit(registry, queries):
    state = SearchState(objective="RQ1", queries=queries)
    prompt = build_decision_prompt(state, registry())
    assert "[ÉTAT]" in prompt and "[DÉCISION]" in prompt
    assert '"pas_utilises": 0' in prompt and "openalex_broad" in prompt
    assert "raw_records" not in prompt


def test_fourni_contrat_action_types_et_bornes():
    with pytest.raises(ValidationError):
        AgentAction(action="explore")
    with pytest.raises(ValidationError):
        AgentAction(action="search", tool="openalex", query="q", limit=0)


# ===========================================================================
# Niveau 1 - Workflow outillé
# ===========================================================================

def test_todo_1_normalize_doi_rend_les_doi_comparables():
    assert normalize_doi("https://doi.org/10.5555/SLR.2024.001") == "10.5555/slr.2024.001"
    assert normalize_doi(" 10.5555/ABC ") == "10.5555/abc"
    assert normalize_doi("doi:10.5555/A B") == "10.5555/ab"


def test_todo_1_normalize_doi_absent():
    assert normalize_doi(None) is None
    assert normalize_doi("   ") is None


def test_todo_2_call_tool_succes_normalise_et_trace(registry):
    records, event = call_tool(registry()["openalex"], "q", 10)
    assert [r.doi for r in records] == ["10.5555/slr.2024.001", "10.5555/slr.2023.014"]
    assert all(r.sources == ["openalex"] for r in records)
    assert (event.tool, event.status, event.found, event.query) == ("openalex", "success", 2, "q")


def test_todo_2_call_tool_transforme_un_429_en_observation(registry):
    records, event = call_tool(registry("perturbe")["semantic_scholar"], "q", 10)
    assert records == []
    assert event.status == "rate_limited" and "429" in event.error


def test_todo_2_call_tool_type_les_autres_erreurs(registry):
    tools_ = registry("panne")
    assert call_tool(tools_["crossref"], "q")[1].status == "http_error"
    assert call_tool(tools_["semantic_scholar"], "q")[1].status == "network_error"


def test_todo_3_dedup_key_doi_puis_titre():
    assert dedup_key(paper("a", doi="10.1/x")) == "doi:10.1/x"
    assert dedup_key(paper("b", title="  Prompt  Engineering ")) == "title:prompt engineering"


def test_todo_3_deduplicate_fusionne_les_sources():
    records = [paper("a", "10.1/x", "openalex"), paper("b", "10.1/y", "openalex"),
               paper("c", "10.1/x", "crossref")]
    unique, removed = deduplicate(records)
    assert removed == 1 and len(unique) == 2
    assert unique[0].sources == ["openalex", "crossref"]
    assert records[0].sources == ["openalex"], "les entrées ne doivent pas être modifiées"


def test_todo_3_deduplicate_par_titre_sans_doi():
    records = [paper("a", None, "semantic_scholar", "Prompt engineering"),
               paper("b", None, "openalex_broad", "PROMPT  Engineering")]
    unique, removed = deduplicate(records)
    assert removed == 1 and unique[0].sources == ["semantic_scholar", "openalex_broad"]


def test_todo_4_workflow_stable(registry, queries):
    state = run_workflow(queries, registry())
    assert [e.tool for e in state.observations] == ["openalex", "crossref", "semantic_scholar"]
    assert (state.raw_count, len(state.papers), state.duplicates_removed) == (4, 3, 1)
    assert state.status == "complete" and state.finished


def test_todo_4_workflow_perturbe_conserve_les_resultats(registry, queries):
    state = run_workflow(queries, registry("perturbe"))
    assert state.observations[-1].status == "rate_limited"
    assert state.raw_count == 4 and state.status == "partial"


def test_todo_4_workflow_respecte_le_registre(registry, queries):
    tools_ = registry(allowed=["openalex", "semantic_scholar"])
    state = run_workflow(queries, tools_)
    assert [e.status for e in state.observations] == ["success", "refused", "success"]
    assert state.status == "partial"


# ===========================================================================
# Niveau 2 - Agent à politique codée
# ===========================================================================

def state_after(queries, events, records=()):
    state = SearchState(objective="test", queries=queries)
    for tool, status in events:
        state.add(search(tool), [], TraceEvent(tool=tool, status=status))
    state.raw_records.extend(records)
    return state


def test_todo_5_decide_next_commence_par_le_plan(queries):
    action = decide_next(SearchState(objective="test", queries=queries))
    assert (action.action, action.tool, action.query) == ("search", "openalex", queries["scholar"])


def test_todo_5_decide_next_source_suivante_meme_apres_un_refus(queries):
    state = state_after(queries, [("openalex", "success"), ("crossref", "refused")])
    action = decide_next(state)
    assert (action.tool, action.query) == ("semantic_scholar", queries["acm"])


def test_todo_5_decide_next_secours_puis_arret(queries):
    events = [("openalex", "success"), ("crossref", "success"), ("semantic_scholar", "success")]
    few = state_after(queries, events, [paper("a", "10.1/a")])
    action = decide_next(few)
    assert (action.tool, action.query) == (FALLBACK_TOOL, queries["scholar"])
    enough = state_after(queries, events, [paper(k, f"10.1/{k}") for k in "abc"])
    assert decide_next(enough).action == "finish"


def test_fourni_regle_1_budget_de_decide_next(queries):
    state = state_after(queries, [("openalex", "success"), ("crossref", "success")])
    assert decide_next(state, max_calls=2).action == "finish"


def test_todo_6_run_agent_execute_puis_termine(registry, queries, scripted):
    decider = scripted([search("openalex", queries["scholar"]), search("crossref", queries["ieee"])])
    state = run_agent(SearchState(objective="t", queries=queries), decider, registry())
    assert [e.tool for e in state.observations] == ["openalex", "crossref"]
    assert state.finished and state.status == "complete" and decider.calls == 3


def test_todo_6_run_agent_trace_un_refus_et_continue(registry, queries, scripted):
    decider = scripted([search("scholar", queries["scholar"]), search("openalex", queries["scholar"])])
    state = run_agent(SearchState(objective="t", queries=queries), decider, registry())
    assert [e.status for e in state.observations] == ["refused", "success"]
    assert state.actions_executed[0].tool == "scholar" and state.finished


def test_todo_6_run_agent_est_borne(registry, queries):
    def never_finish(state):
        return search("openalex", f"q{state.step}")
    state = run_agent(SearchState(objective="t", queries=queries), never_finish, registry(),
                      max_steps=3)
    assert state.step == 3 and not state.finished


def test_todo_6_niveau_2_politique_codee(registry, queries):
    stable = run_level(2, queries, registry())
    assert stable.tools_called() == ["openalex", "crossref", "semantic_scholar"]
    assert stable.status == "complete" and stable.finished
    maigre = run_level(2, queries, registry("maigre"))
    assert maigre.tools_called()[-1] == FALLBACK_TOOL
    assert len(maigre.papers) == 4


# ===========================================================================
# Niveau 3 - Agent ReAct contrôlé
# ===========================================================================

def test_todo_7_parse_agent_action_json_entoure():
    text = 'Voici ma décision :\n```json\n{"action": "search", "tool": "crossref", "query": "q"}\n```'
    action = parse_agent_action(text)
    assert (action.action, action.tool, action.query) == ("search", "crossref", "q")


@pytest.mark.parametrize("text", [
    "", "Je pense qu'il faut chercher sur OpenAlex.", '{"action": "search", "tool": "openalex"',
    '{"action": "explore"}', '{"action": "search", "tool": "openalex", "query": "q", "limit": 0}',
])
def test_todo_7_parse_agent_action_refuse_les_sorties_hors_contrat(text):
    with pytest.raises(ActionError) as caught:
        parse_agent_action(text)
    assert caught.value.status == "invalid"


def test_todo_7_react_controle_avec_llm_discipline(registry, queries):
    state = run_level(3, queries, registry(), model=DemoChatModel("discipline"))
    assert state.tools_called() == ["openalex", "crossref", "semantic_scholar"]
    assert state.finished and state.status == "complete"


def test_todo_8_search_exige_tool_et_query():
    with pytest.raises(ValidationError):
        AgentAction(action="search", tool="openalex")
    with pytest.raises(ValidationError):
        AgentAction(action="search", query="q")


def test_todo_8_finish_sans_outil():
    with pytest.raises(ValidationError):
        AgentAction(action="finish", tool="openalex")
    assert AgentAction(action="finish").tool is None


def test_todo_8_parse_agent_action_refuse_une_action_incoherente():
    with pytest.raises(ActionError) as caught:
        parse_agent_action('{"action": "search", "tool": "openalex"}')
    assert caught.value.status == "invalid"


def test_todo_8_validate_action_transforme_l_erreur(queries):
    with pytest.raises(ActionError) as caught:
        validate_action({"action": "search", "tool": "openalex"})
    assert caught.value.status == "invalid"
    assert validate_action({"action": "search", "tool": "openalex",
                            "query": queries["scholar"]}).tool == "openalex"


def test_todo_8_react_controle_avec_llm_indiscipline(registry, queries):
    state = run_level(3, queries, registry(), model=DemoChatModel("indiscipline"))
    statuses = [e.status for e in state.observations]
    assert statuses[:3] == ["refused", "invalid", "invalid"]
    assert state.observations[0].tool == "scholar"
    assert "openalex" in state.tools_called() and state.finished


# ===========================================================================
# Robustesse
# ===========================================================================

def test_todo_9_relance_unique_apres_un_429(queries):
    state = state_after(queries, [("openalex", "success"), ("semantic_scholar", "rate_limited")])
    retry = retry_after_rate_limit(state)
    assert retry is not None and retry.tool == "semantic_scholar"
    state.add(retry, [], TraceEvent(tool="semantic_scholar", status="rate_limited"))
    assert retry_after_rate_limit(state) is None


def test_todo_9_niveau_2_recupere_la_source_perturbee(registry, queries):
    state = run_level(2, queries, registry("perturbe"))
    assert state.tools_called().count("semantic_scholar") == 2
    assert state.status == "complete" and len(state.papers) == 4


def test_todo_10_refuse_une_action_deja_reussie(queries):
    state = state_after(queries, [("openalex", "success")])
    with pytest.raises(ActionError) as caught:
        check_not_repeated(search("openalex"), state)
    assert caught.value.status == "refused"
    check_not_repeated(search("crossref"), state)


def test_todo_10_autorise_une_seule_relance_apres_429(queries):
    state = state_after(queries, [("semantic_scholar", "rate_limited")])
    check_not_repeated(search("semantic_scholar"), state)
    state.add(search("semantic_scholar"), [], TraceEvent(tool="semantic_scholar", status="rate_limited"))
    with pytest.raises(ActionError):
        check_not_repeated(search("semantic_scholar"), state)


def test_todo_10_react_indiscipline_ne_repete_pas(registry, queries):
    state = run_level(3, queries, registry(), model=DemoChatModel("indiscipline"))
    assert state.tools_called().count("openalex") == 1
    assert any("déjà exécutée" in e.error for e in state.observations)
    assert state.raw_count == 4
