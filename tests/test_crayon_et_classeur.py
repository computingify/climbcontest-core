"""Une correction faite au crayon survit au prochain import — spec 008.

Le doublon que ce fichier interdit a été **reproduit avant d'être corrigé**, le
05/09, sur la branche `feat/008-helloasso-import` :

    LEAS : [(1, 30, 'Les Lezards'), (3, 1, 'Les Lezards')]
    AssertionError: 2 fiches pour la meme personne

L'import rapprochait une ligne du classeur par son **seul dossard**. Il suffisait
qu'un numéro ait changé de main pour que la fiche soit recréée — et, dans le pire
cas, pour que le nom du nouveau porteur soit écrasé alors que ses réussites y
étaient déjà attachées.

Quatre promesses, un test chacune :

1. le classeur ne défait pas une correction de la console ;
2. il ne recrée pas quelqu'un dont le dossard a bougé ;
3. il n'écrit jamais sur le porteur actuel d'un numéro ;
4. il continue de corriger ses propres lignes.
"""

import pytest

from climbcontest import comptes
from climbcontest.contest import ajouter_participant_numerote, enregistrer_reussite
from climbcontest.extensions import db
from climbcontest.models import (
    SOURCE_CLASSEUR, SOURCE_HELLOASSO, Participant,
)
from climbcontest.sheets.importer import Rapport, importer_participants

MDP = "un-mot-de-passe-assez-long"


@pytest.fixture()
def connecte(client, app, competition):
    app.config["SECRET_KEY"] = "une-vraie-cle-de-test-suffisamment-longue"
    comptes.creer("orga", MDP, [comptes.ORGANISATEUR])
    client.post("/admin/connexion", json={"identifiant": "orga", "mot_de_passe": MDP})
    return client


class Classeur:
    """Un classeur figé : les mêmes deux lignes, import après import."""

    LIGNES = [
        ["Dupont Lea", "1", "Dupont", "Lea", "Les Lezards", "U11 F"],
        ["Martin Tom", "2", "Martin", "Tom", "La Grimpe", "U13 H"],
    ]

    def __init__(self, lignes=None):
        self.lignes = self.LIGNES if lignes is None else lignes

    def lire(self, onglet, plage):
        return self.lignes


def importe(comp, classeur=None) -> Rapport:
    rapport = Rapport()
    importer_participants(comp, classeur or Classeur(), rapport)
    return rapport


def lea(comp) -> Participant:
    return Participant.query.filter_by(competition_id=comp.id, nom="Dupont").one()


class TestLaConsoleGagne:
    """« La console gagne, définitivement » — décision du 05/09."""

    def test_le_club_corrige_survit(self, connecte, competition):
        importe(competition)
        p = lea(competition)
        connecte.patch(f"/admin/participants/{p.id}", json={"club": "CAF Vivarais"})

        rapport = importe(competition)

        db.session.refresh(p)
        assert p.club == "CAF Vivarais"
        assert rapport.corrections_conservees == 1
        assert any("corrige(s) dans la console" in a
                   for a in rapport.avertissements), rapport.avertissements

    def test_la_categorie_corrigee_survit(self, connecte, competition):
        """`categorie_forcee` existait déjà pour le barème : la même trace sert
        ici, plutôt qu'une seconde qui finirait par la contredire."""
        importe(competition)
        p = lea(competition)
        connecte.patch(f"/admin/participants/{p.id}", json={"categorie": "U13 F"})

        importe(competition)

        db.session.refresh(p)
        assert p.categorie == "U13 F"

    def test_ce_qui_n_a_pas_ete_corrige_se_met_a_jour(self, connecte, competition):
        """La protection est par CHAMP. Corriger le club ne fige pas la
        catégorie : le classeur reste une source, il cesse d'être un rouleau
        compresseur."""
        importe(competition)
        p = lea(competition)
        connecte.patch(f"/admin/participants/{p.id}", json={"club": "CAF Vivarais"})

        importe(competition, Classeur([
            ["Dupont Lea", "1", "Dupont", "Lea", "Les Lezards", "U13 F"],
        ]))

        db.session.refresh(p)
        assert (p.club, p.categorie) == ("CAF Vivarais", "U13 F")

    def test_l_ecran_dit_ce_qui_est_protege(self, connecte, competition):
        """Une règle qu'on ne peut pas vérifier depuis l'écran où elle
        s'applique n'est pas une règle, c'est une croyance."""
        importe(competition)
        p = lea(competition)
        connecte.patch(f"/admin/participants/{p.id}", json={"club": "CAF Vivarais"})

        liste = connecte.get("/admin/participants").get_json()["participants"]
        fiche = next(x for x in liste if x["id"] == p.id)
        assert fiche["champs_forces"] == ["club"]

    def test_sans_correction_rien_n_est_protege(self, connecte, competition):
        importe(competition)
        liste = connecte.get("/admin/participants").get_json()["participants"]
        assert all(x["champs_forces"] == [] for x in liste)


