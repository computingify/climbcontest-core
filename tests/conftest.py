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


@pytest.fixture()
def app():
    app = creer_app(ConfigTest)
    with app.app_context():
        yield app
        db.session.remove()


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


def pytest_runtest_logreport(report):
    """On somme les trois phases : une attente logee dans une fixture compte."""
    _duree_par_test[report.nodeid] = (
        _duree_par_test.get(report.nodeid, 0.0) + report.duration)


def _hors_budget():
    return sorted(((n, d) for n, d in _duree_par_test.items() if d > BUDGET_S),
                  key=lambda paire: -paire[1])


def pytest_terminal_summary(terminalreporter):
    trop_lents = _hors_budget()
    if not trop_lents:
        return
    terminalreporter.section("des tests attendent quelque chose", red=True)
    for nodeid, duree in trop_lents:
        terminalreporter.line(f"{duree:6.1f} s  {nodeid}")
    terminalreporter.line(
        f"\nBudget : {BUDGET_S:.0f} s par test, fixtures comprises. Au-dela, un "
        "test n'est pas lent : il attend. Une minuterie, un delai reseau, un "
        "sleep. Rendre l'attente REGLABLE plutot que la subir -- c'est ce que "
        "font `?periode=` et CLIMBCONTEST_ATTENTE_VERROU_S. Si l'attente est "
        "vraiment incompressible, CLIMBCONTEST_BUDGET_TEST_S releve le "
        "plafond, et le commit dit pourquoi.")


def pytest_sessionfinish(session, exitstatus):
    if _hors_budget() and session.exitstatus == 0:
        session.exitstatus = 1
