"""Le vocabulaire officiel, et ce qui s'y rattache — spec 045.

Trois choses se vérifient ici, et aucune ne demande de monter l'application :

1. **La liste est celle de la fédération.** Les dix alinéas du §5.4 sont écrits
   en toutes lettres dans le test : si quelqu'un ajoute « U23 » un jour, il
   devra le justifier en modifiant une citation.
2. **Ce qui arrive de travers se rattache.** C'est la demande d'Adrien du
   05/09 — « il manque un espace, une majuscule, il peut aussi manquer le U ».
3. **Ce qui est ambigu ne se rattache pas.** Un rattachement de trop range
   quelqu'un au hasard, et personne ne s'en aperçoit avant le podium.
"""

import pytest

from climbcontest import categories
from climbcontest.formatage import categorie, rattacher

#: Les alinéas a) à j) des Règles d'accès et de participation 2025-2026 (V3),
#: §5.4, recopiés. C'est la SOURCE du test, pas une redite du code.
REGLEMENT = [
    ("U9", "7 et 8 ans"),
    ("U11", "9 et 10 ans"),
    ("U13", "11 et 12 ans"),
    ("U15", "13 et 14 ans"),
    ("U17", "15 et 16 ans"),
    ("U19", "17 et 18 ans"),
    ("U21", "19 et 20 ans"),
    ("Senior", "21 a 39 ans"),
    ("Veteran 1", "40 a 49 ans"),
    ("Veteran 2", "50 ans et plus"),
]


class TestLaListe:
    def test_elle_suit_le_reglement_veterans_fusionnes(self):
        """Dix alinéas, neuf catégories : « les vétérans 1 et 2 concourent dans
        la même catégorie vétéran » (§5.4, même paragraphe)."""
        attendu = []
        for nom, _ in REGLEMENT:
            fusionne = "Veteran" if nom.startswith("Veteran") else nom
            if fusionne not in attendu:
                attendu.append(fusionne)
        assert list(categories.OFFICIELLES) == attendu
        assert len(categories.OFFICIELLES) == 9

    def test_dix_huit_libelles(self):
        assert len(categories.LISTE) == 18
        assert categories.LISTE[0] == "U9 F"
        assert categories.LISTE[-1] == "Veteran H"

    def test_les_genres_vont_par_paires(self):
        """Chaque catégorie porte ses deux genres, et dans le même ordre."""
        for nom in categories.OFFICIELLES:
            assert f"{nom} F" in categories.LISTE
            assert f"{nom} H" in categories.LISTE

    def test_tout_est_ascii(self):
        """La convention du dépôt : pas d'accent dans ce qui part en base et en
        JSON. « Sénior » s'écrit à l'écran, jamais ici."""
        "".join(categories.LISTE).encode("ascii")

    def test_la_regle_lit_les_nouvelles(self):
        assert categories.under("U9 F") == 9
        assert categories.under("U21 H") == 21
        # Pas de Under : le barème ne les attribuera jamais automatiquement.
        assert categories.under("Senior F") is None
        assert categories.under("Veteran H") is None

    def test_les_unders_officiels(self):
        assert categories.unders_de(categories.OFFICIELLES) == [
            9, 11, 13, 15, 17, 19, 21]


class TestCeQuiSeRattache:
    """La table de cas de la spec, §D3. Chaque ligne vient d'un vrai risque."""

    @pytest.mark.parametrize("brut", ["u13 f", "U13F", "u13f", "U13  F", "U13 f"])
    def test_la_casse_et_l_espace(self, brut):
        assert rattacher(brut) == "U13 F"

    @pytest.mark.parametrize("brut", ["13 F", "13f", "13-F", "13   f"])
    def test_le_u_manquant(self, brut):
        """« Il peut aussi arriver qu'il manque le U » — Adrien, 05/09."""
        assert rattacher(brut) == "U13 F"

    @pytest.mark.parametrize("brut", ["U 13 H", "U13-H", "U13/H", "U13.H", "U13_H"])
    def test_les_separateurs(self, brut):
        assert rattacher(brut) == "U13 H"

    @pytest.mark.parametrize("brut", ["U13 M", "u13m", "U13 masculin",
                                      "U13 garçon", "U13 GARCON", "U13 homme"])
    def test_le_m_de_production(self, brut):
        """Le défaut mesuré le 30/08 : 26 « U13 H » et un « U13 M »."""
        assert rattacher(brut) == "U13 H"

    @pytest.mark.parametrize("brut", ["U13 fille", "U13 féminin", "U13 Femme",
                                      "U13 girl", "U13 FILLES"])
    def test_les_ecritures_du_genre(self, brut):
        assert rattacher(brut) == "U13 F"

    @pytest.mark.parametrize("brut,attendu", [
        ("Homme U13", "U13 H"), ("F U13", "U13 F"), ("fille u13", "U13 F"),
    ])
    def test_l_ordre_inverse(self, brut, attendu):
        assert rattacher(brut) == attendu

    @pytest.mark.parametrize("brut,attendu", [
        ("sénior femme", "Senior F"), ("SENIORS F", "Senior F"),
        ("senior h", "Senior H"), ("Senior Homme", "Senior H"),
    ])
    def test_le_senior(self, brut, attendu):
        assert rattacher(brut) == attendu

    @pytest.mark.parametrize("brut,attendu", [
        ("Vétéran 1 H", "Veteran H"), ("veteran 2 h", "Veteran H"),
        ("V1 F", "Veteran F"), ("v2 f", "Veteran F"),
        ("veteran f", "Veteran F"), ("VETERANS H", "Veteran H"),
    ])
    def test_les_veterans_tombent_sur_la_meme(self, brut, attendu):
        """La fusion de D1, vue depuis l'entrée : « Vétéran 1 » et
        « Vétéran 2 » écrivent tous les deux « Veteran »."""
        assert rattacher(brut) == attendu

    @pytest.mark.parametrize("brut,attendu", [("U9 f", "U9 F"), ("u21 h", "U21 H")])
    def test_les_deux_bouts_de_la_liste(self, brut, attendu):
        assert rattacher(brut) == attendu

    def test_les_dix_huit_sont_des_points_fixes(self):
        """Ce qui est déjà officiel ressort identique. Sans ça, un aller-retour
        par la console changerait une valeur sans raison."""
        for libelle in categories.LISTE:
            assert rattacher(libelle) == libelle
            assert categorie(libelle) == libelle


