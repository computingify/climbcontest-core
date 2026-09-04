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

from tests.navigateur import CHROME, piloter

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


def _appels_a_piloter(arbre: ast.Module):
    """Chaque appel a `piloter`, rendu sous une forme comparable.

    ⚠️ On compare la SOURCE des arguments, pas leur valeur : `ast.unparse`
    rend `f"{url}/__harnais?quoi=lecture"` et `f"{url}/__harnais"` differents,
    ce qui est exactement ce qu'on veut. Deux appels dont la source est
    identique jouent forcement le meme parcours.
    """
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == "piloter":
            # `secondes` ne change pas le parcours, seulement la patience :
            # deux appels qui ne different que par lui sont bien identiques.
            args = [ast.unparse(a) for a in n.args]
            mots = sorted(f"{k.arg}={ast.unparse(k.value)}" for k in n.keywords
                          if k.arg != "secondes")
            yield ", ".join(args + mots)


@pytest.mark.parametrize("fichier", FICHIERS, ids=lambda f: f.name)
def test_aucun_parcours_n_est_rejoue_a_l_identique(fichier):
    """Le second controle, et celui qui demande le plus de discernement.

    ⚠️ La regle NAIVE serait « plusieurs tests appellent `piloter`, donc c'est
    du gaspillage ». Elle est fausse : `test_navigateur_reglages_resultats.py`
    appelle `piloter` cinq fois, avec cinq parcours REELLEMENT differents
    (`?src=/__vue`, `?quoi=lecture`, `?quoi=recherche`...), et chacun merite son
    navigateur. Un garde incapable de les distinguer demanderait une exemption
    declaree -- qui finirait posee par reflexe, et ne protegerait plus rien.

    La regle retenue est donc STRUCTURELLE et sans faux positif : deux appels
    dont les arguments sont ecrits a l'identique rejouent le meme parcours, il
    n'y a pas d'autre lecture possible. Les cinq appels de
    `reglages_resultats` s'exemptent tout seuls, sans qu'on ait rien a declarer.
    """
    appels = list(_appels_a_piloter(ast.parse(fichier.read_text(encoding="utf-8"))))
    rejoues = sorted({a for a in appels if appels.count(a) > 1})
    assert rejoues == [], (
        f"dans {fichier.name}, le meme parcours est joue plusieurs fois : "
        f"{rejoues}. Chaque appel coute un demarrage de chromium pour un releve "
        "identique. Faire UN passage qui mesure tout, et le partager par une "
        'fixture en scope="module" -- ou, si les parcours doivent differer, '
        "les faire differer pour de bon")


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


@pytest.mark.skipif(CHROME is None,
                    reason="aucun navigateur : ce test se saute, il n'echoue pas")
def test_piloter_ne_rend_jamais_un_verdict_deja_la():
    """Le piege que `piloter` ferme desormais, verifie par le comportement.

    ⚠️ Ce test COUTE un demarrage de chromium, et c'est assume : c'est le seul
    moyen de prouver la chose plutot que de la relire. Il est borne a une
    seconde de patience -- on ne verifie pas la duree, on verifie que le
    navigateur a bien ete lance au lieu d'etre court-circuite.

    Sans la remise a zero, `piloter` trouve le verdict deja pose, le rend
    instantanement et NE LANCE RIEN. C'est ce qui ferait passer au vert un test
    mutualise sur les mesures du parcours precedent.
    """
    # Un verdict deja rempli : exactement ce que laisse un appel precedent
    # quand la fixture qui porte le dictionnaire est partagee.
    verdict = {"texte": "OK perime=1"}

    # Une adresse ou personne ne repond : le pilote ne peut RIEN poster. Le
    # seul verdict possible est donc un echec -- sauf s'il rend le perime.
    rendu = piloter("http://127.0.0.1:9/", verdict, secondes=1)

    assert not rendu.startswith("OK "), (
        "`piloter` a rendu un verdict qu'il n'a pas produit : "
        f"{rendu!r}. La remise a zero de `verdict['texte']` a saute, et un "
        "test mutualise passerait au vert sur le parcours precedent")
    assert "perime" not in rendu, (
        f"le verdict perime a survecu a l'appel : {rendu!r}")
