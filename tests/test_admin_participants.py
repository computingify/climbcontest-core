"""Participants a chaud et reaffectation (spec 005, IT2).

Le besoin qu'Adrien a decrit en premier : « nous pouvons avoir des ajouts de
participant quelques minutes avant le debut de la competition voire meme alors
que la competition a demarre ».

Sans ces routes, il fallait passer par le classeur puis un reimport -- ce qui
reecrit toute la base au moment ou elle est le plus utilisee.
"""
import pytest

from climbcontest import comptes
from climbcontest.contest import ErreurMetier, ajouter_participant, enregistrer_reussite
from climbcontest.extensions import db
from climbcontest.models import Participant

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, jeu):
    """Un organisateur connecte, et une competition avec des participants."""
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


class TestAjout:

    def test_un_participant_est_ajoute(self, connecte, jeu):
        r = connecte.post("/admin/participants", json={
            "nom": "Nouveau", "prenom": "Venu", "club": "La Grimpe",
            "categorie": "U13 F", "dossard": 42,
        })
        assert r.status_code == 201
        assert r.get_json()["participant"]["dossard"] == 42
        assert Participant.query.filter_by(dossard=42).count() == 1

    def test_le_catalogue_est_incremente(self, connecte, jeu):
        """Sans ca, les telephones ne verraient JAMAIS le nouveau venu : ils ne
        retelechargent que si la version a bouge."""
        avant = jeu["competition"].catalogue_version
        connecte.post("/admin/participants", json={"nom": "Nouveau", "dossard": 42})
        db.session.refresh(jeu["competition"])
        assert jeu["competition"].catalogue_version > avant

    def test_il_apparait_aussitot_dans_le_catalogue(self, connecte, jeu):
        """La preuve de bout en bout : le juge peut le scanner tout de suite."""
        connecte.post("/admin/participants", json={"nom": "Nouveau", "dossard": 42})
        cat = connecte.get("/api/v2/catalog").get_json()
        assert 42 in [p["dossard"] for p in cat["participants"]]

    def test_et_son_qr_est_accepte_par_la_route_du_juge(self, connecte, jeu):
        connecte.post("/admin/participants", json={"nom": "Nouveau", "dossard": 42})
        r = connecte.post("/api/v2/contest/climber/name", json={"id": "42"})
        assert r.status_code == 201, "un ajout a chaud doit etre scannable dans la seconde"

    def test_un_participant_sans_dossard_est_accepte(self, connecte, jeu):
        """L'inscrit qui n'est pas venu : c'est son numero qu'on reprendra."""
        r = connecte.post("/admin/participants", json={"nom": "Absent", "prenom": "Paul"})
        assert r.status_code == 201
        assert r.get_json()["participant"]["dossard"] is None

    def test_sans_nom_c_est_refuse(self, connecte, jeu):
        assert connecte.post("/admin/participants", json={"dossard": 42}).status_code == 400

    def test_un_dossard_deja_pris_est_refuse_avec_le_nom(self, connecte, jeu):
        """« Dossard deja pris » obligerait a chercher dans la liste, au moment
        ou on a le moins de temps."""
        r = connecte.post("/admin/participants", json={"nom": "Doublon", "dossard": 1})
        assert r.status_code == 409
        assert "Dupont" in r.get_json()["message"], "le message doit nommer le porteur"

    def test_deux_homonymes_coexistent(self, connecte, jeu):
        connecte.post("/admin/participants", json={"nom": "Dupont", "prenom": "Lea",
                                                   "dossard": 50})
        r = connecte.post("/admin/participants", json={"nom": "Dupont", "prenom": "Lea",
                                                       "dossard": 51})
        assert r.status_code == 201

    def test_un_dossard_illisible_est_refuse(self, connecte, jeu):
        r = connecte.post("/admin/participants", json={"nom": "X", "dossard": "quarante"})
        assert r.status_code == 400

    def test_un_corps_qui_n_est_pas_un_objet_donne_400(self, connecte, jeu):
        r = connecte.post("/admin/participants", data="[1,2]",
                          content_type="application/json")
        assert r.status_code == 400


