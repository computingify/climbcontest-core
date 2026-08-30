"""L'import du classeur ne perd plus personne, et le dit quand il rejette.

Chaque test correspond à un cas réel du classeur d'Annonay, relevé dans
docs/technical/classeur-google.md.
"""

import pytest

from climbcontest.extensions import db
from climbcontest.models import Bloc, BlocCircuit, Circuit, Participant
from climbcontest.sheets.client import ErreurClasseur
from climbcontest.sheets.importer import importer


class ClasseurFictif:
    """Rejoue des lignes de classeur sans toucher au réseau."""

    def __init__(self, plan=None, listes=None):
        self.plan = plan if plan is not None else self.plan_type()
        self.listes = listes if listes is not None else self.listes_type()

    def lire(self, onglet, plage):
        return {"Plan": self.plan, "Listes": self.listes}[onglet]

    @staticmethod
    def _ligne_plan(zone, couleur, circuits, numero_zone, numero_import):
        """Construit une ligne D:Y (22 colonnes), comme le vrai classeur."""
        l = [""] * 22
        l[0], l[2] = zone, couleur
        for i, actif in zip((6, 8, 10), circuits):
            l[i] = "1" if actif else ""
        l[16], l[21] = numero_zone, str(numero_import)
        return l

    @classmethod
    def plan_type(cls):
        entete = [""] * 22
        entete[6], entete[8], entete[10] = "U11", "U13", "U15"
        return [
            entete,
            cls._ligne_plan("Z", "Jaune", (True, True, False), "J6", 1),
            cls._ligne_plan("Z", "Vert", (True, False, False), "J7", 2),
            cls._ligne_plan("D", "Bleu", (False, True, True), "V21", 3),
        ]

    @staticmethod
    def listes_type():
        return [
            ["Dupont Lea", "1", "Dupont", "Lea", "Les Lezards", "U11 F"],
            ["Martin Tom", "2", "Martin", "Tom", "La Grimpe", "U13 H"],
        ]


class TestImportNominal:
    def test_cree_blocs_circuits_participants(self, app, competition):
        r = importer(competition, ClasseurFictif())
        assert r.blocs_crees == 3
        assert r.circuits_crees == 3
        assert r.participants_crees == 2
        assert Bloc.query.count() == 3
        assert Circuit.query.count() == 3

    def test_le_tag_est_zone_plus_numero(self, app, competition):
        """Le QR code est la concaténation de la zone et du numéro dans la zone."""
        importer(competition, ClasseurFictif())
        assert {b.tag for b in Bloc.query.all()} == {"ZJ6", "ZJ7", "DV21"}

    def test_rattachement_aux_circuits(self, app, competition):
        importer(competition, ClasseurFictif())
        bloc = Bloc.query.filter_by(tag="ZJ6").one()
        noms = {bc.circuit.nom for bc in bloc.circuits}
        assert noms == {"U11", "U13"}

    def test_incremente_le_catalogue(self, app, competition):
        avant = competition.catalogue_version
        importer(competition, ClasseurFictif())
        assert competition.catalogue_version > avant


class TestIdempotence:
    def test_rejouer_ne_duplique_rien(self, app, competition):
        importer(competition, ClasseurFictif())
        r = importer(competition, ClasseurFictif())
        assert r.blocs_crees == 0
        assert r.participants_crees == 0
        assert Bloc.query.count() == 3
        assert Participant.query.count() == 2
        # ZJ6 → U11+U13, ZJ7 → U11, DV21 → U13+U15 = 5 liens
        assert BlocCircuit.query.count() == 5

    def test_reprend_une_correction_du_classeur(self, app, competition):
        """L'ancienne version n'ajoutait que les noms absents : une catégorie
        corrigée dans le classeur n'était jamais reprise."""
        importer(competition, ClasseurFictif())
        corrige = ClasseurFictif(listes=[
            ["Dupont Lea", "1", "Dupont", "Lea", "Les Lezards", "U13 F"],   # U11 F → U13 F
            ["Martin Tom", "2", "Martin", "Tom", "La Grimpe", "U13 H"],
        ])
        r = importer(competition, corrige)
        assert r.participants_mis_a_jour == 1
        assert Participant.query.filter_by(dossard=1).one().categorie == "U13 F"


