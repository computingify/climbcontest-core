"""Le harnais navigateur ne doit pas relancer un chromium par test.

⚠️ **Le defaut que ce fichier ferme, et qui s'est produit deux fois.**

Un test navigateur coute un demarrage de chromium : 0,3 s a chaud, **7,2 s au
premier lancement** d'un runner, et bien davantage sur une machine chargee.
Quand la fixture qui pilote le navigateur est en portee FONCTION et qu'une
vingtaine de tests la lisent, le meme parcours est rejoue une fois par test.

Le symptome ne ressemble pas a sa cause : le fichier finit par depasser le
delai du pilote, sur un parametre **different a chaque execution**, et le rouge
se lit comme un contraste en faute alors que les valeurs mesurees sont bonnes.
C'est exactement ce qui faisait passer ces rouges pour un « alea de runner ».

Mesure du 04/09 :

| Fichier | Avant | Apres |
| --- | --- | --- |
| `test_navigateur_juge_claire.py` (30 tests) | 30 navigateurs, des minutes | 1 navigateur, 1,5 s |
| `test_navigateur_theme_au_choix.py` (13 tests) | 13 navigateurs, 19,2 s | 1 navigateur, 1,6 s |

⚠️ La regle porte sur les fixtures qui appellent `piloter`, PAS sur celles qui
montent un serveur. `test_navigateur_reglages_resultats.py` appelle `piloter`
dans chacun de ses cinq tests, avec cinq parcours differents : sa portee
fonction est correcte, et il doit le rester. Ce qu'on interdit, c'est de rejouer
le MEME parcours N fois.
"""
import ast
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
FICHIERS = sorted(TESTS.glob("test_navigateur_*.py"))


def _portee(decorateur: ast.expr) -> str | None:
    """La portee declaree par `@pytest.fixture(...)`, ou None si absente."""
    if not isinstance(decorateur, ast.Call):
        return None
    for mot in decorateur.keywords:
        if mot.arg == "scope" and isinstance(mot.value, ast.Constant):
            return mot.value.value
    return None


def _est_une_fixture(decorateur: ast.expr) -> bool:
    cible = decorateur.func if isinstance(decorateur, ast.Call) else decorateur
    return isinstance(cible, ast.Attribute) and cible.attr == "fixture"


def _appelle_piloter(noeud: ast.FunctionDef) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == "piloter"
               for n in ast.walk(noeud))


def _fixtures_qui_pilotent(arbre: ast.Module):
    for noeud in arbre.body:
        if not isinstance(noeud, ast.FunctionDef):
            continue
        decos = [d for d in noeud.decorator_list if _est_une_fixture(d)]
        if decos and _appelle_piloter(noeud):
            yield noeud.name, _portee(decos[0])


@pytest.mark.parametrize("fichier", FICHIERS, ids=lambda f: f.name)
def test_une_fixture_qui_pilote_declare_sa_portee(fichier):
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    fautives = [nom for nom, portee in _fixtures_qui_pilotent(arbre)
                if portee in (None, "function")]
    assert fautives == [], (
        f"dans {fichier.name}, la ou les fixtures {fautives} lancent un "
        "navigateur et sont en portee FONCTION : le meme parcours sera rejoue "
        "une fois par test qui les lit. Si le releve est en lecture seule, "
        'poser scope="module". S\'il doit vraiment differer d\'un test a '
        "l'autre, appeler `piloter` dans le test et non dans une fixture "
        "partagee, comme le fait test_navigateur_reglages_resultats.py")


def test_le_garde_regarde_bien_quelque_chose():
    """Un garde qui ne trouve aucun fichier passerait pour toujours vert."""
    assert len(FICHIERS) >= 5, (
        "les tests navigateur ont ete renommes ou deplaces : ce garde ne "
        f"regarde plus que {len(FICHIERS)} fichier(s)")
    pilotantes = [nom for f in FICHIERS
                  for nom, _ in _fixtures_qui_pilotent(ast.parse(
                      f.read_text(encoding="utf-8")))]
    assert pilotantes, (
        "aucune fixture ne pilote plus de navigateur : soit le harnais a "
        "change de forme, soit ce garde ne sait plus le reconnaitre")
