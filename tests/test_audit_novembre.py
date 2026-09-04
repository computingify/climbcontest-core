"""Les durcissements de l'audit du 30/08 — chacun avec le trou qu'il ferme.

La méthode est celle de toute la maison : chaque protection est vérifiée en
montrant qu'AVANT elle, le test tombait.
"""
import pytest
from climbcontest.comptes import _hacher as hacher

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
            mot_de_passe_hache=hacher(MDP),
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

    def test_le_lien_porte_le_jeton_en_requete(self, client, app, jeu,
                                               monkeypatch):
        """⚠️ Ce test verifiait l'INVERSE jusqu'a la spec 014, et le renversement
        est delibere. Il faut donc dire pourquoi, sinon la prochaine relecture
        le prendra pour une regression de securite.

        L'argument d'origine tenait : un fragment n'est pas envoye au serveur,
        donc le jeton ne pouvait pas finir dans un journal. Mais un fragment
        n'est pas non plus transmis a `start_url` du manifeste -- donc
        l'application INSTALLEE demarrait sans jeton, et ne pouvait le retrouver
        que dans son stockage local. Sur iPhone, ce stockage est cloisonne :
        elle demarrait vide, et affichait « cette application a besoin du lien
        fourni par l'organisateur ». Le lien etait donc protege des journaux, et
        inutilisable une fois installe.

        La requete est portee par `start_url` : l'application recoit sa cle a
        chaque lancement, sur toutes les plateformes. Le prix -- la presence
        dans les journaux -- est paye par un filtre sur le proxy, qui masque le
        parametre `j`.

        Et la mesure du risque n'a pas change : ce jeton est AFFICHE AU MUR sous
        forme de QR. Il arrete un robot qui balaie Internet, pas quelqu'un
        present dans la salle.
        """
        monkeypatch.setenv("CLIMBCONTEST_API_KEY_PWA", "jeton-pwa-de-test")
        c = _connecter(client, app, [comptes.ORGANISATEUR])
        d = c.get("/admin/lien-juge").get_json()
        assert d["url"].endswith("/juge?j=jeton-pwa-de-test")
        assert "#j=" not in d["url"]
        assert "<svg" in d["qr"]

    def test_un_jeton_a_caracteres_speciaux_est_echappe(self, client, app, jeu,
                                                        monkeypatch):
        """Sans echappement, un `&` dans la cle couperait l'adresse en deux
        parametres : le jeton arriverait tronque et l'API repondrait 401, sans
        que rien n'indique que la cle a ete coupee en route."""
        monkeypatch.setenv("CLIMBCONTEST_API_KEY_PWA", "a&b c")
        c = _connecter(client, app, [comptes.ORGANISATEUR])
        d = c.get("/admin/lien-juge").get_json()
        assert d["url"].endswith("/juge?j=a%26b%20c")

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
