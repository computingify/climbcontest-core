"""Un seul formatage, et aucun doublon — spec 008, demande du 04/09.

« Débrouille-toi pour uniformiser le formatage, je ne veux pas de doublon. »

Un doublon naît toujours du même écart : deux écritures d'un même nom qui ne
tombent pas sur la même clé. Ce fichier vérifie les trois endroits où l'écart
pouvait naître — l'import du classeur, la saisie au guichet, le relevé
HelloAsso — et les deux gestes qui rattrapent ce qui est déjà là.
"""

import pytest

from climbcontest import comptes, formatage
from climbcontest.contest import (
    ErreurMetier, ajouter_participant, enregistrer_reussite, homonymes,
    participant_identique,
)
from climbcontest.extensions import db
from climbcontest.models import Participant, SOURCE_CLASSEUR
from climbcontest.sheets.importer import Rapport, importer_participants

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, jeu):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


class TestUneSeuleCle:
    """La clé d'identité vit dans `formatage.py`, et une seule existe."""

    @pytest.mark.parametrize("a,b", [
        (("DUPONT", "Jean-Luc"), ("dupont", "jean luc")),
        (("Brunel", "Léa"), ("BRUNEL", "lea")),
        (("  Martin  ", " Tom "), ("Martin", "Tom")),
        (("O'Connor", None), ("o connor", None)),
    ])
    def test_deux_ecritures_une_cle(self, a, b):
        assert formatage.identite(*a) == formatage.identite(*b)

    def test_le_rapprochement_helloasso_utilise_la_meme(self):
        """Deux clés qui vivraient dans deux modules finiraient par diverger,
        et le doublon reviendrait par la porte qu'on n'a pas refermée."""
        from climbcontest.helloasso import rapprochement
        assert rapprochement.cle is formatage.identite
        assert rapprochement.cle_club is formatage.identite_club

    def test_les_clubs_se_comparent_pareil(self):
        assert (formatage.identite_club("Roc N'Potes")
                == formatage.identite_club("ROC N POTES")
                == formatage.identite_club("roc n'potes"))


class TestLImportDuClasseurFormate:
    """Changement de doctrine du 04/09 : le classeur passe par le formatage."""

    def _lignes(self, *lignes):
        return list(lignes)

    def test_la_casse_du_classeur_est_uniformisee(self, app, competition):
        rapport = Rapport()
        importer_participants(competition, None, rapport, self._lignes(
            ["DUPONT LEA", "10", "DUPONT", "LEA", "ANNONAY ESCALADE", "u13f"]))
        p = Participant.query.one()
        assert p.nom == "Dupont" and p.prenom == "Lea"
        assert p.club == "Annonay Escalade"
        assert p.categorie == "U13 F"

    def test_les_sigles_deja_en_capitales_survivent(self, app, competition):
        rapport = Rapport()
        importer_participants(competition, None, rapport, self._lignes(
            ["Martin Tom", "11", "Martin", "Tom", "CAF Vivarais", "U15 H"]))
        assert Participant.query.one().club == "CAF Vivarais"

    def test_la_premiere_orthographe_fait_reference(self, app, competition):
        """La limite honnête de la règle, et ce qui la rachète.

        Sur une PREMIÈRE occurrence en minuscules, rien ne dit que « caf » est
        un sigle : « caf vivarais » devient « Caf Vivarais », et c'est tout ce
        qu'on peut faire. Ce qui compte n'est pas la casse choisie, c'est qu'il
        n'y en ait **qu'une** : une fois « CAF Vivarais » en base, toutes les
        écritures suivantes s'y rangent.
        """
        rapport = Rapport()
        importer_participants(competition, None, rapport, self._lignes(
            ["Martin Tom", "11", "Martin", "Tom", "CAF Vivarais", "U15 H"]))
        ajouter_participant("Autre", "Paul", club="caf vivarais", dossard=12)
        ajouter_participant("Encore", "Luc", club="CAF VIVARAIS", dossard=13)
        assert {p.club for p in Participant.query} == {"CAF Vivarais"}

    def test_le_classeur_et_le_guichet_donnent_le_meme_club(self, app, competition):
        """C'est exactement le doublon qu'on ferme : « ANNONAY ESCALADE »
        importé et « annonay escalade » tapé au guichet."""
        rapport = Rapport()
        importer_participants(competition, None, rapport, self._lignes(
            ["Dupont Lea", "10", "Dupont", "Lea", "ANNONAY ESCALADE", "U13 F"]))
        ajouter_participant("Martin", "Tom", club="annonay escalade",
                            categorie="U13 H", dossard=11)
        clubs = {p.club for p in Participant.query}
        assert clubs == {"Annonay Escalade"}


