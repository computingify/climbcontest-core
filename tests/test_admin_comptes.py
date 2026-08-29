"""Gestion des comptes depuis la console (spec 005).

La ligne de commande sert a AMORCER -- le tout premier compte, quand il n'y a
encore personne pour en creer un. Tout le reste se fait d'ici : demander un
acces SSH a chaque nouveau benevole n'aurait aucun sens.

Le garde-fou central est celui du DERNIER ADMINISTRATEUR. C'est un piege sans
retour : l'unique administrateur se retire ses droits « pour faire propre », et
plus personne ne peut gerer les comptes. Il faut alors un acces SSH a la VM et
la ligne de commande -- typiquement un dimanche matin.
"""
import pytest

from climbcontest import comptes
from climbcontest.extensions import db
from climbcontest.models import Utilisateur

MDP = "un-mot-de-passe-assez-long"
AUTRE = "un-autre-mot-de-passe-long"


@pytest.fixture()
def secret(app):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    return app


@pytest.fixture()
def admin(secret):
    return comptes.creer("chef", MDP, [comptes.ADMIN])


@pytest.fixture()
def connecte(client, admin):
    client.post("/admin/connexion", json={"identifiant": "chef", "mot_de_passe": MDP})
    return client


class TestCreation:

    def test_un_organisateur_est_cree(self, connecte):
        r = connecte.post("/admin/comptes", json={
            "identifiant": "benevole", "mot_de_passe": AUTRE,
            "roles": [comptes.ORGANISATEUR], "nom_affiche": "Marie",
        })
        assert r.status_code == 201
        assert Utilisateur.query.filter_by(identifiant="benevole").count() == 1

    def test_il_peut_se_connecter_aussitot(self, connecte, client):
        connecte.post("/admin/comptes", json={
            "identifiant": "benevole", "mot_de_passe": AUTRE,
            "roles": [comptes.ORGANISATEUR]})
        connecte.post("/admin/deconnexion")
        r = connecte.post("/admin/connexion",
                          json={"identifiant": "benevole", "mot_de_passe": AUTRE})
        assert r.status_code == 200

    def test_un_mot_de_passe_trop_court_est_refuse_avec_un_message(self, connecte):
        r = connecte.post("/admin/comptes", json={
            "identifiant": "x", "mot_de_passe": "court", "roles": [comptes.ORGANISATEUR]})
        assert r.status_code == 400
        assert str(comptes.LONGUEUR_MINIMALE) in r.get_json()["message"]

    def test_un_identifiant_deja_pris(self, connecte):
        assert connecte.post("/admin/comptes", json={
            "identifiant": "chef", "mot_de_passe": AUTRE,
            "roles": [comptes.ADMIN]}).status_code == 409

    def test_un_organisateur_ne_peut_pas_creer_de_compte(self, client, secret):
        comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
        client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
        r = client.post("/admin/comptes", json={
            "identifiant": "x", "mot_de_passe": AUTRE, "roles": [comptes.ADMIN]})
        assert r.status_code == 403


class TestListe:

    def test_la_liste_donne_les_roles_et_l_etat(self, connecte):
        d = connecte.get("/admin/comptes").get_json()
        assert d["comptes"][0]["identifiant"] == "chef"
        assert d["comptes"][0]["roles"] == [comptes.ADMIN]
        assert d["comptes"][0]["actif"] is True

    def test_aucun_hachage_ne_sort(self, connecte):
        """Un hachage n'a rien a faire dans une reponse HTTP."""
        page = connecte.get("/admin/comptes").data.decode()
        assert "scrypt" not in page and "pbkdf2" not in page
        assert "mot_de_passe" not in page

    def test_le_dernier_admin_est_signale(self, connecte):
        """Pour que la console puisse griser ce qui fermerait la porte."""
        d = connecte.get("/admin/comptes").get_json()
        assert d["comptes"][0]["dernier_admin"] is True

    def test_il_ne_l_est_plus_des_qu_il_y_en_a_deux(self, connecte):
        connecte.post("/admin/comptes", json={
            "identifiant": "second", "mot_de_passe": AUTRE, "roles": [comptes.ADMIN]})
        d = connecte.get("/admin/comptes").get_json()
        assert all(c["dernier_admin"] is False for c in d["comptes"])


class TestDernierAdministrateur:
    """Le piege sans retour. Si personne ne le garde, il finit par arriver."""

    def test_le_dernier_admin_ne_peut_pas_se_retirer_le_role(self, connecte, admin):
        r = connecte.post(f"/admin/comptes/{admin.id}/roles",
                          json={"roles": [comptes.ORGANISATEUR]})
        assert r.status_code == 409
        assert "dernier administrateur" in r.get_json()["message"].lower()

    def test_ni_se_desactiver(self, connecte, admin):
        r = connecte.post(f"/admin/comptes/{admin.id}/actif", json={"actif": False})
        assert r.status_code == 409

    def test_le_message_dit_quoi_faire(self, connecte, admin):
        r = connecte.post(f"/admin/comptes/{admin.id}/actif", json={"actif": False})
        assert "nomme d'abord" in r.get_json()["message"].lower()

    def test_mais_c_est_possible_des_qu_un_autre_admin_existe(self, connecte, admin):
        connecte.post("/admin/comptes", json={
            "identifiant": "second", "mot_de_passe": AUTRE, "roles": [comptes.ADMIN]})

        r = connecte.post(f"/admin/comptes/{admin.id}/roles",
                          json={"roles": [comptes.ORGANISATEUR]})

        assert r.status_code == 200

    def test_un_admin_desactive_ne_compte_pas_comme_filet(self, connecte, admin):
        """Sinon on pourrait se retirer le role en s'appuyant sur un compte
        qui ne peut plus se connecter."""
        connecte.post("/admin/comptes", json={
            "identifiant": "second", "mot_de_passe": AUTRE, "roles": [comptes.ADMIN]})
        second = Utilisateur.query.filter_by(identifiant="second").one()
        connecte.post(f"/admin/comptes/{second.id}/actif", json={"actif": False})

        r = connecte.post(f"/admin/comptes/{admin.id}/actif", json={"actif": False})

        assert r.status_code == 409


