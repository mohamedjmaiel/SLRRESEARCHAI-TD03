"""Vérifie la cohérence du TD03 (outil enseignant).

    python outils/verifier_coherence.py

1. etudiant/ et correction/ sont à jour par rapport à outils/source ;
2. correction : tous les tests passent ;
3. étudiant   : les tests « fourni » passent, chaque test « todo » échoue ;
4. progression : après la solution des TODO 1..k, les tests todo_1..todo_k
   passent et les tests des TODO suivants échouent encore ;
5. énoncé : chaque TODO est décrit, chaque groupe de tests existe ;
6. la version étudiant ne parle ni de correction ni de travail à domicile.
"""
import filecmp
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generer_versions import ROOT, SOURCE, render  # noqa: E402

TODOS = list(range(1, 11))
PROBLEMS: list[str] = []


def check(condition: bool, message: str) -> None:
    print(("  ok    " if condition else "  ÉCHEC ") + message)
    if not condition:
        PROBLEMS.append(message)


def run_pytest(folder: Path) -> dict[str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider"],
        cwd=folder, capture_output=True, text=True,
    )
    outcomes = {}
    for line in result.stdout.splitlines():
        match = re.match(r"^(PASSED|FAILED|ERROR) tests/\S+?::(.+?)(?: - .*)?$", line)
        if match:
            outcomes[match.group(2)] = match.group(1)
    return outcomes


def group(test_name: str) -> str:
    match = re.match(r"test_(todo_\d+|fourni)", test_name)
    return match.group(1) if match else "autre"


def summary(outcomes: dict[str, str]) -> dict[str, tuple[int, int]]:
    table = defaultdict(lambda: [0, 0])
    for name, outcome in outcomes.items():
        table[group(name)][0 if outcome == "PASSED" else 1] += 1
    return {key: tuple(value) for key, value in table.items()}


source_agent = (SOURCE / "search_agent.src.py").read_text(encoding="utf-8")

print("1. Versions générées à jour")
for version in ("etudiant", "correction"):
    target = ROOT / version
    generated = (target / "slrresearch" / "search_agent.py").read_text(encoding="utf-8")
    check(generated == render(source_agent, version), f"{version}/slrresearch/search_agent.py")
    commun = SOURCE / "commun"
    for path in commun.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store":
            other = target / path.relative_to(commun)
            check(other.exists() and filecmp.cmp(path, other, shallow=False),
                  f"{version}/{path.relative_to(commun)}")

print("2. Correction : tous les tests passent")
correction = run_pytest(ROOT / "correction")
check(bool(correction) and all(v == "PASSED" for v in correction.values()),
      f"{sum(v == 'PASSED' for v in correction.values())}/{len(correction)} tests réussis")

print("3. Étudiant : fourni vert, TODO rouges")
student = run_pytest(ROOT / "etudiant")
check(set(student) == set(correction), "mêmes tests dans les deux versions")
for name, outcome in sorted(student.items()):
    expected = "PASSED" if group(name) == "fourni" else "FAILED"
    if outcome != expected:
        check(False, f"{name} : {outcome} (attendu {expected})")
print("  résumé", summary(student))

print("4. Progression TODO par TODO")
with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp) / "td03"
    shutil.copytree(ROOT / "etudiant", work, ignore=shutil.ignore_patterns("__pycache__"))
    for k in TODOS:
        solved = set(range(1, k + 1))
        (work / "slrresearch" / "search_agent.py").write_text(
            render(source_agent, "etudiant", solved), encoding="utf-8")
        outcomes = run_pytest(work)
        table = summary(outcomes)
        done_ok = all(table.get(f"todo_{j}", (0, 0))[1] == 0 for j in solved)
        todo_ko = all(table.get(f"todo_{j}", (0, 1))[0] == 0 for j in TODOS if j > k)
        fourni_ok = table.get("fourni", (0, 1))[1] == 0
        check(done_ok and todo_ko and fourni_ok,
              f"après TODO 1..{k} : " + " ".join(f"{g}={p}/{p + f}" for g, (p, f) in sorted(table.items())))

print("5. Énoncé, TODO et tests")
enonce = (ROOT / "etudiant" / "ENONCE_TD03.md").read_text(encoding="utf-8")
code = (ROOT / "etudiant" / "slrresearch" / "search_agent.py").read_text(encoding="utf-8")
for k in TODOS:
    check(f"## TODO {k} " in enonce, f"énoncé : section « TODO {k} »")
    check(f"TODO {k}" in code, f"code étudiant : marqueur TODO {k}")
    check(any(group(name) == f"todo_{k}" for name in correction), f"tests : groupe todo_{k}")
    check(f'-k "todo_{k}"' in enonce or f"-k todo_{k}" in enonce, f"énoncé : commande de test todo_{k}")

print("6. Version étudiant sans correction ni répartition")
for path in (ROOT / "etudiant").rglob("*"):
    if path.suffix in (".py", ".md", ".txt", ".toml", ".ini"):
        text = path.read_text(encoding="utf-8").lower()
        for word in ("domicile", "à la maison", "correction complète", "#@"):
            if word in text:
                check(False, f"{path.relative_to(ROOT)} contient « {word} »")
check(not (ROOT / "etudiant" / "CORRECTION_TD03.md").exists(), "pas de CORRECTION_TD03.md côté étudiant")

print()
if PROBLEMS:
    print(f"{len(PROBLEMS)} problème(s) détecté(s).")
    sys.exit(1)
print("Cohérence vérifiée : aucun problème.")
