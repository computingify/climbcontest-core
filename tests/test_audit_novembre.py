"""Les durcissements de l'audit du 30/08 — chacun avec le trou qu'il ferme.

La méthode est celle de toute la maison : chaque protection est vérifiée en
montrant qu'AVANT elle, le test tombait.
"""
import pytest
from werkzeug.security import generate_password_hash

from climbcontest import comptes
from climbcontest.config import Config
from climbcontest.extensions import db
from climbcontest.models import Utilisateur

MDP = "un-mot-de-passe-assez-long"


def _connecter(client, app, roles):
    """Un compte connecté. `roles=[]` le fabrique EN BASE : l'API de comptes
    refuse un compte sans rôle (« ne sert à rien »), et c'est exactement
    pourquoi ces tests-là sont de la défense en profondeur — ils vérifient que
    même un compte apparu par un chemin imprévu ne peut pas réimporter."""
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    if roles:
        comptes.creer("u", MDP, roles)
    else:
        db.session.add(Utilisateur(
            identifiant="u",
            mot_de_passe_hache=generate_password_hash(MDP),
            actif=True,
        ))
        db.session.commit()
    client.post("/admin/connexion", json={"identifiant": "u", "mot_de_passe": MDP})
    return client


class TestRolesImport:
    """Un réimport réécrit la base : « connecté » ne suffit plus."""

    def test_un_compte_sans_role_ne_peut_plus_reimporter(self, client, app, jeu):
        c = _connecter(client, app, roles=[])
        assert c.post("/admin/import/sheet").status_code == 403

    def test_un_compte_sans_role_ne_lit_plus_le_rapport(self, client, app, jeu):
        c = _connecter(client, app, roles=[])
        assert c.get("/admin/import/rapport").status_code == 403

    def test_un_organisateur_garde_la_main(self, client, app, jeu):
        c = _connecter(client, app, roles=[comptes.ORGANISATEUR])
        # 502 : le classeur de test n'existe pas -- mais le ROLE est passe.
        assert c.post("/admin/import/sheet").status_code in (200, 502)
        assert c.get("/admin/import/rapport").status_code == 200


class TestCookies:
    """Le cookie de session ne doit jamais voyager en clair."""

    def test_la_production_pose_secure_par_defaut(self):
        assert Config.SESSION_COOKIE_SECURE is True
        assert Config.SESSION_COOKIE_HTTPONLY is True
        assert Config.SESSION_COOKIE_SAMESITE == "Lax"

    def test_le_cookie_de_session_porte_ses_drapeaux(self, client, app):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        app.config["SESSION_COOKIE_SECURE"] = True   # comme en production
        comptes.creer("u", MDP, [comptes.ORGANISATEUR])
        r = client.post("/admin/connexion",
                        json={"identifiant": "u", "mot_de_passe": MDP})
        entete = r.headers.get("Set-Cookie", "")
        assert "Secure" in entete
        assert "HttpOnly" in entete
        assert "SameSite=Lax" in entete


class TestLienJuge:
    """Le QR d'installation prévu par la spec 007, enfin réel."""

    def test_sans_cle_pwa_la_reponse_dit_quoi_poser(self, client, app, jeu,
                                                    monkeypatch):
        monkeypatch.delenv("CLIMBCONTEST_API_KEY_PWA", raising=False)
        c = _connecter(client, app, [comptes.ORGANISATEUR])
        r = c.get("/admin/lien-juge")
        assert r.status_code == 409
        assert "CLIMBCONTEST_API_KEY_PWA" in r.get_json()["message"]

    def test_le_lien_porte_le_jeton_en_fragment(self, client, app, jeu,
                                                monkeypatch):
        monkeypatch.setenv("CLIMBCONTEST_API_KEY_PWA", "jeton-pwa-de-test")
        c = _connecter(client, app, [comptes.ORGANISATEUR])
        d = c.get("/admin/lien-juge").get_json()
        assert d["url"].endswith("/juge#j=jeton-pwa-de-test")
        # Un fragment, jamais une query string : le jeton ne doit pas pouvoir
        # finir dans un journal de serveur.
        assert "?j=" not in d["url"]
        assert "<svg" in d["qr"]

    def test_en_local_le_lien_reste_en_http(self, client, app, jeu, monkeypatch):
        # Le client de test parle a `localhost` : forcer https ici produirait
        # un lien invalide en developpement.
        monkeypatch.setenv("CLIMBCONTEST_API_KEY_PWA", "jeton")
        c = _connecter(client, app, [comptes.ORGANISATEUR])
        assert c.get("/admin/lien-juge").get_json()["url"].startswith("http://")

    def test_il_faut_etre_organisateur(self, client, app, jeu, monkeypatch):
        monkeypatch.setenv("CLIMBCONTEST_API_KEY_PWA", "jeton")
        c = _connecter(client, app, roles=[])
        assert c.get("/admin/lien-juge").status_code == 403

    def test_il_faut_etre_connecte(self, client, app, jeu, monkeypatch):
        monkeypatch.setenv("CLIMBCONTEST_API_KEY_PWA", "jeton")
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/lien-juge").status_code == 401