class TestReinitialisation:
    """Le « mot de passe oublie », sans serveur de courriel."""

    def test_l_admin_pose_un_nouveau_mot_de_passe(self, connecte):
        connecte.post("/admin/comptes", json={
            "identifiant": "benevole", "mot_de_passe": AUTRE,
            "roles": [comptes.ORGANISATEUR]})
        u = Utilisateur.query.filter_by(identifiant="benevole").one()

        r = connecte.post(f"/admin/comptes/{u.id}/mot-de-passe",
                          json={"mot_de_passe": "encore-un-autre-mot-de-passe"})

        assert r.status_code == 200
        assert comptes.verifier("benevole", "encore-un-autre-mot-de-passe") is not None

    def test_l_ancien_ne_marche_plus(self, connecte):
        connecte.post("/admin/comptes", json={
            "identifiant": "benevole", "mot_de_passe": AUTRE,
            "roles": [comptes.ORGANISATEUR]})
        u = Utilisateur.query.filter_by(identifiant="benevole").one()
        connecte.post(f"/admin/comptes/{u.id}/mot-de-passe",
                      json={"mot_de_passe": "encore-un-autre-mot-de-passe"})
        assert comptes.verifier("benevole", AUTRE) is None

    def test_un_compte_inconnu_donne_404(self, connecte):
        assert connecte.post("/admin/comptes/99999/mot-de-passe",
                             json={"mot_de_passe": AUTRE}).status_code == 404


class TestMonMotDePasse:
    """Chacun change le sien, sans deranger un administrateur."""

    def test_je_change_mon_mot_de_passe(self, connecte):
        r = connecte.post("/admin/mon-mot-de-passe",
                          json={"actuel": MDP, "nouveau": AUTRE})
        assert r.status_code == 200
        assert comptes.verifier("chef", AUTRE) is not None

    def test_l_ancien_mot_de_passe_est_exige(self, connecte):
        """Sans ca, une session volee -- un ordinateur laisse deverrouille dans
        la salle -- permettrait de s'approprier le compte definitivement."""
        r = connecte.post("/admin/mon-mot-de-passe",
                          json={"actuel": "pas-le-bon-du-tout", "nouveau": AUTRE})
        assert r.status_code == 401
        assert comptes.verifier("chef", MDP) is not None, "rien ne doit avoir change"

    def test_un_nouveau_trop_court_est_refuse(self, connecte):
        r = connecte.post("/admin/mon-mot-de-passe",
                          json={"actuel": MDP, "nouveau": "court"})
        assert r.status_code == 400
        assert comptes.verifier("chef", MDP) is not None

    def test_un_organisateur_le_peut_aussi(self, client, secret):
        """Ce n'est pas un droit d'administration : c'est son propre compte."""
        comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
        client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
        assert client.post("/admin/mon-mot-de-passe",
                           json={"actuel": MDP, "nouveau": AUTRE}).status_code == 200

    def test_sans_session_c_est_refuse(self, client, secret, admin):
        assert client.post("/admin/mon-mot-de-passe",
                           json={"actuel": MDP, "nouveau": AUTRE}).status_code == 401


class TestJournalisation:

    def test_aucun_mot_de_passe_ne_passe_dans_le_journal(self, connecte, caplog):
        import logging
        with caplog.at_level(logging.DEBUG):
            connecte.post("/admin/comptes", json={
                "identifiant": "benevole", "mot_de_passe": AUTRE,
                "roles": [comptes.ORGANISATEUR]})
            connecte.post("/admin/mon-mot-de-passe",
                          json={"actuel": MDP, "nouveau": "encore-un-autre-long"})
        assert AUTRE not in caplog.text
        assert MDP not in caplog.text
        assert "encore-un-autre-long" not in caplog.text

    def test_mais_l_action_est_tracee(self, connecte, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            connecte.post("/admin/comptes", json={
                "identifiant": "benevole", "mot_de_passe": AUTRE,
                "roles": [comptes.ORGANISATEUR]})
        assert "benevole" in caplog.text and "chef" in caplog.text


class TestLeGardeFouAuNiveauMetier:
    """Le meme garde-fou, hors HTTP : il doit tenir quel que soit l'appelant."""

    def test_desactiver_le_dernier_admin_est_refuse(self, admin):
        with pytest.raises(comptes.ErreurCompte) as e:
            comptes.desactiver(admin)
        assert e.value.code == 409

    def test_lui_retirer_le_role_est_refuse(self, admin):
        with pytest.raises(comptes.ErreurCompte):
            comptes.definir_roles(admin, [comptes.ORGANISATEUR])

    def test_desactiver_un_organisateur_est_libre(self, admin):
        u = comptes.creer("benevole", AUTRE, [comptes.ORGANISATEUR])
        comptes.desactiver(u)
        assert u.actif is False

    def test_et_on_peut_le_reactiver(self, admin):
        u = comptes.creer("benevole", AUTRE, [comptes.ORGANISATEUR])
        comptes.desactiver(u)
        comptes.reactiver(u)
        assert u.actif is True
        assert comptes.verifier("benevole", AUTRE) is not None
