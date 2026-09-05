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
import os
import warnings
from pathlib import Path

import pytest

# ⚠️ Importer `piloter` place CE fichier dans le groupe navigateur, exactement
# comme les six autres -- et c'est ce qui permet a
# `test_le_regroupement_arrive_bien_jusqu_a_xdist` de lire son propre
# identifiant : un garde du regroupement doit etre DANS le groupe qu'il
# surveille, sinon il ne prouve rien.
from tests.navigateur import CHROME, GROUPE, NAVIGATEUR, piloter


#: Le nom du test qui paie le demarrage. `tests/conftest.py` le fait passer en
#: TETE du groupe navigateur -- c'est la seule raison d'etre de cette constante,
#: et le garde ci-dessous verifie qu'elle designe bien quelque chose.
DEMARRE_LE_NAVIGATEUR = "test_le_navigateur_demarre_et_repond"


# ⚠️ 45 s, et c'est le SEUL test du depot qui declare son plafond.
#
# Le budget ordinaire est de 20 s, et il vise les tests qui ATTENDENT une
# horloge. Celui-ci n'attend rien : il paie un travail reel et incompressible,
# le premier lancement de chromium. Mesure sur trois passages de CI le 04/09 :
# **12,7 s, 17,1 s et 22,2 s** -- le meme geste, du simple au double, selon ce
# que le runner a d'autre a faire. 45 s laisse de la marge sans devenir un
# plafond qui ne se declenche jamais.
#
# Le geste a NE PAS faire est de relever CLIMBCONTEST_BUDGET_TEST_S : il
# aveuglerait le garde sur les mille huit cent soixante-onze autres tests, et
# personne ne s'en apercevrait.
@pytest.mark.budget(45)
@pytest.mark.skipif(CHROME is None,
                    reason="aucun navigateur : ce test se saute, il n'echoue pas")
def test_le_navigateur_demarre_et_repond():
    """Le premier test du groupe, et celui qui paie le demarrage a froid.

    ⚠️ **Ce n'est pas un test de complaisance.** Le premier lancement de
    chromium coute **17,1 s sur un runner GitHub** -- mesure le 04/09, ou
    l'image fournit un chromium en paquet confine. Ce prix etait facture au
    premier test navigateur venu, par ordre alphabetique : celui de la couture
    des zones affichait 20 s en CI contre 0,13 s sur le Mac, et faisait echouer
    le budget par test en accusant un test qui n'attendait rien.

    C'est exactement le defaut que la chauffe corrigeait AVANT le parallelisme.
    Sous `pytest-xdist`, elle ne marche plus : le processus qui chauffait n'est
    plus celui qui joue les tests, et chauffer dans CHAQUE worker lance quatre
    chromium a froid en concurrence -- mesure aussi, c'est pire (30 s).

    Alors on ne cache plus le prix : on le rend a un test dont c'est le SUJET.
    Celui-ci verifie que le harnais sait ouvrir un navigateur et lui parler --
    ce qui, aujourd'hui, ne se decouvrait qu'a travers l'echec confus d'un test
    de contraste. `tests/conftest.py` le place en tete du groupe ; les autres
    trouvent un navigateur chaud, a 0,3 s.
    """
    NAVIGATEUR.demarrer()
    version = NAVIGATEUR.appeler("Browser.getVersion")
    assert version.get("product", "").lower().startswith(("chrome", "headless")), (
        f"le navigateur a repondu {version!r} : le harnais parle bien CDP, mais "
        "pas a un chromium")
    assert NAVIGATEUR.processus.poll() is None, (
        "le navigateur s'est arrete juste apres avoir repondu")


