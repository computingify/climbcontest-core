"""Le contrat de l'application juge v3.1.4 — le test qui ne doit jamais casser.

L'application est déployée sur le Play Store et ne sera pas mise à jour avant la
spec 003. Ces tests décrivent **exactement** ce qu'elle envoie et ce qu'elle
attend, tel que lu dans `Server.kt` et `MainActivity.kt`.

Si l'un d'eux tombe, l'application ne marche plus le jour de la compétition.
"""

from climbcontest.extensions import db
from climbcontest.models import Success


class TestVerificationGrimpeur:
    """Server.kt : payload {"id": scannedValue}, lit result.data["id"]."""

    def test_dossard_connu_renvoie_201_et_le_nom(self, client, jeu):
        r = client.post("/api/v2/contest/climber/name", json={"id": "1"})
        assert r.status_code == 201
        corps = r.get_json()
        assert corps["success"] is True
        # L'application affiche cette valeur : c'est le NOM, pas le dossard.
        assert corps["id"] == "Dupont Lea"

    def test_le_dossard_arrive_en_texte(self, client, jeu):
        """Le QR code est scanné comme une chaîne, jamais comme un entier."""
        assert client.post("/api/v2/contest/climber/name",
                           json={"id": "1"}).status_code == 201

    def test_dossard_inconnu_renvoie_400_avec_message(self, client, jeu):
        r = client.post("/api/v2/contest/climber/name", json={"id": "999"})
        assert r.status_code == 400
        assert r.get_json()["success"] is False
        assert r.get_json()["message"]

    def test_corps_vide(self, client, jeu):
        r = client.post("/api/v2/contest/climber/name", json={})
        assert r.status_code == 400
        assert r.get_json()["success"] is False


class TestVerificationBloc:
    def test_tag_connu_renvoie_201_et_le_tag(self, client, jeu):
        r = client.post("/api/v2/contest/bloc/name", json={"id": "ZJ6"})
        assert r.status_code == 201
        assert r.get_json()["success"] is True
        assert r.get_json()["id"] == "ZJ6"

    def test_tag_inconnu(self, client, jeu):
        r = client.post("/api/v2/contest/bloc/name", json={"id": "XX99"})
        assert r.status_code == 400
        assert r.get_json()["success"] is False


class TestEnregistrementReussite:
    """Server.kt : payload {"bib": climberId, "bloc": blocId}."""

    def test_reussite_valide(self, client, jeu):
        r = client.post("/api/v2/contest/success", json={"bib": "1", "bloc": "ZJ6"})
        assert r.status_code == 201
        assert r.get_json()["success"] is True
        assert Success.query.count() == 1

    def test_double_envoi_renvoie_201_et_une_seule_ligne(self, client, jeu):
        """Le point le plus important de la spec 002.

        Un double appui sur « Envoyer » ne doit PAS produire d'erreur : le juge
        croirait que ça n'a pas marché et recommencerait. Et il ne doit pas
        produire deux réussites : le classement compte les lignes.
        """
        for _ in range(3):
            r = client.post("/api/v2/contest/success", json={"bib": "1", "bloc": "ZJ6"})
            assert r.status_code == 201
            assert r.get_json()["success"] is True
        assert Success.query.count() == 1

    def test_donnees_manquantes(self, client, jeu):
        for corps in ({}, {"bib": "1"}, {"bloc": "ZJ6"}):
            r = client.post("/api/v2/contest/success", json=corps)
            assert r.status_code == 400
            assert r.get_json()["success"] is False

    def test_dossard_inconnu(self, client, jeu):
        r = client.post("/api/v2/contest/success", json={"bib": "999", "bloc": "ZJ6"})
        assert r.status_code == 400
        assert Success.query.count() == 0

    def test_bloc_hors_circuit_est_accepte(self, client, jeu):
        """Un bloc hors du circuit du grimpeur est enregistré quand même.

        Le classeur enregistre la réussite dans l'onglet Import et l'ignore au
        moment de calculer — c'est le moteur de classement qui filtre (spec 004),
        pas la saisie. On n'invente pas une règle que le classeur n'applique pas :
        refuser ici ferait perdre une information que le juge a réellement vue.
        """
        # Dossard 1 est en U11 F ; DV21 n'est que dans le circuit U13.
        r = client.post("/api/v2/contest/success", json={"bib": "1", "bloc": "DV21"})
        assert r.status_code == 201
        assert Success.query.count() == 1


class TestReussitesPersistees:
    def test_la_reussite_est_en_base_avant_la_reponse(self, client, jeu):
        client.post("/api/v2/contest/success", json={"bib": "1", "bloc": "ZJ6"})
        s = Success.query.one()
        assert s.horodatage is not None
        # NULL = pas encore dans le classeur. C'est ce qui remplace la file RAM.
        assert s.sheet_synced_at is None

    def test_survit_a_une_nouvelle_session(self, client, jeu):
        """Simule un redémarrage : la session est vidée, la donnée reste."""
        client.post("/api/v2/contest/success", json={"bib": "1", "bloc": "ZJ6"})
        db.session.expunge_all()
        assert Success.query.count() == 1
