"""Le jeton HelloAsso — spec 008, lot 4.

Le test qui compte est
`test_deux_appels_concurrents_ne_font_qu_un_rafraichissement`. Il ferme le
défaut qui, sans lui, ne se verrait qu'en production : leur `refresh_token`
tourne, et deux workers qui le rafraîchissent en même temps **se révoquent l'un
l'autre**. En développement il n'y a qu'un processus ; le défaut serait donc
invisible jusqu'au jour de la compétition.

Aucun appel réseau réel : `requests` est doublé.
"""

import json
from datetime import datetime, timedelta

import pytest

from climbcontest.extensions import db
from climbcontest.helloasso import client as ha
from climbcontest.models import Reglage


class Reponse:
    def __init__(self, code=200, donnees=None):
        self.status_code = code
        self._donnees = donnees or {}

    def json(self):
        return self._donnees


@pytest.fixture()
def secrets(app, tmp_path):
    app.config["DOSSIER_SECRETS"] = str(tmp_path)
    return tmp_path


@pytest.fixture()
def relie(secrets):
    ha.ecrire_secret("identifiant-de-test-3715", "un-secret",
                     ha.BAC_A_SABLE)
    return secrets


def jeton_frais(minutes=30):
    return {"access_token": "abc", "refresh_token": "rrr",
            "expire_le": (datetime.now() + timedelta(minutes=minutes)).isoformat()}


class TestLaCle:
    def test_sans_cle_aucun_appel_reseau(self, secrets, monkeypatch):
        appels = []
        monkeypatch.setattr(ha.requests, "post",
                            lambda *a, **k: appels.append(1))
        with pytest.raises(ha.ErreurHelloAsso) as e:
            ha.ClientHelloAsso()
        assert e.value.code == 409
        assert appels == []

    def test_l_etat_ne_rend_jamais_le_secret(self, relie):
        etat = ha.etat()
        rendu = json.dumps(etat)
        assert "un-secret" not in rendu
        assert "identifiant-de-test-3715" not in rendu
        assert etat["cle"] == "…3715"

    def test_l_etat_sans_cle(self, secrets):
        assert ha.etat() == {"configure": False}

    def test_effacer_retire_le_jeton_aussi(self, relie):
        ha._ecrire_jeton(jeton_frais())
        ha.effacer_secret()
        assert ha.lire_secret() is None
        assert db.session.get(Reglage, ha.CLE_JETON) is None

    def test_un_environnement_inconnu_est_refuse(self, secrets):
        with pytest.raises(ha.ErreurHelloAsso):
            ha.ecrire_secret("a", "b", "lune")

    def test_le_bac_a_sable_change_l_hote(self, relie):
        assert "sandbox" in ha.ClientHelloAsso().hote


