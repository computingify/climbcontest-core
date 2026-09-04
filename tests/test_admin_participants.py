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

    def test_sans_dossard_la_route_en_attribue_un(self, connecte, jeu):
        """Spec 013 : le dossard n'est plus saisi, il est attribue.

        Le jeu porte les dossards 1 et 2 (plus un inscrit sans numero) : le
        prochain libre est donc 3.

        ⚠️ Ce test REMPLACE `test_un_participant_sans_dossard_est_accepte`, qui
        verifiait l'inverse. Le contrat de la ROUTE change ; celui de la
        fonction metier, non -- voir `test_present_est_pose_si_un_dossard_est_donne`.
        """
        r = connecte.post("/admin/participants", json={"nom": "Absent", "prenom": "Paul"})
        assert r.status_code == 201
        assert r.get_json()["participant"]["dossard"] == 3

    def test_les_champs_saisis_sont_formates(self, connecte, jeu):
        """Critere A6 : le formatage tient meme sans passer par la console."""
        r = connecte.post("/admin/participants", json={
            "nom": "DUPONT", "prenom": "jean-luc",
            "club": "CAF annonay", "categorie": "u13f",
        })
        assert r.status_code == 201
        p = r.get_json()["participant"]
        # `nom_complet` = nom puis prenom. « DUPONT » -> « Dupont » (casse
        # stricte sur une personne), « jean-luc » -> « Jean-Luc ».
        assert p["nom"] == "Dupont Jean-Luc"
        assert p["club"] == "CAF Annonay"
        assert p["categorie"] == "U13 F"

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


class TestLaReaffectationAEteRetiree:
    """Le dossard ne se change plus depuis la console — décision du 05/09.

    La route existait pour donner le dossard d'un absent à un arrivant de
    dernière minute. Elle fabriquait le doublon que la spec 008 promet
    d'empêcher : l'absent repartait sans numéro, et l'import du classeur, qui ne
    le retrouvait plus, **recréait sa fiche**.

    Le remplacement n'est pas une gêne : `ajouter_participant_numerote()` donne
    le premier numéro libre, et la console imprime la fiche.
    """

    def test_la_route_n_existe_plus(self, connecte, jeu):
        absent = jeu["participants"][2]
        r = connecte.post(f"/admin/participants/{absent.id}/dossard",
                          json={"dossard": 1})
        assert r.status_code == 404
        db.session.refresh(absent)
        assert absent.dossard is None

    def test_le_crayon_ne_la_remplace_pas(self, connecte, jeu):
        """Retirer une route et rouvrir le même geste ailleurs ne protégerait
        rien : c'est exactement comme ça que les règles reviennent."""
        absent = jeu["participants"][2]
        r = connecte.patch(f"/admin/participants/{absent.id}", json={"dossard": 1})
        assert r.status_code == 409
        db.session.refresh(absent)
        assert absent.dossard is None

    def test_la_fonction_metier_a_disparu_avec_elle(self):
        """Une fonction laissée en place se rebranche un jour « puisqu'elle est
        là ». Celle-ci est supprimée, pas neutralisée."""
        from climbcontest import contest
        assert not hasattr(contest, "reaffecter_dossard")


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