class TestLigneIncomplete:
    """Risque R5 : le grimpeur qui disparaissait sans un mot."""

    def test_participant_sans_club_ni_categorie_est_importe(self, app, competition):
        """Google Sheets tronque les cellules vides de fin : la ligne fait 4
        colonnes au lieu de 6. L'ancienne version l'ignorait en silence."""
        cl = ClasseurFictif(listes=[["Sansclub Ana", "7", "Sansclub", "Ana"]])
        r = importer(competition, cl)
        assert r.participants_crees == 1
        p = Participant.query.filter_by(dossard=7).one()
        assert p.club is None and p.categorie is None
        # Importé, mais SIGNALÉ — c'est ce qui manquait.
        assert any("categorie" in a for a in r.avertissements)

    def test_participant_sans_dossard_est_signale(self, app, competition):
        cl = ClasseurFictif(listes=[["Sans Dossard", ""]])
        r = importer(competition, cl)
        assert r.participants_crees == 0
        assert any("sans dossard" in i.lower() for i in r.ignores)

    def test_dossard_illisible(self, app, competition):
        cl = ClasseurFictif(listes=[["Bizarre", "abc", "Bizarre", "X"]])
        r = importer(competition, cl)
        assert r.participants_crees == 0
        assert any("illisible" in i for i in r.ignores)


class TestBlocLigneCourte:
    """Risque R6 : le numéro de bloc deviné, donc faux."""

    def test_ligne_tronquee_rejetee_et_signalee(self, app, competition):
        """Sur une ligne à 17 colonnes, l'ancienne version prenait `line[-1]`,
        c'est-à-dire la colonne T — le numéro de ZONE, pas celui de l'onglet
        Import. Les réussites atterrissaient sur la mauvaise ligne."""
        entete = [""] * 22
        entete[6], entete[8], entete[10] = "U11", "U13", "U15"
        courte = [""] * 17
        courte[0], courte[16] = "Z", "J9"          # s'arrête à la colonne T
        r = importer(competition, ClasseurFictif(plan=[entete, courte]))
        assert r.blocs_crees == 0
        assert any("colonnes" in i for i in r.ignores)
        assert Bloc.query.count() == 0

    def test_numero_lu_a_la_bonne_position(self, app, competition):
        """Le numéro vient de la colonne Y (index 21), pas de la dernière
        colonne remplie."""
        importer(competition, ClasseurFictif())
        assert Bloc.query.filter_by(tag="ZJ6").one().numero == 1
        assert Bloc.query.filter_by(tag="DV21").one().numero == 3


class TestStructureChangee:
    def test_echec_explicite_si_les_circuits_disparaissent(self, app, competition):
        """Si le classeur change de structure, on s'arrête franchement plutôt
        que d'importer n'importe quoi."""
        entete = [""] * 22                          # aucun nom de circuit
        with pytest.raises(ErreurClasseur) as e:
            importer(competition, ClasseurFictif(plan=[entete]))
        assert "structure" in str(e.value).lower()
        assert Bloc.query.count() == 0


class TestParticipantManuelProtege:
    """Spec 013 : l'import n'ecrase jamais un participant ajoute a la main.

    Le scenario : quelqu'un s'inscrit sur place et recoit le dossard 3. Plus
    tard, un import du classeur apporte un dossard 3 -- une AUTRE personne.
    Sans cette protection, la fiche est remplacee en silence, et les reussites
    deja enregistrees sur le dossard 3 se retrouvent au nom du nouveau venu.
    """

    def test_le_classeur_n_ecrase_pas_une_inscription_manuelle(self, app, competition):
        from climbcontest.contest import ajouter_participant_numerote
        from climbcontest.sheets.importer import Rapport, importer_participants

        sur_place = ajouter_participant_numerote("Surplace", club="La Grimpe")
        assert sur_place.dossard == 1

        class ClasseurFactice:
            def lire(self, onglet, plage):
                # colonnes F..K : nom complet, dossard, nom, prenom, club, categorie
                return [["Autre Personne", "1", "Autre", "Personne", "CAF", "U13 H"]]

        rapport = Rapport()
        importer_participants(competition, ClasseurFactice(), rapport)
        db.session.refresh(sur_place)

        assert sur_place.nom == "Surplace", "la fiche manuelle a ete ecrasee"
        assert rapport.participants_mis_a_jour == 0
        assert any("ajoute a la main" in i for i in rapport.ignores), rapport.ignores

    def test_une_ligne_du_classeur_reste_modifiable(self, app, competition):
        """La protection ne vise QUE le manuel : l'import normal fonctionne."""
        from climbcontest.models import SOURCE_CLASSEUR
        from climbcontest.sheets.importer import Rapport, importer_participants

        db.session.add(Participant(competition_id=competition.id, nom="Ancien",
                                   dossard=5, source=SOURCE_CLASSEUR))
        db.session.commit()

        class ClasseurFactice:
            def lire(self, onglet, plage):
                return [["Nouveau Nom", "5", "Nouveau", "Nom", "La Grimpe", "U13 H"]]

        rapport = Rapport()
        importer_participants(competition, ClasseurFactice(), rapport)
        assert rapport.participants_mis_a_jour == 1
        assert Participant.query.filter_by(dossard=5).first().nom == "Nouveau"
