"""Spec 043 — rien de ce site n'entre dans un moteur de recherche.

Pourquoi c'est ici et pas dans le Caddyfile : la configuration du proxy est
recopiee a la main d'un hote a l'autre et derive dans les deux sens ; aucun test
ne la lit. Ecrite dans l'application, la regle voyage avec le code et ces tests
la tiennent.

Trois consignes qui ne se remplacent pas :

    robots.txt      « ne viens pas »        -- lu AVANT la visite
    <meta robots>   « ne garde pas »        -- lu dans une page HTML
    X-Robots-Tag    « ne garde pas »        -- le seul canal d'une reponse JSON

Un robot qui ignore `robots.txt` lit la balise. Un robot qui lit `robots.txt`
mais visite quand meme lit l'en-tete. Les retirer un a un doit faire echouer un
test different a chaque fois.
"""

from climbcontest.contest import enregistrer_reussite


class TestRobotsTxt:

    def test_le_fichier_existe_et_ferme_tout(self, client_sans_cle):
        r = client_sans_cle.get("/robots.txt")
        assert r.status_code == 200
        assert r.mimetype == "text/plain"
        texte = r.get_data(as_text=True)
        assert "User-agent: *" in texte
        assert "Disallow: /" in texte

    def test_il_est_servi_sans_authentification(self, client_sans_cle):
        """Un robot n'a pas de cle d'API : un 401 ici ne dirait rien a personne."""
        assert client_sans_cle.get("/robots.txt").status_code == 200


class TestLaBaliseDansLesPages:
    """Les trois pages HTML servies portent la balise.

    La console et l'application juge la portent aussi : elles n'ont aucune
    raison d'etre indexees, et un oubli se verrait bien plus tard que la pose.
    """

    def _balise(self, reponse):
        html = reponse.get_data(as_text=True)
        return 'name="robots"' in html and "noindex" in html

    def test_page_de_resultats(self, client_sans_cle, jeu):
        assert self._balise(client_sans_cle.get("/"))

    def test_console(self, client_sans_cle):
        assert self._balise(client_sans_cle.get("/console"))

    def test_application_juge(self, client_sans_cle):
        assert self._balise(client_sans_cle.get("/juge"))

    def test_page_de_confidentialite(self, client_sans_cle):
        assert self._balise(client_sans_cle.get("/confidentialite"))


class TestLEnteteSurLApiPublique:
    """⚠️ Les cas d'ERREUR comptent autant que le cas nominal.

    Un `after_request` pose sur la vue plutot que sur le blueprint laisserait
    passer les 404 et les 409 -- c'est-a-dire exactement les adresses qu'un
    robot fabrique en balayant un site.
    """

    def test_sur_le_classement(self, client_sans_cle, jeu):
        r = client_sans_cle.get("/api/public/classement")
        assert r.status_code == 200
        assert r.headers.get("X-Robots-Tag") == "noindex"

    def test_sur_les_reglages_et_les_groupes(self, client_sans_cle, jeu):
        for chemin in ("/api/public/reglages", "/api/public/groupes"):
            assert client_sans_cle.get(chemin).headers.get("X-Robots-Tag") == "noindex"

    def test_sur_un_groupe_inconnu(self, client_sans_cle, jeu):
        r = client_sans_cle.get("/api/public/classement?groupe=Inconnu")
        assert r.status_code == 404
        assert r.headers.get("X-Robots-Tag") == "noindex"

    def test_sur_un_grimpeur_inconnu(self, client_sans_cle, jeu):
        r = client_sans_cle.get("/api/public/grimpeur/9999")
        assert r.status_code == 404
        assert r.headers.get("X-Robots-Tag") == "noindex"

    def test_sur_un_grimpeur_connu(self, client_sans_cle, jeu):
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        r = client_sans_cle.get(f"/api/public/grimpeur/{jeu['participants'][0].id}")
        assert r.status_code == 200
        assert r.headers.get("X-Robots-Tag") == "noindex"

    def test_sans_competition_active(self, client_sans_cle, app):
        """Aucune competition : la route repond une erreur metier, pas un 200."""
        r = client_sans_cle.get("/api/public/classement")
        assert r.status_code >= 400
        assert r.headers.get("X-Robots-Tag") == "noindex"

    def test_l_api_des_juges_n_est_PAS_concernee(self, client, jeu):
        """Le crochet est pose sur le blueprint public, pas sur l'application.

        Ce test dit ce que la regle N'EST PAS. Sans lui, quelqu'un deplacerait
        le crochet sur `app` un jour de refactoring, et personne ne le verrait
        -- l'en-tete serait simplement partout, ce qui se lit comme une regle
        generale qu'il n'est pas.
        """
        r = client.get("/api/v2/catalog")
        assert r.status_code == 200
        assert "X-Robots-Tag" not in r.headers
