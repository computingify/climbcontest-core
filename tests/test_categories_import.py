"""Ce que le classeur écrit de travers entre droit — spec 045, D3 et D4.

⚠️ **C'est le test qui compte le plus de cette spec.** Le classeur Google est la
source qu'on ne contrôle pas : on n'écrit jamais dedans (règle 3 du
`CLAUDE.md`), il continuera donc de dire « U13 M » aussi longtemps qu'il
existera. Si le rattachement n'était pas dans la porte d'entrée, le rattrapage
de la console serait défait au premier import — le défaut fermé par la PR #125
pour le crayon, reposé ici par une autre porte.
"""

from climbcontest.extensions import db
from climbcontest.models import Participant
from climbcontest.sheets.importer import importer
from tests.test_import import ClasseurFictif


def ligne(nom, dossard, categorie):
    return [nom, str(dossard), nom.split()[0], nom.split()[-1],
            "Les Lezards", categorie]


class TestCeQuiSeRattacheALEntree:
    def test_le_m_du_classeur_devient_h(self, app, competition):
        """Le « U13 M » mesuré en production le 30/08, tel qu'il arriverait."""
        importer(competition, ClasseurFictif(
            listes=[ligne("Dupont Lea", 1, "u13m")]))
        assert Participant.query.filter_by(dossard=1).one().categorie == "U13 H"

    def test_le_u_manquant(self, app, competition):
        importer(competition, ClasseurFictif(
            listes=[ligne("Dupont Lea", 1, "13 F")]))
        assert Participant.query.filter_by(dossard=1).one().categorie == "U13 F"

    def test_rien_n_est_signale_quand_on_a_su_lire(self, app, competition):
        r = importer(competition, ClasseurFictif(
            listes=[ligne("Dupont Lea", 1, "u13 f")]))
        assert not [a for a in r.avertissements if "FFME" in a]

    def test_le_classeur_ne_defait_pas_le_rattrapage(self, app, competition):
        """⚠️ Le scénario complet, et la raison d'être de D3.

        On rattache en base, le classeur dit toujours « U13 M », et on
        réimporte. Sans le rattachement à l'entrée, le second import remettrait
        l'ancienne valeur — et le bouton de la console n'aurait servi à rien.
        """
        classeur = ClasseurFictif(listes=[ligne("Dupont Lea", 1, "U13 M")])
        importer(competition, classeur)
        p = Participant.query.filter_by(dossard=1).one()
        assert p.categorie == "U13 H"

        p.categorie = "U13 H"                      # ce que ferait le rattrapage
        db.session.commit()
        importer(competition, classeur)
        assert Participant.query.filter_by(dossard=1).one().categorie == "U13 H"


class TestCeQuOnGardeEtQuOnSignale:
    """D4 : ni ligne refusée, ni catégorie vidée."""

    def test_l_inconnue_est_importee_telle_quelle(self, app, competition):
        r = importer(competition, ClasseurFictif(
            listes=[ligne("Dupont Lea", 1, "Poussin")]))
        assert r.participants_crees == 1
        # La forme est nettoyée — l'ancienne règle — mais rien n'est deviné.
        assert Participant.query.filter_by(dossard=1).one().categorie == "POUSSIN"

    def test_et_elle_est_signalee(self, app, competition):
        r = importer(competition, ClasseurFictif(
            listes=[ligne("Dupont Lea", 1, "Poussin")]))
        alertes = [a for a in r.avertissements if "FFME" in a]
        assert len(alertes) == 1
        assert "POUSSIN" in alertes[0] and "L2" in alertes[0]

    def test_une_ligne_mauvaise_n_empeche_pas_les_autres(self, app, competition):
        """Un classeur mal rempli ne doit pas bloquer un import la veille."""
        r = importer(competition, ClasseurFictif(listes=[
            ligne("Dupont Lea", 1, "Poussin"),
            ligne("Martin Tom", 2, "u13 h"),
        ]))
        assert r.participants_crees == 2
        assert Participant.query.filter_by(dossard=2).one().categorie == "U13 H"

    def test_sans_categorie_le_message_ne_change_pas(self, app, competition):
        """Le vide et l'inconnu sont deux choses : deux messages distincts."""
        r = importer(competition, ClasseurFictif(
            listes=[["Sansclub Ana", "7", "Sansclub", "Ana"]]))
        assert any("sans categorie" in a for a in r.avertissements)
        assert not [a for a in r.avertissements if "FFME" in a]

    def test_deux_imports_ne_signalent_pas_deux_fois_la_meme_ligne(
            self, app, competition):
        """Le rapport porte sur CET import, pas sur l'historique."""
        classeur = ClasseurFictif(listes=[ligne("Dupont Lea", 1, "Poussin")])
        importer(competition, classeur)
        r = importer(competition, classeur)
        assert len([a for a in r.avertissements if "FFME" in a]) == 1
