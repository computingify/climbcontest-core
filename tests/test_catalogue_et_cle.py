"""Le catalogue versionné, et la clé d'API en mode toléré.

Le catalogue est ce qui permettra à l'application juge de valider un scan hors
ligne tout en voyant un participant ajouté en cours de compétition.

La clé d'API est délicate : l'application `v3.1.4` du Play Store n'en envoie
aucune. La rendre obligatoire aujourd'hui la casserait.
"""

import pytest

from climbcontest.auth import compteurs
from climbcontest.contest import incrementer_catalogue
from climbcontest.extensions import db
from climbcontest.models import Participant


class TestCatalogue:
    def test_contenu(self, client, jeu):
        d = client.get("/api/v2/catalog").get_json()
        assert d["version"] >= 1
        # Le participant sans dossard n'est pas scannable : il n'y figure pas.
        assert len(d["participants"]) == 2
        assert len(d["blocs"]) == 3
        assert set(d["circuits"]) == {"U11", "U13"}

    def test_le_bloc_porte_ses_circuits(self, client, jeu):
        d = client.get("/api/v2/catalog").get_json()
        zj6 = next(b for b in d["blocs"] if b["tag"] == "ZJ6")
        assert set(zj6["circuits"]) == {"U11", "U13"}

    def test_304_si_rien_n_a_change(self, client, jeu):
        version = client.get("/api/v2/catalog").get_json()["version"]
        assert client.get(f"/api/v2/catalog?depuis={version}").status_code == 304

    def test_renvoie_tout_si_la_version_a_bouge(self, client, jeu):
        """Le cas réel : un participant ajouté à 14 h doit arriver sur les
        tablettes sans qu'on les redémarre."""
        version = client.get("/api/v2/catalog").get_json()["version"]

        db.session.add(Participant(competition_id=jeu["competition"].id,
                                   nom="Tardif", dossard=42))
        jeu["competition"].catalogue_version += 1
        db.session.commit()

        r = client.get(f"/api/v2/catalog?depuis={version}")
        assert r.status_code == 200
        assert any(p["dossard"] == 42 for p in r.get_json()["participants"])

    def test_une_modification_incremente_la_version(self, client, jeu):
        """Le dossard ne change plus (05/09) ; le reste, si. C'est
        `incrementer_catalogue()` qui previent les telephones."""
        version = client.get("/api/v2/catalog").get_json()["version"]
        jeu["participants"][2].club = "CAF Vivarais"
        incrementer_catalogue(jeu["competition"])
        assert client.get("/api/v2/catalog").get_json()["version"] > version

    def test_sans_competition_active(self, client, app):
        assert client.get("/api/v2/catalog").status_code == 409


class TestCleApiTolere:
    """Le regime de repli, atteignable par `CLIMBCONTEST_API_KEY_STRICTE=0`.

    Il n'est plus le defaut depuis la spec 012, mais il doit continuer de
    marcher : le gel `V3.1.4`, plan de repli garanti de novembre, n'envoie
    aucune cle.
    """

    def setup_method(self):
        for k in compteurs:
            compteurs[k] = 0

    def test_sans_cle_acceptee_mais_comptee(self, client_sans_cle, jeu, app):
        app.config["API_KEY_STRICTE"] = False
        try:
            assert client_sans_cle.get("/api/v2/catalog").status_code == 200
            assert compteurs["sans_cle"] == 1
        finally:
            app.config["API_KEY_STRICTE"] = True

    def test_bonne_cle_acceptee(self, client, jeu):
        assert client.get("/api/v2/catalog").status_code == 200
        assert compteurs["avec_cle"] == 1

    def test_mauvaise_cle_refusee_meme_en_mode_tolere(self, client_sans_cle, jeu, app):
        """Quelqu'un qui envoie une fausse clé n'est pas l'application
        d'origine : on refuse dans les deux modes."""
        app.config["API_KEY_STRICTE"] = False
        try:
            r = client_sans_cle.get("/api/v2/catalog",
                                    headers={"X-Api-Key": "pas-la-bonne"})
            assert r.status_code == 401
            assert compteurs["refusees"] == 1
        finally:
            app.config["API_KEY_STRICTE"] = True


