"""Le catalogue versionné, et la clé d'API en mode toléré.

Le catalogue est ce qui permettra à l'application juge de valider un scan hors
ligne tout en voyant un participant ajouté en cours de compétition.

La clé d'API est délicate : l'application `v3.1.4` du Play Store n'en envoie
aucune. La rendre obligatoire aujourd'hui la casserait.
"""

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
        assert set(d["api"]) == {"sans_cle", "avec_cle", "refusees"}
        assert "miroir_actif" in d