class TestCeQuiNeSeRattachePas:
    """On rattache ou on laisse tel quel. **Jamais à moitié.**"""

    def test_sans_genre(self):
        """« U13 » à côté de « U13 F » couperait le classement en deux."""
        assert rattacher("U13") is None
        assert categorie("U13") == "U13"

    @pytest.mark.parametrize("brut", ["2016", "U2016 F", "2016 F", "1998 H"])
    def test_une_annee_n_est_pas_une_categorie(self, brut):
        """⚠️ Pas théorique : une colonne décalée d'une case dans le classeur
        présenterait une année là où on attend une catégorie. Sans la borne à
        deux chiffres, toute la liste partirait en « U2016 »."""
        assert rattacher(brut) is None

    @pytest.mark.parametrize("brut", ["U12 F", "U10 H", "U8 F", "U14 F", "U99 H"])
    def test_un_under_qui_n_existe_pas(self, brut):
        assert rattacher(brut) is None

    @pytest.mark.parametrize("brut", ["Poussin", "Minime F", "Benjamin H",
                                      "Cadet", "Adulte"])
    def test_l_ancienne_nomenclature(self, brut):
        """On ne devine pas à quoi « Minime » correspond aujourd'hui."""
        assert rattacher(brut) is None

    @pytest.mark.parametrize("brut", ["U13 F et U13 H", "U13 F / U13 H", "F H U13"])
    def test_deux_genres_c_est_ambigu(self, brut):
        """C'est une entête de tableau, pas une catégorie."""
        assert rattacher(brut) is None

    @pytest.mark.parametrize("brut", ["U13 U15 F", "U11 et U13 H"])
    def test_deux_ages_c_est_ambigu(self, brut):
        assert rattacher(brut) is None

    @pytest.mark.parametrize("brut", [None, "", "   ", "\t"])
    def test_le_vide_reste_le_vide(self, brut):
        assert rattacher(brut) is None
        assert categorie(brut) is None


class TestLeRepli:
    """Ce qui ne se rattache pas ressort par l'ANCIENNE règle, intacte."""

    @pytest.mark.parametrize("brut,attendu", [
        ("Poussin", "POUSSIN"), ("minime f", "MINIME F"), ("U13", "U13"),
        ("  espaces   multiples  ", "ESPACES MULTIPLES"),
    ])
    def test_majuscules_et_blancs_reduits(self, brut, attendu):
        assert categorie(brut) == attendu

    def test_le_genre_colle_reste_decolle(self):
        """La règle de la spec 013 survit pour ce qui sort de la liste."""
        assert categorie("U12F") == "U12 F"


class TestUneSeuleTableDeGenre:
    """`GENRES_CONNUS` a déménagé de `helloasso/correspondance` à `formatage`.

    Deux tables auraient dérivé — l'une gagnant une écriture que l'autre n'a
    pas — et le doublon serait revenu par la porte qu'on n'a pas refermée.
    """

    def test_correspondance_lit_la_meme(self):
        from climbcontest import formatage
        from climbcontest.helloasso import correspondance

        assert correspondance.GENRES_CONNUS is formatage.GENRES_CONNUS
        assert correspondance.genre_connu is formatage.genre_connu

    def test_le_rattachement_s_en_sert(self):
        """Ce que « Fille » veut dire pour HelloAsso vaut pour une catégorie."""
        from climbcontest import formatage

        for ecriture, attendu in formatage.GENRES_CONNUS.items():
            assert rattacher(f"U13 {ecriture}") == f"U13 {attendu}"