class TestCorpsMalforme:
    """Un corps inattendu ne doit jamais produire un 500.

    Le garde-fou lisait `api_key` dans le corps JSON sans verifier que c'en
    etait bien un objet : poster `[1,2]` levait une AttributeError et la route
    repondait 500. C'est ce qu'un scanner de vulnerabilites trouve en premier,
    et un 500 sur une route de juge est indistinguable d'une vraie panne.
    """

    def setup_method(self):
        for k in compteurs:
            compteurs[k] = 0

    @pytest.mark.parametrize("corps", ['[1, 2]', '"une chaine"', '42', 'null', 'true'])
    def test_un_json_qui_n_est_pas_un_objet_ne_fait_pas_planter(self, client, jeu, corps):
        r = client.post("/api/v2/contest/climber/name", data=corps,
                        content_type="application/json")
        assert r.status_code != 500, f"corps {corps} a produit une erreur serveur"

    def test_un_corps_qui_n_est_pas_du_json_ne_fait_pas_planter(self, client, jeu):
        r = client.post("/api/v2/contest/success", data="<xml/>",
                        content_type="application/json")
        assert r.status_code != 500

    def test_une_liste_avec_la_bonne_cle_dans_l_entete_reste_acceptee(self, client, jeu):
        """La clé de l'en-tête doit être lue avant même de regarder le corps."""
        r = client.post("/api/v2/contest/climber/name", data='[1, 2]',
                        content_type="application/json",
                        headers={"X-Api-Key": "cle-de-test"})
        assert r.status_code != 500
        assert compteurs["avec_cle"] == 1, "la cle de l'en-tete doit avoir ete vue"


class TestCleApiStricte:
    """Le regime PAR DEFAUT depuis la spec 012."""

    def setup_method(self):
        for k in compteurs:
            compteurs[k] = 0

    def test_le_defaut_est_strict(self, app):
        """Une installation qui oublie la variable doit etre fermee, pas ouverte."""
        assert app.config["API_KEY_STRICTE"] is True

    def test_sans_cle_refusee(self, client_sans_cle, jeu):
        assert client_sans_cle.get("/api/v2/catalog").status_code == 401

    def test_avec_cle_acceptee(self, client, jeu):
        assert client.get("/api/v2/catalog").status_code == 200

    def test_les_routes_publiques_restent_ouvertes(self, client_sans_cle, jeu):
        """Les spectateurs n'ont pas de cle, et n'en auront jamais."""
        assert client_sans_cle.get("/api/public/classement").status_code == 200
        assert client_sans_cle.get("/api/public/groupes").status_code == 200


class TestPlusieursCles:
    """Changer de cle sans jour de bascule (spec 012)."""

    def test_les_deux_cles_passent(self, client_sans_cle, jeu, app):
        app.config["API_KEYS"] = ("courante", "precedente")
        try:
            for cle in ("courante", "precedente"):
                r = client_sans_cle.get("/api/v2/catalog", headers={"X-Api-Key": cle})
                assert r.status_code == 200, cle
        finally:
            app.config["API_KEYS"] = ("cle-de-test",)

    def test_une_cle_retiree_ne_passe_plus(self, client_sans_cle, jeu, app):
        app.config["API_KEYS"] = ("courante",)
        try:
            r = client_sans_cle.get("/api/v2/catalog",
                                    headers={"X-Api-Key": "precedente"})
            assert r.status_code == 401
        finally:
            app.config["API_KEYS"] = ("cle-de-test",)

    def test_une_chaine_vide_n_est_pas_une_cle(self):
        """`CLIMBCONTEST_API_KEY=` ne doit pas ouvrir la porte a `X-Api-Key: `."""
        from climbcontest.config import cles_depuis_environnement as lire

        assert lire({"CLIMBCONTEST_API_KEY": ""}) == ()
        assert lire({"CLIMBCONTEST_API_KEY": "   "}) == ()
        assert lire({}) == ()

    def test_les_deux_variables_alimentent_le_tuple(self):
        from climbcontest.config import cles_depuis_environnement as lire

        assert lire({"CLIMBCONTEST_API_KEY": "a",
                     "CLIMBCONTEST_API_KEY_PRECEDENTE": "b"}) == ("a", "b")

    def test_une_cle_est_nettoyee_de_ses_espaces(self):
        """Une variable posee dans un fichier d'environnement traine souvent
        un espace ou un retour a la ligne. Le telephone, lui, envoie la cle
        exacte : sans ce nettoyage, la comparaison echouerait sans que personne
        ne comprenne pourquoi."""
        from climbcontest.config import cles_depuis_environnement as lire

        assert lire({"CLIMBCONTEST_API_KEY": "  secrete\n"}) == ("secrete",)


