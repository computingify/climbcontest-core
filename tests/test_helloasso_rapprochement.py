"""Le rapprochement — spec 008, lot 5.

Aucune base, aucun réseau : une fonction pure et une table de cas. C'est la
seule façon d'éprouver une règle de rapprochement, parce que ce qui compte est
la frontière entre « je fusionne tout seul » et « je demande ».
"""

import pytest

from climbcontest.helloasso import rapprochement as r


def quelqu_un(identifiant=1, nom="Brunel", prenom="Lea",
              club="Annonay Escalade", categorie="U13 F"):
    return r.Personne(identifiant, nom, prenom, club, categorie)


class TestLaCle:
    @pytest.mark.parametrize("a,b", [
        (("Dupont", "Jean-Luc"), ("DUPONT", "jean luc")),
        (("Brunel", "Léa"), ("brunel", "Lea")),
        (("O'Connor", None), ("o connor", None)),
        (("  Martin  ", " Tom "), ("Martin", "Tom")),
        (("Écrivain", "Éva"), ("ecrivain", "eva")),
    ])
    def test_deux_ecritures_donnent_la_meme_cle(self, a, b):
        assert r.cle(*a) == r.cle(*b)

    def test_deux_personnes_differentes_ne_se_confondent_pas(self):
        assert r.cle("Brunel", "Lea") != r.cle("Brunel", "Leo")

    def test_un_club_se_normalise_pareil(self):
        assert r.cle_club("Roc N'Potes") == r.cle_club("roc n'potes")

    def test_une_cle_vide(self):
        assert r.cle(None, None) == ""


class TestLeVerdict:
    def test_aucun_homonyme(self):
        v = r.confronter(quelqu_un(), [])
        assert v.quoi == r.NOUVEAU

    def test_nom_prenom_club_identiques(self):
        v = r.confronter(quelqu_un(identifiant=None), [quelqu_un(identifiant=7)])
        assert v.quoi == r.MEME_PERSONNE and v.identifiant == 7

    def test_le_meme_nom_ecrit_autrement(self):
        v = r.confronter(
            quelqu_un(identifiant=None, nom="BRUNEL", prenom="léa",
                      club="roc n'potes"),
            [quelqu_un(identifiant=7, nom="Brunel", prenom="Lea",
                       club="Roc N'Potes")])
        assert v.quoi == r.MEME_PERSONNE

    def test_club_different(self):
        v = r.confronter(quelqu_un(identifiant=None, club="CAF Vivarais"),
                         [quelqu_un(identifiant=7, club="Annonay Escalade")])
        assert v.quoi == r.A_TRANCHER
        assert v.motif == r.MOTIF_CLUB_DIFFERENT

    def test_club_absent_du_cote_de_l_inscription(self):
        v = r.confronter(quelqu_un(identifiant=None, club=None),
                         [quelqu_un(identifiant=7)])
        assert v.quoi == r.A_TRANCHER

    def test_club_absent_du_cote_de_la_liste(self):
        """Le cas du guichet : on a saisi un nom, pas de club."""
        v = r.confronter(quelqu_un(identifiant=None),
                         [quelqu_un(identifiant=7, club=None)])
        assert v.quoi == r.A_TRANCHER

    def test_trois_homonymes_un_seul_du_bon_club(self):
        v = r.confronter(
            quelqu_un(identifiant=None, club="CAF Vivarais"),
            [quelqu_un(identifiant=1, club="Annonay Escalade"),
             quelqu_un(identifiant=2, club="CAF Vivarais"),
             quelqu_un(identifiant=3, club="Roc N'Potes")])
        assert v.quoi == r.MEME_PERSONNE and v.identifiant == 2

    def test_deux_homonymes_du_meme_club_demandent_un_humain(self):
        """Ça ne devrait pas exister. Le silence serait pire."""
        v = r.confronter(
            quelqu_un(identifiant=None),
            [quelqu_un(identifiant=1), quelqu_un(identifiant=2)])
        assert v.quoi == r.A_TRANCHER

    def test_sans_nom(self):
        v = r.confronter(quelqu_un(identifiant=None, nom=None, prenom=None), [])
        assert v.quoi == r.A_TRANCHER and v.motif == "sans_nom"


class TestLaCategorieControleSansBloquer:
    def test_une_categorie_differente_rattache_quand_meme(self):
        """Le cas banal : un classeur importé avant l'application du barème."""
        v = r.confronter(quelqu_un(identifiant=None, categorie="U13 F"),
                         [quelqu_un(identifiant=7, categorie="U15 F")])
        assert v.quoi == r.MEME_PERSONNE
        assert v.categorie_differente is True

    def test_la_meme_categorie_ne_signale_rien(self):
        v = r.confronter(quelqu_un(identifiant=None),
                         [quelqu_un(identifiant=7)])
        assert v.categorie_differente is False

    def test_une_categorie_manquante_ne_signale_rien(self):
        v = r.confronter(quelqu_un(identifiant=None, categorie=None),
                         [quelqu_un(identifiant=7)])
        assert v.categorie_differente is False