class TestLaGardeALAjout:
    def test_le_meme_nom_et_le_meme_club_est_refuse(self, app, competition):
        ajouter_participant("Brunel", "Lea", club="Annonay Escalade", dossard=1)
        with pytest.raises(ErreurMetier) as e:
            ajouter_participant("BRUNEL", "léa", club="ANNONAY ESCALADE", dossard=2)
        assert e.value.code == 409
        assert "deja inscrit" in e.value.message

    def test_deux_homonymes_de_clubs_differents_coexistent(self, app, competition):
        """Le risque R5 : deux « Martin Lea » existent vraiment, et les
        confondre en perdrait une."""
        ajouter_participant("Martin", "Lea", club="Les Lezards", dossard=1)
        ajouter_participant("Martin", "Lea", club="La Grimpe", dossard=2)
        assert Participant.query.count() == 2

    def test_le_club_absent_ne_conclut_pas(self, app, competition):
        """Deviner sur un champ vide ferait fusionner deux personnes."""
        ajouter_participant("Martin", "Lea", dossard=1)
        ajouter_participant("Martin", "Lea", dossard=2)
        assert Participant.query.count() == 2

    def test_le_forcage_passe_outre(self, app, competition):
        """Deux cousins homonymes au même club, ça se voit une fois."""
        ajouter_participant("Brunel", "Lea", club="Annonay Escalade", dossard=1)
        ajouter_participant("Brunel", "Lea", club="Annonay Escalade", dossard=2,
                            autoriser_homonyme=True)
        assert Participant.query.count() == 2

    def test_participant_identique(self, app, competition):
        p = ajouter_participant("Brunel", "Lea", club="Annonay Escalade", dossard=1)
        assert participant_identique(competition, "BRUNEL", "LEA",
                                     "annonay escalade").id == p.id
        assert participant_identique(competition, "Brunel", "Lea",
                                     "CAF Vivarais") is None

    def test_homonymes_ignore_le_club(self, app, competition):
        ajouter_participant("Martin", "Lea", club="Les Lezards", dossard=1)
        ajouter_participant("Martin", "Lea", club="La Grimpe", dossard=2)
        assert len(homonymes(competition, "MARTIN", "lea")) == 2


class TestLaRouteDAjout:
    def test_le_refus_porte_la_fiche_qui_ressemble(self, connecte, jeu):
        connecte.post("/admin/participants",
                      json={"nom": "Brunel", "prenom": "Lea",
                            "club": "Annonay Escalade"})
        r = connecte.post("/admin/participants",
                          json={"nom": "BRUNEL", "prenom": "léa",
                                "club": "annonay escalade"})
        assert r.status_code == 409
        assert r.get_json()["homonymes"][0]["nom"] == "Brunel Lea"

    def test_l_ajout_reussi_signale_quand_meme_les_homonymes(self, connecte, jeu):
        """Club différent : on crée, mais on le dit — c'est la « validation
        humaine » de la contrainte métier §3."""
        connecte.post("/admin/participants",
                      json={"nom": "Brunel", "prenom": "Lea", "club": "Un Club"})
        r = connecte.post("/admin/participants",
                          json={"nom": "Brunel", "prenom": "Lea",
                                "club": "Un Autre Club"})
        assert r.status_code == 201
        assert len(r.get_json()["homonymes"]) == 1

    def test_le_forcage_depuis_la_console(self, connecte, jeu):
        connecte.post("/admin/participants",
                      json={"nom": "Brunel", "prenom": "Lea", "club": "Un Club"})
        r = connecte.post("/admin/participants",
                          json={"nom": "Brunel", "prenom": "Lea",
                                "club": "Un Club", "autoriser_homonyme": True})
        assert r.status_code == 201


