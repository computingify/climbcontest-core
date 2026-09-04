"""Fixtures de test. Base en memoire, aucun acces reseau."""
import os
from datetime import date

import pytest
from flask.testing import FlaskClient
from werkzeug.datastructures import Headers

os.environ["CLIMBCONTEST_TEST"] = "1"

from climbcontest import creer_app                       # noqa: E402
from climbcontest.config import ConfigTest               # noqa: E402
from climbcontest.extensions import db                   # noqa: E402
from climbcontest.models import (                        # noqa: E402
    Bloc, BlocCircuit, Circuit, Competition, EN_COURS, Participant,
)


@pytest.fixture(autouse=True)
def _cache_propre():
    """Le cache de classement est un global de module : sans ce nettoyage, un
    test verrait le classement calcule par le precedent."""
    from climbcontest import classement_service
    classement_service.invalider()
    yield
    classement_service.invalider()


# --- L'application, construite une fois -------------------------------------
#
# ⚠️ Elle etait rebatie a CHAQUE test : 11,8 ms, mille deux cents fois, soit
# **14 s** -- et le travail refait n'etait meme pas le notre. Werkzeug compile
# les soixante-sept regles de routage a la construction (une expression
# reguliere et une fonction generee par regle), ce qui pese 78 % du temps de
# `creer_app`. Rien, dans une suite de tests, ne depend du fait que ces regles
# soient recompilees.
#
# Ce qui doit VRAIMENT etre neuf a chaque test, c'est l'etat : la base et la
# configuration. Les deux sont remis a zero ci-dessous, et un garde verifie que
# rien d'autre n'a bouge.


def _empreinte(app) -> tuple:
    """Ce qui ne doit PAS changer d'un test a l'autre.

    Le partage d'une application est sur tant que les tests n'y ajoutent rien.
    Aucun ne le fait aujourd'hui -- les fichiers qui greffent une route de
    harnais (`/__verdict`, `/__harnais`) construisent leur PROPRE application,
    et c'est ce qu'il faut continuer a faire. Mais « aujourd'hui » n'est pas une
    garantie : une route ajoutee a l'application partagee survivrait au test qui
    l'a posee et repondrait dans tous les suivants, sans que rien ne le dise.
    """
    # ⚠️ On compte les gestionnaires d'erreur ENREGISTRES, pas les cases du
    # dictionnaire qui les range. `error_handler_spec` est un `defaultdict`
    # imbrique : Flask y cree des cases vides rien qu'en TRAITANT une erreur.
    # Le compter naivement faisait echouer ce garde sur 419 tests qui n'avaient
    # rien fait de mal -- ils avaient seulement provoque un 404.
    gestionnaires = sum(
        len(par_code) for par_blueprint in app.error_handler_spec.values()
        for par_code in par_blueprint.values())
    return (
        len(app.url_map._rules),
        {p: len(f) for p, f in app.before_request_funcs.items()},
        {p: len(f) for p, f in app.after_request_funcs.items()},
        gestionnaires,
    )


@pytest.fixture(scope="session")
def _application():
    app = creer_app(ConfigTest)
    return app, dict(app.config), _empreinte(app)


@pytest.fixture()
def app(_application):
    """Une base neuve et une configuration neuve, sur une application partagee.

    La configuration est REPOSEE avant le test plutot que nettoyee apres : un
    test qui la modifie -- et cent neuf endroits le font, `SECRET_KEY` en tete
    -- n'affecte alors que lui-meme, meme s'il echoue en cours de route.
    """
    app, config_neuve, empreinte = _application

    app.config.clear()
    app.config.update(config_neuve)
    # `client` et `client_sans_cle` la posent chacun ; on repart du defaut pour
    # qu'un test qui appelle `app.test_client()` directement ne herite pas de
    # la classe choisie par son voisin.
    app.test_client_class = None

    with app.app_context():
        # ⚠️ Les tables du SCHEMA (`verrou`, migrations jouees) sont creees en
        # SQL brut par `preparer_schema` et ne sont pas dans les metadonnees
        # SQLAlchemy : `drop_all` ne les touche pas, et c'est voulu -- elles
        # survivent aussi a un redemarrage en production.
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()

    assert _empreinte(app) == empreinte, (
        "ce test a modifie l'application elle-meme -- une route, un crochet "
        "`before_request` ou un gestionnaire d'erreur -- et l'application est "
        "PARTAGEE par toute la session : l'ajout repondrait dans tous les "
        "tests suivants. Construire une application a soi avec "
        "`creer_app(...)`, comme le font les fichiers de harnais navigateur")