class TestReaffectation:

    def test_un_dossard_vierge_change_de_main(self, connecte, jeu):
        absent = jeu["participants"][2]          # sans dossard
        r = connecte.post(f"/admin/participants/{absent.id}/dossard", json={"dossard": 1})
        assert r.status_code == 200
        db.session.refresh(absent)
        assert absent.dossard == 1

    def test_un_dossard_avec_des_reussites_est_refuse(self, connecte, jeu):
        """La regle metier d'Adrien : jamais sur un dossard en cours de
        participation. Elle est ecrite depuis la spec 002 ; on l'expose."""
        enregistrer_reussite(jeu["participants"][0], jeu["blocs"][0])
        absent = jeu["participants"][2]

        r = connecte.post(f"/admin/participants/{absent.id}/dossard", json={"dossard": 1})

        assert r.status_code == 409
        assert "reussite" in r.get_json()["message"].lower()

    def test_un_participant_inconnu_donne_404(self, connecte, jeu):
        assert connecte.post("/admin/participants/99999/dossard",
                             json={"dossard": 7}).status_code == 404

    def test_sans_le_champ_dossard_c_est_400(self, connecte, jeu):
        p = jeu["participants"][2]
        assert connecte.post(f"/admin/participants/{p.id}/dossard",
                             json={}).status_code == 400

    def test_le_catalogue_bouge_aussi(self, connecte, jeu):
        avant = jeu["competition"].catalogue_version
        connecte.post(f"/admin/participants/{jeu['participants'][2].id}/dossard",
                      json={"dossard": 1})
        db.session.refresh(jeu["competition"])
        assert jeu["competition"].catalogue_version > avant


class TestListe:

    def test_la_liste_est_triee_par_dossard(self, connecte, jeu):
        d = connecte.get("/admin/participants").get_json()
        dossards = [p["dossard"] for p in d["participants"] if p["dossard"]]
        assert dossards == sorted(dossards)

    def test_les_sans_dossard_sont_a_la_fin(self, connecte, jeu):
        d = connecte.get("/admin/participants").get_json()
        assert d["participants"][-1]["dossard"] is None

    def test_la_recherche_par_nom(self, connecte, jeu):
        d = connecte.get("/admin/participants?q=dupont").get_json()
        assert len(d["participants"]) == 1
        assert "Dupont" in d["participants"][0]["nom"]

    def test_la_recherche_par_dossard(self, connecte, jeu):
        d = connecte.get("/admin/participants?q=1").get_json()
        assert [p["dossard"] for p in d["participants"]] == [1]


class TestAccesRefuse:
    """Tout ceci vit derriere l'authentification, sans exception."""

    @pytest.mark.parametrize("methode,chemin", [
        ("get", "/admin/participants"),
        ("post", "/admin/participants"),
        ("post", "/admin/participants/1/dossard"),
    ])
    def test_sans_session_c_est_refuse(self, client, app, jeu, methode, chemin):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        r = getattr(client, methode)(chemin, json={})
        assert r.status_code == 401

    def test_et_rien_n_est_ecrit(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        avant = Participant.query.count()
        client.post("/admin/participants", json={"nom": "Intrus", "dossard": 77})
        assert Participant.query.count() == avant


class TestFonctionMetier:
    """La fonction elle-meme, sans HTTP."""

    def test_la_source_est_manuelle(self, app, jeu):
        from climbcontest.models import SOURCE_MANUEL
        p = ajouter_participant("Nouveau", dossard=42)
        assert p.source == SOURCE_MANUEL, \
            "l'origine doit rester distinguable de l'import du classeur"

    def test_present_est_pose_si_un_dossard_est_donne(self, app, jeu):
        assert ajouter_participant("Avec", dossard=42).present is True
        assert ajouter_participant("Sans").present is False

    def test_les_champs_vides_deviennent_nuls(self, app, jeu):
        p = ajouter_participant("Nom", prenom="  ", club="", categorie=None)
        assert p.prenom is None and p.club is None and p.categorie is None

    def test_sans_competition_active_c_est_refuse(self, app):
        with pytest.raises(ErreurMetier):
            ajouter_participant("Nouveau", dossard=1)