class TestLesDoublonsDejaLa:
    """Une base qui a vécu avant le 04/09 en porte peut-être."""

    def _deux_fiches(self, comp):
        a = Participant(competition_id=comp.id, nom="Brunel", prenom="Lea",
                        club="Annonay Escalade", categorie="U13 F", dossard=47,
                        annee_naissance=2015, source=SOURCE_CLASSEUR)
        b = Participant(competition_id=comp.id, nom="BRUNEL", prenom="LÉA",
                        club="annonay escalade", dossard=88)
        db.session.add_all([a, b])
        db.session.commit()
        return a, b

    def test_ils_se_voient(self, connecte, jeu):
        self._deux_fiches(jeu["competition"])
        d = connecte.get("/admin/doublons").get_json()
        assert len(d["doublons"]) == 1
        assert len(d["doublons"][0]["participants"]) == 2

    def test_deux_clubs_differents_ne_sont_pas_un_doublon(self, connecte, jeu):
        db.session.add_all([
            Participant(competition_id=jeu["competition"].id, nom="Martin",
                        prenom="Lea", club="Les Lezards", dossard=51),
            Participant(competition_id=jeu["competition"].id, nom="Martin",
                        prenom="Lea", club="La Grimpe", dossard=52)])
        db.session.commit()
        assert connecte.get("/admin/doublons").get_json()["doublons"] == []

    def test_sans_club_on_ne_conclut_pas(self, connecte, jeu):
        db.session.add_all([
            Participant(competition_id=jeu["competition"].id, nom="Seul",
                        prenom="Paul", dossard=61),
            Participant(competition_id=jeu["competition"].id, nom="Seul",
                        prenom="Paul", dossard=62)])
        db.session.commit()
        assert connecte.get("/admin/doublons").get_json()["doublons"] == []

    def test_la_fusion_garde_la_fiche_choisie(self, connecte, jeu):
        a, b = self._deux_fiches(jeu["competition"])
        r = connecte.post("/admin/doublons/fusionner",
                          json={"garder": a.id, "absorber": b.id})
        assert r.status_code == 200
        assert db.session.get(Participant, b.id) is None
        assert db.session.get(Participant, a.id).dossard == 47

    def test_la_fusion_deplace_les_reussites(self, connecte, jeu):
        a, b = self._deux_fiches(jeu["competition"])
        enregistrer_reussite(b, jeu["blocs"][0])
        db.session.commit()
        r = connecte.post("/admin/doublons/fusionner",
                          json={"garder": a.id, "absorber": b.id})
        assert r.get_json()["reussites_deplacees"] == 1
        assert len(db.session.get(Participant, a.id).reussites) == 1

    def test_une_reussite_deja_presente_ne_fait_pas_echouer(self, connecte, jeu):
        """La contrainte `uq_reussite` interdirait l'insertion. Perdre une
        réussite déjà présente chez l'autre ne perd rien."""
        a, b = self._deux_fiches(jeu["competition"])
        enregistrer_reussite(a, jeu["blocs"][0])
        enregistrer_reussite(b, jeu["blocs"][0])
        db.session.commit()
        r = connecte.post("/admin/doublons/fusionner",
                          json={"garder": a.id, "absorber": b.id})
        assert r.status_code == 200
        assert r.get_json()["reussites_en_double"] == 1
        assert len(db.session.get(Participant, a.id).reussites) == 1

    def test_la_fusion_complete_les_champs_vides(self, connecte, jeu):
        a, b = self._deux_fiches(jeu["competition"])
        a.annee_naissance = None
        db.session.commit()
        b.annee_naissance = 2015
        db.session.commit()
        connecte.post("/admin/doublons/fusionner",
                      json={"garder": a.id, "absorber": b.id})
        assert db.session.get(Participant, a.id).annee_naissance == 2015

    def test_fusionner_une_fiche_avec_elle_meme(self, connecte, jeu):
        a, _ = self._deux_fiches(jeu["competition"])
        r = connecte.post("/admin/doublons/fusionner",
                          json={"garder": a.id, "absorber": a.id})
        assert r.status_code == 400

    def test_participant_inconnu(self, connecte, jeu):
        r = connecte.post("/admin/doublons/fusionner",
                          json={"garder": 999998, "absorber": 999999})
        assert r.status_code == 404
