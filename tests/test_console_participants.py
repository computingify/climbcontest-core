"""La liste des participants : édition en ligne, filtre, sources — spec 008.

Trois gestes nouveaux dans la console, et un seul écran :

- **le crayon** ouvre la ligne (`PATCH /admin/participants/<id>`) ;
- **le filtre catégorie** sert la sélection d'impression — filtrer, tout
  sélectionner, imprimer ;
- **les pastilles de source** disent d'où vient chaque participant.

Le test le plus important du fichier est
`test_le_dossard_qui_porte_des_reussites_refuse` : l'édition en ligne ne doit
pas rouvrir une règle que la spec 002 a fermée.
"""

import pytest

from climbcontest import comptes
from climbcontest.contest import enregistrer_reussite
from climbcontest.extensions import db
from climbcontest.models import (
    SOURCE_CLASSEUR, SOURCE_MANUEL, Participant,
)

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, jeu):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


def un_participant(comp, **champs):
    defauts = dict(nom="Brunel", prenom="Lea", club="Annonay Escalade",
                   categorie="U13 F", dossard=200, annee_naissance=2015)
    defauts.update(champs)
    p = Participant(competition_id=comp.id, **defauts)
    db.session.add(p)
    db.session.commit()
    return p


class TestLEditionEnLigne:
    def test_un_champ_seul_ne_touche_pas_les_autres(self, connecte, jeu):
        """PATCH, pas PUT : envoyer le club n'efface pas la catégorie."""
        p = un_participant(jeu["competition"])
        r = connecte.patch(f"/admin/participants/{p.id}", json={"club": "CAF Vivarais"})
        assert r.status_code == 200
        db.session.refresh(p)
        assert p.club == "CAF Vivarais"
        assert p.categorie == "U13 F" and p.nom == "Brunel"

    def test_le_formatage_s_applique(self, connecte, jeu):
        """« u13f » saisi à la main devient « U13 F ». Sans ça, « U13 M » et
        « U13 H » cohabiteraient — le défaut mesuré en production le 30/08."""
        p = un_participant(jeu["competition"])
        connecte.patch(f"/admin/participants/{p.id}",
                       json={"categorie": "u13h", "club": "roc n'potes"})
        db.session.refresh(p)
        assert p.categorie == "U13 H"
        assert p.club == "Roc N'Potes"

    def test_les_sigles_courts_restent_en_capitales(self, connecte, jeu):
        p = un_participant(jeu["competition"])
        connecte.patch(f"/admin/participants/{p.id}", json={"club": "CAF vivarais"})
        db.session.refresh(p)
        assert p.club == "CAF Vivarais"

    def test_changer_la_categorie_pose_la_trace_du_geste(self, connecte, jeu):
        """Décision D10 : « Appliquer à tous » ne défera pas ce choix."""
        p = un_participant(jeu["competition"])
        connecte.patch(f"/admin/participants/{p.id}", json={"categorie": "U15 F"})
        db.session.refresh(p)
        assert p.categorie_forcee is True

    def test_reecrire_la_meme_categorie_ne_pose_rien(self, connecte, jeu):
        p = un_participant(jeu["competition"])
        connecte.patch(f"/admin/participants/{p.id}", json={"categorie": "U13 F"})
        db.session.refresh(p)
        assert not p.categorie_forcee

    def test_l_annee_se_modifie(self, connecte, jeu):
        p = un_participant(jeu["competition"])
        connecte.patch(f"/admin/participants/{p.id}", json={"annee_naissance": "2016"})
        db.session.refresh(p)
        assert p.annee_naissance == 2016

    def test_une_annee_illisible_est_refusee(self, connecte, jeu):
        p = un_participant(jeu["competition"])
        r = connecte.patch(f"/admin/participants/{p.id}",
                           json={"annee_naissance": "20a5"})
        assert r.status_code == 400
        db.session.refresh(p)
        assert p.annee_naissance == 2015

    def test_un_nom_vide_est_refuse(self, connecte, jeu):
        p = un_participant(jeu["competition"])
        r = connecte.patch(f"/admin/participants/{p.id}", json={"nom": "   "})
        assert r.status_code == 400
        db.session.refresh(p)
        assert p.nom == "Brunel"

    def test_un_champ_inconnu_est_ignore(self, connecte, jeu):
        """Pas d'erreur 500 : la console peut envoyer un champ de trop."""
        p = un_participant(jeu["competition"])
        r = connecte.patch(f"/admin/participants/{p.id}",
                           json={"couleur_preferee": "bleu"})
        assert r.status_code == 200

    def test_participant_inconnu(self, connecte, jeu):
        assert connecte.patch("/admin/participants/999999", json={}).status_code == 404

    def test_le_catalogue_est_incremente(self, connecte, jeu):
        """Le juge voit le nom : le corriger doit atteindre les téléphones."""
        p = un_participant(jeu["competition"])
        avant = jeu["competition"].catalogue_version
        connecte.patch(f"/admin/participants/{p.id}", json={"nom": "Brunelle"})
        db.session.refresh(jeu["competition"])
        assert jeu["competition"].catalogue_version > avant