class TestLeJeton:
    def test_un_jeton_valide_n_appelle_pas_l_authentification(self, relie, monkeypatch):
        ha._ecrire_jeton(jeton_frais())
        monkeypatch.setattr(ha.requests, "post",
                            lambda *a, **k: pytest.fail("appel interdit"))
        assert ha.ClientHelloAsso().jeton() == "abc"

    def test_le_premier_appel_utilise_client_credentials(self, relie, monkeypatch):
        vus = []

        def faux_post(url, data=None, **k):
            vus.append(data)
            return Reponse(200, {"access_token": "AAA", "refresh_token": "RRR",
                                 "expires_in": 1799})
        monkeypatch.setattr(ha.requests, "post", faux_post)
        assert ha.ClientHelloAsso().jeton() == "AAA"
        assert vus[0]["grant_type"] == "client_credentials"

    def test_un_jeton_expire_se_rafraichit(self, relie, monkeypatch):
        ha._ecrire_jeton({"access_token": "vieux", "refresh_token": "RRR",
                          "expire_le": (datetime.now() - timedelta(minutes=1)).isoformat()})
        vus = []

        def faux_post(url, data=None, **k):
            vus.append(data)
            return Reponse(200, {"access_token": "NEUF", "refresh_token": "RRR2",
                                 "expires_in": 1799})
        monkeypatch.setattr(ha.requests, "post", faux_post)
        assert ha.ClientHelloAsso().jeton() == "NEUF"
        assert vus[0]["grant_type"] == "refresh_token"
        assert ha._lire_jeton()["refresh_token"] == "RRR2"

    def test_deux_appels_concurrents_ne_font_qu_un_rafraichissement(
            self, relie, monkeypatch):
        """Le défaut que ce test ferme ne se verrait qu'en production.

        Leur `refresh_token` tourne : réutiliser A crée C **et révoque B**. Deux
        workers qui rafraîchissent ensemble se cassent donc l'un l'autre. Ici,
        le second n'obtient pas le verrou, relit la base, et trouve le jeton
        que le premier vient d'y déposer.
        """
        ha._ecrire_jeton({"access_token": "vieux", "refresh_token": "RRR",
                          "expire_le": (datetime.now() - timedelta(minutes=1)).isoformat()})
        appels = []

        def faux_post(url, data=None, **k):
            appels.append(data)
            return Reponse(200, {"access_token": "NEUF", "refresh_token": "RRR2",
                                 "expires_in": 1799})
        monkeypatch.setattr(ha.requests, "post", faux_post)

        premier = ha.ClientHelloAsso()
        assert premier.jeton() == "NEUF"

        # Le second arrive alors que le verrou est encore pris : il doit relire
        # la base plutot que de demander un second jeton.
        assert ha._prendre_verrou() is True          # on simule le voisin
        try:
            assert ha.ClientHelloAsso().jeton() == "NEUF"
        finally:
            ha._rendre_verrou()
        assert len(appels) == 1

    def test_le_verrou_ne_se_prend_pas_deux_fois(self, relie):
        assert ha._prendre_verrou() is True
        assert ha._prendre_verrou() is False
        ha._rendre_verrou()
        assert ha._prendre_verrou() is True
        ha._rendre_verrou()

    def test_une_cle_refusee_demande_une_reconnexion(self, relie, monkeypatch):
        monkeypatch.setattr(ha.requests, "post",
                            lambda *a, **k: Reponse(401, {}))
        with pytest.raises(ha.ErreurHelloAsso) as e:
            ha.ClientHelloAsso().jeton()
        assert e.value.reconnecter is True

    def test_le_reseau_coupe_n_est_pas_une_cle_morte(self, relie, monkeypatch):
        def tombe(*a, **k):
            raise ha.requests.RequestException("pas de reseau")
        monkeypatch.setattr(ha.requests, "post", tombe)
        with pytest.raises(ha.ErreurHelloAsso) as e:
            ha.ClientHelloAsso().jeton()
        assert e.value.reconnecter is False

    def test_le_secret_n_apparait_dans_aucun_journal(self, relie, monkeypatch, caplog):
        monkeypatch.setattr(ha.requests, "post",
                            lambda *a, **k: Reponse(200, {"access_token": "A",
                                                          "refresh_token": "R",
                                                          "expires_in": 1799}))
        with caplog.at_level("DEBUG"):
            ha.ClientHelloAsso().jeton()
        assert "un-secret" not in caplog.text