CLE_DE_TEST = "cle-de-test"


class ClientAvecCle(FlaskClient):
    """Un client qui porte la cle d'API, comme l'application des juges.

    Depuis la spec 012, le regime par defaut est STRICT : une requete sans cle
    est refusee. Les tests doivent donc s'executer dans le meme regime que la
    production -- sinon ils prouveraient que les routes marchent dans une
    configuration que personne ne fait tourner.

    La bascule a fait tomber 107 tests d'un coup. Ils ne testaient pas la cle :
    ils passaient simplement parce que l'API etait ouverte.

    Un test qui veut verifier le refus prend [client_sans_cle].
    """

    def open(self, *args, **kwargs):
        entetes = Headers(kwargs.get("headers") or {})
        if "X-Api-Key" not in entetes:
            entetes["X-Api-Key"] = CLE_DE_TEST
        kwargs["headers"] = entetes
        return super().open(*args, **kwargs)


@pytest.fixture()
def hachage_reel(app):
    """Rend a CETTE application la vraie derivation de production.

    `ConfigTest` hache en `pbkdf2:sha256:1` -- une derivation quasi gratuite,
    parce que la suite fait plusieurs centaines de connexions et qu'aucune ne
    verifie la solidite du hachage (voir `comptes.METHODE_HACHAGE`).

    ⚠️ Les rares tests dont le COUT est justement le sujet -- l'egalisation du
    temps de reponse entre un compte connu et un inconnu -- ne peuvent pas se
    contenter de ca : mesurer un rapport entre deux durees de quelques dizaines
    de MICROsecondes, c'est mesurer le bruit de l'horloge. Ils redemandent la
    vraie methode ici, et sont seuls a la payer.
    """
    from climbcontest import comptes
    app.config["HACHAGE_MOT_DE_PASSE"] = comptes.METHODE_HACHAGE
    # Le hachage a vide est mis en cache PAR METHODE : celui de scrypt n'a
    # peut-etre jamais ete calcule dans ce processus, et son calcul tomberait
    # alors dans la premiere mesure du test. On le paie ici.
    comptes._hachage_factice()
    return app


@pytest.fixture()
def client(app):
    app.test_client_class = ClientAvecCle
    return app.test_client()


@pytest.fixture()
def client_sans_cle(app):
    """Le client brut, sans cle : pour verifier qu'une route est bien fermee."""
    app.test_client_class = FlaskClient
    return app.test_client()


@pytest.fixture()
def competition(app):
    c = Competition(nom="Test 2026", date=date(2026, 11, 15),
                    statut=EN_COURS, active=True, spreadsheet_id="fictif")
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture()
def jeu(app, competition):
    """Une compétition minimale : 2 circuits, 3 blocs, 3 participants.

    Volontairement petite et lisible : chaque test doit pouvoir dire de tete ce
    qui est attendu.
    """
    u11 = Circuit(competition_id=competition.id, nom="U11")
    u13 = Circuit(competition_id=competition.id, nom="U13")
    db.session.add_all([u11, u13])
    db.session.flush()

    blocs = []
    for i, (tag, couleur, circuits) in enumerate(
        [("ZJ6", "Jaune", [u11, u13]), ("ZJ7", "Vert", [u11]), ("DV21", "Bleu", [u13])], 1
    ):
        b = Bloc(competition_id=competition.id, tag=tag, numero=i,
                 zone=tag[0], couleur=couleur)
        db.session.add(b)
        db.session.flush()
        for c in circuits:
            db.session.add(BlocCircuit(bloc_id=b.id, circuit_id=c.id))
        blocs.append(b)

    participants = [
        Participant(competition_id=competition.id, nom="Dupont", prenom="Lea",
                    club="Les Lezards", categorie="U11 F", dossard=1, present=True),
        Participant(competition_id=competition.id, nom="Martin", prenom="Tom",
                    club="La Grimpe", categorie="U13 H", dossard=2, present=True),
        # Inscrit qui n'est pas venu : pas de dossard. C'est le cas qui justifie
        # que l'identite soit l'id et non le dossard.
        Participant(competition_id=competition.id, nom="Absent", prenom="Paul",
                    categorie="U11 H", dossard=None),
    ]
    db.session.add_all(participants)
    db.session.commit()
    return {"competition": competition, "blocs": blocs,
            "participants": participants, "circuits": [u11, u13]}


