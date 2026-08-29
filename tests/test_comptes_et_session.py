"""Comptes, sessions et controle d'acces de la console (spec 005, IT1).

Ces tests remplacent une mesure d'attente : jusqu'au 28/08, la console etait
protegee par le garde-fou de cle d'API en MODE TOLERE -- lequel accepte, par
construction, une requete sans cle. `GET /admin/import/rapport` repondait donc
200 depuis Internet.

Le principe verifie partout ici est le meme : FAIL CLOSED. Le defaut est de
refuser. Il n'existe aucune branche « on laisse passer en cas de doute ».
"""
from datetime import datetime, timedelta

import pytest

from climbcontest import comptes
from climbcontest.auth_session import CLE_OUVERTURE, CLE_SESSION, DUREE_SESSION
from climbcontest.extensions import db
from climbcontest.models import Utilisateur

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def secret(app):
    """Sans SECRET_KEY reelle, l'administration refuse de servir (et c'est teste)."""
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    return app


@pytest.fixture()
def admin(secret):
    return comptes.creer("chef", MDP, [comptes.ADMIN], nom_affiche="Le chef")


@pytest.fixture()
def organisateur(secret):
    return comptes.creer("orga", MDP, [comptes.ORGANISATEUR])


def connecter(client, identifiant="chef", mot_de_passe=MDP):
    return client.post("/admin/connexion",
                       json={"identifiant": identifiant, "mot_de_passe": mot_de_passe})


# --- Creation de comptes ----------------------------------------------------

class TestCreation:

    def test_un_compte_est_cree_avec_ses_roles(self, secret):
        u = comptes.creer("alice", MDP, [comptes.ORGANISATEUR])
        assert u.identifiant == "alice"
        assert u.a_le_role(comptes.ORGANISATEUR)
        assert not u.a_le_role(comptes.ADMIN)

    def test_le_mot_de_passe_n_est_jamais_en_clair(self, secret):
        u = comptes.creer("alice", MDP, [comptes.ADMIN])
        assert MDP not in u.mot_de_passe_hache
        assert u.mot_de_passe_hache != MDP
        assert len(u.mot_de_passe_hache) > 40, "un hachage, pas un encodage"

    def test_l_identifiant_est_normalise(self, secret):
        u = comptes.creer("  ALICE  ", MDP, [comptes.ADMIN])
        assert u.identifiant == "alice", "sinon « Alice » et « alice » seraient deux comptes"

    def test_un_identifiant_deja_pris_est_refuse(self, secret):
        comptes.creer("alice", MDP, [comptes.ADMIN])
        with pytest.raises(comptes.ErreurCompte) as e:
            comptes.creer("Alice", MDP, [comptes.ADMIN])
        assert e.value.code == 409

    def test_un_mot_de_passe_trop_court_est_refuse(self, secret):
        with pytest.raises(comptes.ErreurCompte):
            comptes.creer("alice", "court", [comptes.ADMIN])

    def test_un_role_inconnu_est_refuse(self, secret):
        """Fail closed des la creation : un role qu'on ne connait pas ne doit
        pas exister en base, sinon le controle d'acces devrait deviner."""
        with pytest.raises(comptes.ErreurCompte):
            comptes.creer("alice", MDP, ["super-utilisateur"])

    def test_un_compte_sans_role_est_refuse(self, secret):
        with pytest.raises(comptes.ErreurCompte):
            comptes.creer("alice", MDP, [])

    def test_le_mot_de_passe_n_est_pas_journalise(self, secret, caplog):
        import logging
        with caplog.at_level(logging.DEBUG):
            comptes.creer("alice", MDP, [comptes.ADMIN])
        assert MDP not in caplog.text


# --- Verification -----------------------------------------------------------