def _analyser(fichier: Path) -> ast.Module:
    """`ast.parse` COMPILE, donc il rejoue les avertissements de syntaxe du
    fichier lu -- un `\\{` dans une expression reguliere en produit un. Ce
    garde lit tous les fichiers de test : sans ce silence, il remplirait le
    resume de pytest d'avertissements qui ne le concernent pas et qui
    n'appartiennent meme pas au fichier qui les affiche."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(fichier.read_text(encoding="utf-8"))

TESTS = Path(__file__).resolve().parent

# ⚠️ ON NE SE FIE PAS AU NOM DES FICHIERS. La premiere version de ce garde
# regardait `test_navigateur_*.py`, et laissait passer
# `test_coherence_console_ecran.py` -- qui pilote un navigateur sans le dire
# dans son nom, et qui se trouve etre le PREMIER par ordre alphabetique parmi
# ceux qui en lancent un : c'est donc lui qui paie le demarrage a froid de
# chromium, 7,2 s sur un runner. Le fichier le plus expose etait exactement
# celui que le garde ne regardait pas.
#
# On selectionne donc sur ce que le fichier FAIT -- il appelle `piloter` --
# et non sur la facon dont il s'appelle. Un fichier futur qui pilote un
# navigateur sous un autre nom sera couvert sans que personne y pense.
FICHIERS = sorted(f for f in TESTS.glob("test_*.py")
                  if "piloter(" in f.read_text(encoding="utf-8"))


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
    arbre = _analyser(fichier)
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
    assert len(FICHIERS) >= 8, (
        "les tests qui pilotent un navigateur ont ete renommes ou deplaces : "
        f"ce garde ne regarde plus que {len(FICHIERS)} fichier(s)")
    # Le fichier qui a revele l'angle mort doit rester dans le champ : c'est
    # lui qui paie le demarrage a froid, et son nom ne l'annonce pas.
    noms = {f.name for f in FICHIERS}
    assert "test_coherence_console_ecran.py" in noms, (
        "le fichier qui pilote un navigateur sans le dire dans son nom est "
        "sorti du champ du garde : la selection est redevenue nominale")
    pilotantes = [nom for f in FICHIERS
                  for nom, _ in _fixtures_qui_pilotent(_analyser(f))]
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


@pytest.mark.skipif(CHROME is None,
                    reason="aucun navigateur : ce test se saute, il n'echoue pas")
def test_calme_survit_a_une_requete_qui_finit_apres_un_rechargement():
    """⚠️ Le rouge de CI du 05/09, reproduit — et il n'etait pas un alea.

    `calme()` attend que plus aucune requete ne soit en vol. Le compteur est
    remis a zero quand la page change, parce que les requetes de l'ancienne ne
    veulent plus rien dire. Mais leur `finally` s'execute quand meme : sans
    garde, il decremente un compteur deja remis a zero, qui passe a **-1**.
    `_enVol === 0` n'est alors plus jamais vrai, et `calme()` attend ses dix
    secondes avant d'echouer sur un delai — en accusant une page qui est calme
    depuis longtemps.

    Le defaut ne se voit pas sur une machine au repos : les requetes de
    l'ancienne page s'y terminent AVANT la navigation. Il apparait sur un
    runner charge, ou elles se terminent apres. C'est ce qui a fait echouer
    `test_navigateur_console_vue_courante.py` en CI pendant qu'il etait vert
    sur le Mac au meme instant.

    Le parcours ci-dessous force la sequence, sans dependre d'aucune charge :
    on lance une requete LENTE, on navigue pendant qu'elle est en vol, elle se
    termine ensuite, et on demande le calme.
    """
    import threading
    import time

    from flask import Flask, Response, request

    from tests.navigateur import page_harnais, servir

    app = Flask(__name__)
    partie = threading.Event()

    @app.get("/lente")
    def lente():
        # Elle ne rend la main que sur ordre de la sonde : la sequence est
        # garantie, sans aucun `sleep` arbitraire ni pari sur la charge.
        partie.wait(timeout=5)
        return "fini"

    @app.get("/liberer")
    def liberer():
        partie.set()
        return "ok"

    @app.get("/page")
    def page():
        return Response(
            "<!doctype html><title>page</title><body>page</body>",
            mimetype="text/html")

    @app.get("/suivante")
    def suivante():
        return Response(
            "<!doctype html><title>suivante</title><body>suivante</body>",
            mimetype="text/html")

    verdict = {"texte": None}

    @app.post("/__verdict")
    def poser():
        verdict["texte"] = request.get_data(as_text=True)
        return "", 204

    # ⚠️ L'ORDRE fait tout, et c'est ce qui distingue ce test d'un test qui
    # passerait de toute facon : la remise a zero du compteur doit tomber
    # ENTRE le depart de la requete et son arrivee. Elle a lieu dans
    # `calme()` -- il en faut donc un au milieu.
    sonde = r"""
        await attendre("page chargee", () => vue().document.body !== null);

        // 1. Une requete lente, laissee EN VOL : on ne l'attend pas.
        vue().fetch("/lente");

        // 2. On navigue pendant qu'elle est en vol.
        cadre.src = "/suivante";
        await attendre("page suivante",
          () => vue().document.body
             && /suivante/.test(vue().document.body.textContent));

        // 3. Ce `calme()`-ci remet le compteur a zero : la fenetre a change,
        //    et les requetes de l'ancienne ne veulent plus rien dire.
        await calme();

        // 4. MAINTENANT la lente se termine. Son `finally` s'execute sur un
        //    compteur deja remis a zero : sans le garde, il passe a -1.
        await vue().fetch("/liberer");
        await new Promise((r) => setTimeout(r, 400));

        // 5. Et plus aucune attente ne peut se terminer.
        await calme();
        note("calme", "rendu");
    """

    @app.get("/__harnais")
    def harnais():
        return Response(page_harnais("/page", sonde), mimetype="text/html")

    url, arreter = servir(app)
    try:
        debut = time.monotonic()
        rendu = piloter(f"{url}/__harnais", verdict, secondes=20)
    finally:
        partie.set()
        arreter()

    assert rendu.startswith("OK "), (
        f"`calme()` n'est jamais revenu : {rendu!r}. Le compteur de requetes "
        "en vol est passe sous zero apres un rechargement, et plus aucune "
        "attente ne peut se terminer")
    assert time.monotonic() - debut < 10, (
        "`calme()` a mis plus de dix secondes : il a attendu son delai au lieu "
        "de constater le calme")


# --- Le regroupement sous xdist ---------------------------------------------
#
# La portee des fixtures ne suffit plus a garantir « un navigateur ». Depuis
# que la suite tourne en parallele, il faut AUSSI que tous les tests qui
# pilotent atterrissent sur le meme worker -- sinon `pytest-xdist` les
# eparpille et chaque worker redemarre un chromium. Le regroupement est pose
# par `tests/conftest.py` ; ce qui suit verifie qu'il n'oublie personne.


def _modules_qui_pilotent():
    """Les fichiers de test qui importent `piloter`, quel que soit leur nom.

    ⚠️ On ne regarde PAS `test_navigateur_*` : `test_coherence_console_ecran.py`
    pilote sans porter le prefixe, et c'est exactement le fichier qu'un garde
    fonde sur le nom laisserait passer.
    """
    for fichier in sorted(TESTS.glob("test_*.py")):
        arbre = _analyser(fichier)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ImportFrom) and noeud.module == "tests.navigateur":
                if any(a.name == "piloter" for a in noeud.names):
                    yield fichier
                    break


def test_tous_les_fichiers_qui_pilotent_sont_regroupes(pytestconfig):
    """Un fichier qui pilote et que le conftest ne reconnait pas coute un
    navigateur de plus, en silence.

    Le conftest reconnait un module au fait qu'il expose `piloter`. Un fichier
    qui importerait le harnais sous un autre nom (`from tests.navigateur import
    piloter as p`) passerait donc au travers : c'est ce qu'on refuse ici, en
    exigeant que le nom reste `piloter` dans le module.
    """
    import importlib

    manquants = []
    for fichier in _modules_qui_pilotent():
        module = importlib.import_module(f"tests.{fichier.stem}")
        if getattr(module, "piloter", None) is None:
            manquants.append(fichier.name)
    assert manquants == [], (
        f"{manquants} importe(nt) `piloter` mais ne l'expose(nt) pas sous ce "
        "nom : le regroupement de tests/conftest.py ne les reconnaitra pas, "
        "xdist les enverra sur un autre worker, et chacun y redemarrera un "
        "chromium. Garder le nom `piloter` dans le module, meme quand il n'est "
        "qu'un mince enrobage du harnais partage -- c'est ce que fait "
        "test_navigateur_fiche.py")


def test_le_garde_du_regroupement_regarde_bien_quelque_chose():
    fichiers = list(_modules_qui_pilotent())
    assert len(fichiers) >= 6, (
        "ce garde ne trouve plus que "
        f"{[f.name for f in fichiers]} : le harnais a change de forme, ou son "
        "import a change de tournure, et le regroupement n'est plus verifie")


def test_le_regroupement_arrive_bien_jusqu_a_xdist(request):
    """La marque `xdist_group` est-elle posee ASSEZ TOT pour que xdist la voie ?

    ⚠️ Le defaut que ce test ferme s'est produit, et **aucun autre garde ne le
    voyait**. `pytest-xdist` n'ecoute pas la marque au moment de repartir : il
    a deja encode le nom du groupe en suffixe de l'identifiant
    (`...::test_x@navigateur`) depuis son propre
    `pytest_collection_modifyitems`. Une marque posee apres le sien n'existe
    donc pas pour le repartiteur.

    Sans `tryfirst` sur le crochet de `tests/conftest.py`, les tests navigateur
    se retrouvaient repartis sur les quatorze workers -- **quinze processus
    chromium peres au lieu d'un**, mesures le 04/09. La suite restait VERTE :
    le garde des portees de fixtures ne regarde pas la repartition, et le seul
    symptome etait un temps qui ne baissait pas autant qu'annonce.

    Ce test lit ce que xdist a reellement retenu : son propre identifiant.
    """
    if not os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("suite en serie : il n'y a rien a repartir, donc rien a "
                    "verifier ici. Ce test travaille sous xdist, qui est le "
                    "mode par defaut (voir pytest.ini) et celui de la CI")
    assert request.node.nodeid.endswith("@" + GROUPE), (
        f"l'identifiant de ce test est {request.node.nodeid!r} : il ne porte "
        f"pas le suffixe « @{GROUPE} ». La marque xdist_group posee par "
        "tests/conftest.py arrive donc APRES que xdist a fige les "
        "identifiants, et le regroupement est sans effet -- chaque worker "
        "demarrera son propre chromium. La cause est presque toujours le "
        "`@pytest.hookimpl(tryfirst=True)` du crochet, retire ou dépassé par "
        "un autre greffon qui se declare plus tot encore")


def test_le_test_qui_chauffe_existe_bien():
    """`tests/conftest.py` place un test nomme en tete du groupe navigateur.

    S'il etait renomme ou supprime, le placement deviendrait un `for` qui ne
    trouve rien : silencieux, et le demarrage a froid retomberait sur le
    premier test venu -- exactement le defaut qu'on vient de retirer.
    """
    assert DEMARRE_LE_NAVIGATEUR in globals(), (
        f"« {DEMARRE_LE_NAVIGATEUR} » n'existe plus dans ce fichier, alors que "
        "tests/conftest.py le cherche pour le mettre en tete du groupe "
        "navigateur")


@pytest.mark.budget(45)
def test_le_plafond_declare_arrive_jusqu_au_verdict(request):
    """`@pytest.mark.budget(n)` doit atteindre le processus qui rend le verdict.

    ⚠️ Il ne peut pas passer par la collecte. Sous `pytest-xdist`, ce sont les
    WORKERS qui collectent, et le processus qui additionne les durees ne
    collecte rien : une table remplie a la collecte reste vide la ou on la lit.
    Le 04/09, le garde accusait donc en parallele un test qui avait pourtant
    declare son plafond -- et il le faisait en SILENCE, puisque le message
    etait exactement le meme que pour un test fautif.

    `tests/conftest.py` pose la valeur dans `user_properties`, le seul canal
    serialise avec le rapport. Ce test verifie ce geste-la ; le reste du
    chemin appartient a pytest.
    """
    poses = [v for c, v in request.node.user_properties if c == "budget"]
    assert poses == [45.0], (
        f"ce test declare `@pytest.mark.budget(45)` mais ses user_properties "
        f"portent {poses!r} : le plafond ne traversera pas jusqu'au verdict, "
        "et le garde de budget accusera des tests qui ont dit leur prix. Voir "
        "`pytest_runtest_setup` dans tests/conftest.py")