# --- Le budget de temps d'un test -------------------------------------------
#
# Le job `tests` virait au rouge par intermittence, et toujours de la meme
# facon : un test qui ATTEND une horloge -- le battement de 15 s de la page de
# resultats, l'attente d'un verrou de schema, une seconde entiere pour changer
# d'horodatage. Une attente passe en local et casse sur un runner charge, ou
# elle devient une seconde de trop ; et elle ne se signale jamais elle-meme.
#
# Elles ont ete retirees une par une. Ce garde-fou existe pour qu'elles ne
# reviennent pas en douce : un test qui depasse le budget fait echouer la suite
# en NOMMANT le coupable, au lieu de la ralentir jusqu'a ce que quelqu'un s'en
# apercoive.
#
# Le plafond est large. Le plus lent tient aujourd'hui en 7,5 s, dont 5 s que
# gunicorn passe a renoncer sur un port deja pris. Il n'attrape pas la lenteur,
# il attrape l'attente.
BUDGET_S = float(os.environ.get("CLIMBCONTEST_BUDGET_TEST_S", "20"))

_duree_par_test: dict[str, float] = {}

# Les rares tests qui declarent LEUR plafond, par `@pytest.mark.budget(n)`.
#
# ⚠️ Une exception nommee, et pas un plafond global releve. Passer BUDGET_S a
# 45 s pour un seul test aveuglerait le garde sur les mille huit cent
# soixante-onze autres, et personne ne le remarquerait. Ici l'exception se lit
# dans le fichier ou elle s'applique, avec sa raison a cote, et elle a elle
# aussi un plafond.
_budget_par_test: dict[str, float] = {}


def pytest_runtest_setup(item):
    """Fait voyager le plafond declare AVEC le test.

    ⚠️ Il ne peut pas passer par la collecte. Sous `pytest-xdist`, ce sont les
    WORKERS qui collectent ; le processus qui additionne les durees et rend le
    verdict, lui, ne collecte rien. Une table remplie a la collecte reste donc
    vide la ou on la lit, et le plafond declare n'existe pas -- constate le
    04/09 : le garde accusait en parallele un test qui avait pourtant dit son
    prix, et il le faisait en silence, puisque le message etait le meme.

    `user_properties` est serialise avec le rapport : c'est le seul canal qui
    traverse la frontiere.
    """
    marque = item.get_closest_marker("budget")
    if marque is not None:
        item.user_properties.append(("budget", float(marque.args[0])))


def pytest_runtest_logreport(report):
    """On somme les trois phases : une attente logee dans une fixture compte."""
    _duree_par_test[report.nodeid] = (
        _duree_par_test.get(report.nodeid, 0.0) + report.duration)
    for cle, valeur in getattr(report, "user_properties", ()):
        if cle == "budget":
            _budget_par_test[report.nodeid] = float(valeur)


def _plafond(nodeid: str) -> float:
    return _budget_par_test.get(nodeid, BUDGET_S)


def _hors_budget():
    return sorted(((n, d) for n, d in _duree_par_test.items()
                   if d > _plafond(n)),
                  key=lambda paire: -paire[1])


