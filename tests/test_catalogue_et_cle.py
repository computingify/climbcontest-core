"""Le catalogue versionné, et la clé d'API en mode toléré.

Le catalogue est ce qui permettra à l'application juge de valider un scan hors
ligne tout en voyant un participant ajouté en cours de compétition.

La clé d'API est délicate : l'application `v3.1.4` du Play Store n'en envoie
aucune. La rendre obligatoire aujourd'hui la casserait.
"""

import pytest

from climbcontest.auth import compteurs
from climbcontest.contest import reaffecter_dossard
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

    def test_la_reaffectation_incremente_la_version(self, client, jeu):
        version = client.get("/api/v2/catalog").get_json()["version"]
        reaffecter_dossard(jeu["participants"][2], 2)
        assert client.get("/api/v2/catalog").get_json()["version"] > version

    def test_sans_competition_active(self, client, app):
        assert client.get("/api/v2/catalog").status_code == 409


class TestCleApiTolere:
    """Mode par défaut, tant que l'application v3.1.4 est en service."""

    def setup_method(self):
        for k in compteurs:
            compteurs[k] = 0

    def test_sans_cle_acceptee_mais_comptee(self, client, jeu):
        """C'est ce que fait l'application déployée : aucune clé.

        Le compteur est ce qui dira quand on pourra passer en mode strict — le
        jour où il reste à zéro pendant toute une compétition.
        """
        assert client.get("/api/v2/catalog").status_code == 200
        assert compteurs["sans_cle"] == 1

    def test_bonne_cle_acceptee(self, client, jeu):
        r = client.get("/api/v2/catalog", headers={"X-Api-Key": "cle-de-test"})
        assert r.status_code == 200
        assert compteurs["avec_cle"] == 1

    def test_mauvaise_cle_refusee_meme_en_mode_tolere(self, client, jeu):
        """Quelqu'un qui envoie une fausse clé n'est pas l'application
        d'origine : on refuse dans les deux modes."""
        r = client.get("/api/v2/catalog", headers={"X-Api-Key": "pas-la-bonne"})
        assert r.status_code == 401
        assert compteurs["refusees"] == 1


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
    def setup_method(self):
        for k in compteurs:
            compteurs[k] = 0

    def test_sans_cle_refusee(self, client, jeu, app):
        app.config["API_KEY_STRICTE"] = True
        try:
            assert client.get("/api/v2/catalog").status_code == 401
        finally:
            app.config["API_KEY_STRICTE"] = False

    def test_avec_cle_acceptee(self, client, jeu, app):
        app.config["API_KEY_STRICTE"] = True
        try:
            r = client.get("/api/v2/catalog", headers={"X-Api-Key": "cle-de-test"})
            assert r.status_code == 200
        finally:
            app.config["API_KEY_STRICTE"] = False


class TestSanteComplete:
    def test_expose_les_compteurs(self, client, jeu):
        d = client.get("/health").get_json()
        assert d["status"] == "ok"
        assert "reussites_en_attente" in d
        assert {"sans_cle", "avec_cle", "refusees"} <= set(d["api"])
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
        from climbcontest.contest import reaffecter_dossard
        avant = client.get("/api/v2/catalog").headers["ETag"]

        reaffecter_dossard(jeu["participants"][2], 42)

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
    classeur — reecriture de la base et rafale d'appels Google — a la demande
    de n'importe qui.

    Le mode tolere existe pour UNE raison : l'application v3.1.4 du Play Store
    n'envoie pas de cle. Elle n'appelle pas ces routes-la.
    """

    def setup_method(self):
        for k in compteurs:
            compteurs[k] = 0

    @pytest.mark.parametrize("methode,chemin", [
        ("post", "/admin/import/sheet"),
        ("get", "/admin/import/rapport"),
    ])
    def test_sans_cle_refuse_meme_en_mode_tolere(self, client, jeu, methode, chemin):
        r = getattr(client, methode)(chemin)
        assert r.status_code == 401, "le mode tolere ne doit pas s'appliquer ici"
        assert "authentification" in r.get_json()["message"].lower()

    @pytest.mark.parametrize("methode,chemin", [
        ("post", "/admin/import/sheet"),
        ("get", "/admin/import/rapport"),
    ])
    def test_avec_une_mauvaise_cle_refuse(self, client, jeu, methode, chemin):
        r = getattr(client, methode)(chemin, headers={"X-Api-Key": "pas-la-bonne"})
        assert r.status_code == 401

    def test_avec_la_bonne_cle_la_route_repond(self, client, jeu):
        r = client.get("/admin/import/rapport", headers={"X-Api-Key": "cle-de-test"})
        assert r.status_code == 200

    def test_le_refus_est_journalise(self, client, jeu, caplog):
        """Une tentative d'acces a l'administration doit laisser une trace."""
        import logging
        with caplog.at_level(logging.WARNING, logger="climbcontest.auth"):
            client.get("/admin/import/rapport")
        assert any("administration" in m for m in caplog.messages)

    def test_les_routes_du_juge_restent_tolerantes(self, client, jeu):
        """Le durcissement ne doit surtout pas deborder sur la v3.1.4."""
        assert client.post("/api/v2/contest/climber/name",
                           json={"id": "1"}).status_code == 201