class TestLesAppels:
    def _client(self, monkeypatch, pages):
        ha._ecrire_jeton(jeton_frais())
        vus = []

        def faux_get(url, params=None, **k):
            vus.append(params or {})
            return Reponse(200, pages[len(vus) - 1])
        monkeypatch.setattr(ha.requests, "get", faux_get)
        return ha.ClientHelloAsso(), vus

    def test_la_pagination_s_arrete_sur_le_tableau_vide(self, relie, monkeypatch):
        pages = [
            {"data": [{"id": 1}, {"id": 2}],
             "pagination": {"continuationToken": "T1"}},
            {"data": [{"id": 3}], "pagination": {"continuationToken": "T2"}},
            {"data": [], "pagination": {"continuationToken": "T3"}},
        ]
        c, vus = self._client(monkeypatch, pages)
        articles = list(c.articles("club", "Event", "bloc-party"))
        assert [a["id"] for a in articles] == [1, 2, 3]
        assert len(vus) == 3
        assert vus[1]["continuationToken"] == "T1"

    def test_un_jeton_toujours_renvoye_ne_fait_pas_boucler(self, relie, monkeypatch):
        """Leur documentation prévient : le jeton peut survivre aux données.

        S'arrêter sur son absence ferait tourner la boucle pour toujours.
        """
        pages = [{"data": [], "pagination": {"continuationToken": "encore"}}]
        c, _ = self._client(monkeypatch, pages)
        assert list(c.articles("club", "Event", "bloc-party")) == []

    def test_les_parametres_du_releve(self, relie, monkeypatch):
        c, vus = self._client(monkeypatch, [{"data": []}])
        list(c.articles("club", "Event", "bloc-party",
                        depuis=datetime(2026, 11, 15, 9, 30)))
        assert vus[0]["sortField"] == "UpdateDate"
        assert vus[0]["withDetails"] == "true"
        # Recouvrement de cinq minutes : les horloges different des deux cotes.
        assert vus[0]["from"] == datetime(2026, 11, 15, 9, 25).isoformat()

    def test_un_401_en_cours_de_releve_ne_fait_qu_un_reessai(self, relie, monkeypatch):
        ha._ecrire_jeton(jeton_frais())
        codes = [401, 401]
        monkeypatch.setattr(ha.requests, "post",
                            lambda *a, **k: Reponse(200, {"access_token": "A",
                                                          "refresh_token": "R",
                                                          "expires_in": 1799}))
        appels = []

        def faux_get(url, params=None, **k):
            appels.append(1)
            return Reponse(codes[len(appels) - 1] if len(appels) <= len(codes) else 200,
                           {"data": []})
        monkeypatch.setattr(ha.requests, "get", faux_get)
        with pytest.raises(ha.ErreurHelloAsso) as e:
            list(ha.ClientHelloAsso().articles("club", "Event", "bp"))
        assert e.value.reconnecter is True
        assert len(appels) == 2           # l'appel, puis UN reessai

    def test_un_429_est_une_panne_passagere(self, relie, monkeypatch):
        ha._ecrire_jeton(jeton_frais())
        monkeypatch.setattr(ha.requests, "get",
                            lambda *a, **k: Reponse(429, {}))
        with pytest.raises(ha.ErreurHelloAsso) as e:
            list(ha.ClientHelloAsso().articles("club", "Event", "bp"))
        assert e.value.reconnecter is False


class TestSansBase:
    """Le mode des outils lancés depuis le Mac — spec 008.

    ⚠️ Le défaut que ce mode ferme a été trouvé **en lançant l'outil**, pas en
    le relisant : `tools/dump_helloasso.py` tombait sur « working outside of
    application context » dès le premier appel, parce que le jeton vit en base.

    Le jeton vit en base pour UNE raison — quatre workers gunicorn qui le
    rafraîchissent en même temps se révoquent l'un l'autre. Un script à un coup
    n'a ni les quatre workers, ni contexte Flask, ni base ; le jeton y vit donc
    en mémoire, le temps du processus, qui est exactement sa durée utile.
    """

    def test_le_jeton_ne_touche_pas_la_base(self, secrets, monkeypatch):
        appels = []

        def faux_post(url, data=None, **k):
            appels.append(data)
            return Reponse(200, {"access_token": "AAA", "refresh_token": "RRR",
                                 "expires_in": 1799})
        monkeypatch.setattr(ha.requests, "post", faux_post)
        monkeypatch.setattr(ha, "_lire_jeton",
                            lambda: pytest.fail("la base ne doit pas etre lue"))
        monkeypatch.setattr(ha, "_ecrire_jeton",
                            lambda d: pytest.fail("la base ne doit pas etre ecrite"))
        client = ha.ClientHelloAsso(
            {"client_id": "a", "client_secret": "b", "environnement": ha.BAC_A_SABLE},
            sans_base=True)
        assert client.jeton() == "AAA"
        assert appels[0]["grant_type"] == "client_credentials"

    def test_le_jeton_est_garde_le_temps_du_processus(self, secrets, monkeypatch):
        appels = []

        def faux_post(url, data=None, **k):
            appels.append(1)
            return Reponse(200, {"access_token": "AAA", "refresh_token": "R",
                                 "expires_in": 1799})
        monkeypatch.setattr(ha.requests, "post", faux_post)
        client = ha.ClientHelloAsso(
            {"client_id": "a", "client_secret": "b"}, sans_base=True)
        client.jeton()
        client.jeton()
        assert len(appels) == 1

    def test_une_cle_refusee_le_dit(self, secrets, monkeypatch):
        monkeypatch.setattr(ha.requests, "post", lambda *a, **k: Reponse(401, {}))
        client = ha.ClientHelloAsso(
            {"client_id": "a", "client_secret": "b"}, sans_base=True)
        with pytest.raises(ha.ErreurHelloAsso) as e:
            client.jeton()
        assert e.value.reconnecter is True