class TestProchainDossard:
    """L'attribution du numero (spec 013, decision d'Adrien du 30/08).

    « On ne prend que des emplacements de dossard libre, et deux navigateurs ne
    peuvent pas prendre le meme numero s'ils font une demande en meme temps. »
    """

    def test_le_premier_trou_est_comble(self, app, competition):
        from climbcontest.contest import prochain_dossard
        for numero in (1, 2, 3, 7, 8):
            db.session.add(Participant(competition_id=competition.id,
                                       nom=f"P{numero}", dossard=numero))
        db.session.commit()
        assert prochain_dossard(competition) == 4

    def test_sans_trou_c_est_la_suite(self, app, competition):
        from climbcontest.contest import prochain_dossard
        for numero in range(1, 110):
            db.session.add(Participant(competition_id=competition.id,
                                       nom=f"P{numero}", dossard=numero))
        db.session.commit()
        assert prochain_dossard(competition) == 110

    def test_base_vide_commence_a_un(self, app, competition):
        from climbcontest.contest import prochain_dossard
        assert prochain_dossard(competition) == 1

    def test_les_sans_dossard_ne_comptent_pas(self, app, competition):
        """Un inscrit sans numero ne bloque aucun emplacement."""
        from climbcontest.contest import prochain_dossard
        db.session.add(Participant(competition_id=competition.id, nom="Absent"))
        db.session.commit()
        assert prochain_dossard(competition) == 1

    def test_deux_inscriptions_de_suite_ne_partagent_pas_le_numero(self, app, jeu):
        from climbcontest.contest import ajouter_participant_numerote
        a = ajouter_participant_numerote("Premier")
        b = ajouter_participant_numerote("Second")
        assert a.dossard != b.dossard
        assert {a.dossard, b.dossard} == {3, 4}

    def test_la_course_perdue_est_retentee(self, app, jeu, monkeypatch):
        """Le cas des « 2 navigateurs en meme temps ».

        On simule : le calcul rend d'abord un numero DEJA PRIS -- exactement ce
        que voit le second navigateur qui a calcule avant que le premier
        n'ecrive. La contrainte d'unicite refuse, et la retente doit aboutir.
        """
        from climbcontest import contest
        vrai = contest.prochain_dossard
        appels = {"n": 0}

        def calcul_en_retard(comp):
            appels["n"] += 1
            return 1 if appels["n"] == 1 else vrai(comp)   # 1 est deja pris

        monkeypatch.setattr(contest, "prochain_dossard", calcul_en_retard)
        p = contest.ajouter_participant_numerote("Retardataire")
        assert appels["n"] >= 2, "la premiere tentative aurait du echouer"
        assert p.dossard == 3

    def test_l_echec_repete_remonte(self, app, jeu, monkeypatch):
        """Au-dela des essais, ce n'est plus une course mais un defaut."""
        from climbcontest import contest
        monkeypatch.setattr(contest, "prochain_dossard", lambda comp: 1)
        with pytest.raises(ErreurMetier) as e:
            contest.ajouter_participant_numerote("Malchanceux")
        assert e.value.code == 409

    def test_present_est_pose_par_l_attribution(self, app, jeu):
        """Qui recoit un dossard est la : c'est quelqu'un devant le guichet."""
        from climbcontest.contest import ajouter_participant_numerote
        assert ajouter_participant_numerote("Venu").present is True


class TestReferentiels:
    """Les listes qui remplissent les menus deroulants (spec 013, IT3)."""

    def test_les_valeurs_connues_sont_rendues(self, connecte, jeu):
        d = connecte.get("/admin/referentiels").get_json()
        assert d["success"] is True
        assert d["categories"] == ["U11 F", "U11 H", "U13 H"]
        assert d["clubs"] == ["La Grimpe", "Les Lezards"]

    def test_pas_de_nul_dans_les_listes(self, connecte, jeu):
        """L'inscrit « Absent » n'a pas de club : il ne doit pas creer un trou."""
        d = connecte.get("/admin/referentiels").get_json()
        assert None not in d["clubs"] and "" not in d["clubs"]

    def test_une_valeur_inedite_rejoint_la_liste(self, connecte, jeu):
        """C'est ca, « un moyen d'en ajouter » : l'ecrire une fois."""
        connecte.post("/admin/participants",
                      json={"nom": "Neuf", "club": "CAF annonay", "categorie": "u17f"})
        d = connecte.get("/admin/referentiels").get_json()
        assert "CAF Annonay" in d["clubs"]
        assert "U17 F" in d["categories"]

    def test_sans_competition_active_ce_n_est_pas_une_erreur(self, connecte, jeu):
        """Le formulaire doit rester utilisable : « Autre… » suffit."""
        jeu["competition"].active = False
        db.session.commit()
        d = connecte.get("/admin/referentiels").get_json()
        assert d["success"] is True
        assert d["categories"] == [] and d["clubs"] == []

    def test_sans_session_c_est_refuse(self, client, app):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/referentiels").status_code == 401