def pytest_terminal_summary(terminalreporter):
    trop_lents = _hors_budget()
    if not trop_lents:
        return
    terminalreporter.section("des tests attendent quelque chose", red=True)
    for nodeid, duree in trop_lents:
        terminalreporter.line(
            f"{duree:6.1f} s  (plafond {_plafond(nodeid):.0f} s)  {nodeid}")
    terminalreporter.line(
        f"\nBudget : {BUDGET_S:.0f} s par test, fixtures comprises. Au-dela, un "
        "test n'est pas lent : il attend. Une minuterie, un delai reseau, un "
        "sleep. Rendre l'attente REGLABLE plutot que la subir -- c'est ce que "
        "font `?periode=` et CLIMBCONTEST_ATTENTE_VERROU_S. Si l'attente est "
        "vraiment incompressible et propre a UN test, "
        "`@pytest.mark.budget(secondes)` lui donne son plafond -- avec sa "
        "raison a cote, dans le fichier ou on la lira. "
        "CLIMBCONTEST_BUDGET_TEST_S, lui, deplace le plafond de TOUS les "
        "tests : c'est presque toujours le mauvais geste.")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "budget(secondes): le plafond de CE test, quand son cout est reel et "
        "incompressible -- un demarrage de navigateur a froid, par exemple. "
        "La raison s'ecrit dans le test, pas ici.")


def pytest_sessionfinish(session, exitstatus):
    if _hors_budget() and session.exitstatus == 0:
        session.exitstatus = 1


# --- Le navigateur, et un seul ----------------------------------------------
#
# Les fichiers qui pilotent un vrai chromium. `piloter` ne demarre plus un
# processus par parcours : il ouvre un CONTEXTE isole dans un navigateur deja
# la (voir `tests/navigateur.py`). Encore faut-il que tous ces tests tournent
# dans le MEME processus pytest -- sinon `pytest-xdist` les eparpille sur dix
# workers, et on repaie dix demarrages pour n'en economiser qu'un.
#
# ⚠️ Le regroupement est verifie par `tests/test_harnais_navigateur.py`, a deux
# endroits : qu'aucun fichier n'y echappe, et que la marque arrive bien jusqu'a
# xdist. Sans ces gardes, un septieme fichier arriverait un jour, serait
# distribue ailleurs, et personne ne verrait le demarrage supplementaire --
# exactement le defaut qui s'est deja produit deux fois sous une autre forme.
from tests import navigateur as _navigateur                  # noqa: E402
from tests.navigateur import GROUPE as GROUPE_NAVIGATEUR    # noqa: E402


def _pilote_un_navigateur(item) -> bool:
    """Le module de ce test expose-t-il `piloter` ?

    On le lit sur le MODULE plutot que sur un nom de fichier : un fichier qui
    ne s'appelle pas `test_navigateur_*` mais qui pilote quand meme --
    `test_coherence_console_ecran.py` est dans ce cas -- doit etre regroupe lui
    aussi. C'est le fait de piloter qui compte, pas le nom.
    """
    module = getattr(item, "module", None)
    return module is not None and getattr(module, "piloter", None) is not None


