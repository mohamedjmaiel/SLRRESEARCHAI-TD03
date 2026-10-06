"""TD03 - Du sujet aux articles, en trois niveaux (ligne de commande).

    python main.py                       # mode interactif
    python main.py --llm demo --sources simule --scenario perturbe --accepter

Chaîne exécutée :
    sujet -> TD02 (RQ, concepts, revue humaine, requêtes) -> TD03 niveaux 1, 2, 3
"""
import argparse

from slrresearch.config import Settings, build_model, resolve_decoding
from slrresearch.demo_llm import REACT_SCENARIOS, DemoChatModel
from slrresearch.models import short_error
from slrresearch.search_agent import run_level, state_summary
from slrresearch.search_plan import (
    ConceptProposal,
    SearchConcepts,
    accept_proposal,
    apply_human_review,
    build_queries,
    format_concepts_text,
    parse_concepts_text,
)
from slrresearch.td02_bridge import (
    CONCEPT_MAX_OUTPUT_TOKENS,
    REFERENCE_TOPIC,
    generate_questions_for_topic,
    propose_concepts_for_topic,
)
from slrresearch.tools import build_registry, scenario_names

LEVELS = {
    1: "NIVEAU 1 · workflow outillé (le plan décide)",
    2: "NIVEAU 2 · agent à politique codée (des règles décident)",
    3: "NIVEAU 3 · agent ReAct contrôlé (le LLM propose)",
}
DECISION_MAX_OUTPUT_TOKENS = 800


def parse_args():
    parser = argparse.ArgumentParser(description="TD03 - SearchAgent en trois niveaux")
    parser.add_argument("--llm", choices=["demo", "reel"], help="LLM de démonstration ou .env")
    parser.add_argument("--sources", choices=["simule", "reel"], help="catalogue simulé ou API")
    parser.add_argument("--scenario", choices=scenario_names(), help="scénario du catalogue")
    parser.add_argument("--react", choices=REACT_SCENARIOS, help="scénario ReAct (LLM demo)")
    parser.add_argument("--sujet", help="sujet de la revue")
    parser.add_argument("--rq", help="RQ à rechercher (ex. RQ1)")
    parser.add_argument("--accepter", action="store_true",
                        help="accepter les concepts proposés sans les modifier")
    parser.add_argument("--niveaux", default="1,2,3", help="niveaux à exécuter, ex. 1,2")
    return parser.parse_args()


def read(prompt: str, default: str = "") -> str:
    """input() avec valeur par défaut (Entrée, ou entrée standard fermée)."""
    try:
        return input(prompt).strip() or default
    except EOFError:
        print()
        return default


def ask(prompt: str, choices: list[str], default: str) -> str:
    while True:
        answer = read(f"{prompt} {choices} [{default}] : ", default)
        if answer in choices:
            return answer
        print("  Choix invalide.")


def review_proposal(proposal: ConceptProposal) -> SearchConcepts:
    """Revue humaine du TD02 : accepter ou réécrire les concepts d'une RQ."""
    print(f"\n--- {proposal.identifier} · {proposal.question}")
    print(f"Extraction LLM : {proposal.status} (repair : {proposal.repair_attempts})")
    if proposal.extraction:
        print(format_concepts_text(proposal.extraction.concepts))
        if read("Accepter ces concepts ? [O/n] : ", "o").lower() in ("o", "oui", "y"):
            return accept_proposal(proposal)
    else:
        print(f"Aucune proposition exploitable : {proposal.error}")
    while True:
        print("Saisissez un concept par ligne « concept: terme1; terme2 » (ligne vide = fin).")
        lines = []
        while line := read("  > "):
            lines.append(line)
        try:
            return apply_human_review(proposal, parse_concepts_text("\n".join(lines)))
        except ValueError as error:
            print(f"Saisie refusée par le contrat Pydantic : {error}")


def print_state(level: int, state) -> None:
    print(f"\n=== {LEVELS[level]} ===")
    for key, value in state_summary(state).items():
        print(f"  {key:20}: {value}")
    print("  Trace :")
    for event in state.observations:
        detail = f"{event.found} article(s)" if event.status == "success" else short_error(event.error, 90)
        print(f"    pas {event.step} | {event.tool:16} | {event.status:13} | {detail}")
    for paper in state.papers[:6]:
        print(f"    - {paper.title[:70]} | {paper.doi or 'sans DOI'} | {', '.join(paper.sources)}")


