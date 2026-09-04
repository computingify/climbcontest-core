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

⚠️ **L'ordre compte dans chaque classe** : le premier test salit, le second
verifie. Les noms portent la lettre pour que ca reste vrai si quelqu'un les
relit, et pytest joue les tests d'un fichier dans l'ordre ou ils sont ecrits.
"""
from datetime import date

from climbcontest.extensions import db
from climbcontest.models import EN_COURS, Competition, Utilisateur


class TestLaBaseEstNeuveAChaqueTest:
    def test_a_j_ecris_une_competition_et_un_compte(self, app):
        db.session.add(Competition(nom="Salissure", date=date(2026, 11, 15),
                                   statut=EN_COURS, active=True))
        db.session.add(Utilisateur(identifiant="salisseur",
                                   mot_de_passe_hache="x", actif=True))
        db.session.commit()
        assert Competition.query.count() == 1
        assert Utilisateur.query.count() == 1

    def test_b_le_test_suivant_ne_voit_rien(self, app):
        assert Competition.query.count() == 0, (
            "la competition ecrite par le test precedent est encore la : la "
            "base n'est plus remise a neuf entre deux tests, et TOUTE la suite "
            "peut desormais passer sur les donnees du voisin")
        assert Utilisateur.query.count() == 0, (
            "le compte du test precedent est encore la -- meme cause, et le "
            "freinage des connexions (spec 015) garde son etat en base, donc "
            "il fuirait lui aussi")


class TestLaConfigurationEstNeuveAChaqueTest:
    def test_a_je_change_la_configuration(self, app):
        app.config["SECRET_KEY"] = "une-cle-de-salissure"
        app.config["API_KEY_STRICTE"] = False
        app.config["UN_REGLAGE_QUI_N_EXISTE_PAS"] = 42

    def test_b_le_test_suivant_repart_du_defaut(self, app):
        assert app.config["SECRET_KEY"] == "dev-non-secret", (
            "la SECRET_KEY posee par le test precedent a survecu : cent neuf "
            "endroits de la suite modifient la configuration, et ils se "
            "verraient tous entre eux")
        assert app.config["API_KEY_STRICTE"] is True
        assert "UN_REGLAGE_QUI_N_EXISTE_PAS" not in app.config, (
            "une cle AJOUTEE par un test survit : reposer les valeurs connues "
            "ne suffit pas, il faut vider la configuration d'abord")


class TestLaClasseDeClientEstNeuveAChaqueTest:
    """`client` et `client_sans_cle` posent chacun la leur sur l'application.

    Sans remise a zero, un test qui appelle `app.test_client()` directement
    heriterait de celle choisie par son voisin -- donc porterait la cle d'API
    sans le savoir, ou ne la porterait plus. Les deux se lisent comme un
    controle d'acces casse.
    """

    def test_a_je_prends_le_client_qui_porte_la_cle(self, client):
        """`client` pose `ClientAvecCle` SUR L'APPLICATION, pas sur lui-meme.

        On ne regarde que la cle : 409 « aucune competition active » veut dire
        que la requete est PASSEE l'authentification, ce qui est tout ce qu'on
        demande ici.
        """
        assert client.get("/api/v2/catalog").status_code != 401

    def test_b_le_client_nu_ne_porte_aucune_cle(self, app):
        reponse = app.test_client().get("/api/v2/catalog")
        assert reponse.status_code == 401, (
            "le client nu a repondu autre chose que 401 : il porte une cle "
            "d'API, donc il a herite de la classe de client posee par un test "
            "precedent")