# ⚠️ `tryfirst` n'est PAS decoratif. `pytest-xdist` encode le nom du groupe
# dans l'identifiant du test (`...py::test_x@navigateur`) depuis SON propre
# `pytest_collection_modifyitems`, et c'est ce suffixe -- pas la marque -- que
# lit le repartiteur. Une marque posee APRES lui n'est donc jamais vue : les
# tests navigateur se retrouvaient repartis sur les quatorze workers, chacun
# demarrant son chromium. Constate le 04/09 : quinze processus peres au lieu
# d'un, et le garde de portee des fixtures, lui, restait vert -- il ne regarde
# pas la repartition. C'est `test_harnais_navigateur.py` qui ferme ce trou-la.
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    """Regroupe les tests navigateur, puis chauffe le navigateur en fond.

    **Le regroupement.** `--dist loadgroup` envoie sur un MEME worker tous les
    tests portant la meme marque `xdist_group`. On la pose ici plutot que dans
    chaque fichier : un fichier navigateur de plus n'a rien a declarer, et le
    regroupement ne peut pas etre oublie.

    **La chauffe.** Elle ne part que si la selection contient VRAIMENT un test
    navigateur : `pytest tests/test_modele.py` ne doit lancer aucun chromium.
    C'est la liste `pilotes` qui le dit -- et non plus la presence de
    `tests.navigateur` dans `sys.modules`, qui etait vraie des que ce conftest
    lui-meme importait le harnais.

    En fond, et sans jamais attendre le resultat : la chauffe tourne pendant
    les quinze cents tests qui n'ont pas besoin de navigateur. Elle demarre
    desormais le navigateur DE TRAVAIL, pas un chromium jetable -- voir
    `tests.navigateur.chauffer`.
    """
    import threading

    if _navigateur.CHROME is None:
        return                  # pas de navigateur : les tests se sautent seuls

    pilotes = [i for i in items if _pilote_un_navigateur(i)]
    for item in pilotes:
        item.add_marker(pytest.mark.xdist_group(GROUPE_NAVIGATEUR))

    # ⚠️ Le demarrage a froid de chromium coute 17,1 s sur un runner GitHub, et
    # il est paye par le PREMIER test navigateur -- qui, par ordre
    # alphabetique, n'a rien demande. On met donc en tete celui dont c'est le
    # sujet : `test_le_navigateur_demarre_et_repond`. Les autres trouvent un
    # navigateur chaud.
    #
    # Le placement porte sur l'ordre de `items`, que le repartiteur respecte a
    # l'interieur d'un groupe. `tests/test_harnais_navigateur.py` verifie que
    # le test cherche existe toujours : sans lui, ce `next` ne trouverait rien,
    # en silence.
    chauffeur = next((i for i in pilotes
                      if i.name == "test_le_navigateur_demarre_et_repond"), None)
    if chauffeur is not None and pilotes[0] is not chauffeur:
        items.remove(chauffeur)
        items.insert(items.index(pilotes[0]), chauffeur)

    if not pilotes:
        return

    # ⚠️ Sous xdist, chaque WORKER collecte TOUTE la suite avant qu'on lui donne
    # sa part : chauffer ici lancerait un chromium par worker -- quatorze, dont
    # treize pour rien. Mesure du 04/09, avant de s'en apercevoir : quinze
    # processus chromium peres en pleine execution, la ou on en voulait UN.
    if hasattr(config, "workerinput"):
        return                  # le worker du groupe demarrera le sien, seul

    # ⚠️ En PARALLELE, on ne chauffe pas -- et c'est un revirement, mesure en CI.
    #
    # L'idee etait que le processus coordinateur rechauffe le cache disque
    # pendant que les workers travaillent. Sur un runner a quatre coeurs, il
    # fait surtout autre chose : il lance un SECOND chromium a froid, en meme
    # temps que celui du worker qui a herite du groupe. Deux demarrages a froid
    # qui se disputent la machine coutent plus cher qu'un seul.
    #
    # Le premier test navigateur paie donc le demarrage, une fois. C'est
    # exactement ce que la chauffe evitait AVANT le parallelisme -- mais alors,
    # le processus qui chauffait etait celui qui allait s'en servir. Sous
    # xdist, il ne l'est plus, et la chauffe ne s'amortit sur rien.
    #
    # Le cout, lui, ne se cache plus : `_signaler_si_lent` compte desormais le
    # demarrage a part et le NOMME dans son avertissement.
    if config.getoption("numprocesses", None):
        return

    # En serie, le processus qui chauffe est celui qui jouera les tests : la
    # chauffe tourne pendant les mille huit cents tests qui n'ont pas besoin de
    # navigateur, et plus personne ne paie le demarrage.
    threading.Thread(target=_navigateur.chauffer, daemon=True).start()