class TestConfigurationIncoherente:
    """Mode strict et aucune cle : dire ce qui se passe, pas `401`.

    Un `401` enverrait chercher un probleme de cle cote application, alors que
    la variable est absente cote serveur.
    """

    def test_503_et_pas_401(self, client, jeu, app):
        app.config["API_KEYS"] = ()
        try:
            r = client.get("/api/v2/catalog")
            assert r.status_code == 503
            assert "CLIMBCONTEST_API_KEY" in r.get_json()["message"]
        finally:
            app.config["API_KEYS"] = ("cle-de-test",)

    def test_la_sonde_passe_en_degraded(self, client, jeu, app):
        """C'est ce qui doit faire echouer le deploiement.

        Sans cette verification, l'agent de deploiement verrait « ok »,
        validerait la mise en production, et la panne se decouvrirait quand
        vingt-cinq juges commenceraient a scanner.
        """
        app.config["API_KEYS"] = ()
        try:
            r = client.get("/health")
            assert r.status_code == 503
            d = r.get_json()
            assert d["status"] == "degraded"
            assert "CLIMBCONTEST_API_KEY" in d["cle_api"]
        finally:
            app.config["API_KEYS"] = ("cle-de-test",)

    def test_la_sonde_reste_ok_en_mode_tolere_sans_cle(self, client, jeu, app):
        """Sans cle ET en mode tolere, la configuration est coherente : c'est le
        repli, et il ne doit pas faire echouer un deploiement."""
        app.config["API_KEYS"] = ()
        app.config["API_KEY_STRICTE"] = False
        try:
            r = client.get("/health")
            assert r.status_code == 200
            assert r.get_json()["status"] == "ok"
        finally:
            app.config["API_KEYS"] = ("cle-de-test",)
            app.config["API_KEY_STRICTE"] = True

    def test_le_mode_tolere_sans_cle_reste_utilisable(self, client_sans_cle, jeu, app):
        """Sans cle ET en mode tolere, ce n'est pas incoherent : c'est le repli."""
        app.config["API_KEYS"] = ()
        app.config["API_KEY_STRICTE"] = False
        try:
            assert client_sans_cle.get("/api/v2/catalog").status_code == 200
        finally:
            app.config["API_KEYS"] = ("cle-de-test",)
            app.config["API_KEY_STRICTE"] = True


class TestSanteComplete:
    def test_expose_les_compteurs(self, client, jeu):
        d = client.get("/health").get_json()
        assert d["status"] == "ok"
        assert "reussites_en_attente" in d
        assert {"sans_cle", "avec_cle", "refusees"} <= set(d["api"])
        # Le regime et le NOMBRE de cles, jamais les cles.
        assert d["api"]["regime"] == "strict"
        assert d["api"]["cles_acceptees"] == 1
        assert "cle-de-test" not in client.get("/health").get_data(as_text=True)
        assert "miroir_actif" in d

    def test_annonce_que_le_compteur_est_local_au_worker(self, client, jeu):
        """Sans cette mention, le chiffre serait lu comme un total.

        Avec quatre workers gunicorn, `/health` ne montre que la vue de celui
        qui a répondu : conclure « plus personne n'appelle sans clé » ferait
        activer le mode strict et casserait l'application v3.1.4.
        """
        api = client.get("/health").get_json()["api"]
        assert api["portee"] == "ce worker seulement"
        assert isinstance(api["pid"], int)