class TestVerification:

    def test_le_bon_couple_est_accepte(self, admin):
        assert comptes.verifier("chef", MDP) is not None

    def test_la_casse_de_l_identifiant_est_ignoree(self, admin):
        assert comptes.verifier("CHEF", MDP) is not None

    def test_un_mauvais_mot_de_passe_est_refuse(self, admin):
        assert comptes.verifier("chef", "pas-le-bon-du-tout") is None

    def test_un_identifiant_inconnu_est_refuse(self, secret):
        assert comptes.verifier("personne", MDP) is None

    def test_un_compte_desactive_ne_peut_plus_entrer(self, admin):
        comptes.desactiver(admin)
        assert comptes.verifier("chef", MDP) is None

    def test_le_temps_de_reponse_ne_revele_pas_les_comptes(self, admin):
        """Repondre plus vite pour un identifiant inconnu dirait lesquels
        existent -- et c'est la premiere chose qu'on teste sur une console
        exposee. Le hachage a vide egalise les deux chemins.

        On compare des ORDRES DE GRANDEUR, pas des microsecondes : un test de
        temps trop serre devient instable et finit par etre ignore.
        """
        import time

        def duree(identifiant):
            debut = time.perf_counter()
            comptes.verifier(identifiant, "un-mot-de-passe-quelconque")
            return time.perf_counter() - debut

        connu = min(duree("chef") for _ in range(3))
        inconnu = min(duree("personne") for _ in range(3))
        rapport = max(connu, inconnu) / max(1e-9, min(connu, inconnu))
        assert rapport < 5, (
            f"ecart de temps trop marque : connu={connu*1000:.1f} ms, "
            f"inconnu={inconnu*1000:.1f} ms")


# --- Connexion par HTTP -----------------------------------------------------

