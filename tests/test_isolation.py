"""L'application est partagee : ce qui doit rester NEUF a chaque test.

Depuis le 04/09, `tests/conftest.py` ne rebatit plus une application Flask par
test. Elle coutait 11,8 ms -- mille deux cents fois, soit **14 s** -- et
l'essentiel de ce temps etait la recompilation, par Werkzeug, de soixante-sept
regles de routage identiques. Rien dans une suite de tests n'en depend.

Ce qui doit vraiment etre neuf, c'est l'ETAT. Trois choses le sont, et chacune
a son test ici :

    la base            `drop_all` + `create_all` avant chaque test
    la configuration   reposee depuis un instantane pris au demarrage
    la classe de client remise a `None`, donc au defaut de Flask

⚠️ **Pourquoi ces tests plutot qu'une relecture du conftest.** Une isolation qui
se casse ne fait pas echouer la suite : elle la fait passer POUR DE MAUVAISES
RAISONS. Un test verrait les donnees de son voisin, ou sa configuration, et
continuerait a etre vert. C'est le seul mode de defaillance qu'on ne peut pas
attraper en regardant la couleur -- il faut donc des tests qui le regardent
exprès, et qui echouent, eux, si le nettoyage saute.

Le pendant est dans `tests/conftest.py` : un garde de sortie qui refuse qu'un
test ajoute une route ou un crochet a l'application partagee.

⚠️ **Aucun de ces tests ne depend de l'ordre**, et ce n'est pas un luxe. La
premiere version salissait dans un test et verifiait dans le suivant. Lance
avec `pytest-randomly`, l'ordre s'est inverse : les six tests sont passes en
verifiant AVANT que quiconque ait sali -- ils ne prouvaient plus rien, et ils
etaient verts. Exactement le mode de defaillance que ce fichier existe pour
attraper, retourne contre lui.

Chaque test VERIFIE d'abord, puis SALIT. Dans n'importe quel ordre, tous sauf
le premier constatent donc l'etat laisse par un autre. On en met trois par
dimension : deux verifications reelles au minimum, quelle que soit la
permutation.
"""
from datetime import date

import pytest

from climbcontest.extensions import db
from climbcontest.models import EN_COURS, Competition, Utilisateur


def _salir_la_base(marque: str) -> None:
    db.session.add(Competition(nom=marque, date=date(2026, 11, 15),
                               statut=EN_COURS, active=True))
    db.session.add(Utilisateur(identifiant=marque.lower(),
                               mot_de_passe_hache="x", actif=True))
    db.session.commit()


class TestLaBaseEstNeuveAChaqueTest:
    @pytest.mark.parametrize("marque", ["Salissure1", "Salissure2", "Salissure3"])
    def test_la_base_ne_porte_rien_du_test_precedent(self, app, marque):
        assert Competition.query.count() == 0, (
            "une competition ecrite par un autre test est encore la : la base "
            "n'est plus remise a neuf entre deux tests, et TOUTE la suite peut "
            "desormais passer sur les donnees du voisin")
        assert Utilisateur.query.count() == 0, (
            "un compte ecrit par un autre test est encore la -- meme cause, et "
            "le freinage des connexions (spec 015) garde son etat en base, "
            "donc il fuirait lui aussi")
        _salir_la_base(marque)


class TestLaConfigurationEstNeuveAChaqueTest:
    @pytest.mark.parametrize("marque", ["cle1", "cle2", "cle3"])
    def test_la_configuration_repart_du_defaut(self, app, marque):
        assert app.config["SECRET_KEY"] == "dev-non-secret", (
            "une SECRET_KEY posee par un autre test a survecu : cent neuf "
            "endroits de la suite modifient la configuration, et ils se "
            "verraient tous entre eux")
        assert app.config["API_KEY_STRICTE"] is True
        assert "UN_REGLAGE_QUI_N_EXISTE_PAS" not in app.config, (
            "une cle AJOUTEE par un autre test survit : reposer les valeurs "
            "connues ne suffit pas, il faut vider la configuration d'abord")

        app.config["SECRET_KEY"] = marque
        app.config["API_KEY_STRICTE"] = False
        app.config["UN_REGLAGE_QUI_N_EXISTE_PAS"] = 42


class TestLaClasseDeClientEstNeuveAChaqueTest:
    """`client` et `client_sans_cle` posent chacun LEUR classe sur
    l'application, pas sur eux-memes.

    Sans remise a zero, un test qui appelle `app.test_client()` directement
    heriterait de celle choisie par un autre -- donc porterait la cle d'API
    sans le savoir, ou ne la porterait plus. Les deux se lisent comme un
    controle d'acces casse.
    """

    @pytest.mark.parametrize("_", [1, 2, 3])
    def test_le_client_nu_ne_porte_aucune_cle(self, app, _):
        reponse = app.test_client().get("/api/v2/catalog")
        assert reponse.status_code == 401, (
            f"le client nu a repondu {reponse.status_code} au lieu de 401 : il "
            "porte une cle d'API, donc il a herite de la classe de client "
            "posee par un autre test")

        # Puis on salit, pour que les autres tests aient quelque chose a
        # constater -- quel que soit l'ordre dans lequel ils passent.
        app.test_client_class = _ClientQuiPorteUneCle


class _ClientQuiPorteUneCle(__import__("flask").testing.FlaskClient):
    """La meme idee que `ClientAvecCle` du conftest, en plus court."""

    def open(self, *args, **kwargs):
        from werkzeug.datastructures import Headers
        entetes = Headers(kwargs.get("headers") or {})
        entetes.setdefault("X-Api-Key", "cle-de-test")
        kwargs["headers"] = entetes
        return super().open(*args, **kwargs)