class TestEtagCatalogue:
    """Le catalogue doit pouvoir dire « rien n'a change » pour 150 octets.

    Deux mecanismes, parce qu'ils ne servent pas au meme public : `?depuis=`
    pour l'application juge qui garde sa version, `If-None-Match` pour tout ce
    qui parle HTTP standard — Caddy, un cache, un navigateur.

    Les specs 002 et 003 annoncaient une reponse DIFFERENTIELLE. C'est
    volontairement abandonne : a 6-8 ko compresses, un delta couterait un suivi
    des suppressions pour economiser quelques kilo-octets. Les specs ont ete
    corrigees plutot que le code.
    """

    def test_l_etiquette_est_presente(self, client, jeu):
        r = client.get("/api/v2/catalog")
        assert r.status_code == 200
        assert r.headers.get("ETag"), "sans ETag, aucun cache ne peut revalider"

    def test_la_meme_etiquette_donne_304(self, client, jeu):
        etiquette = client.get("/api/v2/catalog").headers["ETag"]
        r = client.get("/api/v2/catalog", headers={"If-None-Match": etiquette})
        assert r.status_code == 304
        assert r.get_data() == b"", "un 304 ne porte pas de corps"

    def test_une_etiquette_faible_est_acceptee(self, client, jeu):
        """Certains caches prefixent l'etiquette par W/."""
        etiquette = client.get("/api/v2/catalog").headers["ETag"]
        r = client.get("/api/v2/catalog", headers={"If-None-Match": f"W/{etiquette}"})
        assert r.status_code == 304

    def test_plusieurs_etiquettes_dont_la_bonne(self, client, jeu):
        etiquette = client.get("/api/v2/catalog").headers["ETag"]
        r = client.get("/api/v2/catalog",
                       headers={"If-None-Match": f'"1234", {etiquette}'})
        assert r.status_code == 304

    def test_une_etiquette_perimee_renvoie_le_catalogue(self, client, jeu):
        r = client.get("/api/v2/catalog", headers={"If-None-Match": '"0"'})
        assert r.status_code == 200
        assert r.get_json()["participants"]

    def test_l_etiquette_change_quand_le_catalogue_change(self, client, jeu):
        avant = client.get("/api/v2/catalog").headers["ETag"]

        jeu["participants"][2].club = "CAF Vivarais"
        incrementer_catalogue(jeu["competition"])

        apres = client.get("/api/v2/catalog").headers["ETag"]
        assert apres != avant, "un participant a change : l'etiquette doit bouger"
        r = client.get("/api/v2/catalog", headers={"If-None-Match": avant})
        assert r.status_code == 200, "l'ancienne etiquette ne doit plus valoir"

    def test_le_304_porte_l_etiquette_courante(self, client, jeu):
        """Sinon un cache ne saurait pas quoi conserver."""
        etiquette = client.get("/api/v2/catalog").headers["ETag"]
        r = client.get("/api/v2/catalog", headers={"If-None-Match": etiquette})
        assert r.headers.get("ETag") == etiquette

    def test_depuis_marche_toujours(self, client, jeu):
        """L'application juge s'en sert : il ne doit pas casser."""
        version = client.get("/api/v2/catalog").get_json()["version"]
        assert client.get(f"/api/v2/catalog?depuis={version}").status_code == 304
        assert client.get(f"/api/v2/catalog?depuis={version - 1}").status_code == 200

    def test_depuis_absurde_renvoie_le_catalogue_complet(self, client, jeu):
        """Jamais une erreur : une application avec une version corrompue doit
        pouvoir repartir."""
        for valeur in ("abc", "-1", "999999"):
            r = client.get(f"/api/v2/catalog?depuis={valeur}")
            assert r.status_code in (200, 304), f"depuis={valeur} -> {r.status_code}"


class TestAdministrationProtegee:
    """La console d'administration ne doit JAMAIS profiter du mode tolere.

    Constate sur la VM le 28/08, en production et expose sur Internet :
    `GET /admin/import/rapport` repondait 200 sans aucune authentification, et
    un POST sur `/admin/import/sheet` aurait declenche un reimport complet du
    classeur -- reecriture de la base et rafale d'appels Google -- a la demande
    de n'importe qui.

    La cle d'API stricte etait une mesure d'attente. Depuis la spec 005, ces
    routes exigent une SESSION : la cle d'API, meme valide, ne donne plus acces
    a l'administration. Le detail est dans tests/test_comptes_et_session.py ;
    ce qui reste ici est le garde-fou de non-regression, place a cote du mode
    tolere pour qu'on ne les reconfonde pas.
    """

    def setup_method(self):
        for k in compteurs:
            compteurs[k] = 0

    @pytest.mark.parametrize("methode,chemin", [
        ("post", "/admin/import/sheet"),
        ("get", "/admin/import/rapport"),
    ])
    def test_sans_authentification_c_est_refuse(self, client, jeu, methode, chemin):
        r = getattr(client, methode)(chemin)
        assert r.status_code in (401, 503), "le mode tolere ne doit pas s'appliquer ici"

    @pytest.mark.parametrize("methode,chemin", [
        ("post", "/admin/import/sheet"),
        ("get", "/admin/import/rapport"),
    ])
    def test_meme_avec_une_cle_d_api_valide(self, client, jeu, methode, chemin):
        """La cle d'API sert aux juges, pas aux organisateurs.

        Elle est partagee entre 25 telephones : en faire un droit
        d'administration reviendrait a donner les cles de la base a tout le
        monde.
        """
        r = getattr(client, methode)(chemin, headers={"X-Api-Key": "cle-de-test"})
        assert r.status_code in (401, 503)

    def test_les_routes_du_juge_restent_tolerantes(self, client, jeu):
        """Le durcissement ne doit surtout pas deborder sur la v3.1.4."""
        assert client.post("/api/v2/contest/climber/name",
                           json={"id": "1"}).status_code == 201
