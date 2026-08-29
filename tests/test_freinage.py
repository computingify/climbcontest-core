"""Frein anti-force-brute sur la connexion (spec 005).

Depuis que `/admin` est joignable depuis Internet -- decision du 29/08, parce
que les organisateurs sont au gymnase et la VM a la maison -- l'authentification
par session est la seule barriere. Elle est solide, mais rien n'empechait un
robot d'essayer des mots de passe en boucle.
"""
from datetime import datetime, timedelta

import pytest

from climbcontest import comptes, freinage
from climbcontest.extensions import db
from climbcontest.models import TentativeConnexion

MDP = "un-mot-de-passe-assez-long"
IP = "203.0.113.7"


@pytest.fixture()
def secret(app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    return app


@pytest.fixture()
def compte(secret):
    return comptes.creer("orga", MDP, [comptes.ORGANISATEUR])


def essayer(client, mot_de_passe="mauvais-mot-de-passe", adresse=IP):
    return client.post("/admin/connexion",
                       json={"identifiant": "orga", "mot_de_passe": mot_de_passe},
                       environ_base={"REMOTE_ADDR": adresse})


class TestTolerance:
    """Une faute de frappe ne doit rien couter."""

    def test_les_premiers_echecs_ne_freinent_pas(self, client, compte):
        for _ in range(freinage.TOLERANCE):
            assert essayer(client).status_code == 401, "401, pas 429"

    def test_le_frein_s_active_au_dela(self, client, compte):
        for _ in range(freinage.TOLERANCE + 1):
            essayer(client)
        r = essayer(client)
        assert r.status_code == 429
        assert "Reessaie dans" in r.get_json()["message"]

    def test_l_en_tete_retry_after_est_pose(self, client, compte):
        """Un client correct sait alors combien attendre, sans deviner."""
        for _ in range(freinage.TOLERANCE + 1):
            essayer(client)
        assert essayer(client).headers.get("Retry-After")


class TestProgression:

    def test_l_attente_double(self, app):
        def attente_pour(echecs):
            db.session.query(TentativeConnexion).delete()
            db.session.add(TentativeConnexion(adresse=IP, echecs=echecs,
                                              derniere=datetime.now()))
            db.session.commit()
            return freinage.attente_restante(IP).total_seconds()

        a = attente_pour(freinage.TOLERANCE + 1)
        b = attente_pour(freinage.TOLERANCE + 2)
        c = attente_pour(freinage.TOLERANCE + 3)
        assert a < b < c, f"{a} {b} {c}"
        assert b == pytest.approx(a * 2, rel=0.2)

    def test_l_attente_est_plafonnee(self, app):
        """Un organisateur qui se trompe le matin ne doit pas attendre une heure.

        Sans plafond, dix erreurs donneraient un delai qui depasse la duree de
        la competition -- et il faudrait aller debloquer quelqu'un a la main,
        exactement au pire moment.
        """
        db.session.add(TentativeConnexion(adresse=IP, echecs=40,
                                          derniere=datetime.now()))
        db.session.commit()
        assert freinage.attente_restante(IP) <= freinage.ATTENTE_MAX

    def test_l_attente_diminue_avec_le_temps(self, app):
        db.session.add(TentativeConnexion(
            adresse=IP, echecs=freinage.TOLERANCE + 2,
            derniere=datetime.now() - timedelta(seconds=3)))
        db.session.commit()
        restante = freinage.attente_restante(IP).total_seconds()
        assert 0 <= restante < 4, restante


class TestRemiseAZero:

    def test_une_connexion_reussie_efface_l_ardoise(self, client, compte):
        for _ in range(freinage.TOLERANCE):
            essayer(client)
        assert essayer(client, mot_de_passe=MDP).status_code == 200
        assert db.session.get(TentativeConnexion, IP) is None

    def test_et_on_peut_se_reconnecter_aussitot(self, client, compte):
        for _ in range(freinage.TOLERANCE):
            essayer(client)
        essayer(client, mot_de_passe=MDP)
        client.post("/admin/deconnexion")
        assert essayer(client, mot_de_passe=MDP).status_code == 200

    def test_l_ardoise_s_efface_apres_un_long_silence(self, app):
        """Une erreur du matin ne doit pas penaliser l'apres-midi."""
        db.session.add(TentativeConnexion(
            adresse=IP, echecs=20,
            derniere=datetime.now() - freinage.OUBLI - timedelta(minutes=1)))
        db.session.commit()
        assert freinage.attente_restante(IP) == timedelta(0)


class TestPortee:

    def test_le_frein_est_par_adresse(self, client, compte):
        """Un robot sur une adresse ne doit pas bloquer l'organisateur sur une
        autre -- sinon le frein deviendrait lui-meme l'arme."""
        for _ in range(freinage.TOLERANCE + 3):
            essayer(client, adresse="198.51.100.1")
        assert essayer(client, mot_de_passe=MDP, adresse="203.0.113.9").status_code == 200

    def test_il_n_est_PAS_par_identifiant(self, client, compte):
        """Compter par identifiant offrirait a n'importe qui le moyen de
        bloquer le compte d'un organisateur en se trompant expres."""
        for _ in range(freinage.TOLERANCE + 3):
            client.post("/admin/connexion",
                        json={"identifiant": "orga", "mot_de_passe": "faux"},
                        environ_base={"REMOTE_ADDR": "198.51.100.2"})
        r = client.post("/admin/connexion",
                        json={"identifiant": "orga", "mot_de_passe": MDP},
                        environ_base={"REMOTE_ADDR": "203.0.113.10"})
        assert r.status_code == 200, "le compte lui-meme ne doit jamais etre bloque"


class TestLeFreinAgitAvantLeHachage:
    def test_une_adresse_freinee_ne_fait_pas_travailler_le_hachage(self, client, compte,
                                                                  monkeypatch):
        """scrypt est lent A DESSEIN : laisser un robot le declencher a chaque
        tentative reviendrait a lui offrir un moyen d'epuiser le serveur."""
        for _ in range(freinage.TOLERANCE + 1):
            essayer(client)

        appels = {"n": 0}
        vrai = comptes.verifier
        monkeypatch.setattr(
            "climbcontest.routes.admin.verifier",
            lambda *a, **k: (appels.__setitem__("n", appels["n"] + 1), vrai(*a, **k))[1])

        essayer(client)

        assert appels["n"] == 0, "le frein doit rendre la main avant la verification"


class TestJournalisation:
    def test_l_activation_du_frein_est_journalisee(self, client, compte, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            for _ in range(freinage.TOLERANCE + 2):
                essayer(client)
        assert "frein" in caplog.text.lower()
