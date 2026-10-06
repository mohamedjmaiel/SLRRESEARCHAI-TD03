"""Génère etudiant/ et correction/ à partir d'une source unique (outil enseignant).

    python outils/generer_versions.py

Marqueurs de outils/source/search_agent.src.py :
    #@ TODO n      début de la solution
    #@ ETUDIANT    début du squelette étudiant (lignes préfixées par « #| »)
    #@ FIN         fin du bloc
"""
import ast
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "outils" / "source"
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".DS_Store", "*.pyc", ".env")


def render(text: str, version: str, solved: set[int] | None = None) -> str:
    """version : "etudiant" ou "correction".

    solved (outil de vérification) : numéros de TODO dont la solution est
    insérée dans la version étudiant, pour simuler une progression.
    """
    out, mode, current = [], "commun", 0
    for line in text.splitlines():
        marker = line.strip()
        if marker.startswith("#@ TODO"):
            current = int(marker.split()[2].split(".")[0])
            mode = "solution"
            if solved and current in solved:
                mode = "solution_forcee"
            continue
        if mode == "solution_forcee":
            if marker == "#@ ETUDIANT":
                mode = "ignorer"
            else:
                out.append(line)
            continue
        if mode == "ignorer":
            if marker == "#@ FIN":
                mode = "commun"
            continue
        if marker == "#@ ETUDIANT":
            mode = "etudiant"
            continue
        if marker == "#@ FIN":
            mode = "commun"
            continue
        if mode == "commun" or (mode == "solution" and version == "correction"):
            out.append(line)
        elif mode == "etudiant" and version == "etudiant":
            out.append(re.sub(r"#\| ?", "", line, count=1))
    if mode != "commun":
        sys.exit("Marqueur #@ FIN manquant")
    return "\n".join(out) + "\n"


def build(version: str) -> Path:
    target = ROOT / version
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SOURCE / "commun", target, ignore=IGNORE)
    agent = (SOURCE / "search_agent.src.py").read_text(encoding="utf-8")
    (target / "slrresearch" / "search_agent.py").write_text(render(agent, version), encoding="utf-8")
    if version == "correction":
        shutil.copytree(SOURCE / "correction_seule", target, dirs_exist_ok=True, ignore=IGNORE)
        code = (target / "slrresearch" / "search_agent.py").read_text(encoding="utf-8")
        for template in target.glob("*.template.md"):
            text = fill_template(template.read_text(encoding="utf-8"), code)
            template.with_name(template.name.replace(".template", "")).write_text(text, encoding="utf-8")
            template.unlink()
    return target


def fill_template(text: str, code: str) -> str:
    """Remplace {{code:nom}} ou {{code:Classe.methode}} par le code de la correction."""
    tree = ast.parse(code)

    def find(name: str) -> str:
        parts = name.split(".")
        nodes = tree.body
        for index, part in enumerate(parts):
            node = next(n for n in nodes if getattr(n, "name", None) == part)
            nodes = getattr(node, "body", [])
        start = node.decorator_list[0].lineno if getattr(node, "decorator_list", None) else node.lineno
        lines = code.splitlines()[start - 1: node.end_lineno]
        return "\n".join(lines) if len(parts) == 1 else __import__("textwrap").dedent("\n".join(lines))

    return re.sub(r"\{\{code:([\w.]+)\}\}", lambda m: find(m.group(1)), text)


if __name__ == "__main__":
    for name in ("etudiant", "correction"):
        print("généré :", build(name).relative_to(ROOT))