class TestLeDossardResteFerme:
    def test_le_dossard_se_change_quand_il_est_libre(self, connecte, jeu):
        p = un_participant(jeu["competition"])
        r = connecte.patch(f"/admin/participants/{p.id}", json={"dossard": 201})
        assert r.status_code == 200
        db.session.refresh(p)
        assert p.dossard == 201

    def test_le_dossard_qui_porte_des_reussites_refuse(self, connecte, jeu):
        """La règle de la spec 002 ne doit pas se contourner par un écran.

        Le dossard 1 du jeu de test porte une réussite : le reprendre pour
        quelqu'un d'autre mélangerait deux grimpeurs dans un classement.
        """
        occupant = Participant.query.filter_by(
            competition_id=jeu["competition"].id, dossard=1).one()
        enregistrer_reussite(occupant, jeu["blocs"][0])
        db.session.commit()

        p = un_participant(jeu["competition"])
        r = connecte.patch(f"/admin/participants/{p.id}", json={"dossard": 1})
        assert r.status_code == 409
        assert "reussites" in r.get_json()["message"]
        db.session.refresh(p)
        assert p.dossard == 200

    def test_le_meme_dossard_ne_declenche_rien(self, connecte, jeu):
        """Réenvoyer la valeur inchangée ne doit pas journaliser une
        réaffectation ni frôler la règle."""
        p = un_participant(jeu["competition"])
        assert connecte.patch(f"/admin/participants/{p.id}",
                              json={"dossard": 200}).status_code == 200


class TestLaListe:
    def test_le_filtre_par_categorie(self, connecte, jeu):
        """C'est lui qui remplace « une catégorie (vide = toutes) » de la tuile
        d'impression retirée."""
        un_participant(jeu["competition"], dossard=201, categorie="U13 F", nom="Une")
        un_participant(jeu["competition"], dossard=202, categorie="U15 H", nom="Deux")
        r = connecte.get("/admin/participants?categorie=U15 H")
        noms = [p["nom"] for p in r.get_json()["participants"]]
        assert noms == ["Deux Lea"]

    def test_la_liste_porte_l_annee_et_les_sources(self, connecte, jeu):
        un_participant(jeu["competition"], dossard=203, nom="Avecannee")
        ligne = [p for p in connecte.get("/admin/participants").get_json()["participants"]
                 if p["nom"].startswith("Avecannee")][0]
        assert ligne["annee_naissance"] == 2015
        assert ligne["sources"] == [SOURCE_CLASSEUR]

    def test_la_source_manuelle(self, connecte, jeu):
        connecte.post("/admin/participants",
                      json={"nom": "Guichet", "categorie": "U13 F"})
        ligne = [p for p in connecte.get("/admin/participants").get_json()["participants"]
                 if p["nom"] == "Guichet"][0]
        assert ligne["sources"] == [SOURCE_MANUEL]

    def test_l_annee_a_l_ajout(self, connecte, jeu):
        r = connecte.post("/admin/participants",
                          json={"nom": "Guichet", "annee_naissance": "2016"})
        assert r.get_json()["participant"]["annee_naissance"] == 2016


class TestLeCatalogueResteMaigre:
    def test_l_annee_de_naissance_ne_part_pas_sur_les_telephones(self, client, jeu):
        """L'année de naissance d'un mineur n'a aucune raison de voyager sur
        vingt-cinq téléphones que le club ne contrôle pas."""
        un_participant(jeu["competition"], dossard=204, nom="Mineur")
        catalogue = client.get("/api/v2/catalog").get_json()
        for p in catalogue["participants"]:
            assert "annee_naissance" not in p
            assert "sources" not in p


class TestLeBaremeParLaRoute:
    def test_il_se_lit(self, connecte, jeu):
        r = connecte.get("/admin/categories")
        corps = r.get_json()
        assert r.status_code == 200
        assert corps["reference"] == 2027
        assert corps["saison"] == "2026-2027"

    def test_l_apercu_n_ecrit_rien(self, connecte, jeu):
        p = un_participant(jeu["competition"], categorie="U15 F", annee_naissance=2015)
        un_participant(jeu["competition"], dossard=205, categorie="U13 F", nom="Autre")
        r = connecte.post("/admin/categories/appliquer", json={"apercu": True})
        assert r.get_json()["changements"][0]["apres"] == "U13 F"
        db.session.refresh(p)
        assert p.categorie == "U15 F"

    def test_appliquer_ecrit(self, connecte, jeu):
        p = un_participant(jeu["competition"], categorie="U15 F", annee_naissance=2015)
        un_participant(jeu["competition"], dossard=205, categorie="U13 F", nom="Autre")
        connecte.post("/admin/categories/appliquer", json={})
        db.session.refresh(p)
        assert p.categorie == "U13 F"

    def test_sans_session(self, client, app, jeu):
        app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
        assert client.get("/admin/categories").status_code == 401
        assert client.post("/admin/categories/appliquer", json={}).status_code == 401