def build_models(llm_mode: str, react: str):
    if llm_mode == "demo":
        model = DemoChatModel(react)
        return model, model, model
    settings = Settings()
    name = settings.ollama_model if settings.provider == "ollama" else settings.groq_model
    print(f"LLM réel : {settings.provider} | {name}")
    return (
        build_model(settings, resolve_decoding("greedy")),
        build_model(settings, resolve_decoding("greedy", max_output_tokens=CONCEPT_MAX_OUTPUT_TOKENS)),
        build_model(settings, resolve_decoding("greedy", max_output_tokens=DECISION_MAX_OUTPUT_TOKENS)),
    )


def main():
    args = parse_args()
    llm_mode = args.llm or ask("LLM", ["demo", "reel"], "demo")
    sources = args.sources or ask("Sources", ["simule", "reel"], "simule")
    scenario = "stable"
    if sources == "simule":
        scenario = args.scenario or ask("Scénario du catalogue", scenario_names(), "stable")
    react = "discipline"
    if llm_mode == "demo":
        react = args.react or ask("Scénario ReAct", list(REACT_SCENARIOS), "discipline")
    model, concept_model, decision_model = build_models(llm_mode, react)

    # ---- Pont TD02 : le sujet devient des requêtes -------------------------
    topic = args.sujet or read(f"Sujet de la revue [{REFERENCE_TOPIC}] : ", REFERENCE_TOPIC)
    if llm_mode == "demo" and topic != REFERENCE_TOPIC:
        print("Attention : le LLM de démonstration simule les réponses du sujet de référence.")
    try:
        outcome = generate_questions_for_topic(model, topic)
    except Exception as error:  # clé absente, réseau, quota...
        print(f"Appel LLM impossible : {short_error(error)}")
        return
    print(f"\n=== TD02 · RQ ({outcome.status}) ===")
    if outcome.status == "human_required":
        print(f"Arrêt : validation humaine requise ({outcome.error}).")
        return
    for question in outcome.questions:
        print(f"  {question.identifier}. {question.question}")
    try:
        proposals = propose_concepts_for_topic(concept_model, outcome, topic)
    except Exception as error:
        print(f"Appel LLM impossible : {short_error(error)}")
        return
    validated = [
        accept_proposal(p) if args.accepter and p.extraction else review_proposal(p)
        for p in proposals
    ]
    plans = build_queries(validated)
    print("\n=== TD02 · requêtes par RQ ===")
    for identifier, queries in plans.items():
        print(f"  {identifier}")
        for base, query in queries.items():
            print(f"    {base:8}: {query}")

    rq = args.rq or ask("RQ à rechercher", list(plans), "RQ1")
    queries = plans[rq]
    question = next(item.question for item in validated if item.identifier == rq)

    # ---- TD03 : mêmes requêtes, trois manières de décider -----------------
    results = {}
    for level in [int(x) for x in args.niveaux.split(",") if x.strip()]:
        registry = build_registry(sources, scenario)   # registre neuf à chaque niveau
        try:
            state = run_level(level, queries, registry, model=decision_model,
                              objective=f"{rq} · {question}")
        except NotImplementedError as error:
            print(f"\n=== {LEVELS[level]} ===\n  Non disponible : {error}")
            continue
        except Exception as error:  # LLM injoignable au niveau 3, par exemple
            print(f"\n=== {LEVELS[level]} ===\n  Échec : {short_error(error)}")
            continue
        print_state(level, state)
        results[level] = state_summary(state)

    if results:
        print("\n=== COMPARAISON ===")
        keys = list(next(iter(results.values())))
        print(f"  {'indicateur':20}" + "".join(f"| niveau {lvl:<5}" for lvl in results))
        for key in keys:
            print(f"  {key:20}" + "".join(f"| {str(r[key]):12}" for r in results.values()))


if __name__ == "__main__":
    main()