class TestAucunDoublon:
    """Le défaut reproduit le 05/09, dans ses trois formes."""

    def test_un_dossard_libere_ne_recree_personne(self, app, competition):
        """Léa n'a plus de dossard — une fusion de doublons, par exemple.

        L'ancienne version ne la retrouvait plus et fabriquait une deuxième
        fiche à son nom.
        """
        importe(competition)
        p = lea(competition)
        p.dossard = None
        db.session.commit()

        importe(competition)

        assert Participant.query.filter_by(nom="Dupont").count() == 1

    def test_le_dossard_libre_lui_est_rendu(self, app, competition):
        """Et tant qu'à la retrouver, autant lui rendre son numéro : le
        classeur le dit, personne ne le porte."""
        importe(competition)
        p = lea(competition)
        p.dossard = None
        db.session.commit()

        rapport = importe(competition)

        db.session.refresh(p)
        assert p.dossard == 1
        assert any("rendu a" in a for a in rapport.avertissements), rapport.avertissements

    def test_le_numero_pris_par_un_autre_ne_recree_personne(self, app, competition):
        """Le cas le plus dangereux : le dossard 1 est passé à quelqu'un d'autre.

        L'ancienne version écrivait « Dupont Lea » SUR ce quelqu'un d'autre.
        """
        importe(competition)
        p = lea(competition)
        p.dossard = None
        db.session.commit()
        autre = ajouter_participant_numerote("Neuve", prenom="Zoe",
                                             club="Annonay Escalade")
        autre.dossard = 1
        db.session.commit()

        rapport = importe(competition)

        db.session.refresh(autre)
        assert autre.nom == "Neuve", "le porteur du dossard 1 a ete ecrase"
        assert Participant.query.filter_by(nom="Dupont").count() == 1
        assert any("porte par" in a for a in rapport.avertissements + rapport.ignores)

    def test_les_reussites_du_porteur_ne_changent_pas_de_main(self, app, competition):
        """La conséquence concrète du cas précédent, mesurée là où elle fait
        mal : au classement."""
        importe(competition)
        p, tom = lea(competition), Participant.query.filter_by(nom="Martin").one()
        p.dossard, tom.dossard = None, None
        db.session.commit()
        tom.dossard = 1
        db.session.commit()
        from climbcontest.models import Bloc
        bloc = Bloc(competition_id=competition.id, tag="ZJ6", numero=1, zone="Z")
        db.session.add(bloc)
        db.session.commit()
        enregistrer_reussite(tom, bloc)

        importe(competition)

        db.session.refresh(tom)
        assert tom.nom == "Martin"
        assert len(tom.reussites) == 1

    def test_une_inscription_helloasso_n_est_pas_ecrasee(self, app, competition):
        """Le classeur ne réécrit que les fiches QU'IL possède."""
        importe(competition)
        p = lea(competition)
        p.dossard = None
        db.session.commit()
        enligne = ajouter_participant_numerote("Enligne", prenom="Sam",
                                               club="La Grimpe",
                                               source=SOURCE_HELLOASSO)
        enligne.dossard = 1
        db.session.commit()

        importe(competition)

        db.session.refresh(enligne)
        assert (enligne.nom, enligne.source) == ("Enligne", SOURCE_HELLOASSO)

    def test_deux_lignes_jumelles_ne_font_pas_deux_fiches(self, app, competition):
        """Deux lignes du MÊME import pour la même personne, sous deux dossards.

        Le rapprochement lit la liste une fois : sans les fiches créées par les
        lignes précédentes, la deuxième ligne repartirait de zéro.
        """
        importe(competition, Classeur([
            ["Dupont Lea", "1", "Dupont", "Lea", "Les Lezards", "U11 F"],
            ["Dupont Lea", "7", "DUPONT", "LEA", "les lezards", "U11 F"],
        ]))

        assert Participant.query.filter_by(nom="Dupont").count() == 1


class TestLeClasseurResteUneSource:
    """Bouclé trop serré, le rapprochement empêcherait le travail normal."""

    def test_il_corrige_la_coquille_de_ses_propres_lignes(self, app, competition):
        """« Dupond » corrigé en « Dupont » dans le classeur, même dossard.

        L'identité ne reconnaît évidemment plus personne : c'est le dossard qui
        tranche, parce que la fiche appartient au classeur et ne porte rien.
        """
        importe(competition, Classeur([
            ["Dupond Lea", "1", "Dupond", "Lea", "Les Lezards", "U11 F"],
        ]))
        rapport = importe(competition)

        assert Participant.query.filter_by(dossard=1).one().nom == "Dupont"
        assert Participant.query.count() == 2
        assert rapport.participants_mis_a_jour == 1

    def test_il_refuse_de_renommer_une_fiche_qui_a_grimpe(self, app, competition):
        """La même coquille, mais la personne a déjà des réussites.

        Là, « corriger un nom » deviendrait « donner ses réussites à quelqu'un
        d'autre ». On refuse, et on le dit.
        """
        importe(competition, Classeur([
            ["Dupond Lea", "1", "Dupond", "Lea", "Les Lezards", "U11 F"],
        ]))
        from climbcontest.models import Bloc
        bloc = Bloc(competition_id=competition.id, tag="ZJ6", numero=1, zone="Z")
        db.session.add(bloc)
        db.session.commit()
        p = Participant.query.filter_by(dossard=1).one()
        enregistrer_reussite(p, bloc)

        rapport = importe(competition, Classeur([
            ["Dupont Lea", "1", "Dupont", "Lea", "Les Lezards", "U11 F"],
        ]))

        db.session.refresh(p)
        assert p.nom == "Dupond", "la fiche a ete renommee malgre sa reussite"
        assert rapport.ignores, "le refus doit se voir dans le rapport"

    def test_rejouer_ne_duplique_toujours_rien(self, app, competition):
        importe(competition)
        rapport = importe(competition)
        assert rapport.participants_crees == 0
        assert Participant.query.count() == 2

    def test_une_vraie_nouvelle_ligne_cree_bien_quelqu_un(self, app, competition):
        importe(competition)
        rapport = importe(competition, Classeur(Classeur.LIGNES + [
            ["Roche Ines", "3", "Roche", "Ines", "Annonay Escalade", "U15 F"],
        ]))
        assert rapport.participants_crees == 1
        assert Participant.query.count() == 3

    def test_la_source_reste_le_classeur(self, app, competition):
        importe(competition)
        assert lea(competition).source == SOURCE_CLASSEUR
