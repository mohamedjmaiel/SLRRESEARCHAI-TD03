"""TD03 - Interface pédagogique : du sujet aux articles, en trois niveaux.

    python -m streamlit run streamlit_app.py
"""
import streamlit as st

from slrresearch.config import Settings, build_model, resolve_decoding
from slrresearch.demo_llm import REACT_SCENARIOS, DemoChatModel
from slrresearch.models import short_error
from slrresearch.search_agent import ROUTES, run_level, state_summary
from slrresearch.search_plan import apply_human_review, build_queries, format_concepts_text, parse_concepts_text
from slrresearch.td02_bridge import (
    CONCEPT_MAX_OUTPUT_TOKENS,
    REFERENCE_TOPIC,
    generate_questions_for_topic,
    propose_concepts_for_topic,
)
from slrresearch.tools import build_registry, scenario_names

LEVELS = {
    1: ("Niveau 1 · workflow outillé", "Le plan fixe ROUTES choisit chaque appel."),
    2: ("Niveau 2 · politique codée", "decide_next choisit l'action selon l'état."),
    3: ("Niveau 3 · ReAct contrôlé", "Le LLM propose ; validation, registre et bornes disposent."),
}
SCENARIO_HELP = {
    "stable": "4 bruts · 3 uniques · 1 doublon",
    "perturbe": "Semantic Scholar répond 429 au premier appel",
    "maigre": "trop peu d'articles : la source de secours devient utile",
    "panne": "Crossref en erreur HTTP, Semantic Scholar hors réseau",
}

st.set_page_config(page_title="SLRResearchAI · TD03", page_icon=":material/travel_explore:", layout="wide")
st.title("TD03 · Des outils à l'agent")
st.code(
    "sujet → TD02 (RQ → concepts → revue humaine → requêtes)\n"
    "      → niveau 1 : le plan décide   → niveau 2 : des règles décident\n"
    "      → niveau 3 : le LLM propose, le logiciel valide, autorise, exécute et borne",
    language="text",
)

# ---------------------------------------------------------------- réglages
with st.sidebar:
    st.header("Réglages")
    llm_mode = st.radio("LLM", ["Démonstration (sans clé)", "Réel (.env)"], key="llm_mode")
    react = st.selectbox("Scénario ReAct de démonstration", REACT_SCENARIOS,
                         disabled=llm_mode != "Démonstration (sans clé)", key="react")
    sources = st.radio("Sources", ["Catalogue simulé", "API réelles"], key="sources")
    scenario = st.selectbox("Scénario du catalogue", scenario_names(),
                            disabled=sources != "Catalogue simulé", key="scenario")
    if sources == "Catalogue simulé":
        st.caption(SCENARIO_HELP.get(scenario, ""))
    st.caption("Résultats simulés et réels ne sont jamais mélangés.")


def get_models():
    """(modèle RQ, modèle concepts, modèle de décision)."""
    if llm_mode.startswith("Démonstration"):
        model = DemoChatModel(react)
        return model, model, model
    settings = Settings()
    return (
        build_model(settings, resolve_decoding("greedy")),
        build_model(settings, resolve_decoding("greedy", max_output_tokens=CONCEPT_MAX_OUTPUT_TOKENS)),
        build_model(settings, resolve_decoding("greedy", max_output_tokens=800)),
    )


for key in ("td03_outcome", "td03_proposals", "td03_plans", "td03_results"):
    st.session_state.setdefault(key, None)
st.session_state.setdefault("td03_run", 0)

# ---------------------------------------------------------------- étape 1 : pont TD02
st.header("Étape 1 · Du sujet aux requêtes (TD02)")
topic = st.text_input("Sujet de la revue", REFERENCE_TOPIC, key="topic")
if llm_mode.startswith("Démonstration") and topic.strip() != REFERENCE_TOPIC:
    st.warning("Le LLM de démonstration simule les réponses du sujet de référence. "
               "Choisissez « Réel (.env) » pour générer des RQ propres à votre sujet.")

if st.button("1 · Générer les RQ et proposer les concepts", type="primary", icon=":material/psychology:"):
    try:
        model, concept_model, _ = get_models()
        outcome = generate_questions_for_topic(model, topic)
        proposals = (None if outcome.status == "human_required"
                     else propose_concepts_for_topic(concept_model, outcome, topic))
        st.session_state.td03_outcome = outcome
        st.session_state.td03_proposals = proposals
        st.session_state.td03_plans = None
        st.session_state.td03_results = None
        st.session_state.td03_run += 1
    except Exception as error:  # clé absente, réseau, sujet vide...
        st.error(f"Génération impossible : {error}")

outcome = st.session_state.td03_outcome
if outcome is not None:
    st.write(f"Workflow TD02 : **{outcome.status}** (repair : {outcome.repair_attempts})")
    if outcome.status == "human_required":
        st.error(f"Validation humaine requise : {outcome.error}")
    for question in outcome.questions:
        st.markdown(f"- **{question.identifier}** · {question.question}")

