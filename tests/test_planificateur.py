"""Le fil du miroir — la partie que rien ne testait (34 % avant l'audit).

Trois promesses, et chacune a son test :

1. il ne se plaint qu'une fois par cause, puis dit « ça repart » ;
2. il ne meurt JAMAIS, même sur une exception imprévue ;
3. sa dernière plainte est lisible de l'extérieur — c'est ce qui a manqué le
   30/08, quand il a fallu un SSH pour comprendre 714 réussites en attente.
"""
import threading
import time
from unittest import mock

import pytest

from climbcontest import creer_app
from climbcontest.config import ConfigTest
from climbcontest.sheets import planificateur


@pytest.fixture()
def app():
    application = creer_app(ConfigTest)
    yield application
    # Chaque test repart d'une memoire d'erreur vierge.
    planificateur._derniere_erreur = None


def _tourner(app, resultats, tours=None, exceptions=None):
    """Fait tourner la boucle sur des résultats joués d'avance, sans attendre.

    `wait(periode)` est remplacé par un compteur : la boucle « dort » sans
    dormir, et s'arrête quand le scénario est épuisé.
    """
    tours = tours if tours is not None else len(resultats)
    arret = threading.Event()
    app.extensions["climbcontest_arret"] = arret
    compteur = {"n": 0}
    vrai_wait = arret.wait

    def wait_sans_attendre(_periode):
        if compteur["n"] >= tours:
            return True          # scenario epuise : on demande l'arret
        compteur["n"] += 1
        return False

    sequence = list(resultats)

    def synchroniser_joue(taille_lot):
        r = sequence.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    with mock.patch.object(arret, "wait", wait_sans_attendre), \
         mock.patch.object(planificateur, "synchroniser", synchroniser_joue):
        planificateur._boucle(app, periode=40, taille_lot=50)


def _resultat(envoyees=0, restantes=0, erreur=None):
    return {"envoyees": envoyees, "restantes": restantes,
            "erreur": erreur, "ignoree": False}


class TestPlaintes:
    def test_la_meme_cause_ne_se_plaint_qu_une_fois(self, app, caplog):
        with caplog.at_level("WARNING"):
            _tourner(app, [
                _resultat(erreur="aucun classeur relie", restantes=3),
                _resultat(erreur="aucun classeur relie", restantes=3),
                _resultat(erreur="aucun classeur relie", restantes=3),
            ])
        plaintes = [r for r in caplog.records if "aucun classeur" in r.message]
        assert len(plaintes) == 1

    def test_une_cause_nouvelle_se_plaint_a_nouveau(self, app, caplog):
        with caplog.at_level("WARNING"):
            _tourner(app, [
                _resultat(erreur="aucun classeur relie", restantes=3),
                _resultat(erreur="jeton Google absent", restantes=3),
            ])
        assert sum("miroir" in r.message for r in caplog.records
                   if r.levelname == "WARNING") == 2

    def test_ca_repart_quand_l_envoi_reprend(self, app, caplog):
        with caplog.at_level("INFO"):
            _tourner(app, [
                _resultat(erreur="reseau coupe", restantes=5),
                _resultat(envoyees=5, restantes=0),
            ])
        assert any("ca repart" in r.message for r in caplog.records)


class TestSurvie:
    def test_une_exception_imprevue_ne_tue_pas_le_fil(self, app, caplog):
        # Si la boucle mourait, le second resultat ne serait jamais consomme
        # et la sequence ressortirait non vide.
        with caplog.at_level("ERROR"):
            _tourner(app, [
                RuntimeError("imprevu"),
                _resultat(envoyees=2, restantes=0),
            ])
        assert any("on continue" in r.message for r in caplog.records)


class TestDerniereErreur:
    def test_l_erreur_est_lisible_de_l_exterieur(self, app):
        _tourner(app, [_resultat(erreur="aucun classeur relie", restantes=714)])
        assert planificateur.derniere_erreur() == "aucun classeur relie"

    def test_elle_s_efface_quand_ca_repart(self, app):
        _tourner(app, [
            _resultat(erreur="reseau coupe", restantes=5),
            _resultat(envoyees=5, restantes=0),
        ])
        assert planificateur.derniere_erreur() is None

    def test_health_l_expose(self, app):
        planificateur._derniere_erreur = "aucun classeur relie a cette competition"
        with app.test_client() as c:
            d = c.get("/health").get_json()
        assert d["miroir_derniere_erreur"] == "aucun classeur relie a cette competition"

    def test_health_dit_null_quand_tout_va_bien(self, app):
        with app.test_client() as c:
            d = c.get("/health").get_json()
        assert d["miroir_derniere_erreur"] is None
