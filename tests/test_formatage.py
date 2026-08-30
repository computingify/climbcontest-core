"""Le formatage de ce qui est saisi a la main (spec 013, IT1).

Des fonctions pures, donc une table de cas : c'est la forme qui rend une regle
de casse verifiable. Chaque ligne porte le cas reel qui l'a fait ecrire.
"""
import pytest

from climbcontest import formatage


class TestNom:
    """Nom et prenom : casse STRICTE, aucune exception (decision D1)."""

    @pytest.mark.parametrize("saisi, attendu", [
        ("dupont", "Dupont"),
        ("DUPONT", "Dupont"),                 # le reflexe des capitales sur un formulaire
        ("dUpOnT", "Dupont"),
        ("jean-luc", "Jean-Luc"),             # le trait d'union est un separateur
        ("marie-claire dubois", "Marie-Claire Dubois"),
        ("roc n'potes", "Roc N'Potes"),       # apostrophe droite
        ("roc n’potes", "Roc N’Potes"),       # apostrophe typographique
        ("élise", "Élise"),                   # les accents ne cassent pas la casse
        ("  jean   dupont  ", "Jean Dupont"), # bords coupes, espaces reduits
    ])
    def test_casse(self, saisi, attendu):
        assert formatage.nom(saisi) == attendu

    def test_un_nom_en_capitales_n_est_pas_un_sigle(self):
        """La difference avec le club, et la raison d'avoir deux fonctions.

        « MARTIN » tape en capitales est un nom, pas un sigle : il doit revenir
        a une casse normale. C'est la decision D1 du 30/08.
        """
        assert formatage.nom("MARTIN") == "Martin"
        assert formatage.nom("DUPUY") == "Dupuy"      # 5 lettres : un sigle le serait


class TestClub:
    """Club : meme regle, mais un sigle deja en capitales survit."""

    @pytest.mark.parametrize("saisi, attendu", [
        ("annonay escalade", "Annonay Escalade"),
        ("la grimpe", "La Grimpe"),
        ("les lezards vagabonds", "Les Lezards Vagabonds"),
        ("roc n'potes", "Roc N'Potes"),
        ("vertic'ardeche", "Vertic'Ardeche"),
    ])
    def test_les_clubs_reels(self, saisi, attendu):
        """Les cinq clubs presents en production le 30/08."""
        assert formatage.club(saisi) == attendu

    @pytest.mark.parametrize("saisi, attendu", [
        ("CAF annonay", "CAF Annonay"),       # 3 lettres
        ("MJC", "MJC"),
        ("ASPTT lyon", "ASPTT Lyon"),         # 5 lettres : la limite, incluse
        ("US annonay", "US Annonay"),         # 2 lettres : la limite basse
    ])
    def test_les_sigles_survivent(self, saisi, attendu):
        assert formatage.club(saisi) == attendu

    def test_un_mot_trop_long_n_est_plus_un_sigle(self):
        """Six caracteres : on ne peut plus le distinguer d'un mot crie."""
        assert formatage.club("ESCALADE") == "Escalade"

    def test_un_sigle_tape_en_minuscules_n_est_pas_devine(self):
        """Limite assumee : rien ne distingue « mjc » de « mjc » le mot.

        On ne devine pas -- l'organisateur a la liste deroulante pour choisir
        la forme deja enregistree.
        """
        assert formatage.club("mjc") == "Mjc"


class TestCategorie:
    """Tout en majuscules, et l'espace avant le genre garanti (decision D4)."""

    @pytest.mark.parametrize("saisi, attendu", [
        ("u13 f", "U13 F"),
        ("U13 f", "U13 F"),
        ("u13  h", "U13 H"),
        ("  u11 f  ", "U11 F"),
    ])
    def test_majuscules_et_espaces(self, saisi, attendu):
        assert formatage.categorie(saisi) == attendu

    @pytest.mark.parametrize("saisi", ["U13F", "u13f", "U13f", "u13F"])
    def test_l_espace_avant_le_genre_est_retabli(self, saisi):
        """Sans cette regle, « U13F » et « U13 F » seraient DEUX categories,
        donc deux classements -- le defaut du « U13 M », sous une autre forme."""
        assert formatage.categorie(saisi) == "U13 F"

    def test_une_categorie_qui_finit_par_f_sans_etre_un_genre(self):
        """L'insertion est ancree sur un CHIFFRE : un mot n'est jamais coupe."""
        assert formatage.categorie("perf") == "PERF"
        assert formatage.categorie("mixte") == "MIXTE"

    @pytest.mark.parametrize("existante", [
        "U11 F", "U11 H", "U13 F", "U13 H", "U15 F", "U15 H", "U17 H",
    ])
    def test_idempotent_sur_l_existant(self, existante):
        """**Le test le plus important du module.**

        Ces sept valeurs sont celles de la production le 30/08. Si le formatage
        en modifiait une seule, des participants changeraient de categorie --
        donc de classement. Il ne doit rien toucher.
        """
        assert formatage.categorie(existante) == existante


class TestVide:
    """Un champ facultatif non renseigne doit etre NULL, pas une chaine vide."""

    @pytest.mark.parametrize("fonction", [formatage.nom, formatage.club,
                                          formatage.categorie])
    @pytest.mark.parametrize("rien", [None, "", "   ", "\t\n"])
    def test_rien_donne_none(self, fonction, rien):
        assert fonction(rien) is None