proposals = st.session_state.td03_proposals
if proposals:
    st.subheader("Revue humaine des concepts")
    st.caption("Une ligne par concept : `concept: terme1; terme2`. Les termes d'une ligne sont reliés par OR, les lignes par AND.")
    columns = st.columns(len(proposals))
    for column, proposal in zip(columns, proposals):
        with column:
            st.markdown(f"**{proposal.identifier}** · extraction `{proposal.status}`")
            default = format_concepts_text(proposal.extraction.concepts) if proposal.extraction else ""
            st.text_area(proposal.question, default, height=150,
                         key=f"concepts_{st.session_state.td03_run}_{proposal.identifier}")
    if st.button("2 · Valider les concepts et construire les requêtes", type="primary", icon=":material/how_to_reg:"):
        validated, errors = [], []
        for proposal in proposals:
            text = st.session_state[f"concepts_{st.session_state.td03_run}_{proposal.identifier}"]
            try:
                validated.append(apply_human_review(proposal, parse_concepts_text(text)))
            except ValueError as error:
                errors.append(f"{proposal.identifier} : {short_error(error)}")
        if errors:
            for error in errors:
                st.error("Contrat Pydantic : " + error)
        else:
            st.session_state.td03_plans = {
                "queries": build_queries(validated),
                "questions": {item.identifier: item.question for item in validated},
            }
            st.session_state.td03_results = None

plans = st.session_state.td03_plans
if not plans:
    st.stop()

with st.expander("Requêtes produites par le TD02", expanded=False):
    st.json(plans["queries"])

# ---------------------------------------------------------------- étape 2 : trois niveaux
st.header("Étape 2 · Mêmes requêtes, trois manières de décider")
rq = st.selectbox("RQ à rechercher", list(plans["queries"]), key="rq")
queries = plans["queries"][rq]
st.dataframe(
    [{"base TD02": base, "outil (ROUTES)": ROUTES[base], "requête transmise sans recopie": query}
     for base, query in queries.items()],
    hide_index=True, width="stretch",
)

if st.button("3 · Exécuter les niveaux 1, 2 et 3", type="primary", icon=":material/play_arrow:"):
    results = {}
    try:
        _, _, decision_model = get_models()
    except Exception as error:
        decision_model = None
        st.warning(f"Niveau 3 indisponible : {error}")
    for level in (1, 2, 3):
        registry = build_registry("simule" if sources == "Catalogue simulé" else "reel", scenario)
        try:
            results[level] = run_level(level, queries, registry, model=decision_model,
                                       objective=f"{rq} · {plans['questions'][rq]}")
        except NotImplementedError as error:
            results[level] = f"Non disponible : {error}"
        except Exception as error:
            results[level] = f"Échec : {error}"
    st.session_state.td03_results = results

results = st.session_state.td03_results
if results:
    tabs = st.tabs([LEVELS[level][0] for level in results])
    for tab, (level, state) in zip(tabs, results.items()):
        with tab:
            st.caption(LEVELS[level][1])
            if isinstance(state, str):
                st.warning(state)
                continue
            summary = state_summary(state)
            cols = st.columns(6)
            cols[0].metric("Statut", summary["statut"].upper())
            cols[1].metric("Appels d'outils", summary["appels_outils"])
            cols[2].metric("Refus / invalides", summary["refus_ou_invalides"])
            cols[3].metric("Bruts", summary["articles_bruts"])
            cols[4].metric("Uniques", summary["articles_uniques"])
            cols[5].metric("Doublons", summary["doublons_retires"])
            st.write("Trace : une ligne par action, réussie ou non")
            st.dataframe(
                [{"pas": e.step,
                  "action": (a.action if a else "—"),
                  "outil": e.tool, "statut": e.status, "trouvés": e.found,
                  "erreur": short_error(e.error)}
                 for a, e in zip(state.actions_executed, state.observations)],
                hide_index=True, width="stretch",
            )
            st.caption("Arrêt : " + ("action finish" if state.finished else "borne de la boucle ou fin du plan"))
            st.write("Articles uniques (avec provenance)")
            st.dataframe(
                [{"titre": p.title, "doi": p.doi or "—", "année": p.year, "sources": ", ".join(p.sources)}
                 for p in state.papers],
                hide_index=True, width="stretch",
            )
    done = {level: state_summary(state) for level, state in results.items() if not isinstance(state, str)}
    if done:
        st.subheader("Comparaison")
        st.dataframe(
            [{"indicateur": key, **{LEVELS[level][0]: str(values[key]) for level, values in done.items()}}
             for key in next(iter(done.values()))],
            hide_index=True, width="stretch",
        )