class TestConnexion:

    def test_connexion_reussie(self, client, admin):
        r = connecter(client)
        assert r.status_code == 200
        assert r.get_json()["roles"] == [comptes.ADMIN]

    def test_mauvais_mot_de_passe(self, client, admin):
        assert connecter(client, mot_de_passe="pas-le-bon-du-tout").status_code == 401

    def test_identifiant_inconnu(self, client, secret):
        assert connecter(client, identifiant="fantome").status_code == 401

    def test_le_message_ne_dit_pas_lequel_des_deux_est_faux(self, client, admin):
        a = connecter(client, mot_de_passe="pas-le-bon-du-tout").get_json()["message"]
        b = connecter(client, identifiant="fantome").get_json()["message"]
        assert a == b, "deux messages differents reveleraient les comptes existants"

    def test_un_corps_qui_n_est_pas_un_objet_donne_400(self, client, secret):
        r = client.post("/admin/connexion", data="[1,2]", content_type="application/json")
        assert r.status_code == 400

    def test_l_echec_est_journalise_avec_l_adresse(self, client, admin, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            connecter(client, mot_de_passe="pas-le-bon-du-tout")
        assert "connexion refusee" in caplog.text

    def test_deconnexion(self, client, admin):
        connecter(client)
        assert client.get("/admin/moi").status_code == 200
        client.post("/admin/deconnexion")
        assert client.get("/admin/moi").status_code == 401


# --- Le controle d'acces ----------------------------------------------------

class TestFailClosed:

    def test_sans_session_c_est_401(self, client, secret):
        assert client.get("/admin/moi").status_code == 401
        assert client.get("/admin/import/rapport").status_code == 401
        assert client.post("/admin/import/sheet").status_code == 401

    def test_avec_session_ca_passe(self, client, admin):
        connecter(client)
        assert client.get("/admin/import/rapport").status_code == 200

    def test_une_session_expiree_est_refusee(self, client, admin):
        connecter(client)
        with client.session_transaction() as s:
            s[CLE_OUVERTURE] = (datetime.now() - DUREE_SESSION - timedelta(minutes=1)).isoformat()
        assert client.get("/admin/moi").status_code == 401

    def test_une_session_sans_date_est_refusee(self, client, admin):
        connecter(client)
        with client.session_transaction() as s:
            del s[CLE_OUVERTURE]
        assert client.get("/admin/moi").status_code == 401

    def test_une_date_illisible_est_refusee(self, client, admin):
        connecter(client)
        with client.session_transaction() as s:
            s[CLE_OUVERTURE] = "pas une date"
        assert client.get("/admin/moi").status_code == 401

    def test_un_utilisateur_supprime_perd_l_acces_immediatement(self, client, admin):
        """La session reste valide, mais le compte est relu en base a chaque
        requete : desactiver quelqu'un pendant la competition doit avoir un
        effet tout de suite, pas dans douze heures."""
        connecter(client)
        comptes.desactiver(admin)
        assert client.get("/admin/moi").status_code == 401

    def test_un_identifiant_de_session_inexistant_est_refuse(self, client, secret):
        with client.session_transaction() as s:
            s[CLE_SESSION] = 99999
            s[CLE_OUVERTURE] = datetime.now().isoformat()
        assert client.get("/admin/moi").status_code == 401

    def test_un_cookie_forge_est_refuse(self, client, admin):
        """Sans la bonne SECRET_KEY, la signature ne tient pas."""
        client.set_cookie("session", "n-importe-quoi.forge")
        assert client.get("/admin/moi").status_code == 401


class TestRoles:

    def test_l_admin_a_tous_les_droits(self, client, admin):
        connecter(client)
        assert client.get("/admin/import/rapport").status_code == 200

    def test_l_organisateur_accede_a_ce_qui_le_concerne(self, client, organisateur):
        connecter(client, identifiant="orga")
        assert client.get("/admin/moi").status_code == 200

    def test_les_roles_sont_annonces(self, client, organisateur):
        connecter(client, identifiant="orga")
        assert client.get("/admin/moi").get_json()["roles"] == [comptes.ORGANISATEUR]

    def test_definir_des_roles_les_remplace(self, secret):
        u = comptes.creer("alice", MDP, [comptes.ORGANISATEUR])
        comptes.definir_roles(u, [comptes.ADMIN])
        db.session.refresh(u)
        assert u.a_le_role(comptes.ADMIN) and not u.a_le_role(comptes.ORGANISATEUR)

    def test_un_role_inconnu_ne_peut_pas_etre_attribue(self, secret):
        u = comptes.creer("alice", MDP, [comptes.ORGANISATEUR])
        with pytest.raises(comptes.ErreurCompte):
            comptes.definir_roles(u, ["dieu"])


class TestSecretParDefaut:
    """Avec la cle de developpement, un cookie de session se forge en trois
    lignes. Mieux vaut une console indisponible qu'une console ouverte.
    """

    def test_l_administration_refuse_de_servir(self, client, app):
        from climbcontest.auth_session import SECRET_DE_DEV
        app.config["SECRET_KEY"] = SECRET_DE_DEV
        r = client.get("/admin/moi")
        assert r.status_code == 503
        assert "SECRET_KEY" in r.get_json()["message"]

    def test_les_routes_des_juges_ne_sont_PAS_affectees(self, client, app, jeu):
        """Le durcissement ne doit jamais deborder sur l'application v3.1.4."""
        from climbcontest.auth_session import SECRET_DE_DEV
        app.config["SECRET_KEY"] = SECRET_DE_DEV
        assert client.post("/api/v2/contest/climber/name",
                           json={"id": "1"}).status_code == 201


class TestPremierAdmin:

    def test_aucun_admin_au_depart(self, secret):
        assert comptes.existe_un_admin() is False

    def test_un_admin_actif_est_detecte(self, admin):
        assert comptes.existe_un_admin() is True

    def test_un_admin_desactive_ne_compte_pas(self, admin):
        comptes.desactiver(admin)
        assert comptes.existe_un_admin() is False

    def test_un_organisateur_ne_compte_pas_comme_admin(self, organisateur):
        assert comptes.existe_un_admin() is False
